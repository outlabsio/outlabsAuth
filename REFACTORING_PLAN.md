# Refactoring Plan: Achieving a Centralized & Declarative RBAC System

## 🎯 Goal

To refactor the authorization logic to be consistent, centralized, and fully aligned with the specifications in `FINAL_PLATFORM_DOCUMENTATION.md`. This plan leverages FastAPI's dependency injection to create a powerful and easy-to-use permission system directly in the endpoint definitions.

---

## 🚨 Core Issues Identified

My analysis revealed three primary issues preventing the system from being production-ready:

1.  **Inconsistent Authorization Logic**: The codebase currently uses a mix of a new `has_permission()` dependency, legacy role-based checks (e.g., `require_admin`), and direct user role checks (`user_has_role`). This makes the flow of control difficult to follow and audit.
2.  **Redundant In-Route Logic**: Many endpoints contain complex, duplicated authorization logic directly within the route handler. This logic should be abstracted into dependencies to keep routes clean and focused on business logic.
3.  **Documentation Discrepancy**: The implemented endpoints, especially for user creation, do not match the API defined in `FINAL_PLATFORM_DOCUMENTATION.md`. Several endpoints are also completely undocumented.

---

## 💡 Proposed Solution: A Unified Permission Dependency

The cornerstone of this refactoring plan is a new, universal dependency factory called `require_permissions`. This single, flexible function will replace the multiple, inconsistent dependencies currently in use.

### **New Dependency Design (`api/dependencies.py`)**

This new dependency will handle all our authorization scenarios with a clear, declarative syntax.

```python
from typing import List, Optional, Union

# ... other imports

def require_permissions(
    any_of: Optional[List[str]] = None,
    all_of: Optional[List[str]] = None
):
    """
    A powerful dependency factory for permission-based access control.

    It can check for:
    - `any_of`: User must have at least one of the specified permissions.
    - `all_of`: User must have all of the specified permissions.

    Usage:
        # Require a single permission
        Depends(require_permissions(all_of=["user:manage_client"]))

        # Require one of several permissions
        Depends(require_permissions(any_of=["user:read_all", "user:read_platform", "user:read_client"]))
    """
    async def _require_permissions_dependency(
        current_user: UserModel = Depends(get_current_user)
    ) -> UserModel:
        # 1. Get user's effective permissions from the service layer
        user_permissions = await user_service.get_user_effective_permissions(current_user.id)

        # 2. Check for "any_of" condition
        if any_of:
            if not any(p in user_permissions for p in any_of):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied. Requires one of the following permissions: {', '.join(any_of)}"
                )

        # 3. Check for "all_of" condition
        if all_of:
            if not all(p in user_permissions for p in all_of):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied. Requires all of the following permissions: {', '.join(all_of)}"
                )

        return current_user
    return _require_permissions_dependency

```

---

## 🔧 Refactoring Steps

### **Step 1: Update `api/dependencies.py`**

1.  **Add the New `require_permissions` Factory**: Implement the code block from the section above.
2.  **Deprecate Old Dependencies**: Remove or comment out legacy dependencies like `require_admin`, `require_role`, `can_access_user`, `require_admin_or_permission`, and any other role-based checkers.
3.  **Create New, Named Dependencies**: For clarity and ease of use, create specific, named dependencies using the new factory.

```python
# In api/dependencies.py

# User Management
can_read_users = require_permissions(any_of=["user:read_all", "user:read_platform", "user:read_client"])
can_manage_users = require_permissions(any_of=["user:manage_all", "user:manage_platform", "user:manage_client"])

# Role Management
can_read_roles = require_permissions(any_of=["role:read_all", "role:read_platform", "role:read_client"])
can_manage_roles = require_permissions(any_of=["role:manage_all", "role:manage_platform", "role:manage_client"])

# Group Management
can_read_groups = require_permissions(any_of=["group:read_client"])
can_manage_groups = require_permissions(any_of=["group:manage_client"])

# Client Account Management
can_read_client_accounts = require_permissions(any_of=["client:read_all", "client:read_platform"])
can_manage_client_accounts = require_permissions(any_of=["client:manage_all", "client:manage_platform"])
```

