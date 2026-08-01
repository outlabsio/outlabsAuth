#!/usr/bin/env python3
"""Quick test script for roles endpoint."""
import requests

# Login
response = requests.post(
    "http://localhost:8003/v1/auth/login",
    json={"email": "admin@test.com", "password": "Test123!!"}
)
print(f"Login status: {response.status_code}")
if response.status_code == 200:
    token = response.json()["access_token"]
    print(f"Got token: {token[:20]}...")

    # Test roles endpoint
    response = requests.get(
        "http://localhost:8003/v1/roles/?page=1&limit=100",
        headers={"Authorization": f"Bearer {token}"}
    )
    print(f"\nRoles endpoint status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Got {data['total']} roles")
        for role in data['items']:
            print(f"  - {role['name']}: {len(role.get('permissions', []))} permissions")
    else:
        print(f"Error: {response.text}")
else:
    print(f"Login failed: {response.text}")
