import requests
import json

# Login
login_response = requests.post(
    "http://localhost:8003/v1/auth/login",
    json={"email": "system@outlabs.io", "password": "Asd123$$"}
)
print(f"Login Status: {login_response.status_code}")
print(f"Login Response: {login_response.text}")

if login_response.status_code == 200:
    token = login_response.json()["access_token"]
    print(f"✅ Logged in, token: {token[:20]}...")
    
    # Try to create role
    role_data = {
        "name": "content_manager",
        "display_name": "Content Manager",
        "description": "Can manage blog posts and comments",
        "permissions": ["post:create"]
    }
    
    print(f"\n📤 Sending role data:")
    print(json.dumps(role_data, indent=2))
    
    response = requests.post(
        "http://localhost:8003/v1/roles/",
        headers={"Authorization": f"Bearer {token}"},
        json=role_data
    )
    
    print(f"\n📨 Response Status: {response.status_code}")
    print(f"📨 Response Body:")
    print(json.dumps(response.json(), indent=2))
