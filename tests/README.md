# Test Plan for outlabsAuth

This document outlines the comprehensive testing strategy for the outlabsAuth RBAC microservice. Our testing approach covers both internal service testing and API endpoint testing with various authentication and authorization scenarios.

## 🏆 Current Test Status

**Overall Progress: 92.3% (60/65 tests passing)** 🎉

### ✅ **Perfect Modules (100% Success)**

- **Authentication Routes**: 3/3 tests (100%) - Login, logout, /me endpoint
- **User Management Routes**: 14/14 tests (100%) - Complete CRUD operations ⭐
- **Role Management Routes**: 16/16 tests (100%) - Complete role lifecycle ⭐ **NEWLY COMPLETED!**
- **Permission Management Routes**: 10/10 tests (100%) - Permission CRUD operations ⭐ **NEWLY COMPLETED!**
- **Security Service**: 15/15 tests (100%) - Password hashing, JWT operations

### 🔧 **Modules In Progress**

- **Integration Tests**: 2/7 tests (28.6%) - Only 5 failures remaining (end-to-end workflows)

### 🎯 **Next Priority Areas**

1. **Integration Tests**: Fix remaining 307 redirects and missing configuration
2. **Client Account Routes**: Implementation and testing (future module)
3. **Performance Testing**: Load and stress testing (future enhancement)

## 🚀 Major Breakthrough: Complete Resolution of 307 Redirect and ObjectId Issues

**Problem**: Role and permission routes were suffering from the same 307 redirect and ObjectId serialization issues that initially affected user routes.

**Root Causes Identified & Solved**:

1. **✅ FIXED: Trailing Slash Redirects**

   - **Problem**: Routes like `/v1/roles` and `/v1/permissions` → 307 redirects to `/v1/roles/` and `/v1/permissions/`
   - **Solution**: Updated all test URLs to include trailing slashes
   - **Impact**: Fixed 13+ failing tests across role and permission modules

2. **✅ FIXED: Schema Alias Confusion**

   - **Problem**: Tests sending `{"id": "value"}` but schemas expecting `{"_id": "value"}` due to Pydantic aliases
   - **Root Cause**: Role and permission models use string IDs with `alias="_id"`
   - **Solution**: Updated test data to use `_id` field names consistently
   - **Impact**: Resolved 422 validation errors and KeyError exceptions

3. **✅ FIXED: Test Data Conflicts**

   - **Problem**: Tests failing with 409 conflicts due to reusing same test IDs across test runs
   - **Solution**: Implemented unique UUID-based test IDs (e.g., `test_role_a1b2c3d4`)
   - **Impact**: Eliminated false positive failures from data conflicts

4. **✅ FIXED: ObjectId Serialization in API Routes**
   - **Problem**: Role and permission routes returning model objects directly causing serialization issues
   - **Solution**: Added manual field mapping in route handlers similar to user routes:
     ```python
     role_dict = role.model_dump(by_alias=True)
     role_dict["id"] = role_dict.pop("_id", role_dict.get("id"))
     return role_dict
     ```
   - **Impact**: Consistent JSON responses across all modules

**Success Rate Journey**:

- **Initial**: 58.5% (38/65 tests)
- **After User Routes Fix**: 58.5% (same)
- **After Role & Permission Fix**: **92.3% (60/65 tests)** 🎉

---

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

### 1. ✅ Authentication Testing (`test_auth_routes.py`) - **COMPLETED (3/3)**

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

### 2. ✅ User Management Testing (`test_user_routes.py`) - **COMPLETED (14/14)**

#### ✅ **RESOLVED: 307 Trailing Slash Redirect Issue**

**Status**: 14/14 tests passing (100%) ✅

**Root Cause Identified & Fixed**: FastAPI automatic trailing slash redirects + Pydantic v2 ObjectId serialization issues

**Solutions Implemented**:

1. **✅ FIXED: Trailing Slash Redirects**
   - Updated test URLs from `/v1/users` → `/v1/users/`
