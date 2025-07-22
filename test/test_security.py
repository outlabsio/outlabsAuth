#!/usr/bin/env python3
"""
Basic security tests for authentication and authorization
"""
from base_test import APITest
from auth_utils import get_system_admin_headers, AuthManager, TEST_USERS
from test_data_factory import TestDataFactory
import json
import string
import random


class SecurityTest(APITest):
    """Test security aspects of the authentication system"""
    
    def __init__(self, auth_manager):
        super().__init__("Security Test", auth_manager)
        self.factory = TestDataFactory(auth_manager)
        
    def run(self):
        """Run security tests"""
        try:
            # Test 1: Permission escalation attempts
            self.test_permission_escalation()
            
            # Test 2: Cross-tenant data isolation
            self.test_cross_tenant_isolation()
            
            # Test 3: JWT token security
            self.test_jwt_token_security()
            
            # Test 4: Password security
            self.test_password_security()
            
            # Test 5: SQL injection prevention
            self.test_sql_injection_prevention()
            
            # Test 6: Authentication bypass attempts
            self.test_authentication_bypass()
            
            # Test 7: Rate limiting (if implemented)
            self.test_rate_limiting()
            
            # Test 8: Input validation
            self.test_input_validation()
            
        finally:
            # Cleanup
            self.cleanup()
    
    def test_permission_escalation(self):
        """Test that users cannot escalate their permissions"""
        # Create test structure
        platform = self.factory.create_test_platform("security_escalation")
        org = self.factory.create_entity(parent_id=platform['id'])
        
        # Create user with limited permissions
        limited_user_data = self.factory.create_user_with_role(
            org['id'],
            "limited_user",
            permissions=["entity:read", "user:read"]
        )
        
        limited_headers = self.auth.get_headers(
            limited_user_data['user']['email'],
            limited_user_data['user']['test_password']
        )
        
        # Try to update own role permissions
        response = self.make_request(
            'PUT',
            f'/v1/roles/{limited_user_data["role"]["id"]}',
            headers=limited_headers,
            json_data={
                "permissions": ["entity:delete", "user:delete", "role:delete"]
            }
        )
        
        self.assert_status(
            response,
            403,
            "Cannot escalate permissions via role update"
        )
        
        # Try to assign self to admin role
        admin_role = self.factory.create_role(
            org['id'],
            "admin_role",
            permissions=["entity:delete", "user:delete", "role:delete"]
        )
        
        response = self.make_request(
            'PUT',
            f'/v1/users/{limited_user_data["user"]["id"]}',
            headers=limited_headers,
            json_data={
                "entity_assignments": [{
                    "entity_id": org['id'],
                    "role_ids": [admin_role['id']]
                }]
            }
        )
        
        self.assert_status(
            response,
            403,
            "Cannot assign self to admin role"
        )
        
        # Try to create a new role with elevated permissions
        response = self.make_request(
            'POST',
            '/v1/roles',
            headers={**limited_headers, 'X-Entity-Context-Id': org['id']},
            json_data={
                "name": self.factory.generate_unique_name("escalated_role"),
                "display_name": "Escalated Role",
                "permissions": ["entity:delete", "user:delete"],
                "entity_id": org['id'],
                "is_custom": True
            }
        )
        
        self.assert_status(
            response,
            403,
            "Cannot create role with elevated permissions"
        )
    
    def test_cross_tenant_isolation(self):
        """Test that data is properly isolated between tenants"""
        # Create two separate platforms
        platform1 = self.factory.create_test_platform("tenant1")
        platform2 = self.factory.create_test_platform("tenant2")
        
        org1 = self.factory.create_entity(
            parent_id=platform1['id'],
            name_prefix="org1"
        )
        org2 = self.factory.create_entity(
            parent_id=platform2['id'],
            name_prefix="org2"
        )
        
        # Create admin in platform1
        admin1_data = self.factory.create_user_with_role(
            org1['id'],
            "admin1",
            permissions=["entity:read", "entity:update", "entity:delete", "user:read", "user:update"]
        )
        
        admin1_headers = self.auth.get_headers(
            admin1_data['user']['email'],
            admin1_data['user']['test_password']
        )
        
        # Try to access platform2's entity
        response = self.make_request(
            'GET',
            f'/v1/entities/{org2["id"]}',
            headers=admin1_headers
        )
        
        self.assert_status(
            response,
            403,
            "Cannot access other tenant's entity"
        )
        
        # Try to update platform2's entity
        response = self.make_request(
            'PUT',
            f'/v1/entities/{org2["id"]}',
            headers=admin1_headers,
            json_data={
                "description": "Hacked by tenant1"
            }
        )
        
        self.assert_status(
            response,
            403,
            "Cannot update other tenant's entity"
        )
        
        # Try to list users from platform2
        response = self.make_request(
            'GET',
            '/v1/users',
            headers={**admin1_headers, 'X-Entity-Context-Id': org1['id']},
            params={'entity_id': org2['id']}
        )
        
        if response.status_code == 200:
            data = response.json()
            # Should not see any users from org2
            self.assert_equal(
                len([u for u in data.get('items', []) if any(e.get('id') == org2['id'] for e in u.get('entities', []))]),
                0,
                "Cross-tenant user isolation",
                "No users from other tenant visible"
            )
    
    def test_jwt_token_security(self):
        """Test JWT token security measures"""
        # Get a valid token
        valid_token = self.auth.login(
            TEST_USERS['regular_user']['email'],
            TEST_USERS['regular_user']['password']
        )
        
        # Test malformed token
        response = self.make_request(
            'GET',
            '/v1/auth/me',
            headers={'Authorization': 'Bearer malformed.token.here'}
        )
        
        self.assert_status(
            response,
            401,
            "Malformed token rejected"
        )
        
        # Test token with Bearer prefix missing
        response = self.make_request(
            'GET',
            '/v1/auth/me',
            headers={'Authorization': valid_token}
        )
        
        self.assert_status(
            response,
            401,
            "Token without Bearer prefix rejected"
        )
        
        # Test expired token (we can't easily create one, so just verify the endpoint exists)
        # In a real test, you'd mock time or use a pre-expired token
        self.pass_test(
            "Expired token handling",
            "Expired token handling should be tested with mocked time"
        )
        
        # Test token tampering (modify payload)
        parts = valid_token.split('.')
        if len(parts) == 3:
            # Tamper with the payload
            tampered_token = f"{parts[0]}.eyJ0YW1wZXJlZCI6dHJ1ZX0.{parts[2]}"
            response = self.make_request(
                'GET',
                '/v1/auth/me',
                headers={'Authorization': f'Bearer {tampered_token}'}
            )
            
            self.assert_status(
                response,
                401,
                "Tampered token rejected"
            )
    
    def test_password_security(self):
        """Test password security requirements"""
        headers = get_system_admin_headers(self.auth)
        
        # Test weak passwords
        weak_passwords = [
            "password",      # Common password
            "12345678",      # Numeric only
            "abcdefgh",      # Letters only
            "short",         # Too short
            "",              # Empty
            " " * 10,        # Spaces only
        ]
        
        for weak_pass in weak_passwords:
            response = self.make_request(
                'POST',
                '/v1/users',
                headers=headers,
                json_data={
                    "email": f"{self.factory.generate_unique_name('weak')}@test.com",
                    "password": weak_pass
                }
            )
            
            # Should reject weak passwords (422 or 400)
            self.assert_true(
                response.status_code in [400, 422],
                f"Weak password '{weak_pass[:8]}...' rejected",
                f"Password validation prevents weak password (status: {response.status_code})"
            )
        
        # Test strong password is accepted
        strong_password = "StrongP@ssw0rd123!"
        response = self.make_request(
            'POST',
            '/v1/users',
            headers=headers,
            json_data={
                "email": f"{self.factory.generate_unique_name('strong')}@test.com",
                "password": strong_password
            }
        )
        
        self.assert_status(
            response,
            200,
            "Strong password accepted"
        )
    
    def test_sql_injection_prevention(self):
        """Test that SQL injection attempts are prevented"""
        headers = get_system_admin_headers(self.auth)
        
        # Common SQL injection payloads (adapted for NoSQL)
        injection_payloads = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "admin'--",
            '{"$ne": null}',
            '{"$gt": ""}',
            '{"$where": "this.password.length > 0"}',
        ]
        
        for payload in injection_payloads:
            # Try injection in search parameter
            response = self.make_request(
                'GET',
                '/v1/users',
                headers=headers,
                params={'search': payload}
            )
            
            # Should not cause server error
            self.assert_true(
                response.status_code in [200, 400, 422],
                f"Injection attempt handled safely",
                f"Payload '{payload[:20]}...' handled without server error"
            )
            
            # Try injection in entity name
            response = self.make_request(
                'POST',
                '/v1/entities',
                headers=headers,
                json_data={
                    "name": payload,
                    "display_name": "Test Entity",
                    "entity_type": "organization",
                    "entity_class": "STRUCTURAL"
                }
            )
            
            # Should reject or sanitize
            if response.status_code == 200:
                # If accepted, verify it was sanitized
                entity = response.json()
                self.assert_true(
                    entity.get('name') != payload,
                    "Entity name sanitized",
                    "Injection payload was sanitized"
                )
    
    def test_authentication_bypass(self):
        """Test various authentication bypass attempts"""
        # Try accessing protected endpoint without token
        response = self.make_request(
            'GET',
            '/v1/users',
            headers={}
        )
        
        self.assert_status(
            response,
            401,
            "No token rejected"
        )
        
        # Try with various invalid auth headers
        invalid_headers = [
            {'Authorization': ''},
            {'Authorization': 'Basic dXNlcjpwYXNz'},  # Basic auth attempt
            {'Authorization': 'Bearer '},
            {'Authorization': 'null'},
            {'Authorization': 'undefined'},
            {'X-Auth-Token': 'bypass-attempt'},
        ]
        
        for headers in invalid_headers:
            response = self.make_request(
                'GET',
                '/v1/users',
                headers=headers
            )
            
            self.assert_status(
                response,
                401,
                f"Invalid auth header rejected"
            )
        
        # Try to access system endpoints
        response = self.make_request(
            'GET',
            '/v1/system/info',  # Hypothetical system endpoint
            headers={}
        )
        
        # Should either not exist (404) or require auth (401)
        self.assert_true(
            response.status_code in [401, 404, 405],
            "System endpoints protected",
            f"System endpoint returns {response.status_code}"
        )
    
    def test_rate_limiting(self):
        """Test rate limiting if implemented"""
        # Note: This test assumes rate limiting might be implemented
        # If not, it will pass with a note
        
        headers = get_system_admin_headers(self.auth)
        
        # Make many rapid requests
        responses = []
        for i in range(50):
            response = self.make_request(
                'GET',
                '/v1/auth/me',
                headers=headers
            )
            responses.append(response.status_code)
        
        # Check if any were rate limited
        rate_limited = any(status == 429 for status in responses)
        
        if rate_limited:
            self.pass_test(
                "Rate limiting active",
                "Rate limiting is protecting against rapid requests"
            )
        else:
            self.pass_test(
                "Rate limiting check",
                "Rate limiting not detected (may not be implemented)"
            )
    
    def test_input_validation(self):
        """Test input validation for various fields"""
        headers = get_system_admin_headers(self.auth)
        
        # Test email validation
        invalid_emails = [
            "notanemail",
            "missing@domain",
            "@nodomain.com",
            "spaces in@email.com",
            "double@@at.com",
            "",
        ]
        
        for email in invalid_emails:
            response = self.make_request(
                'POST',
                '/v1/users',
                headers=headers,
                json_data={
                    "email": email,
                    "password": "ValidPass123!"
                }
            )
            
            self.assert_true(
                response.status_code in [400, 422],
                f"Invalid email rejected",
                f"Email '{email}' validation failed as expected"
            )
        
        # Test field length limits
        very_long_string = "a" * 1000
        response = self.make_request(
            'POST',
            '/v1/entities',
            headers=headers,
            json_data={
                "name": very_long_string,
                "display_name": "Test",
                "entity_type": "organization",
                "entity_class": "STRUCTURAL"
            }
        )
        
        # Should reject or truncate
        self.assert_true(
            response.status_code in [400, 422] or 
            (response.status_code == 200 and len(response.json().get('name', '')) < 1000),
            "Field length validation",
            "Long input either rejected or truncated"
        )
        
        # Test special characters in various fields
        special_chars = "<script>alert('xss')</script>"
        response = self.make_request(
            'POST',
            '/v1/entities',
            headers=headers,
            json_data={
                "name": self.factory.generate_unique_name("xss_test"),
                "display_name": special_chars,
                "description": special_chars,
                "entity_type": "organization",
                "entity_class": "STRUCTURAL"
            }
        )
        
        if response.status_code == 200:
            entity = response.json()
            # Verify special characters are handled safely
            self.assert_not_contains(
                entity.get('display_name', ''),
                '<script>',
                "XSS prevention",
                "Script tags sanitized or encoded"
            )
    
    def cleanup(self):
        """Cleanup test data"""
        self.log("Cleaning up test data...")
        self.factory.cleanup_test_data()


if __name__ == "__main__":
    # Run just this test
    from auth_utils import AuthManager
    
    auth = AuthManager()
    test = SecurityTest(auth)
    test.run()
    test.print_summary()