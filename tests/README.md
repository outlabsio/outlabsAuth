# Test Plan for outlabsAuth

This document outlines the comprehensive testing strategy for the outlabsAuth RBAC microservice. Our testing approach covers both internal service testing and API endpoint testing with various authentication and authorization scenarios.

## Test Architecture

### Test Organization

- **Unit Tests**: Individual service/component testing
- **Integration Tests**: Cross-component workflow testing
- **API Tests**: End-to-end HTTP endpoint testing
- **Security Tests**: Authentication, authorization, and security validation
- **Performance Tests**: Load and stress testing (future)

### Test Orchestrator

Use `python tests/test_orchestrator.py` to run all tests with comprehensive reporting:

- Individual module execution with timing
- Success/failure statistics
- JSON report generation
- Parallel execution support

## Testing Categories

### 1. Authentication Testing (`test_auth_routes.py`)

#### ✅ Completed

- [x] Basic login with valid credentials
- [x] Login failure with invalid credentials
- [x] `/me` endpoint authentication

#### 🔄 Planned Authentication Tests

- [ ] **Password Validation**
  - [ ] Login with empty password
  - [ ] Login with password too short
  - [ ] Login with password too long (>128 chars)
  - [ ] Login with special characters in password
  - [ ] Login with Unicode/emoji passwords
- [ ] **Email Validation**
  - [ ] Login with invalid email formats
  - [ ] Login with non-existent email
  - [ ] Login with email case sensitivity tests
- [ ] **Rate Limiting & Security**
  - [ ] Multiple failed login attempts (account lockout)
  - [ ] Account unlock after lockout period
  - [ ] Brute force protection testing
  - [ ] IP-based rate limiting
- [ ] **Session Management**
  - [ ] Token expiration handling
  - [ ] Refresh token rotation
  - [ ] Session revocation (logout)
  - [ ] Multiple device login
  - [ ] Concurrent session limits
- [ ] **Password Reset Workflow**
  - [ ] Request reset with valid email
  - [ ] Request reset with invalid email
  - [ ] Reset with valid token
  - [ ] Reset with expired token
  - [ ] Reset with used token
  - [ ] Reset with invalid token format
  - [ ] Password complexity validation during reset
- [ ] **Password Change**
  - [ ] Change with correct current password
  - [ ] Change with incorrect current password
  - [ ] Password complexity validation
  - [ ] Session invalidation after password change

### 2. User Management Testing (`test_user_routes.py`)

#### 🔄 Planned User CRUD Tests

- [ ] **User Creation**
  - [ ] Create user with valid data
  - [ ] Create user with duplicate email
  - [ ] Create user with invalid email format
  - [ ] Create user with missing required fields
  - [ ] Create user with invalid role assignments
  - [ ] Create user without proper permissions
  - [ ] Bulk user creation (success/partial failure scenarios)
- [ ] **User Retrieval**
  - [ ] Get all users (admin perspective)
  - [ ] Get users with pagination
  - [ ] Get user by valid ID
  - [ ] Get user by invalid ID format
  - [ ] Get non-existent user
  - [ ] Get users filtered by role
  - [ ] Get users filtered by status
  - [ ] Search users by email/name
- [ ] **User Updates**
  - [ ] Update user profile information
  - [ ] Update user roles (with permission)
  - [ ] Update user roles (without permission)
  - [ ] Update user status (activate/deactivate)
  - [ ] Update non-existent user
  - [ ] Partial updates vs full updates
- [ ] **User Deletion** (if implemented)
  - [ ] Delete user with proper permissions
  - [ ] Delete user without permissions
  - [ ] Delete non-existent user
  - [ ] Delete user with active sessions

### 3. Role Management Testing (`test_role_routes.py`)

#### 🔄 Planned Role Tests

- [ ] **Role Creation**
  - [ ] Create role with valid permissions
  - [ ] Create role with invalid permissions
  - [ ] Create role with duplicate ID
  - [ ] Create role without required fields
  - [ ] Create role without proper permissions
- [ ] **Role Retrieval**
  - [ ] Get all roles
  - [ ] Get role by ID
  - [ ] Get non-existent role
  - [ ] Get roles with pagination
- [ ] **Role Updates**
  - [ ] Update role permissions
  - [ ] Update role metadata
  - [ ] Update non-existent role
  - [ ] Update system roles (should fail)
- [ ] **Role Deletion**
  - [ ] Delete custom role
  - [ ] Delete system role (should fail)
  - [ ] Delete role assigned to users
  - [ ] Delete non-existent role
- [ ] **Role Assignment Rules**
  - [ ] Validate `is_assignable_by_main_client` flag
  - [ ] Test role hierarchy constraints
  - [ ] Test permission inheritance

### 4. Permission Management Testing (`test_permission_routes.py`)

#### 🔄 Planned Permission Tests

- [ ] **Permission Creation**
  - [ ] Create permission with valid format
  - [ ] Create permission with invalid ID format
  - [ ] Create duplicate permission
  - [ ] Permission naming convention validation
- [ ] **Permission Retrieval**
  - [ ] Get all permissions
  - [ ] Get permission by ID
  - [ ] Get permissions with pagination
  - [ ] Filter permissions by service/resource
- [ ] **Permission Validation**
  - [ ] Validate service:resource:action format
  - [ ] Test permission dependencies
  - [ ] Test permission conflicts

### 5. Authorization Testing (`test_authorization.py` - New)

#### 🔄 Planned Authorization Tests

