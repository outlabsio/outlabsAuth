# FastAPI Dependencies Documentation

## Overview

The OutlabsAuth system implements a **sophisticated multi-layer dependency architecture** using FastAPI's dependency injection system. This approach provides declarative security, clean code separation, and flexible access control that scales from simple admin/user distinctions to enterprise-grade permission models with hundreds of specific permissions across multiple organizational scopes.

## 🏗️ **Architecture: Three-Layer Permission System**

Our dependency system operates on **three complementary layers** that work together to provide comprehensive access control:

### **Layer 1: Atomic Scoped Permissions**

The foundation layer consists of granular permissions scoped to organizational levels:

```python
# SYSTEM SCOPE (scope: "system", scope_id: null)
"user:create"              # Create users anywhere in the system
"infrastructure:manage"    # Manage core system infrastructure
"platform:create"          # Create new platform instances

# PLATFORM SCOPE (scope: "platform", scope_id: "platform_123")
"analytics:view"           # View platform-wide analytics
"client_account:create"    # Create client accounts on this platform
"support:cross_client"     # Support all clients on this platform

# CLIENT SCOPE (scope: "client", scope_id: "client_456")
"listings:create"          # Create property listings for this client
"users:manage"             # Manage users within this client organization
"reports:view"             # View reports for this client
```

### **Layer 2: Permission Categories (Dependency Families)**

Broad permission categories that group related permissions for rapid development:

```python
# Current permission families in the system
require_group_manage_access = require_admin_or_permission("group:manage")
require_role_manage_access = require_admin_or_permission("role:manage")
require_user_read_access = require_admin_or_permission("user:read")
require_permission_manage_access = require_admin_or_permission("permission:manage")
```

### **Layer 3: Role-Based Admin Shortcuts**

Administrative roles that bypass specific permission checks for operational efficiency:

```python
# Role-based dependencies
require_super_admin        # System admin (unrestricted access)
require_admin             # Any admin role (system/platform/client)
require_platform_admin    # Platform admin access only
require_client_admin      # Client admin access only
```

## 🎯 **Core Dependency Patterns**

### **1. Role-Based Access Control**

Simple role requirements for straightforward access control:

```python
# Basic role checking
@router.get("/admin-dashboard")
async def admin_dashboard(
    user: UserModel = Depends(require_super_admin)
):
    return {"message": "Super admin access granted"}

# Multiple role options
@router.get("/management-panel")
async def management_panel(
    user: UserModel = Depends(require_admin)  # Any admin role
):
    return {"message": "Admin access granted"}
```

### **2. Permission-Based Access Control**

Specific permission requirements for granular control:

```python
# Specific permission required
@router.post("/users")
async def create_user(
    user_data: UserCreateSchema,
    _: UserModel = Depends(has_permission("user:create"))
):
    return await user_service.create_user(user_data)
```

### **3. Hybrid Admin-or-Permission Dependencies**

The most flexible pattern - admin roles OR specific permissions:

```python
# Admin roles bypass permission checks, regular users need specific permission
@router.get("/users")
async def get_users(
    user: UserModel = Depends(require_user_read_access)  # Admin OR user:read
):
    # Works for:
    # - Any admin (super_admin, admin, client_admin)
    # - Users with "user:read" permission
    return await user_service.get_users()
```

### **4. User Access Control with Scoping**

Advanced patterns for user data access with automatic scope validation:

```python
# Self-or-admin access with client scoping
@router.get("/users/{user_id}")
async def get_user(
    user: UserModel = Depends(can_access_user())
):
    # Handles:
    # - Users accessing their own data
    # - Admins accessing any user data
    # - Client admin scoping (can't see other clients' users)
    return convert_user_to_response(user)

# Validates access but returns current user
@router.put("/users/{user_id}")
async def update_user(
    user_data: UserUpdateSchema,
    current_user: UserModel = Depends(require_self_or_admin())
):
    # current_user is guaranteed to have access to the target user
    return await user_service.update_user(user_data, current_user)
```

### **5. Scope-Based Admin Dependencies**

Dependencies that validate admin access for specific scopes:

