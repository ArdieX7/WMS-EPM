#!/usr/bin/env python3

from fastapi.testclient import TestClient
from wms_app.main import app

client = TestClient(app)

# Test reservations dashboard
print("=== TESTING RESERVATIONS DASHBOARD ===")
response = client.get('/reservations/dashboard')
print(f'Status: {response.status_code}')
if response.status_code != 200:
    print(f'Error: {response.text}')
else:
    print('Reservations dashboard works!')

# Test analysis dashboard  
print("\n=== TESTING ANALYSIS DASHBOARD ===")
response = client.get('/analysis/dashboard')
print(f'Status: {response.status_code}')
if response.status_code != 200:
    print(f'Error: {response.text}')
else:
    print('Analysis dashboard works!')

# Test analysis data
print("\n=== TESTING ANALYSIS DATA ===")
response = client.get('/analysis/data')
print(f'Status: {response.status_code}')
if response.status_code != 200:
    print(f'Error: {response.text}')
else:
    print('Analysis data works!')
    data = response.json()
    print(f'KPIs: {data["kpis"]}')