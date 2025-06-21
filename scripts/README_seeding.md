# Database Seeding Guide

This guide explains how to set up realistic test data for the outlabsAuth system using a hierarchical seeding approach that mirrors real-world usage patterns.

## Overview

The seeding system uses a **hierarchical approach** that reflects real-world scenarios:

1. **Platform Admin** creates client accounts
2. **Client Admins** create their own users and groups
3. **Different companies** have isolated data
4. **Role hierarchies** are properly established

This approach is perfect for testing access control, data scoping, and permission enforcement.

## Available Scripts

### 1. `seed_main.py` - Foundation Data

**Purpose**: Sets up essential system data in the main database

- Creates permissions, roles, and a platform admin user
- Creates some basic client accounts and users
- Uses direct database/service calls (not API requests)

**Usage**:

```bash
python scripts/seed_main.py
```

**Creates**:

- Platform admin: `admin@test.com` / `admin123`
- Essential permissions and roles
- Sample client accounts (ACME, Tech Startup)
- Basic users for testing

### 2. `seed.py` - Test Database Setup

**Purpose**: Sets up test data in the test database

- Similar to `seed_main.py` but for testing
- Uses test database instead of main database

**Usage**:

```bash
python scripts/seed.py
```

### 3. `seed_via_api.py` - Realistic API-Based Seeding ⭐

**Purpose**: Creates realistic test data through HTTP API calls

- **Platform admin** creates client accounts via API
- **Client admins** create their teams via API
- **Simulates real user behavior** and tests API endpoints
- **Perfect for access control testing**

**Prerequisites**:

- API server must be running: `uvicorn api.main:app --reload`
- Foundation data must exist: `python scripts/seed_main.py`

**Usage**:

```bash
# 1. Start the API server
uvicorn api.main:app --reload

# 2. In another terminal, run the API seeding
python scripts/seed_via_api.py
```

**Creates**:

- **3 Companies**: GreenTech Industries, MedCorp Healthcare, RetailPlus
- **12+ Users**: Client admins, managers, employees for each company
- **Groups**: Engineering teams, management teams, operational groups
- **Realistic data isolation** for testing cross-company access control

### 4. `test_data_helper.py` - Test Utilities

**Purpose**: Provides easy access to test user credentials

- Simple API to get users by company and role
- Helper functions for common test scenarios
- Credential management for tests

**Usage**:

```python
from test_data_helper import TestDataHelper

# Get specific users
admin = TestDataHelper.get_platform_admin()
greentech_admin = TestDataHelper.get_client_admin("greentech")
employee = TestDataHelper.get_employee("medcorp", 0)

# Get test scenarios
admin, employee = get_cross_company_scenario()
admin, manager, employee = get_hierarchy_scenario("greentech")
```

## Recommended Seeding Workflow

### For Development

```bash
# 1. Seed foundation data
python scripts/seed_main.py

# 2. Start API server
uvicorn api.main:app --reload

# 3. Add realistic test data
python scripts/seed_via_api.py
```

### For Testing

```bash
# 1. Seed test database
python scripts/seed.py

# 2. Start API server (if testing API endpoints)
uvicorn api.main:app --reload

# 3. Add realistic API test data
python scripts/seed_via_api.py

# 4. Run access control tests
pytest tests/test_enhanced_access_control.py -v
```

## Test User Credentials

After running `seed_via_api.py`, you'll have these users available:

### Platform Admin

- **Email**: `admin@test.com`
- **Password**: `admin123`
- **Role**: Platform administrator with full system access

### GreenTech Industries

- **Admin**: `admin@greentech.com` / `greentech123`
- **Manager**: `manager@greentech.com` / `green123`
- **Engineers**: `engineer1@greentech.com`, `engineer2@greentech.com`, `engineer3@greentech.com` / `green123`

### MedCorp Healthcare

- **Admin**: `admin@medcorp.com` / `medcorp123`
- **Manager**: `manager@medcorp.com` / `med123`
- **Staff**: `staff1@medcorp.com`, `staff2@medcorp.com`, `staff3@medcorp.com` / `med123`

### RetailPlus

- **Admin**: `admin@retailplus.com` / `retail123`
- **Manager**: `manager@retailplus.com` / `retail123`
- **Employees**: `employee1@retailplus.com`, `employee2@retailplus.com`, `employee3@retailplus.com` / `retail123`

## Testing Scenarios

This seeding approach enables comprehensive testing of:

### 1. Cross-Company Data Isolation

```python
# GreenTech admin should only see GreenTech users
# MedCorp admin should only see MedCorp users
# Neither should access the other's data
```

### 2. Role-Based Access Control

```python
# Client admins can create users in their company
# Managers have limited permissions
# Employees have read-only access to relevant data
```

### 3. Platform vs Client Admin Privileges

```python
# Platform admin can see all companies
# Platform admin can create client accounts
# Client admins are scoped to their company
```

### 4. Group Access Control

```python
# Engineering groups contain engineers
# Management groups contain managers and admins
# Groups are isolated by company
```

## Advanced Usage

### Custom Test Data

You can extend `seed_via_api.py` to create custom scenarios:

```python
# Add more companies
await client.create_client_account(platform_admin_email, {
    "name": "Your Custom Company",
    "description": "Custom test company"
})

# Add specialized roles
# Create industry-specific user hierarchies
# Add complex group structures
```

### Integration with Tests

The `test_data_helper.py` makes it easy to write tests:

```python
def test_cross_company_access():
    # Get users from different companies
    company1_admin = TestDataHelper.get_client_admin("greentech")
    company2_employee = TestDataHelper.get_employee("medcorp", 0)

    # Test that admin cannot access other company's data
    # ... test implementation
```

## Troubleshooting

### Common Issues

1. **"Authentication failed"** when running `seed_via_api.py`

   - Make sure you ran `seed_main.py` first
   - Check that the API server is running on http://localhost:8000

2. **"Connection refused"** errors

   - Start the API server: `uvicorn api.main:app --reload`
   - Check the database is running (MongoDB)

3. **Test users not found**
   - Run the seeding scripts in order
   - Check database connection settings

### Verification

To verify your seeding worked:

```python
# Run the test data helper
python scripts/test_data_helper.py

# This will show all available users and their credentials
```

## Benefits of This Approach

1. **Realistic Testing**: Uses actual API calls like real clients would
2. **Proper Data Isolation**: Each company has its own isolated data
3. **Role Hierarchies**: Tests proper permission enforcement
4. **Scalable**: Easy to add more companies, users, or scenarios
5. **Maintainable**: Clear separation between foundation data and test scenarios

This seeding approach gives you everything needed to thoroughly test access control, data scoping, and permission systems in a realistic environment that mirrors production usage patterns.
