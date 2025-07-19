#!/usr/bin/env python3

import sys
sys.path.append('/mnt/c/WMS_EPM')

from wms_app.database import get_db
from wms_app.models.products import EanCode

try:
    db = next(get_db())
    
    # Controlla EAN esistenti
    ean_codes = db.query(EanCode).all()
    
    print(f"EAN codes in database: {len(ean_codes)}")
    for ean in ean_codes[:10]:  # Primi 10
        print(f"  EAN: {ean.ean} -> SKU: {ean.product_sku}")
    
    # Controlla EAN specifici del test
    test_eans = ["9788838668001", "9788838668002"]
    for test_ean in test_eans:
        ean = db.query(EanCode).filter(EanCode.ean == test_ean).first()
        if ean:
            print(f"Test EAN {test_ean} found -> SKU: {ean.product_sku}")
        else:
            print(f"Test EAN {test_ean} NOT FOUND")
            
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()