```python
# System admin required (super admin only)
@router.post("/system/roles")
async def create_system_role(
    role_data: RoleCreateSchema,
    admin: UserModel = Depends(require_scope_admin("system"))
):
    return await role_service.create_role(role_data, "system")

# Platform admin required
@router.post("/platform/features")
async def create_platform_feature(
    feature_data: FeatureCreateSchema,
    admin: UserModel = Depends(require_scope_admin("platform"))
):
    return await feature_service.create_feature(feature_data)

# Client admin required
@router.post("/client/departments")
async def create_department(
    dept_data: DepartmentCreateSchema,
    admin: UserModel = Depends(require_scope_admin("client"))
):
    return await department_service.create_department(dept_data)
```

## 🔧 **Implementation Guide**

### **Creating New Dependencies**

#### **1. Simple Role Dependencies**

```python
# In api/dependencies.py

# Single role requirement
def require_manager():
    """Requires manager role specifically."""
    return require_role("manager")

# Multiple role options
def require_supervisor():
    """Requires supervisor or manager role."""
    return require_any_role(["supervisor", "manager"])

# Usage in routes
@router.get("/reports")
async def get_reports(
    user: UserModel = Depends(require_manager)
):
    return await report_service.get_reports()
```

#### **2. Permission-Based Dependencies**

```python
# Specific permission required
def require_export_access():
    """Requires data export permission."""
    return has_permission("data:export")

# Admin or specific permission
def require_analytics_access():
    """Admin access or analytics permission."""
    return require_admin_or_permission("analytics:view")

# Usage
@router.get("/analytics")
async def get_analytics(
    user: UserModel = Depends(require_analytics_access)
):
    return await analytics_service.get_data()
```

#### **3. Resource-Specific Dependencies**

```python
# Resource access validation
def can_access_project(project_id_param: str = "project_id"):
    """Validates access to specific project."""
    async def _can_access_project(
        request: Request,
        current_user: UserModel = Depends(get_current_user)
    ) -> ProjectModel:
        project_id = request.path_params.get(project_id_param)
        project = await project_service.get_project(project_id)

        if not project:
            raise HTTPException(404, "Project not found")

        # Check access (admin, project member, or specific permission)
        if (user_has_role(current_user, "admin") or
            project.is_member(current_user.id) or
            await has_project_permission(current_user, project, "read")):
            return project

        raise HTTPException(403, "Access denied")
    return _can_access_project

# Usage
@router.get("/projects/{project_id}")
async def get_project(
    project: ProjectModel = Depends(can_access_project())
):
    return project_to_response(project)
```

### **Granular Permission Control**

#### **From Broad to Specific**

```python
# Start with broad categories during development
require_document_access = require_admin_or_permission("document:manage")

# Refine to specific operations as needed
require_document_create = require_admin_or_permission("document:create")
require_document_delete = require_admin_or_permission("document:delete")
require_document_share = require_admin_or_permission("document:share")
require_document_export = require_admin_or_permission("document:export")

# Apply granular control
@router.post("/documents")
async def create_document(
    doc_data: DocumentCreateSchema,
    _: UserModel = Depends(require_document_create)  # Specific permission
):
    return await document_service.create(doc_data)

@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    _: UserModel = Depends(require_document_delete)  # Different permission
):
    return await document_service.delete(doc_id)
```

#### **Conditional Granularity**

```python
# Different permission levels for the same endpoint
@router.get("/financial-reports")
async def get_financial_reports(
    detail_level: str = Query("basic"),
    user: UserModel = Depends(require_user_read_access)
):
    if detail_level == "detailed":
        # Check for elevated permission inline
        user_permissions = await user_service.get_user_effective_permissions(user.id)
        if not ("finance:detailed" in user_permissions or user_has_role(user, "admin")):
            raise HTTPException(403, "Detailed reports require finance:detailed permission")

    return await finance_service.get_reports(detail_level)
```

## 🎨 **Design Patterns and Best Practices**

### **1. Access Control Only Pattern**

When you only need access validation without using the user object:

