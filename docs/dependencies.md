# FastAPI Dependencies Documentation

## Overview

The OutlabsAuth system implements a **unified declarative RBAC dependency architecture** using FastAPI's dependency injection system. This approach provides enterprise-grade access control through a clean, hierarchical permission model that scales from simple role-based access to granular permission-based authorization across multiple organizational scopes.

## 🏗️ **Architecture: Unified Hierarchical Permission System**

Our dependency system operates on a **unified hierarchical permission model** with automatic scope resolution:

### **Hierarchical Permission Structure**

Permissions follow a three-tier hierarchy where higher levels inherit access to lower levels:

```python
# TIER 1: SYSTEM-WIDE ACCESS (highest privilege)
"user:read_all"          # Read users across the entire system
"user:manage_all"        # Manage users system-wide
"role:manage_all"        # Manage roles across all scopes

# TIER 2: PLATFORM-SCOPED ACCESS (platform admin level)
"user:read_platform"     # Read users within the platform
"user:manage_platform"   # Manage users within the platform
"group:read_platform"    # Read groups within the platform

# TIER 3: CLIENT-SCOPED ACCESS (client organization level)
"user:read_client"       # Read users within client organization
"user:manage_client"     # Manage users within client organization
"role:read_client"       # Read roles within client organization
```

### **Automatic Scope Resolution**

The system automatically resolves user permissions based on their organizational context:

```python
# User: jane@propertyhub.com (Platform Admin)
# Effective permissions include:
effective_permissions = [
    "user:read_all",         # System permissions
    "user:manage_platform",  # Platform permissions
    "analytics:view",        # Platform-specific permissions
    # Inherits client permissions for all clients on their platform
]

# User: john@acmerealty.com (Client Admin for ACME Realty)
# Effective permissions include:
effective_permissions = [
    "user:read_client",      # Client-scoped user read access
    "user:manage_client",    # Client-scoped user management
    "listings:create",       # Client-specific business permissions
    # Automatically scoped to ACME Realty only
]
```

## 🎯 **New Unified Dependency System**

### **1. Core Permission Factory**

The foundation of the new system is the `require_permissions()` factory:

```python
# Single permission required
@router.get("/data")
async def get_data(
    _: UserModel = Depends(require_permissions(any_of=["data:read_client"]))
):
    return await data_service.get_data()

# Multiple permission options (OR logic)
@router.get("/reports")
async def get_reports(
    _: UserModel = Depends(require_permissions(any_of=[
        "reports:read_all",
        "reports:read_platform",
        "reports:read_client"
    ]))
):
    return await report_service.get_reports()

# Multiple permissions required (AND logic)
@router.post("/advanced-operation")
async def advanced_operation(
    _: UserModel = Depends(require_permissions(all_of=[
        "operation:execute",
        "audit:create"
    ]))
):
    return await service.execute_advanced_operation()
```

### **2. Named Semantic Dependencies**

Pre-configured dependencies for common access patterns:

```python
# USER MANAGEMENT
@router.get("/users")
async def get_all_users(
    current_user: UserModel = Depends(can_read_users),  # Auto-scoped data filtering
    skip: int = 0, limit: int = 100
):
    users = await user_service.get_users(current_user=current_user, skip=skip, limit=limit)
    return [convert_user_to_response(user) for user in users]

@router.post("/users")
async def create_user(
    user_data: UserCreateSchema,
    _: UserModel = Depends(can_manage_users)  # Access control only
):
    return await user_service.create_user(user_data)

# ROLE MANAGEMENT
@router.get("/roles")
async def get_roles(
    _: UserModel = Depends(can_read_roles)
):
    return await role_service.get_roles()

@router.post("/roles")
async def create_role(
    role_data: RoleCreateSchema,
    _: UserModel = Depends(can_manage_roles)
):
    return await role_service.create_role(role_data)

# GROUP MANAGEMENT
@router.get("/groups")
async def get_groups(
    _: UserModel = Depends(can_read_groups)
):
    return await group_service.get_groups()

@router.put("/groups/{group_id}")
async def update_group(
    group_id: str,
    group_data: GroupUpdateSchema,
    _: UserModel = Depends(can_manage_groups)
):
    return await group_service.update_group(group_id, group_data)
```

### **3. Resource Access Control**

