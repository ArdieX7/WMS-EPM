#!/usr/bin/env python3

import sys
sys.path.append('.')

try:
    print("1. Testing imports...")
    from wms_app.main import app
    print("   [OK] Main app imported")
    
    from wms_app.routers import reservations
    print("   [OK] Reservations router imported")
    
    from wms_app.routers import analysis  
    print("   [OK] Analysis router imported")
    
    print("\n2. Testing app routes...")
    routes = [route.path for route in app.routes]
    print(f"   Total routes: {len(routes)}")
    
    reservation_routes = [r for r in routes if 'reservation' in r]
    analysis_routes = [r for r in routes if 'analysis' in r]
    
    print(f"   Reservation routes: {reservation_routes}")
    print(f"   Analysis routes: {analysis_routes}")
    
    print("\n3. Testing database connection...")
    from wms_app.database.database import SessionLocal
    db = SessionLocal()
    db.close()
    print("   [OK] Database connection OK")
    
    print("\n[SUCCESS] App startup test PASSED")
    
except Exception as e:
    print(f"\n[ERROR] App startup test FAILED: {e}")
    import traceback
    traceback.print_exc()