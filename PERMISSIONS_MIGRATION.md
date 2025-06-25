# Permissions Migration Guide 🔄

**Date**: 2024-01-15  
**Version**: Phase 1 - Granular Permissions Implementation  
**Status**: Breaking Changes - Test Updates Required

## 🚨 Breaking Changes Summary

We've migrated from broad permissions to **granular scoped permissions** to fix security issues and improve access control. This is a **breaking change** that affects tests and role definitions.

### **Root Issue Fixed**

- **Problem**: `basic_user` role had `["user:read", "group:read"]` permissions
- **Issue**: `require_user_read_access = require_admin_or_permission("user:read")` allowed ANY user with `user:read` to access admin endpoints
- **Result**: Basic users could see all users in the system (security breach)

### **Solution Applied**

- ✅ **Granular permissions**: `user:read_self` vs `user:read_all`
- ✅ **Fixed dependencies**: `require_user_read_access = require_admin`
- ✅ **Proper role scoping**: Basic users get self-access only

---

## 📋 Permission Changes

### **🗑️ REMOVED Permissions**

These broad permissions have been **completely removed**:

```python
# ❌ REMOVED - Too broad, security risk
"user:read"           → Use "user:read_self" or "user:read_all"
"user:create"         → Use "user:manage_client" or "user:manage_all"
"user:update"         → Use "user:manage_client" or "user:manage_all"
"user:delete"         → Use "user:manage_client" or "user:manage_all"
"role:read"           → Use "role:read_client" or "role:read_all"
"role:create"         → Use "role:manage_client" or "role:manage_all"
"role:update"         → Use "role:manage_client" or "role:manage_all"
"role:delete"         → Use "role:manage_client" or "role:manage_all"
"permission:read"     → Use "permission:read_client" or "permission:read_all"
"permission:create"   → Use "permission:manage_client" or "permission:manage_all"
"group:read"          → Use "group:read_own" or "group:read_all"
"group:create"        → Use "group:manage_client" or "group:manage_all"
"group:update"        → Use "group:manage_client" or "group:manage_all"
"group:delete"        → Use "group:manage_client" or "group:manage_all"
"client_account:*"    → Use "client:*" naming convention
```

### **✅ NEW Granular Permissions**

#### **Self-Access (Default for all users)**

```python
"user:read_self"              # Read own profile
"user:update_self"            # Update own profile
"user:change_password"        # Change own password
"group:read_own"              # View own group memberships
"client:read_own"             # View own client info
"permission:create_own_scope" # Create permissions in own scope
"role:create_own_scope"       # Create roles in own scope
"group:create_own_scope"      # Create groups in own scope
```

#### **Client-Scoped (For client admins)**

```python
"user:read_client"      # Read users in same client
"user:manage_client"    # CRUD users in same client
"role:read_client"      # Read roles in same client
"role:manage_client"    # CRUD roles in same client
"group:read_client"     # Read groups in same client
"group:manage_client"   # CRUD groups in same client
"permission:read_client"    # Read permissions in same client
"permission:manage_client"  # CRUD permissions in same client
```

#### **Admin-Only (System-wide)**

```python
"user:read_all"         # Read all users (admin only)
"user:manage_all"       # Global user management (admin only)
"role:read_all"         # Read all roles (admin only)
"role:manage_all"       # Global role management (admin only)
"group:read_all"        # Read all groups (admin only)
"group:manage_all"      # Global group management (admin only)
"permission:read_all"   # Read all permissions (admin only)
"permission:manage_all" # Global permission management (admin only)
```

#### **Platform-Level**

```python
"client:create"              # Create new client accounts
"client:read_platform"       # Read all platform clients
"client:manage_platform"     # Manage clients across platform
"support:cross_client"       # Support across platform clients
```

#### **Kept for Transition**

```python
"user:add_member"       # Add users to client account
"user:bulk_create"      # Bulk user creation
"group:manage_members"  # Add/remove group members
```

---

## 👥 Role Changes

### **Updated Role Permissions**

#### **basic_user** (Default for all users)

```python
# BEFORE - Empty permissions (security issue)
permissions: []

# AFTER - Self-access permissions
permissions: [
    "user:read_self", "user:update_self", "user:change_password",
    "group:read_own", "client:read_own",
    "permission:create_own_scope", "role:create_own_scope", "group:create_own_scope"
]
```

#### **client_admin** (Client-level management)

```python
# BEFORE - Broad permissions
permissions: ["user:create", "user:read", "user:update", "user:delete", ...]

# AFTER - Client-scoped permissions
permissions: [
    "user:manage_client", "user:add_member",
    "group:manage_client", "group:manage_members",
    "role:read_client", "permission:read_client", "client:read_own"
]
```

