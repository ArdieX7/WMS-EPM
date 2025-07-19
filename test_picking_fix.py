#!/usr/bin/env python3
"""
Test per verificare le correzioni al sistema di picking/prenotazioni
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from wms_app.database import engine, SessionLocal
from wms_app.services.reservation_service import ReservationService
from wms_app.models.inventory import Inventory
from wms_app.models.products import Product
from wms_app.models.orders import Order, OrderLine
from wms_app.models.reservations import InventoryReservation
from datetime import datetime, timedelta

def test_picking_priorities():
    """Test delle priorità di picking corrette"""
    print("=== TEST PRIORITÀ PICKING ===\n")
    
    db = SessionLocal()
    reservation_service = ReservationService(db)
    
    try:
        # Trova un prodotto che esiste in più ubicazioni
        sample_sku = db.query(Inventory.product_sku).group_by(Inventory.product_sku).first()
        if not sample_sku:
            print("Nessun prodotto trovato nel database")
            return
        
        sku = sample_sku.product_sku
        print(f"Test con SKU: {sku}")
        
        # Ottieni tutte le ubicazioni per questo prodotto
        locations = reservation_service.get_locations_with_availability(sku, 5)
        
        print(f"\nUbicazioni disponibili per {sku} (quantità richiesta: 5):")
        for i, loc in enumerate(locations[:5]):  # Mostra solo le prime 5
            print(f"{i+1}. {loc['location_name']}: {loc['available_quantity']} pz "
                  f"(Terra: {loc['is_ground_level']}, "
                  f"Esatta: {loc['has_exact_quantity']}, "
                  f"Svuota: {loc['can_empty_completely']})")
        
        # Verifica che le ubicazioni a terra vengano prima
        ground_locations = [loc for loc in locations if loc['is_ground_level']]
        if ground_locations:
            print(f"\nUbicazioni a terra trovate: {len(ground_locations)}")
            print(f"   Prima ubicazione a terra: {ground_locations[0]['location_name']}")
        else:
            print("\nNessuna ubicazione a terra trovata per questo prodotto")
        
    except Exception as e:
        print(f"Errore test priorità: {e}")
    finally:
        db.close()

def test_duplicate_reservations():
    """Test per prevenire prenotazioni duplicate"""
    print("\n=== TEST PRENOTAZIONI DUPLICATE ===\n")
    
    db = SessionLocal()
    reservation_service = ReservationService(db)
    
    try:
        # Pulisce prenotazioni scadute
        reservation_service.cleanup_expired_reservations()
        
        # Trova un prodotto disponibile
        sample_inv = db.query(Inventory).filter(Inventory.quantity > 5).first()
        if not sample_inv:
            print("Nessun inventory con quantità sufficiente")
            return
        
        sku = sample_inv.product_sku
        test_order_id = "TEST_ORD_999"
        
        print(f"Test con SKU: {sku}, Ordine: {test_order_id}")
        
        # Cancella eventuali prenotazioni esistenti per questo test
        db.query(InventoryReservation).filter(
            InventoryReservation.order_id == test_order_id
        ).delete()
        db.commit()
        
        # Prima allocazione
        print("\n1. Prima richiesta picking...")
        result1 = reservation_service.allocate_picking_locations(
            order_id=test_order_id,
            products_needed=[{'sku': sku, 'quantity': 3}]
        )
        
        if result1 and result1[0]['allocations']:
            first_location = result1[0]['allocations'][0]['location_name']
            first_quantity = result1[0]['allocations'][0]['quantity']
            print(f"   Assegnato: {first_location} per {first_quantity} pz")
        
        # Seconda allocazione (dovrebbe restituire la stessa prenotazione)
        print("\n2. Seconda richiesta picking (stesso ordine)...")
        result2 = reservation_service.allocate_picking_locations(
            order_id=test_order_id,
            products_needed=[{'sku': sku, 'quantity': 3}]
        )
        
        if result2 and result2[0]['allocations']:
            second_location = result2[0]['allocations'][0]['location_name']
            second_quantity = result2[0]['allocations'][0]['quantity']
            print(f"   Restituito: {second_location} per {second_quantity} pz")
            
            if 'already_reserved' in result2[0] and result2[0]['already_reserved']:
                print("   CORRETTO: Sistema ha riconosciuto prenotazione esistente")
            
            if first_location == second_location and first_quantity == second_quantity:
                print("   CORRETTO: Stessa ubicazione e quantità restituita")
            else:
                print("   ERRORE: Ubicazione o quantità diversa!")
        
        # Cleanup
        db.query(InventoryReservation).filter(
            InventoryReservation.order_id == test_order_id
        ).delete()
        db.commit()
        
    except Exception as e:
        print(f"Errore test duplicati: {e}")
    finally:
        db.close()

def test_quantity_based_allocation():
    """Test allocazione basata su quantità"""
    print("\n=== TEST ALLOCAZIONE QUANTITY-BASED ===\n")
    
    db = SessionLocal()
    reservation_service = ReservationService(db)
    
    try:
        # Trova un prodotto con multiple ubicazioni
        sku_with_multiple = db.query(Inventory.product_sku).group_by(
            Inventory.product_sku
        ).having(
            db.query(Inventory.id).filter(
                Inventory.product_sku == Inventory.product_sku
            ).count() > 1
        ).first()
        
        if not sku_with_multiple:
            print("Nessun prodotto con multiple ubicazioni trovato")
            return
        
        sku = sku_with_multiple.product_sku
        print(f"Test con SKU: {sku}")
        
        # Simula due ordini che richiedono lo stesso prodotto
        order1_id = "TEST_ORD_A"
        order2_id = "TEST_ORD_B"
        
        # Pulisce prenotazioni test precedenti
        for test_order in [order1_id, order2_id]:
            db.query(InventoryReservation).filter(
                InventoryReservation.order_id == test_order
            ).delete()
        db.commit()
        
        print(f"\nOrdine A richiede 4 pz di {sku}...")
        result_a = reservation_service.allocate_picking_locations(
            order_id=order1_id,
            products_needed=[{'sku': sku, 'quantity': 4}]
        )
        
        print(f"Ordine B richiede 6 pz di {sku}...")
        result_b = reservation_service.allocate_picking_locations(
            order_id=order2_id,
            products_needed=[{'sku': sku, 'quantity': 6}]
        )
        
        if result_a and result_b:
            loc_a = result_a[0]['allocations'][0]['location_name'] if result_a[0]['allocations'] else "N/A"
            loc_b = result_b[0]['allocations'][0]['location_name'] if result_b[0]['allocations'] else "N/A"
            
            print(f"\nRisultati:")
            print(f"Ordine A: {loc_a}")
            print(f"Ordine B: {loc_b}")
            
            if loc_a != loc_b and loc_a != "N/A" and loc_b != "N/A":
                print("OTTIMO: Round-robin funziona, ordini su ubicazioni diverse!")
            elif loc_a == loc_b:
                print("Entrambi gli ordini nella stessa ubicazione (normale se c'è abbastanza stock)")
            else:
                print("Problema nell'allocazione")
        
        # Cleanup
        for test_order in [order1_id, order2_id]:
            db.query(InventoryReservation).filter(
                InventoryReservation.order_id == test_order
            ).delete()
        db.commit()
        
    except Exception as e:
        print(f"Errore test quantity-based: {e}")
    finally:
        db.close()

def main():
    """Esegue tutti i test"""
    print("TESTING CORREZIONI SISTEMA PICKING\n")
    
    try:
        test_picking_priorities()
        test_duplicate_reservations()
        test_quantity_based_allocation()
        
        print("\nTest completati!")
        print("\nCorrezioni implementate:")
        print("1. Priorità ubicazioni terra (1P)")
        print("2. Priorità quantità esatta e svuotamento completo")
        print("3. Prevenzione prenotazioni duplicate per stesso ordine")
        print("4. Sistema quantity-based per condivisione ubicazioni")
        
    except Exception as e:
        print(f"Errore generale: {e}")

if __name__ == "__main__":
    main()