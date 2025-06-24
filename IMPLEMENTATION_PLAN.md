# RBAC Architecture Enhancement Implementation Plan

## 🎯 **Overview**

This plan outlines the implementation of **scoped permissions** and **enhanced groups** to complete our three-tier RBAC architecture.

## 📋 **Current vs Target Architecture**

### **Current State**

- ✅ **Roles**: Fully scoped (system/platform/client)
- ⚠️ **Groups**: Client-only scoped, roles assigned to groups
- ❌ **Permissions**: Global only, no scoping

### **Target State**

- ✅ **Roles**: Fully scoped (system/platform/client)
- ✅ **Groups**: Fully scoped (system/platform/client), direct permissions only
- ✅ **Permissions**: Fully scoped (system/platform/client)

## 🚀 **Implementation Phases**

### **Phase 1: Scoped Permissions Model**

**Estimated Time**: 2-3 days

#### **1.1 Create New Permission Model**

```python
# api/models/permission_model.py
class PermissionScope(str, Enum):
    SYSTEM = "system"
    PLATFORM = "platform"
    CLIENT = "client"

class PermissionModel(Document):
    id: str = Field(alias="_id")  # "platform:analytics:view"
    name: str  # "analytics:view"
    display_name: str  # "View Analytics"
    description: Optional[str] = None

    # Scoping
    scope: PermissionScope
    scope_id: Optional[str] = None

    # Metadata
    created_by_user_id: Optional[str] = None
    created_by_client_id: Optional[str] = None
```

#### **1.2 Create Permission Schemas**

```python
# api/schemas/permission_schema.py
class PermissionCreateSchema(BaseModel):
    name: str
    display_name: str
    description: Optional[str] = None
    scope: PermissionScope

class PermissionResponseSchema(BaseModel):
    id: str
    name: str
    display_name: str
    description: Optional[str] = None
    scope: PermissionScope
    scope_id: Optional[str] = None
```

#### **1.3 Update Permission Service**

```python
# api/services/permission_service.py
class PermissionService:
    async def create_permission(
        self,
        permission_data: PermissionCreateSchema,
        current_user_id: str,
        current_client_id: Optional[str] = None,
        scope_id: Optional[str] = None
    ) -> PermissionModel:
        # Implement scoped permission creation

    async def get_permissions_by_scope(
        self,
        scope: PermissionScope,
        scope_id: Optional[str] = None
    ) -> List[PermissionModel]:
        # Get permissions for specific scope
```

### **Phase 2: Enhanced Groups Model**

**Estimated Time**: 2-3 days

#### **2.1 Update Group Model**

```python
# api/models/group_model.py
class GroupScope(str, Enum):
    SYSTEM = "system"      # Lead company internal teams
    PLATFORM = "platform"  # Corporate client internal teams
    CLIENT = "client"      # Location/franchise teams

class GroupModel(BaseDocument):
    name: str
    display_name: str
    description: Optional[str] = None

    # Direct permissions (remove roles field)
    permissions: List[str] = Field(default_factory=list)

        # Scoping
    scope: GroupScope
    scope_id: Optional[str] = None  # None for system groups

    # Metadata
    created_by_user_id: Optional[str] = None
    created_by_client_id: Optional[str] = None
```

#### **2.2 Update Group Schemas**

```python
# api/schemas/group_schema.py
class GroupCreateSchema(BaseModel):
    name: str
    display_name: str
    description: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)
    scope: GroupScope
    # scope_id determined by service based on user context

class GroupUpdateSchema(BaseModel):
    name: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[List[str]] = None
```

#### **2.3 Update Group Service**

```python
# api/services/group_service.py
class GroupService:
    async def create_group(
        self,
        group_data: GroupCreateSchema,
        current_user_id: str,
        current_client_id: Optional[str] = None,
        scope_id: Optional[str] = None
    ) -> GroupModel:
        # Implement scoped group creation with permission validation

    async def get_groups_by_scope(
        self,
        scope: GroupScope,
        scope_id: str
    ) -> List[GroupModel]:
        # Get groups for specific scope
```

### **Phase 3: User Permission Aggregation**

**Estimated Time**: 1-2 days

#### **3.1 Enhanced User Service**

```python
# api/services/user_service.py
class UserService:
    async def get_user_effective_permissions(
        self,
        user_id: PydanticObjectId
    ) -> Set[str]:
        """
        Aggregate permissions from:
        1. Direct role assignments
        2. Group memberships
        """
        user = await self.get_user_by_id(user_id)
        permissions = set()

        # Get permissions from roles
        for role_id in user.roles:
            role = await role_service.get_role_by_id(role_id)
            if role:
                permissions.update(role.permissions)

        # Get permissions from groups
        for group in user.groups:
            if hasattr(group, 'permissions'):
                permissions.update(group.permissions)

        return permissions
```

#### **3.2 Update Auth Routes**

```python
# api/routes/auth_routes.py
@router.get("/me")
async def get_current_user_profile(...):
    # Include effective permissions in response
    effective_permissions = await user_service.get_user_effective_permissions(user.id)

    return UserProfileResponseSchema(
        ...existing_fields...,
        effective_permissions=list(effective_permissions)
    )
```

### **Phase 4: API Routes Enhancement**