#### **platform_admin** (Platform-level management)

```python
# BEFORE - Mixed broad permissions
permissions: ["user:create", "user:read", "client_account:create", ...]

# AFTER - Platform-level permissions
permissions: [
    "user:manage_all", "user:add_member", "user:bulk_create",
    "role:manage_all", "permission:manage_all",
    "client:create", "client:manage_platform",
    "group:manage_all", "group:manage_members"
]
```

#### **super_admin** (Unchanged)

```python
# ALL permissions (admin:* wildcard)
permissions: [ALL_SYSTEM_PERMISSIONS]
```

---

## 🧪 Test Updates Required

### **Tests That WILL Break**

1. **Any test checking broad permissions**:

   ```python
   # ❌ WILL FAIL - Permission removed
   assert "user:read" in user.permissions

   # ✅ UPDATE TO
   assert "user:read_all" in admin.permissions  # For admins
   assert "user:read_self" in user.permissions  # For basic users
   ```

2. **Role permission assertions**:

   ```python
   # ❌ WILL FAIL - basic_user no longer empty
   assert len(basic_user.permissions) == 0

   # ✅ UPDATE TO
   assert "user:read_self" in basic_user.permissions
   ```

3. **Dependency checks**:

   ```python
   # ❌ WILL FAIL - Now admin-only
   # Any test assuming users with "user:read" can access user lists

   # ✅ UPDATE TO
   # Only admins can access user lists via require_user_read_access
   ```

### **Search & Replace Guide for Tests**

```bash
# Quick sed commands for bulk test updates
sed -i 's/"user:read"/"user:read_self"/g' tests/*.py
sed -i 's/"user:create"/"user:manage_client"/g' tests/*.py
sed -i 's/"group:read"/"group:read_own"/g' tests/*.py
sed -i 's/"client_account:/"client:/g' tests/*.py

# Manual review needed for admin vs user context
grep -r "user:read_self" tests/  # Should be for basic users
grep -r "user:read_all" tests/   # Should be for admins only
```

### **Test Categories Needing Updates**

1. **`test_access_control.py`** - Permission checking logic
2. **`test_auth_routes.py`** - Role-based endpoint access
3. **`test_user_routes.py`** - User CRUD permissions
4. **`test_role_routes.py`** - Role management permissions
5. **`test_group_routes.py`** - Group access permissions
6. **Any integration tests** - End-to-end permission flows

---

## 🔧 Migration Steps

### **1. Update Database**

```bash
# Re-seed with new permission structure
python scripts/seed_essential_users.py --db outlabsAuth_test

# Verify new permissions exist
python scripts/verify_super_admin.py --test
```

### **2. Update Tests**

```bash
# Run tests to see what breaks
pytest tests/ -v

# Update failing tests with new permission names
# Focus on tests checking specific permissions
```

### **3. Update Dependencies**

- ✅ **Already done**: `require_user_read_access = require_admin`
- Check other dependencies for broad permission usage

### **4. Verify Security**

```bash
# Test that basic users can't access admin endpoints
pytest tests/test_access_control.py::test_regular_user_cannot_access_admin_endpoints -v

# Should PASS now (was failing before)
```

---

## 🎯 Expected Outcomes

### **Security Improvements**

- ✅ Basic users can only read their own data
- ✅ Client admins scoped to their client only
- ✅ Clear permission hierarchy (self → client → platform → system)
- ✅ No accidental admin access via broad permissions

### **Test Results**

- 🔴 **Before**: `test_regular_user_cannot_access_admin_endpoints` **FAILED**
- 🟢 **After**: All access control tests should **PASS**

### **Breaking Changes Impact**

- 📊 **Estimated test failures**: 15-25 tests need permission name updates
- ⏱️ **Fix time**: 1-2 hours of find/replace + verification
- 🛡️ **Security benefit**: Major - eliminates accidental admin access

---

## 📚 Reference

### **Permission Naming Convention**

```
{resource}:{action}_{scope}

Examples:
user:read_self     → Read own user data
user:read_client   → Read users in same client
user:read_all      → Read all users (admin only)
user:manage_client → Full CRUD in client scope
user:manage_all    → Full CRUD system-wide (admin only)
```

### **Scope Hierarchy**

```
system (all data)
  ↓
platform (cross-client within platform)
  ↓
client (within client account)
  ↓
self (own data only)
```

### **Quick Reference**

- **Self-access**: `*:*_self`, `*:read_own`
- **Client-scoped**: `*:*_client`, `*:manage_client`
- **Admin-only**: `*:*_all`, `*:manage_all`
- **Legacy kept**: `user:add_member`, `user:bulk_create`, `group:manage_members`

---

**🚀 Ready to implement? Run the migration steps above and update failing tests with new permission names!**
