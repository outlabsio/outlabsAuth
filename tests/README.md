# OutlabsAuth Testing Suite

Comprehensive test suite for the OutlabsAuth library covering Phase 2 (SimpleRBAC) functionality.

## Table of Contents

- [Quick Start](#quick-start)
- [Test Structure](#test-structure)
- [Running Tests](#running-tests)
- [Test Coverage](#test-coverage)
- [Writing Tests](#writing-tests)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

### Prerequisites

1. **MongoDB**: Tests require a running MongoDB instance
   ```bash
   # Using Docker (recommended)
   docker run -d -p 27017:27017 --name mongo-test mongo:latest

   # Or use local MongoDB installation
   mongod --dbpath /path/to/test/db
   ```

2. **Install test dependencies**:
   ```bash
   uv sync --extra test
   # or
   pip install -e ".[test]"
   ```

### Run All Tests

```bash
# Run all tests with coverage
uv run pytest

# Run with verbose output
uv run pytest -v

# Run with coverage report
uv run pytest --cov=outlabs_auth --cov-report=html
```

---

## Test Structure

```
tests/
├── README.md              # This file
├── conftest.py            # Shared fixtures (database, auth instances, test data)
│
├── unit/                  # Unit tests (isolated component testing)
│   ├── test_password.py   # Password hashing and validation
│   ├── test_jwt.py        # JWT token operations
│   ├── test_validation.py # Input validation utilities
│   ├── test_user_service.py    # User CRUD operations
│   ├── test_auth_service.py    # Login/logout/token refresh
│   ├── test_role_service.py    # Role management
│   └── test_permission_service.py  # Permission checking
│
├── integration/           # Integration tests (multiple components)
│   ├── test_simple_rbac.py         # SimpleRBAC end-to-end flows
│   ├── test_fastapi_deps.py        # FastAPI dependency injection
│   └── test_authentication_flow.py # Complete auth workflows
│
└── fixtures/              # Test data and utilities
    └── sample_data.py     # Sample users, roles, permissions
```

---

## Running Tests

### Run Specific Test Files

```bash
# Run unit tests only
uv run pytest tests/unit/

# Run integration tests only
uv run pytest tests/integration/

# Run specific test file
uv run pytest tests/unit/test_user_service.py

# Run specific test function
uv run pytest tests/unit/test_user_service.py::test_create_user
```

### Run Tests by Pattern

```bash
# Run all tests matching "user"
uv run pytest -k "user"

# Run all tests matching "login"
uv run pytest -k "login"

# Run all tests NOT matching "slow"
uv run pytest -k "not slow"
```

### Run with Different Output Modes

```bash
# Verbose output (show all test names)
uv run pytest -v

# Very verbose (show print statements)
uv run pytest -vv

# Show print statements even for passing tests
uv run pytest -s

# Stop at first failure
uv run pytest -x

# Show local variables on failure
uv run pytest -l
```

### Coverage Reports

```bash
# Generate HTML coverage report
uv run pytest --cov=outlabs_auth --cov-report=html
# Open htmlcov/index.html in browser

# Terminal coverage report
uv run pytest --cov=outlabs_auth --cov-report=term

# Coverage with missing lines
uv run pytest --cov=outlabs_auth --cov-report=term-missing
```

---

## Test Coverage

### Phase 2 Test Coverage

**Unit Tests** (Isolated component testing):

| Component | File | Tests | Coverage |
|-----------|------|-------|----------|
| Password Utils | `test_password.py` | 8 tests | Hashing, verification, validation |
| JWT Utils | `test_jwt.py` | 10 tests | Token creation, verification, expiration |
| Validation | `test_validation.py` | 12 tests | Email, names, slugs, permissions |
| UserService | `test_user_service.py` | 15 tests | CRUD, search, status updates |
| AuthService | `test_auth_service.py` | 12 tests | Login, logout, token refresh, lockout |
| RoleService | `test_role_service.py` | 10 tests | Role CRUD, permission assignment |
| PermissionService | `test_permission_service.py` | 8 tests | Permission checking, wildcards |

**Integration Tests** (End-to-end workflows):

| Test Suite | File | Tests | Coverage |
|------------|------|-------|----------|
| SimpleRBAC | `test_simple_rbac.py` | 10 tests | Full auth workflows |
| FastAPI Deps | `test_fastapi_deps.py` | 8 tests | Dependency injection |
| Auth Flow | `test_authentication_flow.py` | 6 tests | Complete user journeys |

**Target**: 95%+ code coverage for Phase 2

---

## Writing Tests

### Test Naming Conventions

```python
# Good test names (descriptive and specific)
def test_create_user_with_valid_data_succeeds()
def test_login_with_invalid_password_raises_error()
def test_token_refresh_with_expired_token_fails()

# Bad test names (vague)
def test_user()
def test_login()
def test_token()
```

### Test Structure (AAA Pattern)

```python
async def test_create_user_with_valid_data(auth: SimpleRBAC):
    """Test that creating a user with valid data succeeds."""

    # Arrange - Set up test data
    user_data = {
        "email": "test@example.com",
        "password": "SecurePass123!",
        "first_name": "John",
        "last_name": "Doe"
    }

    # Act - Perform the action
    user = await auth.user_service.create_user(**user_data)

    # Assert - Verify the results
    assert user.email == "test@example.com"
    assert user.profile.first_name == "John"
    assert user.profile.last_name == "Doe"
    assert user.status == UserStatus.ACTIVE
```

### Using Fixtures

```python
async def test_login_with_existing_user(
    auth: SimpleRBAC,
    test_user: UserModel,
    test_password: str
):
    """Test login with an existing user."""

    # test_user fixture provides a pre-created user
    # test_password fixture provides the plain text password

    user, tokens = await auth.auth_service.login(
        email=test_user.email,
        password=test_password
    )

    assert user.id == test_user.id
    assert tokens.access_token is not None
```

### Testing Exceptions

```python
async def test_create_user_with_duplicate_email_raises_error(
    auth: SimpleRBAC,
    test_user: UserModel
):
    """Test that creating a user with duplicate email raises error."""

    with pytest.raises(UserAlreadyExistsError) as exc_info:
        await auth.user_service.create_user(
            email=test_user.email,  # Duplicate email
            password="NewPass123!",
            first_name="Jane",
            last_name="Smith"
        )

    assert "already exists" in str(exc_info.value.message).lower()
```

---

## Available Fixtures

### Database Fixtures

- **`mongo_client`**: Motor AsyncIOMotorClient instance
- **`test_db`**: Clean test database (auto-cleaned after each test)

### Auth Instance Fixtures

- **`auth`**: Initialized SimpleRBAC instance
- **`auth_config`**: Test AuthConfig instance

### Test Data Fixtures

- **`test_password`**: Standard test password (`"TestPass123!"`)
- **`test_user`**: Pre-created test user
- **`test_admin`**: Pre-created admin user (superuser)
- **`test_role`**: Pre-created role with permissions
- **`test_permissions`**: List of test permissions

### Usage Example

```python
async def test_with_fixtures(
    auth: SimpleRBAC,
    test_user: UserModel,
    test_role: RoleModel,
    test_password: str
):
    """Example test using multiple fixtures."""

    # Fixtures are automatically provided by pytest
    # No need to set them up manually

    # Test user already exists in database
    assert test_user.email == "test@example.com"

    # Test role already exists
    assert len(test_role.permissions) > 0

    # Can log in with test user
    user, tokens = await auth.auth_service.login(
        email=test_user.email,
        password=test_password
    )

    assert user.id == test_user.id
```

---

## Troubleshooting

### MongoDB Connection Issues

**Problem**: `ServerSelectionTimeoutError`

```bash
# Check if MongoDB is running
docker ps | grep mongo

# Start MongoDB
docker start mongo-test

# Or start new container
docker run -d -p 27017:27017 --name mongo-test mongo:latest
```

**Problem**: Test database not cleaning up

```python
# Ensure you're using test_db fixture
async def test_example(test_db):  # ✅ Good
    pass

async def test_example():  # ❌ Bad - no cleanup
    pass
```

### Test Isolation Issues

**Problem**: Tests pass individually but fail when run together

```bash
# Run tests in random order to catch isolation issues
uv run pytest --random-order

# Run specific test in isolation
uv run pytest tests/unit/test_user_service.py::test_create_user -v
```

**Solution**: Ensure each test uses `test_db` fixture for database cleanup.

### Slow Tests

```bash
# Show slowest 10 tests
uv run pytest --durations=10

# Mark slow tests
@pytest.mark.slow
async def test_expensive_operation():
    pass

# Skip slow tests
uv run pytest -m "not slow"
```

### Import Errors

**Problem**: `ModuleNotFoundError: No module named 'outlabs_auth'`

```bash
# Install package in editable mode
uv pip install -e .

# Or install with test dependencies
uv sync --extra test
```

---

## Test Best Practices

### DO ✅

- **Use descriptive test names** that explain what is being tested
- **Test one thing per test** (single assertion concept)
- **Use fixtures** for setup and teardown
- **Test both success and error cases**
- **Use AAA pattern** (Arrange, Act, Assert)
- **Clean up after tests** (use fixtures with cleanup)
- **Add docstrings** explaining test purpose
- **Test edge cases** (empty strings, None values, boundary conditions)

### DON'T ❌

- **Don't use production database** for tests
- **Don't depend on test execution order**
- **Don't use sleep()** (use proper async/await)
- **Don't hardcode values** that could change
- **Don't test implementation details** (test behavior)
- **Don't write tests without assertions**
- **Don't skip flaky tests** (fix them instead)

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      mongodb:
        image: mongo:latest
        ports:
          - 27017:27017

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install uv
          uv sync --extra test

      - name: Run tests with coverage
        run: |
          uv run pytest --cov=outlabs_auth --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
```

---

## Continuous Testing During Development

### Watch Mode (Auto-run tests on file changes)

```bash
# Install pytest-watch
uv pip install pytest-watch

# Run tests in watch mode
uv run ptw -- tests/

# Watch specific directory
uv run ptw -- tests/unit/
```

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: uv run pytest
        language: system
        pass_filenames: false
        always_run: true
```

---

## Need Help?

- **Documentation**: Check the main README.md and docs/
- **Issues**: Report bugs at https://github.com/outlabs/outlabsAuth/issues
- **Examples**: See `examples/` directory for usage examples

---

**Last Updated**: 2025-01-14
**Phase**: Phase 2 - SimpleRBAC Testing
**Coverage Target**: 95%+