```python
# Use _ to indicate access control only
@router.get("/public-data")
async def get_public_data(
    _: UserModel = Depends(require_user_read_access)  # Access control only
):
    # User object not needed in function logic
    return await data_service.get_public_data()
```

### **2. User Object Required Pattern**

When you need the user object for business logic:

```python
@router.get("/my-profile")
async def get_my_profile(
    current_user: UserModel = Depends(get_current_user)  # Need user object
):
    # Use user object for business logic
    profile = await profile_service.get_profile(current_user.id)
    return enhance_profile_with_user_data(profile, current_user)
```

### **3. Resource Access Pattern**

When returning the validated resource:

```python
@router.get("/users/{user_id}")
async def get_user_detail(
    target_user: UserModel = Depends(can_access_user())  # Returns target user
):
    # target_user is the user being accessed (with access validated)
    return user_to_detailed_response(target_user)
```

### **4. Progressive Enhancement Pattern**

Start simple, add granularity as needed:

```python
# Phase 1: Simple admin check
@router.post("/reports")
async def create_report(
    report_data: ReportCreateSchema,
    _: UserModel = Depends(require_admin)
):
    pass

# Phase 2: Add specific permission
@router.post("/reports")
async def create_report(
    report_data: ReportCreateSchema,
    _: UserModel = Depends(require_admin_or_permission("report:create"))
):
    pass

# Phase 3: Different permissions for different report types
@router.post("/reports")
async def create_report(
    report_data: ReportCreateSchema,
    current_user: UserModel = Depends(get_current_user)
):
    # Dynamic permission checking based on report type
    required_permission = f"report:{report_data.type}:create"
    user_permissions = await user_service.get_user_effective_permissions(current_user.id)

    if not (user_has_role(current_user, "admin") or required_permission in user_permissions):
        raise HTTPException(403, f"Required permission: {required_permission}")

    return await report_service.create(report_data)
```

## 🔄 **How Scoped Permissions Work**

### **Automatic Scope Resolution**

The system automatically resolves permissions based on user context:

```python
# User: john@acmerealestate.com (ACME Real Estate client)
# Roles: ["sales_agent"] (client-scoped to ACME)
# Groups: ["weekend_team"] (client-scoped to ACME)

# When get_user_effective_permissions() is called:
effective_permissions = [
    # From sales_agent role (client scope: ACME)
    "listings:create",        # Can create listings for ACME
    "user:read",             # System permission from role

    # From weekend_team group (client scope: ACME)
    "weekend:access",        # Weekend access for ACME
    "leads:assign"          # Assign leads within ACME
]

# Scope isolation ensures:
# - john can't see Elite Properties' listings
# - john can't manage Downtown Realty's users
# - john's "listings:create" only works for ACME
```

### **Cross-Scope Access for Admins**

Higher-level admins get permissions from multiple scopes:

```python
# Platform Admin: admin@propertyhub.com
effective_permissions = [
    # System permissions
    "user:read", "user:create",

    # Platform permissions (PropertyHub platform)
    "analytics:view", "client_account:create", "support:cross_client",

    # Client permissions (can access all clients on platform)
    "client:*"  # Wildcard or explicit permissions from all clients
]

# Super Admin: gets permissions from ALL scopes
# Platform Admin: gets system + their platform + all platform clients
# Client Admin: gets system + their client only
```

## 📊 **Dependency Reference**

### **Available Dependencies**

#### **Role-Based**

```python
require_super_admin           # System super admin only
require_admin                # Any admin role (super/platform/client)
require_platform_admin       # Platform admin roles
require_role("role_name")     # Specific role required
require_any_role(["r1", "r2"]) # Any of the specified roles
```

#### **Permission-Based**

```python
has_permission("permission:name")                    # Specific permission required
require_admin_or_permission("permission:name")      # Admin role OR permission
```

#### **Scope-Based Admin**

```python
require_scope_admin("system")     # System admin (super admin only)
require_scope_admin("platform")   # Platform admin for their platform
require_scope_admin("client")     # Client admin for their client
```

#### **Pre-configured Categories**

```python
require_user_read_access          # Admin OR user:read permission
require_role_manage_access        # Admin OR role:manage permission
require_group_manage_access       # Admin OR group:manage permission
require_permission_manage_access  # Admin OR permission:manage permission
```