2. **✅ FIXED: Pydantic v2 ObjectId Serialization**
   - Added manual ObjectId → string conversion in all user route handlers
3. **✅ FIXED: UserCreateSchema ObjectId Issue**
   - Changed `client_account_id: Optional[PyObjectId]` → `Optional[str]`

#### ✅ **COMPLETED: User CRUD Test Coverage (14/14)**

**User Creation Tests (4/4)**:

- ✅ Create user with valid data
- ✅ Create user with duplicate email (409 conflict)
- ✅ Create user with invalid email format (422 validation)
- ✅ Create user without permissions (401/307 unauthorized)

**User Retrieval Tests (4/4)**:

- ✅ Get all users with admin token
- ✅ Get users with pagination parameters
- ✅ Get user by valid ID
- ✅ Get user by invalid ID format (422)
- ✅ Get non-existent user (404)

**User Update Tests (2/2)**:

- ✅ Update user information successfully
- ✅ Update non-existent user (404)

**Bulk Operations Tests (2/2)**:

- ✅ Bulk create multiple users
- ✅ Bulk create with duplicates handling

**Security Tests (2/2)**:

- ✅ Unauthorized access protection
- ✅ Authentication token validation

### 3. ✅ Role Management Testing (`test_role_routes.py`) - **COMPLETED (16/16)** 🎉

**Status**: 16/16 tests passing (100%) ✅ **NEWLY COMPLETED!**

**Issues Resolved**:

1. **✅ FIXED: 307 Redirect Issues** - Added trailing slashes to all test URLs
2. **✅ FIXED: Schema Alias Issues** - Updated test data to use `_id` instead of `id`
3. **✅ FIXED: Test Data Conflicts** - Implemented unique UUID-based test IDs
4. **✅ FIXED: ObjectId Serialization** - Added manual field mapping in route responses

#### ✅ **COMPLETED: Role CRUD Test Coverage (16/16)**

**Role Creation Tests (4/4)**:

- ✅ Create role with valid permissions
- ✅ Create role with duplicate ID (409 conflict)
- ✅ Create role with invalid permissions (400 validation)
- ✅ Create role without proper permissions (401 unauthorized)

**Role Retrieval Tests (4/4)**:

- ✅ Get all roles with admin token
- ✅ Get roles with pagination parameters
- ✅ Get role by valid ID
- ✅ Get non-existent role (404)

**Role Update Tests (2/2)**:

- ✅ Update role information successfully
- ✅ Update non-existent role (404)

**Role Deletion Tests (2/2)**:

- ✅ Delete custom role successfully
- ✅ Delete non-existent role (404)

**Role Business Logic Tests (4/4)**:

- ✅ System role deletion handling
- ✅ Permission validation during role creation
- ✅ Role assignability flag functionality
- ✅ Unauthorized access protection

### 4. ✅ Permission Management Testing (`test_permission_routes.py`) - **COMPLETED (10/10)** 🎉

**Status**: 10/10 tests passing (100%) ✅ **NEWLY COMPLETED!**

**Issues Resolved**:

1. **✅ FIXED: 307 Redirect Issues** - Added trailing slashes to all test URLs
2. **✅ FIXED: Missing Route** - Added `get_permission_by_id` route implementation
3. **✅ FIXED: Schema Alias Issues** - Updated test data to use `_id` instead of `id`
4. **✅ FIXED: Test Data Conflicts** - Implemented unique UUID-based test IDs
5. **✅ FIXED: ObjectId Serialization** - Added manual field mapping in route responses

#### ✅ **COMPLETED: Permission CRUD Test Coverage (10/10)**

**Permission Creation Tests (4/4)**:

- ✅ Create permission with valid format
- ✅ Create permission with duplicate ID (409 conflict)
- ✅ Create permission with invalid format (validation test)
- ✅ Create permission without proper permissions (401 unauthorized)

**Permission Retrieval Tests (4/4)**:

