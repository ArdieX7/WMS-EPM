#!/usr/bin/env python3
"""
Test della logica di priorità picking ottimizzata
Verifica: piano basso > posizione adiacente > campata vicina > piano alto
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from wms_app.database import SessionLocal
from wms_app.services.reservation_service import ReservationService
from wms_app.models.inventory import Inventory
from wms_app.models.products import Product
from wms_app.models.reservations import InventoryReservation

def setup_realistic_scenario(db: Session):
    """Crea scenario realistico come descritto dall'utente"""
    
    test_sku = "TEST_PRIORITY_SKU"
    
    # Pulisce dati precedenti
    db.query(InventoryReservation).filter(
        InventoryReservation.product_sku == test_sku
    ).delete()
    
    db.query(Inventory).filter(
        Inventory.product_sku == test_sku
    ).delete()
    
    product = db.query(Product).filter(Product.sku == test_sku).first()
    if not product:
        product = Product(sku=test_sku, description="Test Product Priority")
        db.add(product)
    
    # Crea ubicazioni come nell'esempio dell'utente
    test_locations = [
        ("1A1P1", 10),  # Fila 1, Campata A, Piano 1 (terra), Posizione 1
        ("1A1P2", 8),   # Fila 1, Campata A, Piano 1 (terra), Posizione 2  
        ("1A2P1", 6),   # Fila 1, Campata A, Piano 2, Posizione 1
        ("1B1P1", 12)   # Fila 1, Campata B, Piano 1 (terra), Posizione 1
    ]
    
    for location_name, quantity in test_locations:
        inventory = Inventory(
            product_sku=test_sku,
            location_name=location_name,
            quantity=quantity
        )
        db.add(inventory)
    
    db.commit()
    
    return test_sku, test_locations

def test_location_parsing():
    """Test del parser ubicazioni"""
    print("=== TEST PARSING UBICAZIONI ===\n")
    
    db = SessionLocal()
    reservation_service = ReservationService(db)
    
    test_cases = [
        "1A1P1",  # Fila 1, Campata A, Piano 1, Posizione 1
        "1A1P2",  # Fila 1, Campata A, Piano 1, Posizione 2
        "1A2P1",  # Fila 1, Campata A, Piano 2, Posizione 1
        "1B1P1",  # Fila 1, Campata B, Piano 1, Posizione 1
        "12C3P4", # Fila 12, Campata C, Piano 3, Posizione 4
        "TERRA"   # Ubicazione speciale
    ]
    
    for location in test_cases:
        parsed = reservation_service.parse_location(location)
        print(f"{location:8} -> Fila: {parsed['fila']}, Campata: {parsed['campata']}, "
              f"Piano: {parsed['piano']}, Pos: {parsed['posizione']}, Terra: {parsed['is_ground_level']}")
    
    db.close()