**Estimated Time**: 2-3 days

#### **4.1 Permission Routes**

```python
# api/routes/permission_routes.py
@router.post("/")
async def create_permission(...)

@router.get("/")
async def get_permissions(...)

@router.get("/available")
async def get_available_permissions(...)  # Similar to roles/available

@router.put("/{permission_id}")
async def update_permission(...)

@router.delete("/{permission_id}")
async def delete_permission(...)
```

#### **4.2 Enhanced Group Routes**

```python
# api/routes/group_routes.py - Update existing routes
@router.post("/")
async def create_group(...):
    # Handle scoped group creation with permissions

@router.put("/{group_id}")
async def update_group(...):
    # Validate permission changes

@router.get("/available")
async def get_available_groups(...):
    # Return groups user can assign, by scope
```

### **Phase 5: Data Migration**

**Estimated Time**: 1-2 days

#### **5.1 Permission Migration Script**

```python
# scripts/migrate_permissions.py
async def migrate_global_permissions_to_scoped():
    """
    Migrate existing global permissions to scoped permissions
    """
    # Get all existing permissions
    old_permissions = await OldPermissionModel.find_all().to_list()

    for old_perm in old_permissions:
        # Determine scope based on permission name
        if old_perm.id.startswith("platform:"):
            scope = PermissionScope.PLATFORM
        elif old_perm.id.startswith("client:"):
            scope = PermissionScope.CLIENT
        else:
            scope = PermissionScope.SYSTEM

        # Create new scoped permission
        new_perm = PermissionModel(
            id=old_perm.id,
            name=extract_name_from_id(old_perm.id),
            display_name=old_perm.description or old_perm.id,
            scope=scope,
            scope_id=None  # Will be set by admin for platform/client perms
        )
        await new_perm.insert()
```

#### **5.2 Group Migration Script**

```python
# scripts/migrate_groups.py
async def migrate_groups_from_roles_to_permissions():
    """
    Migrate groups from having roles to having direct permissions
    """
    groups = await GroupModel.find_all().to_list()

    for group in groups:
        # Get all permissions from current roles
        all_permissions = set()
        for role_id in group.roles:
            role = await RoleModel.get(role_id)
            if role:
                all_permissions.update(role.permissions)

        # Update group with direct permissions
        group.permissions = list(all_permissions)
        group.roles = []  # Remove roles

        # Add scoping based on client_account
        if group.client_account:
            group.scope = GroupScope.CLIENT
            group.scope_id = str(group.client_account.id)

        await group.save()
```

## 🧪 **Testing Strategy**

### **Unit Tests**

- ✅ Permission model validation and scoping
- ✅ Group model with direct permissions
- ✅ User effective permission aggregation
- ✅ Service layer scoped operations

### **Integration Tests**

- ✅ Permission creation across scopes
- ✅ Group creation with permission validation
- ✅ User permission aggregation from roles + groups
- ✅ API endpoint authorization with new permissions

### **Migration Tests**

- ✅ Data migration integrity
- ✅ Permission mapping correctness
- ✅ Group role-to-permission conversion

## 📊 **Success Criteria**

### **Functional Requirements**

- ✅ Permissions scoped to system/platform/client levels
- ✅ Groups scoped to platform/client levels only
- ✅ Groups use direct permissions instead of roles
- ✅ Users get permissions from roles + groups combined
- ✅ Perfect tenant isolation maintained

### **Performance Requirements**

- ✅ Permission aggregation completes in <100ms
- ✅ Scoped queries use proper database indexes
- ✅ No N+1 query problems in group/permission lookups

### **Security Requirements**

- ✅ Platform permissions don't leak to other platforms
- ✅ Client permissions don't leak to other clients
- ✅ Group permissions respect scope boundaries
- ✅ Permission validation on all CRUD operations

## 🔄 **Migration Timeline**

### **Week 1**: Foundation

- Days 1-3: Phase 1 (Scoped Permissions)
- Days 4-5: Phase 2 (Enhanced Groups)

### **Week 2**: Integration

- Days 1-2: Phase 3 (User Permission Aggregation)
- Days 3-5: Phase 4 (API Routes)

### **Week 3**: Migration & Testing

- Days 1-2: Phase 5 (Data Migration)
- Days 3-5: Comprehensive testing and bug fixes

## 🚨 **Risk Mitigation**

### **Data Integrity**

- ✅ Run migration in staging first
- ✅ Backup database before migration
- ✅ Rollback plan prepared
- ✅ Gradual deployment with feature flags

### **Performance Impact**

- ✅ Database indexes planned for all queries
- ✅ Permission caching strategy
- ✅ Load testing with realistic data volumes

### **Breaking Changes**

- ✅ API versioning strategy
- ✅ Backward compatibility maintained during transition
- ✅ Client notification plan for API changes

## ✅ **Definition of Done**

- [ ] All 5 phases implemented and tested
- [ ] Data migration scripts tested and documented
- [ ] API documentation updated
- [ ] All existing tests still pass
- [ ] New tests achieve >95% coverage
- [ ] Performance benchmarks met
- [ ] Security audit completed
- [ ] README.md updated with new architecture

**Estimated Total Time**: 2-3 weeks
**Priority**: High (Completes core RBAC architecture)