Advanced patterns for accessing specific resources:

```python
# User access with automatic scoping
@router.get("/users/{user_id}")
async def get_user(
    target_user: UserModel = Depends(can_access_user())  # Returns target user if accessible
):
    return convert_user_to_response(target_user)

# Self-or-admin pattern (returns current user)
@router.put("/users/{user_id}")
async def update_user(
    user_data: UserUpdateSchema,
    current_user: UserModel = Depends(require_self_or_admin())  # Validates access, returns current user
):
    target_user_id = request_context.path_params["user_id"]
    return await user_service.update_user(target_user_id, user_data, current_user)

# Hierarchical client access
@router.get("/accounts/{account_id}/data")
async def get_client_data(
    account_id: str,
    _: UserModel = Depends(has_hierarchical_client_access())
):
    return await client_service.get_data(account_id)
```

## 🔧 **Available Dependencies**

### **Named Permission Dependencies**

These are the primary dependencies you should use:

```python
# USER MANAGEMENT
can_read_users = require_permissions(any_of=["user:read_all", "user:read_platform", "user:read_client"])
can_manage_users = require_permissions(any_of=["user:manage_all", "user:manage_platform", "user:manage_client"])

# ROLE MANAGEMENT
can_read_roles = require_permissions(any_of=["role:read_all", "role:read_platform", "role:read_client"])
can_manage_roles = require_permissions(any_of=["role:manage_all", "role:manage_platform", "role:manage_client"])

# GROUP MANAGEMENT
can_read_groups = require_permissions(any_of=["group:read_all", "group:read_platform", "group:read_client"])
can_manage_groups = require_permissions(any_of=["group:manage_all", "group:manage_platform", "group:manage_client"])

# CLIENT ACCOUNT MANAGEMENT
can_read_client_accounts = require_permissions(any_of=["client:read_all", "client:read_platform"])
can_manage_client_accounts = require_permissions(any_of=["client:manage_all", "client:manage_platform"])

# PERMISSION MANAGEMENT
can_read_permissions = require_permissions(any_of=["permission:read_all", "permission:read_platform"])
can_manage_permissions = require_permissions(any_of=["permission:manage_all", "permission:manage_platform"])
```

### **Core Dependency Factories**

```python
# Permission-based access
require_permissions(any_of=["perm1", "perm2"])    # OR logic: user needs any of these permissions
require_permissions(all_of=["perm1", "perm2"])    # AND logic: user needs all of these permissions
require_permissions(any_of=["p1"], all_of=["p2"]) # Mixed: any of first group AND all of second group

# Role-based access
require_role("role_name")                         # Specific role required
require_any_role(["role1", "role2"])             # Any of the specified roles
require_admin                                     # Any admin role (super_admin, admin)

# Resource access control
can_access_user(user_id_param="user_id")         # User access validation (returns target user)
require_self_or_admin(user_id_param="user_id")   # Self-or-admin access (returns current user)
has_hierarchical_client_access(target_client_field="account_id")  # Multi-tenant client access
```

### **Utility Functions**

```python
# User role utilities
user_has_role(user: UserModel, role_name: str) -> bool
user_has_any_role(user: UserModel, role_names: List[str]) -> bool
user_is_client_admin(user: UserModel) -> bool
user_get_role_names(user: UserModel) -> List[str]

# Response utilities
convert_user_to_response(user: UserModel) -> Dict[str, Any]

# Validation utilities
validate_object_id(object_id: str, object_type: str = "ObjectId") -> PydanticObjectId
```

## 🎨 **Design Patterns and Best Practices**

### **1. Clean Route Architecture Pattern**

The new system promotes clean, declarative routes:

```python
# ✅ GOOD: Clean, declarative, single responsibility
@router.get("/users", response_model=List[UserResponseSchema])
async def get_all_users(
    current_user: UserModel = Depends(can_read_users),  # Declarative access control
    skip: int = 0, limit: int = 100
):
    # Service layer handles scoping automatically
    users = await user_service.get_users(current_user=current_user, skip=skip, limit=limit)
    return [convert_user_to_response(user) for user in users]

# ❌ OLD: Complex, mixed concerns, hard to maintain
@router.get("/users", dependencies=[Depends(require_user_read_access)])
async def get_users(user_and_token: Tuple = Depends(get_current_user_with_token)):
    current_user, _ = user_and_token
    # 20+ lines of complex scoping logic...
    user_permissions = await user_service.get_user_effective_permissions(current_user.id)
    is_super_admin = user_has_role(current_user, "super_admin")
    # ... more complex logic
```