### **Step 2: Refactor Route Handlers (`user_routes.py`, `role_routes.py`, etc.)**

Update all route handlers to use the new, declarative dependencies. This will drastically simplify the code and remove redundant logic.

**Example: Refactoring `GET /v1/users/`**

**Before (`api/routes/user_routes.py`):**

```python
@router.get("/", response_model=List[UserResponseSchema])
async def get_all_users(
    current_user: UserModel = Depends(require_user_read_access),
    skip: int = 0,
    limit: int = 100
):
    # Complex, redundant, and hard-to-audit logic inside the route
    user_permissions = await user_service.get_user_effective_permissions(current_user.id)
    is_super_admin = user_has_role(current_user, "super_admin")
    has_manage_all = "user:manage_all" in user_permissions
    # ... more complex logic ...
    client_account_id = None
    if is_super_admin or has_manage_all or has_read_all:
        pass
    elif current_user.client_account:
        # ... more complex logic ...
        client_account_id = current_user.client_account.id

    users = await user_service.get_users(skip=skip, limit=limit, client_account_id=client_account_id)
    return [convert_user_to_response(user) for user in users]
```

**After (`api/routes/user_routes.py`):**

```python
from ..dependencies import can_read_users # Import the new dependency

@router.get("/", response_model=List[UserResponseSchema])
async def get_all_users(
    current_user: UserModel = Depends(can_read_users), # Clean, declarative, and secure!
    skip: int = 0,
    limit: int = 100
):
    """
    Retrieve a list of users, automatically scoped by the user's permissions.
    """
    # The user_service is now responsible for scoping the query based on the
    # authenticated user's context (e.g., their client_account_id).
    users = await user_service.get_users(
        current_user=current_user,
        skip=skip,
        limit=limit
    )
    return [convert_user_to_response(user) for user in users]
```

_(Note: This change will require a minor update to the `user_service.get_users` method to accept the `current_user` object and apply scoping logic there.)_

**Example: Refactoring `PUT /v1/users/{user_id}`**

**Before:**

```python
@router.put("/{user_id}", response_model=UserResponseSchema, dependencies=[Depends(has_permission("user:manage_client"))])
async def update_user(...):
    # ...
    # Redundant, manual access control logic inside the route handler
    is_super_admin = user_has_role(current_user, "super_admin")
    if not is_super_admin and token_data.client_account_id:
        if user_to_update.client_account:
            if str(user_to_update.client_account.id) != token_data.client_account_id:
                raise HTTPException(...)
    # ...
```

**After:**

```python
from ..dependencies import can_manage_users # Import the new dependency

@router.put("/{user_id}", response_model=UserResponseSchema)
async def update_user(
    user_id: str,
    user_data: UserUpdateSchema,
    current_user: UserModel = Depends(can_manage_users)
):
    # The dependency has already confirmed the user has the right permissions.
    # The service layer should handle the final check to ensure a client admin
    # is not updating a user outside their own client account.
    updated_user = await user_service.update_user(user_id, user_data, current_user)

    if not updated_user:
         # Service layer returned None because of a scope violation (e.g. client admin)
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found or access denied.")

    return convert_user_to_response(updated_user)
```

### **Step 3: Update Service Layer**

Modify service methods like `get_users` and `update_user` to accept the `current_user: UserModel` as an argument. The service will use the user's properties (`client_account`, `roles`, etc.) to correctly filter database queries, ensuring perfect data isolation. This centralizes data scoping logic in the service layer where it belongs.

### **Step 4: Align Documentation**

1.  **Add Missing Endpoints**: Update `FINAL_PLATFORM_DOCUMENTATION.md` to include the undocumented endpoints like `/logout_all`, `/sessions`, and the password management routes.
2.  **Correct API Definitions**: Adjust the documentation to reflect the final, refactored API structure, ensuring it is a single source of truth.

---

## ✅ Expected Outcome

By following this plan, the outlabsAuth platform will have:

- A **single, clear, and declarative** method for endpoint protection.
- **Simplified route handlers** that are easy to read and maintain.
- **Centralized authorization logic** within `api/dependencies.py` and data scoping logic within the service layer.
- **Full alignment** with the architecture described in the project documentation.
- A truly **secure, auditable, and enterprise-grade** RBAC system.
