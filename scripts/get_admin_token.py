#!/usr/bin/env python3
"""
Quick script to get an admin access token for testing
Default credentials: system@outlabs.io / Asd123$$$
"""
import requests
import json
import sys

# Default credentials
DEFAULT_EMAIL = "system@outlabs.io"
DEFAULT_PASSWORD = "Asd123$$$"
BASE_URL = "http://localhost:8030"

def get_token(email=DEFAULT_EMAIL, password=DEFAULT_PASSWORD):
    """Get access token for the admin user"""
    
    # Login endpoint
    url = f"{BASE_URL}/v1/auth/login"
    
    # Form data (not JSON for login endpoint)
    data = {
        "username": email,
        "password": password
    }
    
    try:
        response = requests.post(url, data=data)
        response.raise_for_status()
        
        tokens = response.json()
        return tokens
    
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        if hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}")
        return None

def main():
    # Check if custom credentials provided
    email = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_EMAIL
    password = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PASSWORD
    
    print(f"Getting token for: {email}")
    
    tokens = get_token(email, password)
    
    if tokens:
        print("\n✅ Success! Here's your access token:\n")
        print(tokens['access_token'])
        print(f"\n📋 Token type: {tokens['token_type']}")
        print(f"⏱️  Expires in: {tokens['expires_in']} seconds")
        
        print("\n🚀 Example usage:")
        print(f'export TOKEN="{tokens["access_token"]}"')
        print('curl -H "Authorization: Bearer $TOKEN" http://localhost:8030/v1/users/me')
        
        # Also save to file for convenience
        with open('.admin_token', 'w') as f:
            f.write(tokens['access_token'])
        print("\n💾 Token saved to .admin_token file")
    else:
        print("\n❌ Failed to get token")
        print("Make sure the system is initialized and the credentials are correct")

if __name__ == "__main__":
    main()