- [ ] **Role-Based Access Control**
  - [ ] User with admin role accessing admin endpoints
  - [ ] User with basic role accessing admin endpoints (should fail)
  - [ ] User accessing endpoints matching their permissions
  - [ ] User accessing endpoints without required permissions
- [ ] **Client Account Isolation**
  - [ ] Users seeing only their client account data
  - [ ] Main client users managing sub-users
  - [ ] Cross-client account access prevention
- [ ] **Permission Hierarchies**
  - [ ] Test permission inheritance
  - [ ] Test permission conflicts resolution
  - [ ] Test role combination scenarios
- [ ] **Edge Cases**
  - [ ] User with no roles
  - [ ] User with deactivated roles
  - [ ] Role with no permissions
  - [ ] Permission changes affecting active sessions

### 6. Security Testing (`test_security.py` - New)

#### 🔄 Planned Security Tests

- [ ] **Input Validation**
  - [ ] SQL injection attempts in all inputs
  - [ ] XSS payload injection
  - [ ] Path traversal attempts
  - [ ] Large payload handling
  - [ ] Malformed JSON handling
- [ ] **Authentication Security**
  - [ ] JWT token tampering
  - [ ] Token replay attacks
  - [ ] Token injection attempts
  - [ ] Weak password validation
  - [ ] Password hash security
- [ ] **Authorization Security**
  - [ ] Privilege escalation attempts
  - [ ] Role manipulation attempts
  - [ ] Permission bypass attempts
  - [ ] Client account isolation breaches
- [ ] **Data Protection**
  - [ ] Sensitive data exposure in responses
  - [ ] Password hash exposure prevention
  - [ ] Audit log integrity
  - [ ] Personal data handling compliance

### 7. Integration Testing (`test_integration.py`)

#### ✅ Partially Completed

- [x] Basic user lifecycle workflow
- [x] Authentication flow
- [x] Role and permission workflow

#### 🔄 Planned Integration Tests

- [ ] **Complete Workflows**
  - [ ] User registration → email verification → first login
  - [ ] Password reset → login with new password
  - [ ] Role assignment → permission verification → access test
  - [ ] Client account creation → user assignment → isolation test
- [ ] **Multi-User Scenarios**
  - [ ] Concurrent user operations
  - [ ] Role changes affecting multiple users
  - [ ] Bulk operations with mixed success/failure
- [ ] **System State Tests**
  - [ ] Database consistency after complex operations
  - [ ] Cache invalidation scenarios
  - [ ] Session cleanup and management

### 8. Performance Testing (`test_performance.py` - Future)

#### 🔄 Planned Performance Tests

- [ ] **Load Testing**
  - [ ] Concurrent login requests
  - [ ] High-volume user creation
  - [ ] Token validation performance
  - [ ] Database query optimization
- [ ] **Stress Testing**
  - [ ] Memory usage under load
  - [ ] Database connection pooling
  - [ ] Rate limiting effectiveness
  - [ ] Error handling under stress

## Test Data Management

### Test Users

- **admin@test.com**: Platform administrator (seeded)
- **testuser@example.com**: Basic test user
- **mainuser@client1.com**: Main client user
- **subuser@client1.com**: Sub-user under client1
- **user@client2.com**: User from different client account

### Test Roles

- **platform_admin**: Full system access (seeded)
- **client_admin**: Client account management
- **basic_user**: Limited read access
- **test_role**: Custom role for testing

### Test Permissions

- Standard CRUD permissions (seeded)
- Custom test permissions
- Invalid/malformed permissions for negative testing

## Test Environment Setup

### Prerequisites

1. MongoDB running locally or test database configured
2. Test database seeded with initial data
3. Environment variables set for testing

### Running Tests

```bash
# Run all tests with orchestrator
python tests/test_orchestrator.py

# Run specific test modules
pytest tests/test_auth_routes.py -v
pytest tests/test_user_routes.py -v

# Run with coverage
pytest --cov=api tests/

# Run security tests only
pytest tests/test_security.py -v
```

## Test Reporting

### Automated Reports

- JSON test reports (`test_report.json`)
- Coverage reports
- Performance metrics
- Security scan results

### Manual Testing Checklist

- [ ] UI/UX flows (if frontend exists)
- [ ] Cross-browser compatibility
- [ ] Mobile responsiveness
- [ ] Accessibility compliance

## Future Enhancements

### Test Infrastructure

- [ ] Continuous Integration setup
- [ ] Automated security scanning
- [ ] Performance regression testing
- [ ] Test data factories
- [ ] Mock external services

### Advanced Testing

- [ ] Property-based testing with Hypothesis
- [ ] Contract testing with API consumers
- [ ] Chaos engineering tests
- [ ] Multi-environment testing

## Contributing to Tests

### Adding New Tests

1. Follow the existing test structure
2. Include both positive and negative test cases
3. Add comprehensive docstrings
4. Update this README with new test categories
5. Ensure tests are isolated and idempotent

### Test Naming Convention

- `test_<functionality>_<scenario>`: e.g., `test_login_with_invalid_password`
- Use descriptive names that explain the test purpose
- Group related tests in classes: `TestUserAuthentication`

### Test Data Guidelines

- Use realistic but obviously fake data
- Avoid hardcoded values where possible
- Clean up test data appropriately
- Use fixtures for common test data

---

**Total Test Coverage Goal**: 90%+ line coverage, 100% critical path coverage

**Priority**: Security and authentication tests are highest priority, followed by core CRUD operations, then edge cases and performance tests.
