from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
import re
import math

from wms_app.models.inventory import Inventory
from wms_app.models.reservations import InventoryReservation
from wms_app.models.products import Product

class ReservationService:
    """
    Servizio per la gestione delle prenotazioni di inventario con logica Round-Robin
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.reservation_timeout_hours = 4  # 4 ore come richiesto
    
    def parse_location(self, location_name: str) -> Dict:
        """
        Parser per ubicazioni formato: [FILA][CAMPATA][PIANO]P[POSIZIONE]
        Es: 1A1P1 = Fila 1, Campata A, Piano 1, Posizione 1
        """
        # Pattern: numeri + lettera + numeri + P + numeri
        pattern = r'^(\d+)([A-Z]+)(\d+)P(\d+)$'
        match = re.match(pattern, location_name.upper())
        
        if match:
            fila = int(match.group(1))
            campata = match.group(2)
            piano = int(match.group(3))
            posizione = int(match.group(4))
            
            return {
                'fila': fila,
                'campata': campata,
                'piano': piano,
                'posizione': posizione,
                'is_ground_level': piano == 1,
                'location_name': location_name
            }
        else:
            # Fallback per ubicazioni speciali (es: TERRA)
            return {
                'fila': 0,
                'campata': 'SPECIAL',
                'piano': 1,
                'posizione': 1,
                'is_ground_level': True,
                'location_name': location_name
            }
    
    def calculate_location_priority(self, location: Dict, reference_location: Optional[Dict] = None) -> Tuple:
        """
        Calcola priorità ubicazione per ottimizzazione percorso picking
        
        Priorità corrette:
        1. Piano basso (1 = terra)
        2. Campata (per raggruppare ubicazioni nella stessa scaffalatura)
        3. Posizione (più bassa nella stessa campata)
        4. Distanza da ubicazione di riferimento (per multi-SKU)
        """
        fila = location['fila']
        campata_ord = ord(location['campata'][0]) if location['campata'] != 'SPECIAL' else 0
        piano = location['piano']
        posizione = location['posizione']
        
        # Priorità 1: Piano (terra = 1 ha priorità massima)
        piano_priority = piano
        
        # Priorità 2: Campata (per completare una scaffalatura prima di spostarsi)
        campata_priority = campata_ord
        
        # Priorità 3: Posizione (più bassa = migliore nella stessa campata)
        posizione_priority = posizione
        
        # Priorità 4: Distanza da riferimento (per multi-SKU)
        distance_penalty = 0
        if reference_location:
            # Distanza Manhattan tra ubicazioni
            fila_diff = abs(fila - reference_location['fila'])
            campata_diff = abs(campata_ord - ord(reference_location['campata'][0])) if reference_location['campata'] != 'SPECIAL' else 0
            distance_penalty = fila_diff + campata_diff
        
        # Tuple per sorting: valori più bassi = priorità maggiore
        return (piano_priority, campata_priority, posizione_priority, distance_penalty)
    
    def sort_locations_by_picking_efficiency(self, locations: List[Dict], reference_location: Optional[Dict] = None) -> List[Dict]:
        """
        Ordina le ubicazioni per efficienza picking ottimizzata
        """
        # Aggiungi informazioni strutturali a ogni ubicazione
        enhanced_locations = []
        for loc in locations:
            parsed = self.parse_location(loc['location_name'])
            enhanced_loc = {**loc, **parsed}
            enhanced_locations.append(enhanced_loc)
        
        # Ordina per priorità picking
        enhanced_locations.sort(key=lambda x: self.calculate_location_priority(x, reference_location))
        
        return enhanced_locations
    
    def get_available_quantity(self, location_name: str, product_sku: str) -> int:
        """
        Calcola la quantità disponibile in una ubicazione considerando le prenotazioni attive
        """
        # Quantità fisica in magazzino
        inventory = self.db.query(Inventory).filter(
            Inventory.location_name == location_name,
            Inventory.product_sku == product_sku
        ).first()
        
        physical_quantity = inventory.quantity if inventory else 0
        
        # Quantità prenotata (solo prenotazioni attive e non scadute)
        reserved_quantity = self.db.query(func.sum(InventoryReservation.reserved_quantity)).filter(
            and_(
                InventoryReservation.location_name == location_name,
                InventoryReservation.product_sku == product_sku,
                InventoryReservation.status == 'active',
                InventoryReservation.expires_at > datetime.utcnow()
            )
        ).scalar() or 0
        
        return max(0, physical_quantity - reserved_quantity)
    
    def get_locations_with_availability(self, product_sku: str, required_quantity: int = 1, reference_location: Optional[Dict] = None) -> List[Dict]:
        """
        Ottiene tutte le ubicazioni con disponibilità per un prodotto, ordinate per efficienza picking
        Priorità: 1) Prenotazioni attive, 2) Efficienza percorso (piano basso, vicinanza, ecc.)
        """
        # Trova tutte le ubicazioni con il prodotto
        locations_query = self.db.query(
            Inventory.location_name,
            Inventory.quantity.label('physical_quantity')
        ).filter(
            Inventory.product_sku == product_sku,
            Inventory.quantity > 0
        ).all()
        
        # Trova ubicazioni con prenotazioni attive per questo prodotto
        locations_with_active_reservations = self.db.query(InventoryReservation.location_name).filter(
            and_(
                InventoryReservation.product_sku == product_sku,
                InventoryReservation.status == 'active',
                InventoryReservation.expires_at > datetime.utcnow()
            )
        ).distinct().all()
        
        locations_being_used = {r.location_name for r in locations_with_active_reservations}
        
        locations_with_availability = []
        
        for location in locations_query:
            available_qty = self.get_available_quantity(location.location_name, product_sku)
            if available_qty > 0:
                # Parse della struttura ubicazione
                parsed_location = self.parse_location(location.location_name)
                
                # Verifica se ha la quantità esatta richiesta
                has_exact_quantity = available_qty == required_quantity
                
                # Verifica se può essere svuotata completamente (fisica = disponibile)
                can_empty_completely = location.physical_quantity == available_qty
                
                # Verifica se ha prenotazioni attive (quantity-based priority)
                has_active_reservations = location.location_name in locations_being_used
                
                locations_with_availability.append({
                    'location_name': location.location_name,
                    'physical_quantity': location.physical_quantity,
                    'available_quantity': available_qty,
                    'can_fulfill': available_qty >= required_quantity,
                    'has_exact_quantity': has_exact_quantity,
                    'can_empty_completely': can_empty_completely,
                    'has_active_reservations': has_active_reservations,
                    # Aggiungi info strutturali
                    **parsed_location
                })
        
        # Separazione tra ubicazioni con e senza prenotazioni attive
        locations_with_reservations = [loc for loc in locations_with_availability if loc['has_active_reservations']]
        locations_without_reservations = [loc for loc in locations_with_availability if not loc['has_active_reservations']]
        
        # Ordina separatamente con algoritmo di efficienza picking
        sorted_with_reservations = self.sort_locations_by_picking_efficiency(locations_with_reservations, reference_location)
        sorted_without_reservations = self.sort_locations_by_picking_efficiency(locations_without_reservations, reference_location)
        
        # QUANTITY-BASED: Prenotazioni attive sempre prima
        final_sorted = sorted_with_reservations + sorted_without_reservations
        
        return final_sorted
    
    def get_round_robin_location(self, product_sku: str, order_id: str, required_quantity: int) -> Optional[str]:
        """
        Metodo legacy - usa get_round_robin_location_optimized per nuove implementazioni
        """
        return self.get_round_robin_location_optimized(product_sku, order_id, required_quantity, None)
    
    def get_round_robin_location_optimized(self, product_sku: str, order_id: str, required_quantity: int, reference_location: Optional[Dict] = None) -> Optional[str]:
        """
        Algoritmo Round-Robin ottimizzato con percorso picking efficiente
        
        Priorità:
        1. Prenotazioni attive (quantity-based)
        2. Piano basso > posizione adiacente > campata vicina > piano alto
        3. Distanza minima da ubicazione precedente (multi-SKU)
        """
        available_locations = self.get_locations_with_availability(product_sku, required_quantity, reference_location)
        
        if not available_locations:
            return None
        
        # L'ordinamento è già ottimizzato per efficienza picking
        return available_locations[0]['location_name']
    
    def create_reservation(self, order_id: str, product_sku: str, location_name: str, quantity: int) -> InventoryReservation:
        """
        Crea una nuova prenotazione
        """
        # Verifica disponibilità
        available = self.get_available_quantity(location_name, product_sku)
        if available < quantity:
            raise ValueError(f"Quantità insufficiente. Disponibile: {available}, richiesto: {quantity}")
        
        # Calcola scadenza (4 ore da ora)
        expires_at = datetime.utcnow() + timedelta(hours=self.reservation_timeout_hours)
        
        reservation = InventoryReservation(
            order_id=order_id,
            product_sku=product_sku,
            location_name=location_name,
            reserved_quantity=quantity,
            expires_at=expires_at,
            status='active'
        )
        
        self.db.add(reservation)
        self.db.commit()
        self.db.refresh(reservation)
        
        return reservation
    
    def allocate_picking_locations(self, order_id: str, products_needed: List[Dict]) -> List[Dict]:
        """
        Alloca ubicazioni per una lista di prodotti usando Round-Robin + Quantity-Based + Ottimizzazione percorso
        
        Args:
            order_id: ID dell'ordine
            products_needed: [{'sku': 'ABC', 'quantity': 5}, ...]
            
        Returns:
            [{'sku': 'ABC', 'allocations': [{'location': 'X', 'quantity': 3}, {'location': 'Y', 'quantity': 2}]}]
        """
        allocation_results = []
        last_location = None  # Per ottimizzazione percorso multi-SKU
        
        for i, product in enumerate(products_needed):
            sku = product['sku']
            needed_qty = product['quantity']
            
            # CORREZIONE BUG: Verifica se esistono già prenotazioni per questo ordine+prodotto
            existing_reservations = self.db.query(InventoryReservation).filter(
                and_(
                    InventoryReservation.order_id == order_id,
                    InventoryReservation.product_sku == sku,
                    InventoryReservation.status == 'active',
                    InventoryReservation.expires_at > datetime.utcnow()
                )
            ).all()
            
            if existing_reservations:
                # Restituisce le prenotazioni esistenti invece di crearne di nuove
                allocations = []
                total_reserved = 0
                
                for reservation in existing_reservations:
                    allocations.append({
                        'location_name': reservation.location_name,
                        'quantity': reservation.reserved_quantity,
                        'reservation_id': reservation.id
                    })
                    total_reserved += reservation.reserved_quantity
                
                allocation_results.append({
                    'sku': sku,
                    'requested_quantity': needed_qty,
                    'allocated_quantity': total_reserved,
                    'remaining_quantity': max(0, needed_qty - total_reserved),
                    'allocations': allocations,
                    'fully_allocated': total_reserved >= needed_qty,
                    'already_reserved': True
                })
                continue
            
            # Se non ci sono prenotazioni esistenti, procedi con l'allocazione normale
            allocations = []
            remaining_qty = needed_qty
            
            while remaining_qty > 0:
                # Trova prossima ubicazione con ottimizzazione percorso
                location = self.get_round_robin_location_optimized(sku, order_id, remaining_qty, last_location)
                
                if not location:
                    # Nessuna ubicazione disponibile per il prodotto
                    break
                
                # Calcola quanto possiamo prendere da questa ubicazione
                available = self.get_available_quantity(location, sku)
                to_take = min(remaining_qty, available)
                
                if to_take > 0:
                    # Crea prenotazione
                    reservation = self.create_reservation(order_id, sku, location, to_take)
                    
                    allocations.append({
                        'location_name': location,
                        'quantity': to_take,
                        'reservation_id': reservation.id
                    })
                    
                    remaining_qty -= to_take
                    
                    # Aggiorna last_location per ottimizzazione percorso successivo
                    last_location = self.parse_location(location)
                else:
                    # Nessuna quantità disponibile, esci dal loop
                    break
            
            allocation_results.append({
                'sku': sku,
                'requested_quantity': needed_qty,
                'allocated_quantity': needed_qty - remaining_qty,
                'remaining_quantity': remaining_qty,
                'allocations': allocations,
                'fully_allocated': remaining_qty == 0,
                'already_reserved': False
            })
        
        return allocation_results
    
    def complete_reservation(self, reservation_id: int, actually_picked: int) -> bool:
        """
        Completa una prenotazione dopo il picking reale
        """
        reservation = self.db.query(InventoryReservation).filter(
            InventoryReservation.id == reservation_id
        ).first()
        
        if not reservation:
            return False
        
        reservation.status = 'completed'
        
        # Se ha prelevato meno del prenotato, libera la differenza
        if actually_picked < reservation.reserved_quantity:
            difference = reservation.reserved_quantity - actually_picked
            # La differenza viene automaticamente liberata marcando come completed
        
        self.db.commit()
        return True
    
    def cleanup_expired_reservations(self) -> int:
        """
        Pulisce le prenotazioni scadute automaticamente
        """
        expired_count = self.db.query(InventoryReservation).filter(
            and_(
                InventoryReservation.status == 'active',
                InventoryReservation.expires_at <= datetime.utcnow()
            )
        ).update({'status': 'expired'})
        
        self.db.commit()
        return expired_count
    
    def manual_cleanup_all_reservations(self) -> int:
        """
        Cleanup manuale di TUTTE le prenotazioni (per reset emergenze)
        """
        count = self.db.query(InventoryReservation).filter(
            InventoryReservation.status == 'active'
        ).update({'status': 'cancelled'})
        
        self.db.commit()
        return count
    
    def get_reservation_status(self, order_id: str) -> List[Dict]:
        """
        Ottiene lo stato delle prenotazioni per un ordine
        """
        reservations = self.db.query(InventoryReservation).filter(
            InventoryReservation.order_id == order_id
        ).all()
        
        return [{
            'id': r.id,
            'product_sku': r.product_sku,
            'location_name': r.location_name,
            'reserved_quantity': r.reserved_quantity,
            'status': r.status,
            'expires_at': r.expires_at,
            'reserved_at': r.reserved_at
        } for r in reservations]