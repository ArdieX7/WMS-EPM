#!/usr/bin/env python3

import sys
import asyncio
sys.path.append('.')
from wms_app.database.database import SessionLocal
from wms_app.services.reservation_service import ReservationService

async def test_round_robin_system():
    db = SessionLocal()
    try:
        service = ReservationService(db)
        
        print('=== TEST ROUND-ROBIN + RESERVATION SYSTEM ===')
        
        # Test 1: Verifica disponibilità per un prodotto
        sku = 'ICG-09INT3-ID'
        print(f'\n1. Disponibilità per {sku}:')
        locations = service.get_locations_with_availability(sku, 5)
        for loc in locations[:3]:
            print(f'   {loc["location_name"]}: {loc["available_quantity"]} pz disponibili')
        
        # Test 2: Alloca per ordini multipli (simula il tuo scenario)
        print(f'\n2. Test scenario: 2 ordini richiedono stesso SKU')
        
        # Ordine 11: richiede 5 pz
        print('\n   Ordine 11 richiede 5 pz...')
        allocation1 = service.allocate_picking_locations('11', [{'sku': sku, 'quantity': 5}])
        if allocation1[0]['allocations']:
            loc1 = allocation1[0]['allocations'][0]['location_name']
            qty1 = allocation1[0]['allocations'][0]['quantity']
            print(f'   -> Ordine 11 assegnato a: {loc1} (prende {qty1} pz)')
        
        # Ordine 22: richiede 6 pz  
        print('\n   Ordine 22 richiede 6 pz...')
        allocation2 = service.allocate_picking_locations('22', [{'sku': sku, 'quantity': 6}])
        if allocation2[0]['allocations']:
            loc2 = allocation2[0]['allocations'][0]['location_name']
            qty2 = allocation2[0]['allocations'][0]['quantity']
            print(f'   -> Ordine 22 assegnato a: {loc2} (prende {qty2} pz)')
        
        # Verifica se Round-Robin ha funzionato
        if allocation1[0]['allocations'] and allocation2[0]['allocations']:
            loc1 = allocation1[0]['allocations'][0]['location_name']
            loc2 = allocation2[0]['allocations'][0]['location_name']
            
            if loc1 != loc2:
                print(f'\n[OK] ROUND-ROBIN FUNZIONA: Ordini inviati a ubicazioni diverse!')
                print(f'   Ordine 11 -> {loc1}')
                print(f'   Ordine 22 -> {loc2}')
            else:
                print(f'\n[WARN] ROUND-ROBIN: Entrambi alla stessa ubicazione: {loc1}')
                print('   (Normale se solo una ubicazione ha abbastanza stock)')
        
        # Test 3: Stato prenotazioni
        print(f'\n3. Prenotazioni attive:')
        reservations11 = service.get_reservation_status('11')
        reservations22 = service.get_reservation_status('22')
        all_reservations = reservations11 + reservations22
        for r in all_reservations:
            print(f'   Prenotazione {r["id"]}: {r["product_sku"]} in {r["location_name"]} ({r["reserved_quantity"]} pz, status: {r["status"]})')
        
        # Test 4: Cleanup
        print(f'\n4. Test cleanup manuale...')
        cleaned = service.manual_cleanup_all_reservations()
        print(f'   Pulite {cleaned} prenotazioni')
        
        print('\n=== TUTTI I TEST COMPLETATI ===')
        
    except Exception as e:
        print(f'Errore durante il test: {e}')
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_round_robin_system())