- ✅ Get all permissions with admin token
- ✅ Get permissions with pagination parameters
- ✅ Get permission by valid ID
- ✅ Get non-existent permission (404)

**Permission Validation Tests (2/2)**:

- ✅ Permission naming convention validation
- ✅ Unauthorized access protection

### 5. ✅ Security Service Testing (`test_security_service.py`) - **COMPLETED (15/15)**

**All security functions working perfectly**:

- ✅ Password hashing and verification (bcrypt)
- ✅ JWT token generation and validation
- ✅ Token expiration handling
- ✅ Invalid token detection
- ✅ Security utility functions

### 6. 🔧 Integration Testing (`test_integration.py`) - **28.6% (2/7)**

**Current Status**: Most failures are 307 redirects and one configuration issue

#### ✅ Working Integration Tests (2/7)

- ✅ Authentication and authorization flow
- ✅ Session management workflow

#### 🔄 Integration Tests In Progress (5/7)

- [ ] **Complete User Lifecycle** - 307 redirect in user creation
- [ ] **Role and Permission Workflow** - 307 redirects in permission/role creation
- [ ] **Password Reset Workflow** - Missing `PASSWORD_RESET_TOKEN_EXPIRE_MINUTES` config
- [ ] **Bulk Operations Workflow** - 307 redirect in bulk operations
- [ ] **Error Handling and Recovery** - 307 redirect in error scenarios

**Identified Issues to Fix**:

1. **307 Redirects**: Integration tests need trailing slash updates (same pattern as other modules)
2. **Missing Config**: Need to add `PASSWORD_RESET_TOKEN_EXPIRE_MINUTES` to settings
3. **Field Names**: Update integration tests to use `_id` instead of `id` for consistency

### 7. Authorization Testing (`test_authorization.py` - Future)

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

### 8. Security Testing (`test_security.py` - Future)

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

### 9. Performance Testing (`test_performance.py` - Future)

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
- **test*role*[uuid]**: Custom role for testing (with unique IDs)

### Test Permissions

- Standard CRUD permissions (seeded)
- **test:permission:[uuid]**: Custom test permissions (with unique IDs)
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
pytest tests/test_role_routes.py -v
pytest tests/test_permission_routes.py -v

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

## Lessons Learned & Best Practices

### Key Debugging Insights

1. **Always Check FastAPI Trailing Slash Behavior**: 307 redirects are often caused by missing trailing slashes
2. **Pydantic v2 Alias Handling**: Be careful with field aliases - test data must match schema expectations
3. **Use Unique Test Data**: Implement UUID-based test identifiers to avoid conflicts between test runs
4. **Manual ObjectId Serialization**: Convert ObjectId fields manually in route responses for consistent JSON output
5. **Debug with Response Content**: Always print response content when debugging 422/400 errors

### Testing Patterns That Work

1. **Consistent URL Patterns**: Always use trailing slashes in test URLs
2. **UUID-Based Test Data**: Generate unique identifiers for test entities
3. **Field Name Consistency**: Use `_id` for string-based document IDs consistently
4. **Comprehensive Error Testing**: Test both success and failure scenarios
5. **Gradual Module Completion**: Fix one module completely before moving to the next

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
6. Use unique UUIDs for test data to avoid conflicts

### Test Naming Convention

- `test_<functionality>_<scenario>`: e.g., `test_login_with_invalid_password`
- Use descriptive names that explain the test purpose
- Group related tests in classes: `TestUserAuthentication`

### Test Data Guidelines

- Use realistic but obviously fake data
- Generate unique identifiers with UUID for test entities
- Clean up test data appropriately
- Use fixtures for common test data

---

**Total Test Coverage Goal**: 95%+ line coverage, 100% critical path coverage

**Current Achievement**: **92.3% (60/65 tests passing)** 🎉

**Priority**: Complete integration tests (5 remaining failures), then expand to client account and performance testing.

**Next Milestone**: Achieve 95%+ success rate by fixing integration test 307 redirects and configuration issues.