### **2. Service Layer Integration Pattern**

Services automatically handle data scoping:

```python
# Service layer automatically filters data based on user permissions
@router.get("/users")
async def get_users(
    current_user: UserModel = Depends(can_read_users),
    skip: int = 0, limit: int = 100
):
    # user_service.get_users() automatically applies scoping based on current_user
    users = await user_service.get_users(current_user=current_user, skip=skip, limit=limit)
    return [convert_user_to_response(user) for user in users]

# Service handles access control validation
@router.put("/users/{user_id}")
async def update_user(
    user_id: str,
    user_data: UserUpdateSchema,
    current_user: UserModel = Depends(can_manage_users)
):
    # Service validates that current_user can update the target user
    updated_user = await user_service.update_user(user_id, user_data, current_user)
    return convert_user_to_response(updated_user)
```

### **3. Access Control Only vs User Object Pattern**

```python
# Access control only (use _ to indicate unused)
@router.delete("/groups/{group_id}")
async def delete_group(
    group_id: str,
    _: UserModel = Depends(can_manage_groups)  # Only need access validation
):
    await group_service.delete_group(group_id)
    return {"message": "Group deleted successfully"}

# Need user object for business logic
@router.get("/my-profile")
async def get_my_profile(
    current_user: UserModel = Depends(get_current_user)  # Need user object
):
    profile = await profile_service.get_profile(current_user.id)
    return enhance_profile_with_user_data(profile, current_user)
```

### **4. Progressive Enhancement Pattern**

Start simple, add granularity as needed:

```python
# Phase 1: Simple named dependency
@router.post("/reports")
async def create_report(
    report_data: ReportCreateSchema,
    _: UserModel = Depends(can_manage_reports)  # If this exists
):
    return await report_service.create(report_data)

# Phase 2: Custom permission factory
@router.post("/reports")
async def create_report(
    report_data: ReportCreateSchema,
    _: UserModel = Depends(require_permissions(any_of=[
        "reports:create_all",
        "reports:create_platform",
        "reports:create_client"
    ]))
):
    return await report_service.create(report_data)

# Phase 3: Conditional permissions based on report type
@router.post("/reports")
async def create_report(
    report_data: ReportCreateSchema,
    current_user: UserModel = Depends(get_current_user)
):
    # Dynamic permission determination
    if report_data.type == "financial":
        required_permissions = ["financial:create_all", "financial:create_platform"]
    elif report_data.type == "operational":
        required_permissions = ["ops:create_all", "ops:create_platform", "ops:create_client"]
    else:
        required_permissions = ["reports:create_client"]

    # Manual permission checking for dynamic scenarios
    user_permissions = await user_service.get_user_effective_permissions(current_user.id)

    has_permission = any(perm in user_permissions for perm in required_permissions)
    if not has_permission:
        raise HTTPException(403, f"Required permissions: {required_permissions}")

    return await report_service.create(report_data, current_user)
```

## 🔄 **How the New System Works**

### **1. Automatic Permission Resolution**

```python
# When can_read_users is called:
# 1. Gets user's effective permissions from user_service.get_user_effective_permissions()
# 2. Checks if user has ANY of: ["user:read_all", "user:read_platform", "user:read_client"]
# 3. Service layer uses current_user context for automatic data scoping

@router.get("/users")
async def get_users(
    current_user: UserModel = Depends(can_read_users)  # Permission check happens here
):
    # Service automatically scopes data based on current_user's permissions and context
    users = await user_service.get_users(current_user=current_user)
    return [convert_user_to_response(user) for user in users]
```

### **2. Service Layer Data Scoping**

