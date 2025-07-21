#!/usr/bin/env python3
"""
Base test class for API tests
"""
import requests
from typing import Dict, Any, List, Optional
from auth_utils import AuthManager, TEST_USERS
import json


class APITest:
    """Base class for API tests"""
    
    def __init__(self, name: str, auth_manager: AuthManager):
        self.name = name
        self.auth = auth_manager
        self.base_url = auth_manager.base_url
        self.results: List[Dict[str, Any]] = []
        self.passed = 0
        self.failed = 0
    
    def log(self, message: str, level: str = "INFO"):
        """Log a message"""
        print(f"[{level}] {self.name}: {message}")
    
    def make_request(self, method: str, endpoint: str, headers: Dict[str, str], 
                    json_data: Optional[Dict] = None, params: Optional[Dict] = None) -> requests.Response:
        """Make an API request"""
        url = f"{self.base_url}{endpoint}"
        
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=json_data,
            params=params
        )
        
        return response
    
    def assert_status(self, response: requests.Response, expected_status: int, test_name: str):
        """Assert response status code"""
        if response.status_code == expected_status:
            self.pass_test(test_name, f"Status code {expected_status} as expected")
        else:
            self.fail_test(test_name, 
                         f"Expected status {expected_status}, got {response.status_code}. Response: {response.text}")
    
    def assert_equal(self, actual: Any, expected: Any, test_name: str, message: str = ""):
        """Assert equality"""
        if actual == expected:
            self.pass_test(test_name, message or f"Value equals {expected}")
        else:
            self.fail_test(test_name, f"Expected {expected}, got {actual}. {message}")
    
    def assert_true(self, condition: bool, test_name: str, message: str):
        """Assert condition is true"""
        if condition:
            self.pass_test(test_name, message)
        else:
            self.fail_test(test_name, message)
    
    def assert_contains(self, container: Any, item: Any, test_name: str, message: str = ""):
        """Assert item in container"""
        if item in container:
            self.pass_test(test_name, message or f"Contains {item}")
        else:
            self.fail_test(test_name, f"Does not contain {item}. {message}")
    
    def assert_not_contains(self, container: Any, item: Any, test_name: str, message: str = ""):
        """Assert item not in container"""
        if item not in container:
            self.pass_test(test_name, message or f"Does not contain {item}")
        else:
            self.fail_test(test_name, f"Should not contain {item}. {message}")
    
    def assert_greater_than_or_equal(self, actual: Any, expected: Any, test_name: str, message: str = ""):
        """Assert actual >= expected"""
        if actual >= expected:
            self.pass_test(test_name, message or f"{actual} >= {expected}")
        else:
            self.fail_test(test_name, f"Expected at least {expected}, got {actual}. {message}")
    
    def pass_test(self, test_name: str, message: str):
        """Record a passing test"""
        self.passed += 1
        self.results.append({
            'test': test_name,
            'status': 'PASS',
            'message': message
        })
        self.log(f"✓ {test_name}: {message}", "PASS")
    
    def fail_test(self, test_name: str, message: str):
        """Record a failing test"""
        self.failed += 1
        self.results.append({
            'test': test_name,
            'status': 'FAIL',
            'message': message
        })
        self.log(f"✗ {test_name}: {message}", "FAIL")
    
    def run(self):
        """Run all tests - must be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement run()")
    
    def get_summary(self) -> Dict[str, Any]:
        """Get test summary"""
        return {
            'name': self.name,
            'total': self.passed + self.failed,
            'passed': self.passed,
            'failed': self.failed,
            'results': self.results
        }
    
    def print_summary(self):
        """Print test summary"""
        total = self.passed + self.failed
        print(f"\n{self.name} Summary:")
        print(f"  Total tests: {total}")
        print(f"  Passed: {self.passed} ({self.passed/total*100:.1f}%)")
        print(f"  Failed: {self.failed} ({self.failed/total*100:.1f}%)")
        
        if self.failed > 0:
            print("\n  Failed tests:")
            for result in self.results:
                if result['status'] == 'FAIL':
                    print(f"    - {result['test']}: {result['message']}")


class TestSuite:
    """Collection of API tests"""
    
    def __init__(self, name: str = "API Test Suite"):
        self.name = name
        self.tests: List[APITest] = []
        self.auth = AuthManager()
    
    def add_test(self, test_class):
        """Add a test class to the suite"""
        test_instance = test_class(self.auth)
        self.tests.append(test_instance)
    
    def run_all(self):
        """Run all tests in the suite"""
        print(f"\n{'='*60}")
        print(f"Running {self.name}")
        print(f"{'='*60}\n")
        
        total_passed = 0
        total_failed = 0
        
        for test in self.tests:
            print(f"\nRunning {test.name}...")
            print("-" * 40)
            
            try:
                test.run()
            except Exception as e:
                test.fail_test("Test Execution", f"Test crashed: {str(e)}")
            
            test.print_summary()
            total_passed += test.passed
            total_failed += test.failed
        
        # Print overall summary
        print(f"\n{'='*60}")
        print(f"Overall Test Results")
        print(f"{'='*60}")
        print(f"Total tests run: {total_passed + total_failed}")
        print(f"Total passed: {total_passed}")
        print(f"Total failed: {total_failed}")
        
        if total_failed == 0:
            print("\n✅ All tests passed!")
        else:
            print(f"\n❌ {total_failed} tests failed")
        
        return total_failed == 0