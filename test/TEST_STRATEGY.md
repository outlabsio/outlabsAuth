# OutlabsAuth Comprehensive Test Strategy

## Executive Summary

This document outlines the comprehensive testing strategy for OutlabsAuth, a FastAPI-based authentication and authorization service. Our testing approach focuses on **API-level testing** to ensure the system behaves correctly from the perspective of consuming applications. All tests interact with the system through HTTP endpoints, validating real-world usage patterns.

## Table of Contents

1. [Testing Philosophy](#testing-philosophy)
2. [Test Suite Architecture](#test-suite-architecture)
3. [Test Categories](#test-categories)
4. [Test Data Management](#test-data-management)
5. [Permission Testing Methodology](#permission-testing-methodology)
6. [Platform Scenarios](#platform-scenarios)
7. [Test Execution Guidelines](#test-execution-guidelines)
8. [Success Metrics](#success-metrics)

## Testing Philosophy

### Why API Testing?

- **Real-world validation**: Tests exercise the same endpoints that client applications use
- **Contract verification**: Ensures API contracts remain stable
- **Integration coverage**: Validates the full stack from routes to database
- **Security validation**: Tests authentication and authorization as implemented
- **Performance insights**: Measures actual response times

### Core Principles

1. **Isolation**: Each test suite creates its own test data
2. **Repeatability**: Tests can run multiple times with same results
3. **Independence**: Tests don't depend on execution order
4. **Clarity**: Test names clearly describe what's being tested
5. **Completeness**: Every API endpoint and permission scope is tested

## Test Suite Architecture

### Directory Structure

```
test/
├── README.md                    # Quick start guide
├── TEST_STRATEGY.md            # This document
├── auth_tokens.json            # Cached authentication tokens (git-ignored)
│
├── Infrastructure/
│   ├── auth_utils.py           # Authentication management
│   ├── base_test.py            # Base test class and assertions
│   ├── test_data_factory.py    # Test data creation utilities
│   ├── permission_helpers.py   # Permission testing utilities
│   └── context_utils.py        # Entity context management
│
├── Core Tests/
│   ├── test_authentication.py  # Auth endpoints
│   ├── test_user_management.py # User CRUD operations
│   ├── test_entity_hierarchy.py # Entity structure tests
│   ├── test_roles_permissions.py # Role and permission tests
│   └── test_memberships.py     # Entity membership tests
│
├── Advanced Tests/
│   ├── test_permission_enforcement.py # Permission validation
│   ├── test_platform_isolation.py    # Multi-tenant isolation
│   └── test_entity_access.py         # Access control tests
│
├── Scenario Tests/
│   ├── test_complex_scenarios.py     # Real-world use cases
│   ├── test_diverse_platform.py      # Complex hierarchy
│   ├── test_uaya_platform.py         # Flat structure
│   └── test_qdarte_platform.py       # Multi-sided marketplace
│
└── run_all_tests.py            # Test orchestrator
```

### Test Infrastructure Components

#### 1. Test Data Factory

```python
class TestDataFactory:
    """Creates consistent test data for all test suites"""
    
    async def create_test_platform(self, name: str) -> Dict:
        """Creates an isolated platform for testing"""
        
    async def create_entity_hierarchy(self, platform_id: str, depth: int) -> List[Dict]:
        """Creates a multi-level entity structure"""
        
    async def create_user_with_role(self, entity_id: str, role_name: str) -> Dict:
        """Creates a user with specific role in entity"""
        
    async def cleanup_test_data(self, platform_id: str):
        """Removes all test data for a platform"""
```

#### 2. Permission Test Helpers

```python
class PermissionTestHelper:
    """Utilities for testing permissions"""
    
    def assert_has_permission(self, user_token: str, endpoint: str, method: str):
        """Verifies user can access endpoint"""
        
    def assert_no_permission(self, user_token: str, endpoint: str, method: str):
        """Verifies user cannot access endpoint"""
        
    def test_permission_inheritance(self, user_token: str, permission: str, entity_hierarchy: List):
        """Tests permission inheritance through entity hierarchy"""
```

## Test Categories

### 1. User Management Tests

**Purpose**: Validate all user-related operations

**Key Test Cases**:
- User registration with email verification
- User profile management (self vs admin)
- Password operations (change, reset, forgot)
- User search and filtering
- User deactivation and reactivation
- Cross-platform user access

**Example Test**:
```python
def test_user_cannot_edit_others_profile():
    # User A creates account
    user_a = factory.create_user("user_a@test.com")
    
    # User B creates account  
    user_b = factory.create_user("user_b@test.com")
    
    # User A tries to edit User B's profile
    response = api.put(f"/users/{user_b.id}", 
                      headers=user_a.headers,
                      json={"first_name": "Hacked"})
    
    assert response.status_code == 403
```

### 2. Entity Hierarchy Tests

**Purpose**: Validate entity structure rules and relationships

**Key Test Cases**:
- Structural entities can contain structural or access groups
- Access groups can only contain other access groups
- Parent-child relationship integrity
- Entity status transitions
- Circular hierarchy prevention
- Entity metadata management

**Example Test**:
```python
def test_access_group_cannot_contain_structural():
    # Create access group
    access_group = factory.create_entity(
        entity_class="ACCESS_GROUP",
        entity_type="admin_group"
    )
    
    # Try to create structural entity as child
    response = api.post("/entities",
                       json={
                           "entity_class": "STRUCTURAL",
                           "entity_type": "team",
                           "parent_entity_id": access_group.id
                       })
    
    assert response.status_code == 400
    assert "Access groups cannot contain structural entities" in response.json()["detail"]
```

### 3. Role and Permission Tests

**Purpose**: Validate role management and permission system

**Key Test Cases**:
- System permissions are immutable
- Custom permissions per platform
- Role assignment constraints
- Permission inheritance (action and scope)
- Role validity periods
- Cross-entity role restrictions

**Permission Scope Hierarchy**:
```
manage_all
    ├── manage_platform
    │   ├── manage_organization  
    │   │   └── manage
    │   └── manage
    └── manage
```

**Example Test**:
```python
def test_permission_scope_inheritance():
    # User with user:manage_organization
    org_admin = factory.create_user_with_permission("user:manage_organization")
    
    # Can manage users in child entities
    team = factory.create_child_entity(organization)
    response = api.post(f"/entities/{team.id}/members",
                       headers=org_admin.headers,
                       json={"user_id": new_user.id})
    
    assert response.status_code == 200
    
    # Cannot manage users in sibling organization
    sibling_org = factory.create_entity(parent=platform)
    response = api.post(f"/entities/{sibling_org.id}/members",
                       headers=org_admin.headers,
                       json={"user_id": new_user.id})
    
    assert response.status_code == 403
```

### 4. Membership Tests

**Purpose**: Validate user-entity relationships

**Key Test Cases**:
- Add/remove members with proper permissions
- Multiple role assignments
- Membership validity periods
- Last admin protection
- Membership status transitions
- Bulk operations

**Example Test**:
```python
def test_cannot_remove_last_admin():
    # Create entity with one admin
    entity = factory.create_entity()
    admin = factory.create_user_with_role(entity, "admin")
    
    # Try to remove the admin
    response = api.delete(f"/entities/{entity.id}/members/{admin.id}",
                         headers=admin.headers)
    
    assert response.status_code == 400
    assert "Cannot remove the last admin" in response.json()["detail"]
```

### 5. Permission Enforcement Tests

**Purpose**: Validate permission checks on all endpoints

**Key Test Cases**:
- Every endpoint requires appropriate permissions
- Entity context affects permissions
- Hierarchical permission checks
- Cross-entity access denial
- Permission delegation

**Test Matrix Example**:
| Endpoint | Method | Required Permission | Entity Context |
|----------|--------|-------------------|----------------|
| /entities | POST | entity:create | Parent entity |
| /entities/{id} | PUT | entity:manage | Target entity |
| /entities/{id}/members | POST | member:manage | Target entity |
| /users | GET | user:read | Platform/Org |

### 6. Platform Isolation Tests

**Purpose**: Ensure complete data isolation between platforms

**Key Test Cases**:
- Users in Platform A cannot see Platform B data
- Platform admins only see their platform
- No data leakage in search/filter operations
- Cross-platform user scenarios

**Example Test**:
```python
def test_platform_isolation():
    # Create two platforms
    platform_a = factory.create_platform("platform_a")
    platform_b = factory.create_platform("platform_b")
    
    # Create admin in platform A
    admin_a = factory.create_platform_admin(platform_a)
    
    # Admin A queries all entities
    response = api.get("/entities", headers=admin_a.headers)
    
    # Should not see any platform B entities
    entity_ids = [e["id"] for e in response.json()["items"]]
    platform_b_entities = factory.get_platform_entities(platform_b)
    
    for entity in platform_b_entities:
        assert entity.id not in entity_ids
```

## Test Data Management

### Test Data Lifecycle

1. **Setup Phase**
   - Create isolated test platform
   - Build required entity hierarchy
   - Create test users and roles
   - Establish permissions

2. **Execution Phase**
   - Run test scenarios
   - Validate responses
   - Check side effects

3. **Teardown Phase**
   - Remove test entities
   - Clean up test users
   - Reset sequences

### Test Data Principles

- **Unique Identifiers**: Use UUIDs or timestamps in test data names
- **Isolation**: Each test suite uses its own platform
- **Predictability**: Test data factory ensures consistent structure
- **Cleanup**: Always remove test data after completion

## Permission Testing Methodology

### Permission Test Patterns

1. **Positive Testing**: Verify allowed actions succeed
2. **Negative Testing**: Verify forbidden actions fail
3. **Boundary Testing**: Test permission scope limits
4. **Inheritance Testing**: Validate hierarchical permissions

### Permission Test Matrix

For each permission scope, test:

```
Resource: user
Actions: read, update, manage
Scopes: self, entity, organization, platform, all

Test Cases:
- user:read + self scope = Can read own profile
- user:read + entity scope = Can read users in same entity
- user:manage + organization scope = Can manage all users in org hierarchy
- user:manage_all = Can manage users across platforms
```

### Entity Context Testing

Test how X-Entity-Context-Id header affects permissions:

```python
def test_entity_context_permissions():
    # User has role in Team A
    user = factory.create_user_with_role(team_a, "manager")
    
    # With Team A context - succeeds
    response = api.get("/users",
                      headers={**user.headers, "X-Entity-Context-Id": team_a.id})
    assert response.status_code == 200
    
    # With Team B context - fails
    response = api.get("/users", 
                      headers={**user.headers, "X-Entity-Context-Id": team_b.id})
    assert response.status_code == 403
```

## Platform Scenarios

### 1. Diverse Platform (Complex Hierarchy)

**Structure**:
```
Diverse (Platform)
├── National Brokerage (Organization)
│   ├── Florida Division (Branch)
│   │   ├── Miami Team (Team)
│   │   └── Orlando Team (Team)
│   └── Texas Division (Branch)
│       └── Houston Team (Team)
└── Regional Brokerage (Organization)
```

**Test Focus**:
- Deep permission inheritance
- Cross-branch isolation
- Hierarchical role assignments

### 2. uaya Platform (Flat Structure)

**Structure**:
```
uaya (Platform)
├── Platform Admins (Access Group)
├── Professional Interpreters (Access Group)
└── General Users (Implicit)
```

**Test Focus**:
- Simple role-based access
- No hierarchical complexity
- Group-based permissions

### 3. qdarte Platform (Multi-Sided)

**Structure**:
```
qdarte (Platform)
├── Client Portal (Organization)
│   └── Premium Clients (Access Group)
└── Creator Portal (Organization)
    └── Verified Creators (Access Group)
```

**Test Focus**:
- Separate user spaces
- Cross-portal isolation
- Portal-specific roles

### 4. Referral Brokerage (Hybrid)

**Structure**:
```
Referral Platform (Platform)
├── Corporate (Organization)
├── Team Alpha (Team)
├── Team Beta (Team)
└── Independent Agents (Direct members)
```

**Test Focus**:
- Optional team membership
- Direct platform members
- Mixed hierarchy

## Test Execution Guidelines

### Running Tests

1. **All Tests**:
   ```bash
   python run_all_tests.py
   ```

2. **Specific Category**:
   ```bash
   python run_all_tests.py --test user_management
   ```

3. **With Fresh Auth**:
   ```bash
   python run_all_tests.py --clear-cache
   ```

### Test Environment Requirements

- FastAPI server running on http://localhost:8030
- MongoDB accessible
- Test user accounts created
- Email service (or mock) configured

### Continuous Integration

```yaml
test:
  script:
    - docker-compose up -d
    - sleep 10  # Wait for services
    - cd test
    - python run_all_tests.py --clear-cache
    - docker-compose down -v
```

## Success Metrics

### Coverage Goals

- **Endpoint Coverage**: 100% of API endpoints tested
- **Permission Coverage**: Every permission scope validated
- **Error Coverage**: All error responses tested
- **Business Logic**: Key workflows validated

### Performance Benchmarks

- Authentication: < 200ms
- Entity queries: < 100ms  
- Permission checks: < 50ms
- Bulk operations: < 5s for 100 items

### Security Validation

- No unauthorized data access
- Proper error messages (no data leakage)
- Rate limiting enforced
- Token expiration respected

## Troubleshooting

### Common Issues

1. **Authentication Failures**
   - Clear token cache: `--clear-cache`
   - Check user credentials
   - Verify server is running

2. **Permission Errors**
   - Verify test data setup
   - Check entity relationships
   - Validate role assignments

3. **Isolation Failures**
   - Ensure unique platform names
   - Clean up old test data
   - Check for hardcoded IDs

### Debug Mode

Enable verbose logging:
```python
TEST_DEBUG=true python run_all_tests.py
```

## Next Steps

1. Implement test infrastructure components
2. Create core test suites
3. Add scenario-based tests
4. Set up CI/CD integration
5. Create performance benchmarks
6. Add security scanning

---

This test strategy ensures OutlabsAuth meets all functional requirements while maintaining security and performance standards. Regular execution of these tests provides confidence in system reliability and correctness.