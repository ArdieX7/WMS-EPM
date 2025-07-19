#!/usr/bin/env python3

import sys
sys.path.append('/mnt/c/WMS_EPM')

from wms_app.database import get_db
from wms_app.models.products import Product, EanCode

try:
    db = next(get_db())
    
    # Prodotti di test
    test_products = [
        {
            "sku": "PROD001",
            "description": "Prodotto Test 1",
            "estimated_value": 10.50,
            "eans": ["9788838668001"]
        },
        {
            "sku": "PROD002", 
            "description": "Prodotto Test 2",
            "estimated_value": 15.75,
            "eans": ["9788838668002"]
        },
        {
            "sku": "PROD003",
            "description": "Prodotto Test 3", 
            "estimated_value": 20.00,
            "eans": ["9788838668003"]
        }
    ]
    
    for prod_data in test_products:
        # Controlla se esiste già
        existing = db.query(Product).filter(Product.sku == prod_data["sku"]).first()
        if not existing:
            # Crea prodotto
            product = Product(
                sku=prod_data["sku"],
                description=prod_data["description"],
                estimated_value=prod_data["estimated_value"]
            )
            db.add(product)
            
            # Crea EAN
            for ean in prod_data["eans"]:
                existing_ean = db.query(EanCode).filter(EanCode.ean == ean).first()
                if not existing_ean:
                    ean_obj = EanCode(ean=ean, product_sku=prod_data["sku"])
                    db.add(ean_obj)
            
            print(f"Added product {prod_data['sku']} with EANs {prod_data['eans']}")
        else:
            print(f"Product {prod_data['sku']} already exists")
    
    db.commit()
    print("Test data setup completed")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()