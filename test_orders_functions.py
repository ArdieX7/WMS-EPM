#!/usr/bin/env python3
"""
Script di test per verificare le funzionalità di archiviazione e annullamento ordini.
"""

import requests
import json

BASE_URL = "http://127.0.0.1:8003"

def test_orders_list():
    """Testa la lista degli ordini."""
    print("=== TEST: Lista Ordini ===")
    try:
        response = requests.get(f"{BASE_URL}/orders/")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            orders = response.json()
            print(f"Trovati {len(orders)} ordini")
            for order in orders[:3]:  # Mostra solo i primi 3
                print(f"  - Order {order['id']}: {order['order_number']} (Completed: {order['is_completed']}, Archived: {order.get('is_archived', 'N/A')}, Cancelled: {order.get('is_cancelled', 'N/A')})")
            return orders
        else:
            print(f"Errore: {response.text}")
            return []
    except Exception as e:
        print(f"Errore di connessione: {e}")
        return []

def test_archive_order(order_id):
    """Testa l'archiviazione di un ordine."""
    print(f"\n=== TEST: Archiviazione Ordine {order_id} ===")
    try:
        response = requests.post(f"{BASE_URL}/orders/{order_id}/archive")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"Errore di connessione: {e}")
        return False

def test_cancel_order(order_id):
    """Testa l'annullamento di un ordine."""
    print(f"\n=== TEST: Annullamento Ordine {order_id} ===")
    try:
        response = requests.post(f"{BASE_URL}/orders/{order_id}/cancel")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"Errore di connessione: {e}")
        return False

def test_archived_orders():
    """Testa la lista degli ordini archiviati."""
    print(f"\n=== TEST: Lista Ordini Archiviati ===")
    try:
        response = requests.get(f"{BASE_URL}/orders/archived")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"Errore di connessione: {e}")
        return False

if __name__ == "__main__":
    print("🧪 AVVIO TEST FUNZIONALITÀ ORDINI")
    print("=" * 50)
    
    # Test 1: Lista ordini per trovare candidati per i test
    orders = test_orders_list()
    
    if orders:
        # Cerca un ordine completato per test archiviazione
        completed_orders = [o for o in orders if o.get('is_completed') and not o.get('is_archived')]
        in_progress_orders = [o for o in orders if not o.get('is_completed') and not o.get('is_cancelled')]
        
        if completed_orders:
            print(f"\nTentativo di archiviazione ordine completato: {completed_orders[0]['id']}")
            test_archive_order(completed_orders[0]['id'])
        else:
            print("\nNessun ordine completato disponibile per test archiviazione")
        
        if in_progress_orders:
            print(f"\nTentativo di annullamento ordine in corso: {in_progress_orders[0]['id']}")
            test_cancel_order(in_progress_orders[0]['id'])
        else:
            print("\nNessun ordine in corso disponibile per test annullamento")
    
    # Test lista ordini archiviati
    test_archived_orders()
    
    print("\n" + "=" * 50)
    print("🏁 TEST COMPLETATI")