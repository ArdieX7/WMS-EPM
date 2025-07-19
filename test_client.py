#!/usr/bin/env python3

import urllib.request
import urllib.parse
import json
import sys

def test_endpoint(url, method='GET', data=None, headers=None):
    print(f"\n=== Testing {method} {url} ===")
    
    if headers is None:
        headers = {}
        
    if data and isinstance(data, dict):
        data = json.dumps(data).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req) as response:
            result = response.read().decode('utf-8')
            print(f"Status: {response.status}")
            print(f"Response: {result[:200]}...")
            return True
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.reason}")
        error_body = e.read().decode('utf-8')
        print(f"Error details: {error_body}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False

def main():
    base_url = "http://localhost:8002"
    
    # Test basic endpoints
    test_endpoint(f"{base_url}/")
    test_endpoint(f"{base_url}/analysis/data")
    
    # Test inventory update
    test_data = {
        "product_sku": "SND-09HRSB-ID",
        "location_name": "TERRA",
        "quantity": 4
    }
    test_endpoint(f"{base_url}/inventory/update-stock", "POST", test_data)
    
    # Test with existing product in database
    test_data2 = {
        "product_sku": "ICG-09INT3-ID",
        "location_name": "TERRA", 
        "quantity": 5
    }
    test_endpoint(f"{base_url}/inventory/update-stock", "POST", test_data2)

if __name__ == "__main__":
    main()