```python
# In user_service.get_users():
async def get_users(current_user: UserModel, skip: int = 0, limit: int = 100) -> List[UserModel]:
    user_permissions = await get_user_effective_permissions(current_user.id)

    if "user:read_all" in user_permissions:
        # System admin: can see all users
        return await UserModel.find().skip(skip).limit(limit).to_list()

    elif "user:read_platform" in user_permissions:
        # Platform admin: can see all users on their platform
        platform_clients = await get_platform_client_ids(current_user)
        return await UserModel.find({
            "$or": [
                {"client_account": {"$in": platform_clients}},
                {"client_account": None}  # Platform users
            ]
        }).skip(skip).limit(limit).to_list()

    elif "user:read_client" in user_permissions:
        # Client admin: can see users in their client organization only
        return await UserModel.find({
            "client_account": current_user.client_account.id
        }).skip(skip).limit(limit).to_list()
```

### **3. Permission Inheritance**

Higher-level permissions automatically include lower-level access:

```python
# User with "user:read_all" permission:
effective_permissions = [
    "user:read_all",      # Explicit permission
    # Implicitly includes:
    # "user:read_platform" (can read platform users)
    # "user:read_client"   (can read client users)
]

# User with "user:read_platform" permission:
effective_permissions = [
    "user:read_platform", # Explicit permission
    # Implicitly includes:
    # "user:read_client"   (can read client users within platform)
]
```

## 🧪 **Testing the New System**

### **Mocking Named Dependencies**

```python
# test_routes.py
def test_user_management_endpoint():
    # Mock the named dependency
    def mock_can_read_users():
        return Mock(id="user_id", email="user@test.com")

    app.dependency_overrides[can_read_users] = mock_can_read_users

    client = TestClient(app)
    response = client.get("/users")

    assert response.status_code == 200
    app.dependency_overrides.clear()

def test_permission_factory():
    # Mock custom permission dependency
    def mock_custom_permission():
        return Mock(id="user_id", permissions=["custom:read"])

    custom_dependency = require_permissions(any_of=["custom:read"])
    app.dependency_overrides[custom_dependency] = mock_custom_permission

    response = client.get("/custom-endpoint")
    assert response.status_code == 200
```

### **Integration Testing**

```python
async def test_hierarchical_permissions():
    # Create user with platform-level permission
    user = await user_service.create_user(UserCreateSchema(
        email="platform@test.com",
        password="password"
    ))

    # Create role with platform permission
    role = await role_service.create_role(RoleCreateSchema(
        name="platform_manager",
        permissions=["user:read_platform"]
    ))

    user.roles.append(role)
    await user.save()

    # Test with real authentication
    token = security_service.create_access_token(str(user.id))
    headers = {"Authorization": f"Bearer {token}"}

    # Should pass the can_read_users dependency
    # (user:read_platform is one of the accepted permissions)
    response = client.get("/users", headers=headers)
    assert response.status_code == 200
```

## 📊 **Migration from Legacy System**

### **Deprecated Dependencies**

The following dependencies are **deprecated** and should be migrated:

```python
# DEPRECATED - Replace with named dependencies
require_user_read_access    → can_read_users
require_user_manage_access  → can_manage_users
require_role_read_access    → can_read_roles
require_role_manage_access  → can_manage_roles
require_group_manage_access → can_manage_groups
require_permission_manage_access → can_manage_permissions

# DEPRECATED - Replace with require_permissions() factory
require_admin_or_permission("permission:name") → require_permissions(any_of=["permission:name"])
```

### **Migration Examples**

```python
# OLD PATTERN
@router.get("/users")
async def get_users(
    user: UserModel = Depends(require_user_read_access)
):
    # Complex manual scoping logic...
    pass

# NEW PATTERN
@router.get("/users")
async def get_users(
    current_user: UserModel = Depends(can_read_users)
):
    users = await user_service.get_users(current_user=current_user)
    return [convert_user_to_response(user) for user in users]

# OLD PATTERN
@router.post("/roles")
async def create_role(
    role_data: RoleCreateSchema,
    _: UserModel = Depends(require_admin_or_permission("role:manage"))
):
    pass

# NEW PATTERN
@router.post("/roles")
async def create_role(
    role_data: RoleCreateSchema,
    _: UserModel = Depends(can_manage_roles)
):
    return await role_service.create_role(role_data)
```

## 🚀 **Advanced Patterns**

### **1. Custom Permission Dependencies**

