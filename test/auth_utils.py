#!/usr/bin/env python3
"""
Authentication utilities for API testing
Handles login, token caching, and token refresh
"""
import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, Optional
import requests
from pathlib import Path


class AuthManager:
    """Manages authentication tokens for API testing"""
    
    def __init__(self, base_url: str = "http://localhost:8030", cache_file: str = "auth_tokens.json"):
        self.base_url = base_url
        self.cache_file = Path(__file__).parent / cache_file
        self.tokens: Dict[str, Dict] = self._load_cache()
    
    def _load_cache(self) -> Dict[str, Dict]:
        """Load cached tokens from file"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_cache(self):
        """Save tokens to cache file"""
        with open(self.cache_file, 'w') as f:
            json.dump(self.tokens, f, indent=2)
    
    def _is_token_valid(self, token_data: Dict) -> bool:
        """Check if a token is still valid"""
        if not token_data or 'expires_at' not in token_data:
            return False
        
        # Check if token expires in more than 1 minute
        expires_at = datetime.fromisoformat(token_data['expires_at'])
        return datetime.now() < expires_at - timedelta(minutes=1)
    
    def login(self, email: str, password: str, force_refresh: bool = False) -> str:
        """
        Login and get access token
        Uses cached token if valid, otherwise authenticates
        """
        # Check cache first
        if not force_refresh and email in self.tokens:
            token_data = self.tokens[email]
            if self._is_token_valid(token_data):
                print(f"Using cached token for {email}")
                return token_data['access_token']
        
        # Authenticate
        print(f"Authenticating {email}...")
        response = requests.post(
            f"{self.base_url}/v1/auth/login/json",
            json={"email": email, "password": password},
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code != 200:
            raise Exception(f"Login failed for {email}: {response.status_code} - {response.text}")
        
        data = response.json()
        
        # Calculate expiration time
        expires_in = data.get('expires_in', 900)  # Default 15 minutes
        expires_at = datetime.now() + timedelta(seconds=expires_in)
        
        # Cache the token
        self.tokens[email] = {
            'access_token': data['access_token'],
            'refresh_token': data.get('refresh_token', ''),
            'expires_at': expires_at.isoformat(),
            'email': email
        }
        self._save_cache()
        
        return data['access_token']
    
    def get_headers(self, email: str, password: str) -> Dict[str, str]:
        """Get authorization headers for API requests"""
        token = self.login(email, password)
        return {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
    
    def clear_cache(self):
        """Clear all cached tokens"""
        self.tokens = {}
        self._save_cache()
        if self.cache_file.exists():
            self.cache_file.unlink()
        print("Token cache cleared")


# Test users configuration
TEST_USERS = {
    'system_admin': {
        'email': 'system@outlabs.io',
        'password': 'Asd123$$$',
        'description': 'System administrator with full access'
    },
    'regular_user': {
        'email': 'clearise@gmail.com', 
        'password': 'Asd123$$$',
        'description': 'Regular user with limited access'
    }
}


# Convenience functions
def get_system_admin_headers(auth_manager: Optional[AuthManager] = None) -> Dict[str, str]:
    """Get headers for system admin"""
    if not auth_manager:
        auth_manager = AuthManager()
    return auth_manager.get_headers(
        TEST_USERS['system_admin']['email'],
        TEST_USERS['system_admin']['password']
    )


def get_regular_user_headers(auth_manager: Optional[AuthManager] = None) -> Dict[str, str]:
    """Get headers for regular user"""
    if not auth_manager:
        auth_manager = AuthManager()
    return auth_manager.get_headers(
        TEST_USERS['regular_user']['email'],
        TEST_USERS['regular_user']['password']
    )


if __name__ == "__main__":
    # Test the auth manager
    auth = AuthManager()
    
    print("Testing authentication...")
    try:
        # Test system admin login
        token = auth.login(TEST_USERS['system_admin']['email'], TEST_USERS['system_admin']['password'])
        print(f"System admin token: {token[:20]}...")
        
        # Test caching - should use cached token
        token2 = auth.login(TEST_USERS['system_admin']['email'], TEST_USERS['system_admin']['password'])
        print(f"Second login (should be cached): {token2[:20]}...")
        
        # Test regular user
        headers = get_regular_user_headers(auth)
        print(f"Regular user headers: {list(headers.keys())}")
        
    except Exception as e:
        print(f"Error: {e}")