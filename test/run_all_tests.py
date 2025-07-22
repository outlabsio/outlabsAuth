#!/usr/bin/env python3
"""
Main test runner - orchestrates all API tests
"""
import sys
import argparse
from datetime import datetime
from base_test import TestSuite
from auth_utils import AuthManager

# Import all test modules
from test_authentication import AuthenticationTest
from test_user_management import UserManagementTest
from test_entity_hierarchy import EntityHierarchyTest
from test_entity_access import EntityAccessTest
from test_roles_permissions import RolePermissionTest
from test_memberships import MembershipTest
from test_permission_enforcement import PermissionEnforcementTest
from test_complex_scenarios import ComplexScenarioTest
from test_security import SecurityTest


def main():
    """Run all API tests"""
    parser = argparse.ArgumentParser(description='Run OutlabsAuth API tests')
    parser.add_argument('--clear-cache', action='store_true', 
                       help='Clear authentication token cache before running')
    parser.add_argument('--test', type=str, help='Run only specific test')
    parser.add_argument('--list', action='store_true', help='List available tests')
    
    args = parser.parse_args()
    
    # Initialize test suite
    suite = TestSuite("OutlabsAuth API Test Suite")
    
    # Available tests - ORDER MATTERS!
    # Tests are run in the order they appear here
    available_tests = {
        'authentication': AuthenticationTest,      # Basic auth must work first
        'user_management': UserManagementTest,   # User CRUD operations
        'entity_hierarchy': EntityHierarchyTest, # Entity structure and rules
        'entity_access': EntityAccessTest,       # Access control validation
        'role_permissions': RolePermissionTest,  # Role and permission management
        'memberships': MembershipTest,           # User-entity membership operations
        'permission_enforcement': PermissionEnforcementTest,  # Permission checks on endpoints
        'complex_scenarios': ComplexScenarioTest,  # Real-world multi-entity scenarios
        'security': SecurityTest,                # Security tests
    }
    
    if args.list:
        print("Available tests:")
        for name in available_tests:
            print(f"  - {name}")
        return
    
    # Clear cache if requested
    if args.clear_cache:
        auth = AuthManager()
        auth.clear_cache()
        print("Authentication cache cleared\n")
    
    # Add tests to suite
    if args.test:
        if args.test in available_tests:
            suite.add_test(available_tests[args.test])
        else:
            print(f"Error: Unknown test '{args.test}'")
            print("Use --list to see available tests")
            return 1
    else:
        # Add all tests
        for test_class in available_tests.values():
            suite.add_test(test_class)
    
    # Record start time
    start_time = datetime.now()
    
    # Run tests
    success = suite.run_all()
    
    # Calculate duration
    duration = datetime.now() - start_time
    print(f"\nTest suite completed in {duration.total_seconds():.2f} seconds")
    
    # Return appropriate exit code
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())