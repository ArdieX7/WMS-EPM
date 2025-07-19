#!/usr/bin/env python3

import sys
sys.path.append('.')

import uvicorn
from wms_app.main import app

if __name__ == "__main__":
    print("Starting test server on http://127.0.0.1:8006")
    print("Available routes:")
    for route in app.routes:
        print(f"  {route.path}")
    
    print("\nStarting server...")
    uvicorn.run(app, host="127.0.0.1", port=8006, log_level="info")