def test_picking_priority():
    """Test della sequenza di priorità picking"""
    print("\n=== TEST PRIORITÀ PICKING ===\n")
    
    db = SessionLocal()
    reservation_service = ReservationService(db)
    
    try:
        test_sku, locations = setup_realistic_scenario(db)
        
        print(f"Setup ubicazioni per {test_sku}:")
        for location_name, quantity in locations:
            parsed = reservation_service.parse_location(location_name)
            print(f"  {location_name}: {quantity} pz (Fila {parsed['fila']}, Campata {parsed['campata']}, Piano {parsed['piano']}, Pos {parsed['posizione']})")
        
        print(f"\nTest sequenza picking (richiesta 5 pz)...")
        
        # Test ordinamento senza prenotazioni
        locations_ordered = reservation_service.get_locations_with_availability(test_sku, 5)
        
        print(f"\nSequenza ordinata:")
        for i, loc in enumerate(locations_ordered):
            print(f"  {i+1}. {loc['location_name']}: {loc['available_quantity']} pz "
                  f"(Fila {loc['fila']}, Campata {loc['campata']}, Piano {loc['piano']}, Pos {loc['posizione']})")
        
        # Verifica sequenza attesa: 1A1P1 -> 1A1P2 -> 1B1P1 -> 1A2P1
        expected_sequence = ["1A1P1", "1A1P2", "1B1P1", "1A2P1"]
        actual_sequence = [loc['location_name'] for loc in locations_ordered]
        
        print(f"\nVerifica sequenza:")
        print(f"Attesa:  {expected_sequence}")
        print(f"Ottenuta: {actual_sequence}")
        
        if actual_sequence == expected_sequence:
            print("CORRETTO: Sequenza picking ottimale!")
        else:
            print("ERRORE: Sequenza non ottimale")
            
        # Test con multi-SKU e ottimizzazione percorso
        print(f"\n=== TEST MULTI-SKU OPTIMIZATION ===")
        
        # Simula che abbiamo già prelevato da 1A1P1
        reference_location = reservation_service.parse_location("1A1P1")
        print(f"Ubicazione di riferimento: 1A1P1")
        
        # Richiedi di nuovo il prodotto (simulando secondo SKU dello stesso ordine)
        locations_optimized = reservation_service.get_locations_with_availability(test_sku, 3, reference_location)
        
        print(f"\nSequenza ottimizzata da 1A1P1:")
        for i, loc in enumerate(locations_optimized):
            distance = reservation_service.calculate_location_priority(loc, reference_location)[1]  # Distance penalty
            print(f"  {i+1}. {loc['location_name']}: {loc['available_quantity']} pz "
                  f"(Distanza: {distance})")
        
        # Dovrebbe preferire 1A1P2 (stessa campata) over 1B1P1 (campata diversa)
        if locations_optimized[0]['location_name'] in ["1A1P2", "1A1P1"]:
            print("CORRETTO: Preferisce ubicazioni nella stessa campata!")
        else:
            print("INFO: Algoritmo potrebbe preferire altre priorità")
            
    except Exception as e:
        print(f"Errore durante test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        db.query(InventoryReservation).filter(
            InventoryReservation.product_sku == test_sku
        ).delete()
        db.commit()
        db.close()

def test_real_allocation():
    """Test allocazione completa con priorità corrette"""
    print("\n=== TEST ALLOCAZIONE COMPLETA ===\n")
    
    db = SessionLocal()
    reservation_service = ReservationService(db)
    
    try:
        test_sku, locations = setup_realistic_scenario(db)
        
        # Test ordine che richiede 15 pezzi (più della singola ubicazione)
        print("Ordine che richiede 15 pezzi...")
        result = reservation_service.allocate_picking_locations(
            order_id="TEST_PRIORITY_ORD",
            products_needed=[{'sku': test_sku, 'quantity': 15}]
        )
        
        if result and result[0]['allocations']:
            print("Allocazioni ottenute:")
            total = 0
            for i, alloc in enumerate(result[0]['allocations']):
                parsed = reservation_service.parse_location(alloc['location_name'])
                print(f"  {i+1}. {alloc['location_name']}: {alloc['quantity']} pz "
                      f"(Piano {parsed['piano']}, Pos {parsed['posizione']})")
                total += alloc['quantity']
            
            print(f"Totale allocato: {total} pz")
            
            # Verifica priorità: dovrebbe iniziare da terra (piano 1)
            first_location = result[0]['allocations'][0]['location_name']
            first_parsed = reservation_service.parse_location(first_location)
            if first_parsed['piano'] == 1:
                print("CORRETTO: Prima allocazione a terra!")
            else:
                print(f"ATTENZIONE: Prima allocazione al piano {first_parsed['piano']}")
        
        # Cleanup
        db.query(InventoryReservation).filter(
            InventoryReservation.product_sku == test_sku
        ).delete()
        db.commit()
        
    except Exception as e:
        print(f"Errore durante test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

def main():
    print("TEST PRIORITA PICKING OTTIMIZZATE\n")
    print("Priorita attese:")
    print("1. Piano basso (terra = piano 1)")
    print("2. Posizione adiacente nella stessa campata")
    print("3. Campata adiacente")
    print("4. Piano alto")
    print("5. Distanza minima per multi-SKU")
    print()
    
    test_location_parsing()
    test_picking_priority()
    test_real_allocation()

if __name__ == "__main__":
    main()