```python
# Create application-specific permission dependencies
can_export_data = require_permissions(any_of=[
    "export:data_all",
    "export:data_platform",
    "export:data_client"
])

can_manage_billing = require_permissions(all_of=[
    "billing:access",
    "financial:manage"
])

# Usage
@router.get("/export/users")
async def export_users(
    _: UserModel = Depends(can_export_data)
):
    return await export_service.export_users()

@router.post("/billing/invoice")
async def create_invoice(
    invoice_data: InvoiceCreateSchema,
    _: UserModel = Depends(can_manage_billing)
):
    return await billing_service.create_invoice(invoice_data)
```

### **2. Conditional Dependencies**

```python
def require_context_aware_permission():
    """Dynamic permission based on request context."""
    async def _context_permission(
        request: Request,
        current_user: UserModel = Depends(get_current_user)
    ) -> UserModel:
        # Extract context from request
        resource_type = request.path_params.get("resource_type")

        # Build permission dynamically
        required_permissions = [
            f"{resource_type}:manage_all",
            f"{resource_type}:manage_platform",
            f"{resource_type}:manage_client"
        ]

        # Check permissions
        user_permissions = await user_service.get_user_effective_permissions(current_user.id)

        if any(perm in user_permissions for perm in required_permissions):
            return current_user

        raise HTTPException(403, f"Required permissions: {required_permissions}")

    return _context_permission

# Usage
@router.post("/{resource_type}/items")
async def create_resource_item(
    resource_type: str,
    item_data: dict,
    _: UserModel = Depends(require_context_aware_permission())
):
    return await dynamic_service.create_item(resource_type, item_data)
```

### **3. Composite Permission Validation**

```python
# Multiple validation layers
async def require_senior_manager():
    """Requires both role AND permissions."""
    async def _composite_check(
        manager: UserModel = Depends(require_role("manager")),
        _: UserModel = Depends(require_permissions(any_of=["senior:access"]))
    ) -> UserModel:
        return manager
    return _composite_check

@router.get("/sensitive-data")
async def get_sensitive_data(
    manager: UserModel = Depends(require_senior_manager())
):
    return await sensitive_service.get_data(manager)
```

## 📈 **Performance Considerations**

### **Permission Caching**

```python
# The system automatically caches permissions within request scope
# user_service.get_user_effective_permissions() includes intelligent caching

# For high-frequency endpoints, consider service-level optimizations:
@router.get("/high-frequency-endpoint")
async def high_frequency_endpoint(
    current_user: UserModel = Depends(can_read_users)
):
    # Service layer should use optimized queries with proper indexing
    result = await optimized_service.get_data(current_user)
    return result
```

## 📝 **Best Practices Summary**

### **✅ Do's**

- **Use named dependencies** (`can_read_*`, `can_manage_*`) for standard operations
- **Use `require_permissions()`** for custom permission combinations
- **Let services handle scoping** - pass `current_user` to service methods
- **Use `_` parameter** when you only need access control validation
- **Start with broad permissions**, add granularity as requirements evolve
- **Test dependencies** both in isolation and integration scenarios

### **❌ Don'ts**

- **Don't use deprecated dependencies** (`require_user_read_access`, etc.)
- **Don't implement manual scoping** in route handlers
- **Don't bypass the dependency system** with inline permission checks
- **Don't create overly complex dependencies** - keep them focused and testable
- **Don't forget automatic permission inheritance** - higher levels include lower levels

### **🎯 Decision Framework**

1. **Standard CRUD operations?** → Use named dependencies (`can_read_*`, `can_manage_*`)
2. **Custom permission combination?** → Use `require_permissions(any_of=[], all_of=[])`
3. **Resource access validation?** → Use `can_access_user()`, `require_self_or_admin()`
4. **Complex conditional logic?** → Create custom dependency factory
5. **Performance critical?** → Ensure service layer optimization and caching

## 🌟 **Conclusion**

The new unified RBAC dependency system provides:

- **🎯 Declarative Security**: Clear, readable permission requirements
- **🏗️ Clean Architecture**: Separation of concerns between routes and business logic
- **📊 Automatic Scoping**: Service layer handles data filtering transparently
- **🔧 Flexible Permissions**: Hierarchical permissions with inheritance
- **⚡ High Performance**: Built-in caching and optimized query patterns
- **🧪 Testable Design**: Easy to mock and test in isolation

This architecture enables rapid development while maintaining enterprise-grade security and the flexibility to handle complex multi-tenant scenarios as your application scales.