#### **User Access Control**

```python
can_access_user(param="user_id")         # Returns target user if accessible
require_self_or_admin(param="user_id")   # Returns current user if has access
```

#### **Client Access Control**

```python
has_hierarchical_client_access(param="account_id")  # Multi-tenant client access
```

### **Dependency Factory Parameters**

Most dependency factories accept parameters for customization:

```python
# Parameter examples
can_access_user(user_id_param="target_user_id")     # Custom parameter name
has_hierarchical_client_access(target_client_field="client_id")  # Custom field
require_role("manager")                              # Specific role name
require_any_role(["supervisor", "manager", "lead"]) # Multiple role options
```

## 🚀 **Advanced Patterns**

### **1. Conditional Dependencies**

```python
# Different dependencies based on request data
def get_report_dependency(report_type: str):
    if report_type == "financial":
        return require_admin_or_permission("finance:read")
    elif report_type == "hr":
        return require_admin_or_permission("hr:read")
    else:
        return require_user_read_access

@router.get("/reports/{report_type}")
async def get_report(
    report_type: str,
    user: UserModel = Depends(lambda: get_report_dependency(report_type))
):
    return await report_service.get_report(report_type)
```

### **2. Composite Dependencies**

```python
# Multiple validation layers
def require_project_manager_access():
    """Requires both manager role AND project permissions."""
    async def _composite_check(
        manager: UserModel = Depends(require_role("manager")),
        _: UserModel = Depends(has_permission("project:manage"))
    ) -> UserModel:
        return manager
    return _composite_check

@router.post("/projects/{project_id}/milestones")
async def create_milestone(
    project_id: str,
    milestone_data: MilestoneCreateSchema,
    manager: UserModel = Depends(require_project_manager_access())
):
    return await milestone_service.create(project_id, milestone_data, manager)
```

### **3. Dynamic Permission Dependencies**

```python
# Permission determined at runtime
def require_dynamic_permission():
    async def _dynamic_check(
        request: Request,
        current_user: UserModel = Depends(get_current_user)
    ) -> UserModel:
        # Extract context from request
        action = request.path_params.get("action")
        resource = request.path_params.get("resource")

        # Build permission name dynamically
        required_permission = f"{resource}:{action}"

        # Check permission
        user_permissions = await user_service.get_user_effective_permissions(current_user.id)

        if user_has_role(current_user, "admin") or required_permission in user_permissions:
            return current_user

        raise HTTPException(403, f"Required permission: {required_permission}")

    return _dynamic_check

@router.post("/{resource}/{action}")
async def dynamic_endpoint(
    resource: str,
    action: str,
    user: UserModel = Depends(require_dynamic_permission())
):
    return await generic_service.perform_action(resource, action, user)
```

## 🧪 **Testing Dependencies**

### **Mocking Dependencies in Tests**

```python
# test_routes.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock

def test_admin_endpoint():
    # Mock the dependency
    def mock_require_admin():
        return Mock(id="admin_id", email="admin@test.com")

    # Override dependency
    app.dependency_overrides[require_admin] = mock_require_admin

    client = TestClient(app)
    response = client.get("/admin-only-endpoint")

    assert response.status_code == 200

    # Clean up
    app.dependency_overrides.clear()

def test_permission_dependency():
    # Mock user with specific permissions
    def mock_user_with_permission():
        user = Mock()
        user.id = "user_id"
        # Mock the permission check
        return user

    app.dependency_overrides[require_group_manage_access] = mock_user_with_permission

    client = TestClient(app)
    response = client.post("/groups", json={"name": "test_group"})

    assert response.status_code == 201
```

### **Integration Testing**

```python
# test_integration.py
async def test_real_permission_flow():
    # Create real user with real permissions
    user = await user_service.create_user(UserCreateSchema(
        email="test@example.com",
        password="password"
    ))

    # Create real role with real permissions
    role = await role_service.create_role(RoleCreateSchema(
        name="test_role",
        permissions=["group:manage"]
    ))

    # Assign role to user
    user.roles.append(role)
    await user.save()

    # Test with real authentication
    token = security_service.create_access_token(str(user.id))
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post("/groups",
                          json={"name": "test_group"},
                          headers=headers)

    assert response.status_code == 201
```

