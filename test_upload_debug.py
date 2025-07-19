#!/usr/bin/env python3

import sys
sys.path.append('/mnt/c/WMS_EPM')

from wms_app.database import get_db
from wms_app.services.serial_service import SerialService

# Test contenuto file
file_content = """1234
9788838668001
SN001
9788838668001
SN002
5678
9788838668002
SN100"""

print("Testing SerialService parsing...")

# Crea una sessione database mock
try:
    db = next(get_db())
    service = SerialService(db)
    
    print("Service created successfully")
    
    # Test parse
    result = service.parse_serial_file(file_content, "test_user")
    
    print("Parse result:")
    print(f"Success: {result.success}")
    print(f"Message: {result.message}")
    print(f"Errors: {result.errors}")
    print(f"Total lines: {result.total_lines_processed}")
    print(f"Total serials: {result.total_serials_found}")
    print(f"Total orders: {result.total_orders_found}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()