#!/usr/bin/env python3
"""
Test specifico per il comportamento quantity-based del sistema di prenotazioni
Scenario: 14pz in 1A1P1 -> Ordine A (10pz) -> Ordine B (10pz) dovrebbe prendere 4pz da 1A1P1
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
from datetime import datetime

def setup_test_scenario(db: Session):
    """Prepara scenario di test con dati controllati"""
    
    # Trova o crea un prodotto di test
    test_sku = "TEST_QTY_SKU"
    test_location_1 = "1A1P1"
    test_location_2 = "1A1P2"
    
    # Pulisce dati precedenti
    db.query(InventoryReservation).filter(
        InventoryReservation.product_sku == test_sku
    ).delete()
    
    db.query(Inventory).filter(
        Inventory.product_sku == test_sku
    ).delete()
    
    product = db.query(Product).filter(Product.sku == test_sku).first()
    if not product:
        product = Product(sku=test_sku, description="Test Product Quantity")
        db.add(product)
    
    # Crea inventario controllato - 1A1P1 deve essere prioritario (terra)
    inv1 = Inventory(
        product_sku=test_sku,
        location_name=test_location_1,  # 1A1P1 - posizione a terra
        quantity=14  # 14 pezzi in 1A1P1
    )
    
    inv2 = Inventory(
        product_sku=test_sku,
        location_name=test_location_2,  # 1A1P2 - posizione sopra
        quantity=20  # 20 pezzi in 1A1P2
    )
    
    db.add(inv1)
    db.add(inv2)
    db.commit()
    
    return test_sku, test_location_1, test_location_2

def test_quantity_based_logic():
    """Test del comportamento quantity-based"""
    print("=== TEST QUANTITY-BASED COMPORTAMENTO ===\n")
    
    db = SessionLocal()
    reservation_service = ReservationService(db)
    
    try:
        # Setup scenario
        test_sku, loc1, loc2 = setup_test_scenario(db)
        print(f"Setup completato:")
        print(f"- {loc1}: 14 pezzi di {test_sku}")
        print(f"- {loc2}: 20 pezzi di {test_sku}")
        
        # DEBUG: Verifica ordinamento ubicazioni
        print(f"\nDEBUG: Ordinamento ubicazioni per {test_sku} (richiesta 10 pz):")
        locations_debug = reservation_service.get_locations_with_availability(test_sku, 10)
        for i, loc in enumerate(locations_debug):
            print(f"  {i+1}. {loc['location_name']}: {loc['available_quantity']} pz "
                  f"(Terra: {loc['is_ground_level']}, Prenotazioni: {loc['has_active_reservations']})")
        
        # STEP 1: Ordine A richiede 10 pezzi
        print(f"\n1. Ordine A richiede 10 pezzi di {test_sku}...")
        result_a = reservation_service.allocate_picking_locations(
            order_id="ORD_A_QTY",
            products_needed=[{'sku': test_sku, 'quantity': 10}]
        )
        
        if result_a and result_a[0]['allocations']:
            alloc_a = result_a[0]['allocations'][0]
            print(f"   Assegnato: {alloc_a['location_name']} per {alloc_a['quantity']} pz")
            
            # Verifica disponibilità residua in loc1
            available_loc1 = reservation_service.get_available_quantity(loc1, test_sku)
            available_loc2 = reservation_service.get_available_quantity(loc2, test_sku)
            print(f"   Disponibilità residua {loc1}: {available_loc1} pz")
            print(f"   Disponibilità residua {loc2}: {available_loc2} pz")
        
        # STEP 2: Ordine B richiede 10 pezzi (dovrebbe preferire il residuo di loc1)
        print(f"\n2. Ordine B richiede 10 pezzi di {test_sku}...")
        
        # DEBUG: Verifica ordinamento dopo Ordine A
        print(f"DEBUG: Ordinamento ubicazioni dopo Ordine A:")
        locations_debug2 = reservation_service.get_locations_with_availability(test_sku, 10)
        for i, loc in enumerate(locations_debug2):
            print(f"  {i+1}. {loc['location_name']}: {loc['available_quantity']} pz "
                  f"(Terra: {loc['is_ground_level']}, Prenotazioni: {loc['has_active_reservations']})")
        
        result_b = reservation_service.allocate_picking_locations(
            order_id="ORD_B_QTY",
            products_needed=[{'sku': test_sku, 'quantity': 10}]
        )
        
        if result_b and result_b[0]['allocations']:
            print(f"   Allocazioni per Ordine B:")
            total_b = 0
            for i, alloc in enumerate(result_b[0]['allocations']):
                print(f"     {i+1}. {alloc['location_name']}: {alloc['quantity']} pz")
                total_b += alloc['quantity']
            print(f"   Totale allocato: {total_b} pz")
            
            # VERIFICA COMPORTAMENTO ATTESO
            first_alloc = result_b[0]['allocations'][0]
            if first_alloc['location_name'] == loc1:
                expected_qty_loc1 = 4  # 14 - 10 = 4 residui
                if first_alloc['quantity'] == expected_qty_loc1:
                    print(f"   CORRETTO: Prima allocazione {loc1} per {expected_qty_loc1} pz (residuo)")
                else:
                    print(f"   ERRORE: Doveva prendere {expected_qty_loc1} pz da {loc1}, ha preso {first_alloc['quantity']}")
            else:
                print(f"   ERRORE: Doveva iniziare da {loc1} (ubicazione con residuo), ha iniziato da {first_alloc['location_name']}")
        
        # STEP 3: Ordine C richiede 1 pezzo (dovrebbe andare al residuo di loc2)
        print(f"\n3. Ordine C richiede 1 pezzo di {test_sku}...")
        result_c = reservation_service.allocate_picking_locations(
            order_id="ORD_C_QTY",
            products_needed=[{'sku': test_sku, 'quantity': 1}]
        )
        
        if result_c and result_c[0]['allocations']:
            alloc_c = result_c[0]['allocations'][0]
            print(f"   Assegnato: {alloc_c['location_name']} per {alloc_c['quantity']} pz")
            
            # VERIFICA: Dovrebbe preferire ubicazione con prenotazioni attive
            if len(result_b[0]['allocations']) > 1:  # Se ordine B ha usato anche loc2
                second_alloc_b = result_b[0]['allocations'][1]
                if alloc_c['location_name'] == second_alloc_b['location_name']:
                    print(f"   CORRETTO: Usa stessa ubicazione dell'ordine B ({alloc_c['location_name']})")
                else:
                    print(f"   INFO: Ubicazione diversa dall'ordine B")
        
        # Mostra stato finale prenotazioni
        print(f"\n4. Stato finale prenotazioni per {test_sku}:")
        all_reservations = db.query(InventoryReservation).filter(
            InventoryReservation.product_sku == test_sku,
            InventoryReservation.status == 'active'
        ).all()
        
        for res in all_reservations:
            print(f"   {res.order_id}: {res.location_name} -> {res.reserved_quantity} pz")
        
        # Verifica disponibilità finali
        final_loc1 = reservation_service.get_available_quantity(loc1, test_sku)
        final_loc2 = reservation_service.get_available_quantity(loc2, test_sku)
        print(f"\nDisponibilità finali:")
        print(f"   {loc1}: {final_loc1} pz disponibili")
        print(f"   {loc2}: {final_loc2} pz disponibili")
        
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
    print("TEST QUANTITY-BASED FIXING\n")
    print("Scenario:")
    print("- 1A1P1: 14 pezzi")
    print("- 1A1P2: 20 pezzi")
    print("- Ordine A: 10 pezzi -> dovrebbe andare a 1A1P1")
    print("- Ordine B: 10 pezzi -> 4 da 1A1P1 + 6 da 1A1P2")
    print("- Ordine C: 1 pezzo -> da 1A1P2 (residuo ordine B)")
    print()
    
    test_quantity_based_logic()

if __name__ == "__main__":
    main()