## 📈 **Performance Considerations**

### **Dependency Caching**

```python
# Cache permission lookups within request scope
@lru_cache(maxsize=1)
async def get_cached_user_permissions(user_id: str) -> List[str]:
    """Cache permissions for the duration of the request."""
    return await user_service.get_user_effective_permissions(user_id)

def require_cached_permission(permission_name: str):
    """Permission check with caching."""
    async def _cached_permission_check(
        current_user: UserModel = Depends(get_current_user)
    ) -> UserModel:
        if user_has_role(current_user, "admin"):
            return current_user

        # Use cached permissions
        user_permissions = await get_cached_user_permissions(str(current_user.id))

        if permission_name in user_permissions:
            return current_user

        raise HTTPException(403, "Access denied")

    return _cached_permission_check
```

### **Optimizing Database Queries**

```python
# Fetch user with related data in single query
async def get_current_user_with_permissions(
    token: str = Depends(get_token_from_request)
) -> UserModel:
    """Get user with all related data fetched."""
    token_data = security_service.decode_access_token(token)

    # Single query with all relationships
    user = await UserModel.get(
        PydanticObjectId(token_data.user_id),
        fetch_links=True  # Loads roles, groups, client_account
    )

    if not user:
        raise HTTPException(404, "User not found")

    return user

# Use optimized dependency
def require_optimized_access():
    return require_admin_or_permission_optimized("group:manage")

async def require_admin_or_permission_optimized(permission_name: str):
    """Optimized permission check with single DB query."""
    async def _optimized_check(
        current_user: UserModel = Depends(get_current_user_with_permissions)
    ) -> UserModel:
        # All user data already loaded, no additional queries needed
        if user_has_role(current_user, "admin"):
            return current_user

        # Check permissions from already-loaded data
        user_permissions = extract_permissions_from_loaded_user(current_user)

        if permission_name in user_permissions:
            return current_user

        raise HTTPException(403, "Access denied")

    return _optimized_check
```

## 📝 **Best Practices Summary**

### **Do's**

✅ **Start with broad categories** like `require_admin` or `require_user_read_access`
✅ **Add granular permissions** as requirements become more specific
✅ **Use `_` parameter** when you only need access control validation
✅ **Combine multiple dependencies** for complex validation scenarios
✅ **Cache permission lookups** for performance-critical endpoints
✅ **Test dependencies** both in isolation and integration scenarios
✅ **Document custom dependencies** with clear usage examples

### **Don'ts**

❌ **Don't create dependencies for every single permission** - start broad
❌ **Don't ignore scope boundaries** - respect system/platform/client isolation
❌ **Don't bypass dependency validation** in route logic
❌ **Don't create overly complex dependencies** - keep them focused and testable
❌ **Don't forget to handle edge cases** like missing roles or malformed tokens
❌ **Don't hard-code permission names** - use constants or configuration

### **Decision Framework**

1. **Simple admin check?** → Use `require_admin`
2. **Specific permission needed?** → Use `require_admin_or_permission("permission:name")`
3. **User access to own data?** → Use `can_access_user()` or `require_self_or_admin()`
4. **Complex validation logic?** → Create custom dependency factory
5. **Performance critical?** → Add caching and query optimization
6. **Multiple permission levels?** → Use conditional dependencies or inline checks

## 🌟 **Conclusion**

The FastAPI dependency system in OutlabsAuth provides a **powerful, flexible, and scalable** approach to access control that:

- **Scales from simple to complex** - Start with broad categories, add granularity as needed
- **Maintains clean separation** - Security logic separate from business logic
- **Respects organizational boundaries** - Automatic scope isolation
- **Optimizes for developer experience** - Declarative, type-safe, and testable
- **Supports enterprise requirements** - Handles complex multi-tenant scenarios

This architecture enables rapid development while maintaining the flexibility to implement sophisticated permission models as your application grows and requirements become more complex.
