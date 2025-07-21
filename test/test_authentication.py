#!/usr/bin/env python3
"""
Test authentication endpoints
"""
from base_test import APITest
from auth_utils import TEST_USERS
import time


class AuthenticationTest(APITest):
    """Test authentication flows"""
    
    def __init__(self, auth_manager):
        super().__init__("Authentication Test", auth_manager)
    
    def run(self):
        """Run authentication tests"""
        # Test 1: Valid login
        self.test_valid_login()
        
        # Test 2: Invalid credentials
        self.test_invalid_credentials()
        
        # Test 3: Get current user
        self.test_get_current_user()
        
        # Test 4: Token expiration
        self.test_token_validation()
    
    def test_valid_login(self):
        """Test login with valid credentials"""
        response = self.make_request(
            'POST',
            '/v1/auth/login/json',
            headers={'Content-Type': 'application/json'},
            json_data={
                'email': TEST_USERS['system_admin']['email'],
                'password': TEST_USERS['system_admin']['password']
            }
        )
        
        self.assert_status(response, 200, "Valid login")
        
        data = response.json()
        self.assert_true(
            'access_token' in data,
            "Login returns access token",
            "Access token present in response"
        )
        
        self.assert_true(
            'token_type' in data and data['token_type'] == 'bearer',
            "Login returns token type",
            "Token type is 'bearer'"
        )
        
        self.assert_true(
            'expires_in' in data and data['expires_in'] > 0,
            "Login returns expiration",
            f"Token expires in {data.get('expires_in', 0)} seconds"
        )
    
    def test_invalid_credentials(self):
        """Test login with invalid credentials"""
        # Test wrong password
        response = self.make_request(
            'POST',
            '/v1/auth/login/json',
            headers={'Content-Type': 'application/json'},
            json_data={
                'email': TEST_USERS['system_admin']['email'],
                'password': 'WrongPassword123!'
            }
        )
        
        self.assert_status(response, 401, "Invalid password rejected")
        
        # Test non-existent user
        response = self.make_request(
            'POST',
            '/v1/auth/login/json',
            headers={'Content-Type': 'application/json'},
            json_data={
                'email': 'nonexistent@example.com',
                'password': 'Password123!'
            }
        )
        
        self.assert_status(response, 401, "Non-existent user rejected")
        
        # Test malformed email
        response = self.make_request(
            'POST',
            '/v1/auth/login/json',
            headers={'Content-Type': 'application/json'},
            json_data={
                'email': 'not-an-email',
                'password': 'Password123!'
            }
        )
        
        self.assert_true(
            response.status_code in [400, 422],
            "Malformed email rejected",
            f"Status {response.status_code} - Invalid email format rejected"
        )
    
    def test_get_current_user(self):
        """Test getting current user info"""
        # Get token
        headers = self.auth.get_headers(
            TEST_USERS['system_admin']['email'],
            TEST_USERS['system_admin']['password']
        )
        
        # Get current user
        response = self.make_request(
            'GET',
            '/v1/auth/me',
            headers=headers
        )
        
        self.assert_status(response, 200, "Get current user")
        
        data = response.json()
        self.assert_equal(
            data.get('email'),
            TEST_USERS['system_admin']['email'],
            "Current user email",
            "Email matches logged in user"
        )
        
        self.assert_true(
            'id' in data,
            "User has ID",
            f"User ID: {data.get('id', 'None')}"
        )
    
    def test_token_validation(self):
        """Test token validation"""
        # Test with invalid token
        response = self.make_request(
            'GET',
            '/v1/auth/me',
            headers={
                'Authorization': 'Bearer invalid-token-12345',
                'Content-Type': 'application/json'
            }
        )
        
        self.assert_status(response, 401, "Invalid token rejected")
        
        # Test without token
        response = self.make_request(
            'GET',
            '/v1/auth/me',
            headers={'Content-Type': 'application/json'}
        )
        
        self.assert_true(
            response.status_code in [401, 403],
            "Missing token rejected",
            f"Status {response.status_code} - Request without token rejected"
        )


if __name__ == "__main__":
    # Run just this test
    from auth_utils import AuthManager
    
    auth = AuthManager()
    test = AuthenticationTest(auth)
    test.run()
    test.print_summary()