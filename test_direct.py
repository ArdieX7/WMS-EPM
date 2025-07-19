#!/usr/bin/env python3

import sys
sys.path.append('.')

from wms_app.database.database import SessionLocal
from wms_app.routers.reservations import get_reservations_dashboard
from wms_app.routers.analysis import get_analysis_data
import asyncio
from fastapi import Request

class MockRequest:
    def __init__(self):
        self.url = MockURL()

class MockURL:
    def __init__(self):
        self.path = '/reservations/dashboard'

async def test_reservations():
    db = SessionLocal()
    try:
        request = MockRequest()
        result = await get_reservations_dashboard(request, db)
        print("[OK] Reservations dashboard works!")
        print(f"Template response: {type(result)}")
    except Exception as e:
        print(f"[ERROR] Reservations error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

def test_analysis():
    db = SessionLocal()
    try:
        result = get_analysis_data(db)
        print("[OK] Analysis data works!")
        print(f"KPIs: {result.kpis}")
        print(f"Products count: {len(result.total_stock_by_product)}")
    except Exception as e:
        print(f"[ERROR] Analysis error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    print("=== TESTING ENDPOINTS DIRECTLY ===")
    
    print("\n1. Testing Analysis Data:")
    test_analysis()
    
    print("\n2. Testing Reservations Dashboard:")
    asyncio.run(test_reservations())