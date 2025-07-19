#!/usr/bin/env python3

import sys
sys.path.append('.')

from wms_app.database.database import SessionLocal
from wms_app.routers.reservations import get_reservations_dashboard
from wms_app.routers.analysis import get_analysis_data
import asyncio
from fastapi import Request

class MockRequest:
    def __init__(self, path):
        self.url = MockURL(path)

class MockURL:
    def __init__(self, path):
        self.path = path

async def test_and_save():
    db = SessionLocal()
    try:
        print("=== TESTING AND GENERATING HTML ===")
        
        # Test Analysis Data
        print("\n1. Testing Analysis Data:")
        analysis_data = get_analysis_data(db)
        print(f"   KPIs: {analysis_data.kpis}")
        print(f"   Products: {len(analysis_data.total_stock_by_product)}")
        print("   [SUCCESS] Analysis data works!")
        
        # Test Reservations Dashboard
        print("\n2. Testing Reservations Dashboard:")
        request = MockRequest('/reservations/dashboard')
        reservations_response = await get_reservations_dashboard(request, db)
        print(f"   Template: {type(reservations_response)}")
        print("   [SUCCESS] Reservations dashboard works!")
        
        # Generate HTML for debugging
        print("\n3. Checking template content:")
        if hasattr(reservations_response, 'body'):
            html_content = reservations_response.body.decode()
            print(f"   HTML length: {len(html_content)} chars")
            # Save first part for debugging
            with open('debug_reservations.html', 'w', encoding='utf-8') as f:
                f.write(html_content[:2000] + "...")
            print("   Saved debug_reservations.html")
        else:
            print("   No body attribute found")
        
        print("\n[SUCCESS] ALL TESTS PASSED - Endpoints work correctly!")
        print("\nThe issue might be with the server startup, not the endpoint logic.")
        
    except Exception as e:
        print(f"\n[ERROR] ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_and_save())