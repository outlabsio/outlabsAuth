# OutlabsAuth API Test Suite

This directory contains comprehensive API tests for the OutlabsAuth authentication service.

## Overview

The test suite uses direct API calls (not pytest) to test the authentication service endpoints. It includes:

- **Authentication caching**: Tokens are cached locally to avoid re-authenticating for every test
- **Comprehensive assertions**: Status codes, response data, permissions, etc.
- **Test orchestration**: Run all tests or specific tests
- **Clear reporting**: Detailed pass/fail results with summaries

## Structure

- `auth_utils.py` - Authentication utilities and token caching
- `base_test.py` - Base test class and test suite orchestrator
- `run_all_tests.py` - Main test runner
- `test_*.py` - Individual test modules
- `auth_tokens.json` - Cached authentication tokens (git-ignored)

## Running Tests

### Run all tests:
```bash
cd test
python run_all_tests.py
```

### Run specific test:
```bash
python run_all_tests.py --test entity_access
```

### List available tests:
```bash
python run_all_tests.py --list
```

### Clear token cache:
```bash
python run_all_tests.py --clear-cache
```

## Available Tests

1. **entity_access** - Tests entity access control and permissions
   - Verifies users only see entities they have access to
   - Tests filtering for different user types
   - Validates the fix for the top-level entity visibility issue

2. **authentication** - Tests authentication endpoints
   - Valid/invalid login attempts
   - Token validation
   - Current user endpoint

## Test Users

The test suite uses two predefined users:

1. **System Admin** (`system@outlabs.io`)
   - Has full system access
   - Can see all entities

2. **Regular User** (`clearise@gmail.com`)
   - Limited access
   - Only sees entities they have membership in

## Adding New Tests

1. Create a new test file `test_<feature>.py`
2. Import and extend the `APITest` base class
3. Implement the `run()` method with your tests
4. Use assertion methods: `assert_status()`, `assert_equal()`, `assert_true()`, etc.
5. Import your test in `run_all_tests.py`
6. Add to the `available_tests` dictionary

Example:
```python
from base_test import APITest

class MyNewTest(APITest):
    def __init__(self, auth_manager):
        super().__init__("My New Test", auth_manager)
    
    def run(self):
        # Your test logic here
        response = self.make_request('GET', '/v1/endpoint', headers)
        self.assert_status(response, 200, "Test description")
```

## Notes

- The API server must be running on `http://localhost:8030`
- MongoDB must be accessible
- Test users must exist in the database
- Token cache expires based on API token lifetime (15 minutes by default)