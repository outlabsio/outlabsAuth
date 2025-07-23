# outlabsAuth Architecture Guide

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        External Platforms                         │
├─────────────────┬─────────────────┬─────────────┬───────────────┤
│  Diverse Leads  │ Referral Broker │     uaya    │    qdarte     │
│   (Nuxt.js)     │ (Nuxt+FastAPI)  │ (Flutter)   │  (Next.js)    │
└────────┬────────┴────────┬────────┴──────┬──────┴───────┬───────┘
         │                 │                │              │
         └─────────────────┴────────────────┴──────────────┘
                                  │
                           API Gateway (HTTPS)
                                  │
┌─────────────────────────────────┴─────────────────────────────────┐
│                         outlabsAuth API                            │
├────────────────────────────────────────────────────────────────────┤
│  - Authentication Service    - Authorization Service               │
│  - User Management          - Entity Management                   │
│  - Role Management          - Permission Management               │
└────────────────────────────────────────────────────────────────────┘
                                  │
┌─────────────────────────────────┴─────────────────────────────────┐
│                          MongoDB Database                          │
│  Collections: users, entities, roles, permissions, tokens         │
└────────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. API Layer (FastAPI)

The API provides RESTful endpoints for all authentication and authorization operations:

```python
/v1/auth/          # Authentication endpoints
/v1/users/         # User management
/v1/entities/      # Entity management (orgs, teams, groups)
/v1/roles/         # Role management
/v1/permissions/   # Permission management
/v1/platforms/     # Platform configuration
```

### 2. Service Layer

Clean separation of concerns with dedicated services:

```python
AuthService        # Login, logout, token management
UserService        # User CRUD, profile management
EntityService      # Entity hierarchy, memberships
PermissionService  # Permission checking, inheritance
RoleService        # Role assignment, management
```

### 3. Data Models (Beanie ODM)

#### Core Models

```python
# Entity - The unified model for all organizational structures
EntityModel:
  - id: str
  - name: str  # System identifier (lowercase, no spaces)
  - display_name: str  # User-friendly name
  - entity_class: "STRUCTURAL" | "ACCESS_GROUP"
  - entity_type: str  # Flexible: "organization", "division", "region", or any custom type
  - platform_id: str
  - parent_entity: Link[EntityModel]
  - metadata: dict  # Flexible configuration data

# User - Platform users
UserModel:
  - id: str
  - email: str
  - profile: UserProfile
  - is_active: bool
  - is_system_user: bool

# EntityMembership - User's relationship to entities
EntityMembershipModel:
  - user: Link[UserModel]
  - entity: Link[EntityModel]
  - role_in_entity: str
  - joined_at: datetime

# Permission - Custom business permissions
PermissionModel:
  - id: str
  - name: str  # e.g., "lead:create", "invoice:approve"
  - display_name: str
  - description: str
  - resource: str  # e.g., "lead", "invoice"
  - action: str  # e.g., "create", "approve"
  - scope: Optional[str]  # e.g., "team", "department"
  - entity_id: Optional[str]  # Scoped to specific entity
  - is_system: bool  # Built-in vs custom
  - is_active: bool
  - tags: List[str]
  - metadata: dict  # Business rules, conditions
```

## Authentication Flow

### 1. Login Process

```sequence
Platform App -> outlabsAuth: POST /v1/auth/login {email, password}
outlabsAuth -> Database: Validate credentials
outlabsAuth -> outlabsAuth: Generate tokens
outlabsAuth -> Database: Store refresh token
outlabsAuth -> Platform App: Return {access_token, refresh_token, user}
Platform App -> Platform App: Store tokens locally
```

### 2. Token Validation

```python
# Every API request includes
Authorization: Bearer <access_token>

# outlabsAuth validates:
1. Token signature
2. Token expiration
3. User still active
4. Platform access
```

### 3. Permission Checking

```sequence
Platform App -> outlabsAuth: GET /v1/users/me/permissions?context=entity_123
outlabsAuth -> Database: Get user's entities
outlabsAuth -> Database: Get entity roles
outlabsAuth -> Database: Get role permissions
outlabsAuth -> outlabsAuth: Apply inheritance rules
outlabsAuth -> Platform App: Return ["lead:read", "lead:create", ...]
```

## Platform and Entity System

### Key Concept: Platforms are Top-Level Entities

In OutlabsAuth, **there is no separate "Platform" model**. Instead, any entity without a parent is effectively a platform. This elegant design provides maximum flexibility:

- **Top-level entities** (entities with `parent_entity = null`) are your platforms
- These can have **any entity_type**: "platform", "workspace", "company", "account", "tenant", or whatever fits your business model
- The **platform_id** of a top-level entity is its own ID
- All child entities inherit their **platform_id** from their parent chain

This design means you can:
- Name your top-level entities based on your business terminology
- Create multiple isolated platforms in the same system
- Have different organizational structures under each platform
- Maintain complete data isolation between platforms

Example top-level entities (all are platforms):
```python
# A SaaS company might use "workspace"
{
  "name": "acme_workspace",
  "entity_type": "workspace",
  "parent_entity": null,  # This makes it a platform
  "platform_id": "self"   # Will be set to its own ID
}

# An enterprise might use "company"
{
  "name": "megacorp",
  "entity_type": "company",
  "parent_entity": null,  # This makes it a platform
  "platform_id": "self"   # Will be set to its own ID
}

# A government agency might use "agency"
{
  "name": "dept_of_example",
  "entity_type": "agency",
  "parent_entity": null,  # This makes it a platform
  "platform_id": "self"   # Will be set to its own ID
}
```

## Entity Hierarchy System

### Flexible Entity Types
Once you have your top-level entity (platform), you can build any organizational structure beneath it:

**Traditional Corporate Structure:**
```
Platform (Acme Corp)
└── Organization (Acme Industries)
    ├── Division (Sales Division)
    │   ├── Department (Enterprise Sales)
    │   │   └── Unit (West Coast Unit)
    │   └── Department (SMB Sales)
    └── Division (Engineering Division)
```

**Real Estate Platform:**
```
Platform (Diverse)
└── Organization (Diverse Leads)
    ├── Region (West Coast)
    │   ├── Office (Los Angeles Office)
    │   │   └── Team (Luxury Properties Team)
    │   └── Office (Seattle Office)
    └── Region (East Coast)
```

**Government Agency:**
```
Platform (City Services)
└── Organization (Municipal Government)
    ├── Bureau (Transportation Bureau)
    │   ├── Section (Roads & Highways)
    │   └── Section (Public Transit)
    └── Bureau (Public Safety Bureau)
```

### Entity Classes (Fixed)
While entity types are flexible, entity classes remain fixed:

1. **STRUCTURAL**: Forms the organizational hierarchy
   - Can contain other structural entities or access groups
   - Examples: Any organizational unit (division, office, team, etc.)

2. **ACCESS_GROUP**: Cross-cutting permission groups
   - Can only contain other access groups
   - Examples: admin_group, viewer_group, project_team, committee

### Access Groups (as Entities)
Provide flexible permissions across the hierarchy:
```
Los Angeles Office
├── [Structural] Luxury Properties Team
├── [Access Group] VIP Client Handlers
├── [Access Group] Regional Admins
└── [Access Group] Q4 Sales Initiative
```

### Permission Inheritance

```python
# Permissions flow down the hierarchy
Platform Admin: platform:manage_all
    ↓ includes
Organization Admin: organization:manage_all
    ↓ includes
Branch Manager: branch:manage_all
    ↓ includes
Team Lead: team:manage_all
```

## Role System: Context-Aware Roles

Unlike traditional RBAC systems where roles are globally assigned to users, outlabsAuth implements **Context-Aware Roles** where roles are assigned through entity memberships. This provides maximum flexibility while maintaining clean architecture.

### How Roles Work

#### 1. Role Definition
```python
class RoleModel(BaseDocument):
    # Identity
    name: str  # e.g., "agent", "team_lead", "branch_manager"
    display_name: str
    description: str
    
    # Permissions this role grants
    permissions: List[str] = Field(default_factory=list)
    # e.g., ["user:read", "lead:create", "report:view_quarterly"]
    # These are validated against system and custom permissions
    
    # Scoping
    entity: Link[EntityModel]  # Which entity owns this role
    assignable_at_types: List[str]  # Flexible entity types where it can be assigned
    # e.g., ["office", "team"] means assignable at office or team level
    
    # Metadata
    is_system_role: bool = False  # Platform-defined vs custom
```

#### 2. Role Assignment via Entity Membership
```python
class EntityMembershipModel(BaseDocument):
    user: Link[UserModel]
    entity: Link[EntityModel]
    
    # User's roles within THIS specific entity
    roles: List[Link[RoleModel]] = Field(default_factory=list)
    
    # Examples:
    # - Maria is an "agent" in Miami Office
    # - Maria is a "vip_specialist" in VIP Handlers Group
    # - John is a "team_lead" in Sales Team
    # - John is a "compliance_officer" in Compliance Group
```

### Real-World Role Examples

#### Platform-Level Roles (Diverse Platform)
```yaml
Roles created at platform level:
  - platform_admin:
      permissions: ["platform:manage_all", "organization:manage_all"]
      assignable_at: ["platform"]
      
  - organization_admin:
      permissions: ["organization:manage", "branch:create", "user:manage_platform"]
      assignable_at: ["organization"]
```

#### Organization-Level Roles (Diverse Leads)
```yaml
Roles created by Diverse Leads:
  - branch_manager:
      permissions: ["branch:manage", "team:create", "user:manage_branch", "report:view_branch"]
      assignable_at: ["branch"]
      
  - agent:
      permissions: ["lead:read", "lead:create", "lead:update_own", "client:read"]
      assignable_at: ["branch", "team"]
      
  - team_lead:
      permissions: ["team:manage", "lead:assign", "report:view_team", "user:view_team"]
      assignable_at: ["team"]
```

#### Access Group Roles (Miami Office)
```yaml
Roles for specific groups:
  - vip_specialist:
      permissions: ["lead:vip_access", "commission:premium_rate", "client:vip_notes"]
      assignable_at: ["functional_group"]
      
  - compliance_officer:
      permissions: ["audit:perform", "report:compliance", "user:audit_trail"]
      assignable_at: ["permission_group"]
```

### Multi-Context Example

**Maria's Journey:**

1. **Joins Miami Office as Agent**
```json
{
  "membership_id": "mem_001",
  "user": "Maria",
  "entity": "Miami Office",
  "roles": ["agent"]
}
// Permissions: lead:read, lead:create, lead:update_own
```

2. **Joins VIP Handlers Group**
```json
{
  "membership_id": "mem_002",
  "user": "Maria",
  "entity": "VIP Handlers",
  "roles": ["vip_specialist"]
}
// Additional permissions: lead:vip_access, commission:premium_rate
```

3. **Promoted to Team Lead of Sales Team**
```json
{
  "membership_id": "mem_003",
  "user": "Maria",
  "entity": "Sales Team",
  "roles": ["team_lead"]
}
// Additional permissions: team:manage, lead:assign, report:view_team
```

**Total Permissions**: Maria now has permissions from ALL her roles across different entities.

### Role Management APIs

#### Create Role for Entity
```http
POST /v1/entities/{entity_id}/roles
{
  "name": "senior_agent",
  "display_name": "Senior Agent",
  "permissions": [
    "lead:read",
    "lead:create",
    "lead:update",
    "lead:delete_own",
    "report:view_personal"
  ],
  "assignable_at_types": ["branch", "team"]
}
```

#### Assign Role to User
```http
POST /v1/entities/{entity_id}/members/{user_id}/roles
{
  "role_ids": ["role_senior_agent", "role_mentor"]
}
```

### Permission Resolution with Roles

```python
async def get_user_permissions(user: UserModel, context: EntityModel) -> Set[str]:
    permissions = set()
    
    # Get all user's entity memberships
    memberships = await EntityMembershipModel.find(
        EntityMembershipModel.user.id == user.id,
        fetch_links=True
    ).to_list()
    
    for membership in memberships:
        # Check if membership is active and valid
        if not membership.is_active():
            continue
            
        # Get permissions from roles in this membership
        for role in membership.roles:
            permissions.update(role.permissions)
        
        # Context-aware: Extra permissions if accessing child entities
        if membership.entity.is_ancestor_of(context):
            # Add hierarchical permissions
            permissions.add(f"{context.entity_type}:manage")
    
    return permissions
```

### Benefits of Context-Aware Roles

1. **Flexibility**: Same user can have different roles in different contexts
2. **Granularity**: Roles can be scoped to specific entity types
3. **Clarity**: Clear understanding of "who can do what where"
4. **Scalability**: No role explosion - roles are contextual
5. **Auditability**: Easy to see all roles a user has across entities

### Role Visibility and Scoping Rules

#### Role Creation and Ownership
When a role is created within an entity, it follows these visibility rules:

1. **Default Visibility**: A role created in an entity is only assignable within that entity and its descendants
2. **Inheritance Path**: Roles flow DOWN the hierarchy, not up
3. **Platform Exception**: Platform-level roles can be marked as "globally assignable"

```python
# Miami Office creates a role
miami_senior_agent = RoleModel(
    name="senior_agent",
    entity=miami_office,  # Owner entity
    assignable_at_types=["branch", "team"],  # Can be assigned at these levels
    # This role is ONLY available within Miami Office and its child entities
)

# Platform creates a global role
platform_auditor = RoleModel(
    name="platform_auditor",
    entity=diverse_platform,
    assignable_at_types=["platform", "organization", "branch"],
    is_global=True  # Available across entire platform
)
```

#### Role Assignment Rules
```python
# Valid: Assigning Miami's role to someone in Miami
membership = EntityMembershipModel(
    user=user,
    entity=miami_office,
    roles=[miami_senior_agent]  # ✓ Valid
)

# Invalid: Assigning Miami's role to someone in California
membership = EntityMembershipModel(
    user=user,
    entity=california_branch,
    roles=[miami_senior_agent]  # ✗ Invalid - role not visible here
)
```

### Permission Inheritance Patterns

#### 1. Hierarchical Permission Flow
Permissions flow both from roles AND entity hierarchy:

```python
async def get_user_permissions(user: UserModel, context: EntityModel) -> Set[str]:
    permissions = set()
    
    # Get all user's memberships
    memberships = await EntityMembershipModel.find(
        EntityMembershipModel.user.id == user.id,
        fetch_links=True
    ).to_list()
    
    for membership in memberships:
        # 1. Direct role permissions
        for role in membership.roles:
            permissions.update(role.permissions)
        
        # 2. Hierarchical permissions
        # If user has role in parent, they get read access to children
        if membership.entity.is_ancestor_of(context):
            permissions.add(f"{context.entity_type}:read")
            
            # If they have management role in parent, they can manage children
            if any("manage" in role.name for role in membership.roles):
                permissions.add(f"{context.entity_type}:manage")
    
    return permissions
```

#### 2. Example: Maria's Permission Resolution
```yaml
Maria's Memberships:
  1. Miami Office - Role: agent
     Permissions: [lead:read, lead:create]
     
  2. Sales Team (child of Miami) - Role: team_lead
     Permissions: [team:manage, lead:assign]
     
  3. VIP Handlers (access group in Miami) - Role: vip_specialist
     Permissions: [lead:vip_access]

When accessing a lead in Sales Team context:
  - From membership #1: lead:read, lead:create (role permissions)
  - From membership #2: team:manage, lead:assign (role permissions)
  - From membership #3: lead:vip_access (if VIP lead)
  - From hierarchy: team:read (parent has access to child)
  
Total: All above permissions combined
```

### Managing Role Updates

#### Updating Existing Memberships
```http
# Add role to existing membership
POST /v1/memberships/{membership_id}/roles
{
  "role_id": "role_senior_agent"
}

# Remove role from membership
DELETE /v1/memberships/{membership_id}/roles/{role_id}

# Replace all roles (promotion scenario)
PUT /v1/memberships/{membership_id}/roles
{
  "role_ids": ["role_senior_agent", "role_mentor"]
}
```

#### Role Promotion Example
```python
# Promote Maria from agent to senior_agent in Miami Office
membership = await EntityMembershipModel.find_one(
    EntityMembershipModel.user.id == maria.id,
    EntityMembershipModel.entity.id == miami_office.id
)

# Remove old role
membership.roles = [r for r in membership.roles if r.name != "agent"]

# Add new role
senior_role = await RoleModel.find_one(
    RoleModel.name == "senior_agent",
    RoleModel.entity.id == miami_office.id
)
membership.roles.append(senior_role)

await membership.save()
```

### Preventing Circular Dependencies

The system includes protection against circular role/permission dependencies:

```python
class PermissionService:
    async def resolve_permissions(
        self, 
        starting_permissions: Set[str], 
        visited: Set[str] = None
    ) -> Set[str]:
        if visited is None:
            visited = set()
        
        resolved = set(starting_permissions)
        to_process = list(starting_permissions)
        
        while to_process:
            perm = to_process.pop()
            
            # Cycle detection
            if perm in visited:
                logger.warning(f"Circular dependency detected: {perm}")
                continue
                
            visited.add(perm)
            
            # Get implied permissions
            implied = PERMISSION_IMPLICATIONS.get(perm, [])
            for imp in implied:
                if imp not in resolved:
                    resolved.add(imp)
                    to_process.append(imp)
        
        return resolved
```

This approach provides a powerful, flexible role system that adapts to any organizational structure while maintaining clean separation of concerns and preventing common pitfalls.

## Hybrid Authorization System (RBAC + ReBAC + ABAC)

outlabsAuth implements a powerful hybrid authorization model that combines three proven access control paradigms:

- **RBAC (Role-Based Access Control)**: Roles define base permissions
- **ReBAC (Relationship-Based Access Control)**: Entity relationships provide context
- **ABAC (Attribute-Based Access Control)**: Conditions enable granular, context-aware control

### Permission Architecture

#### 1. Enhanced Permission Model
```python
# Represents a single condition for ABAC
class Condition(BaseModel):
    # The attribute to check (dot-notation for nested attributes)
    # e.g., "user.department", "resource.value", "environment.time"
    attribute: str
    
    # The operator for comparison
    # e.g., "EQUALS", "LESS_THAN", "GREATER_THAN", "IN", "CONTAINS"
    operator: str
    
    # The value to compare against (can be static or dynamic reference)
    value: Any  # Can be number, string, list, or {"ref": "user.spending_limit"}

class PermissionModel(BaseDocument):
    # Identity
    name: str  # e.g., "lead:create", "invoice:approve"
    display_name: str  # Human-readable name
    description: str
    
    # Structure (auto-derived from name)
    resource: str  # e.g., "lead", "invoice"
    action: str  # e.g., "create", "approve"
    scope: Optional[str]  # e.g., "team", "department"
    
    # Ownership
    entity_id: Optional[str]  # Scoped to specific entity
    is_system: bool  # Built-in vs custom
    is_active: bool
    
    # ABAC Support - NEW
    conditions: List[Condition] = Field(default_factory=list)
    
    # Metadata
    tags: List[str]  # For categorization
    metadata: dict  # Legacy - being phased out in favor of conditions
```

#### 2. System vs Custom Permissions

**System Permissions** (Built-in, immutable):
```python
SYSTEM_PERMISSIONS = {
    # User management
    "user:read", "user:create", "user:manage", "user:manage_client",
    
    # Entity management
    "entity:read", "entity:create", "entity:manage", "entity:manage_all",
    
    # Role management
    "role:read", "role:create", "role:manage", "role:assign",
    
    # Permission management
    "permission:read", "permission:create", "permission:manage",
    
    # Wildcards
    "*:manage_all", "*:read_all"
}
```

**Custom Permissions** (Platform-specific):
```python
# CRM Platform
"lead:create", "lead:assign", "lead:convert",
"opportunity:close", "commission:calculate"

# E-commerce Platform
"product:publish", "order:refund", "discount:create",
"inventory:manage", "report:view_revenue"

# Healthcare Platform
"patient:view", "prescription:create", "prescription:approve",
"appointment:schedule", "billing:submit"
```

### Permission Creation and Management

#### 1. Creating Conditional Permissions
```python
# Platform creates a permission with ABAC conditions
permission = await PermissionModel.create({
    "name": "invoice:approve",
    "display_name": "Approve Invoices",
    "description": "Allows approving invoices for payment",
    "tags": ["finance", "accounting"],
    "conditions": [
        {
            "attribute": "resource.value",
            "operator": "LESS_THAN_OR_EQUAL",
            "value": 50000
        },
        {
            "attribute": "resource.status",
            "operator": "EQUALS",
            "value": "pending_approval"
        }
    ]
})

# Backward compatible - permissions without conditions work as before
simple_permission = await PermissionModel.create({
    "name": "lead:read",
    "display_name": "Read Leads",
    "description": "View lead information"
    # No conditions - always granted if user has permission
})
```

#### 2. Permission Validation in Roles
```python
# When creating/updating roles, permissions are validated
role = await RoleModel.create({
    "name": "sales_manager",
    "permissions": [
        "user:read",          # System permission
        "lead:create",        # Custom permission
        "lead:assign",        # Custom permission
        "report:view_sales"   # Custom permission
    ]
})

# Validation ensures all permissions exist and are active
```

### Policy Evaluation Engine

The permission system now includes a full policy evaluation engine that handles RBAC, ReBAC, and ABAC checks:

```python
async def check_permission(
    user: UserModel,
    permission: str,
    entity: EntityModel,
    resource_attributes: Dict[str, Any] = None
) -> PermissionCheckResult:
    """
    Evaluate permission with full hybrid model support
    """
    # 1. RBAC Check - Does user have the permission through roles?
    user_permissions = await resolve_user_permissions(user, entity)
    if permission not in user_permissions:
        return PermissionCheckResult(
            allowed=False,
            reason="User lacks required permission",
            evaluation_details={
                "rbac_check": "failed",
                "missing_permission": permission
            }
        )
    
    # 2. ReBAC Check - Is the entity relationship valid?
    if not await check_entity_access(user, entity):
        return PermissionCheckResult(
            allowed=False,
            reason="Invalid entity relationship",
            evaluation_details={
                "rbac_check": "passed",
                "rebac_check": "failed"
            }
        )
    
    # 3. ABAC Check - Evaluate conditions if present
    permission_model = await PermissionModel.find_one({"name": permission})
    if permission_model and permission_model.conditions:
        # Gather all attributes for evaluation
        context = {
            "user": await gather_user_attributes(user),
            "resource": resource_attributes or {},
            "entity": await gather_entity_attributes(entity),
            "environment": await gather_environment_attributes()
        }
        
        # Evaluate each condition
        conditions_results = []
        for condition in permission_model.conditions:
            result = await evaluate_condition(condition, context)
            conditions_results.append({
                "condition": f"{condition.attribute} {condition.operator} {condition.value}",
                "result": "passed" if result else "failed"
            })
            
            if not result:
                return PermissionCheckResult(
                    allowed=False,
                    reason=f"Condition failed: {condition.attribute} {condition.operator} {condition.value}",
                    evaluation_details={
                        "rbac_check": "passed",
                        "rebac_check": "passed",
                        "conditions_evaluated": conditions_results
                    }
                )
    
    # All checks passed
    return PermissionCheckResult(
        allowed=True,
        reason="All authorization checks passed",
        evaluation_details={
            "rbac_check": "passed",
            "rebac_check": "passed",
            "conditions_evaluated": conditions_results if permission_model.conditions else []
        }
    )

async def evaluate_condition(condition: Condition, context: Dict[str, Any]) -> bool:
    """
    Evaluate a single ABAC condition
    """
    # Extract the attribute value using dot notation
    attribute_value = extract_attribute(condition.attribute, context)
    
    # Handle dynamic value references
    compare_value = condition.value
    if isinstance(compare_value, dict) and "ref" in compare_value:
        compare_value = extract_attribute(compare_value["ref"], context)
    
    # Perform the comparison based on operator
    return perform_comparison(attribute_value, condition.operator, compare_value)
```

### Permission Expansion Rules

System permissions support automatic expansion:
```python
PERMISSION_HIERARCHY = {
    "user": {
        "manage": ["read", "create", "update", "delete", "invite"],
        "manage_client": ["manage", "assign_roles", "bulk_operations"],
        "manage_platform": ["manage_client", "cross_client_operations"]
    },
    "entity": {
        "manage": ["read", "create", "update", "delete"],
        "manage_all": ["manage", "manage_children", "manage_members"]
    }
}
```

**Note**: Custom permissions do NOT automatically expand. If you want `lead:manage` to include other permissions, you must explicitly assign them all.

### Real-World Permission Examples

#### CRM Platform (Diverse Leads)
```yaml
Custom Permissions:
  Sales:
    - lead:create: "Create new leads"
    - lead:assign: "Assign leads to agents"
    - lead:convert: "Convert leads to opportunities"
    - commission:calculate: "Calculate agent commissions"
    
  Reporting:
    - report:view_sales: "View sales reports"
    - report:view_commission: "View commission reports"
    - report:export: "Export reports to CSV/PDF"
    
  Management:
    - branch:override_rules: "Override branch business rules"
    - agent:manage_quota: "Set agent quotas"
```

#### Healthcare Platform
```yaml
Custom Permissions:
  Clinical:
    - patient:view_history: "View full patient history"
    - prescription:write: "Write new prescriptions"
    - prescription:approve: "Approve controlled substances"
    - lab:order: "Order lab tests"
    
  Administrative:
    - appointment:schedule: "Schedule appointments"
    - billing:submit_claim: "Submit insurance claims"
    - billing:adjust: "Adjust billing amounts"
```

### Permission Checking Flow

```python
# 1. Route Protection
@router.post("/leads", dependencies=[Depends(require_permission("lead:create"))])
async def create_lead(data: LeadCreate):
    # Handler only executes if user has permission
    
# 2. Service Layer Check
async def assign_lead(lead_id: str, agent_id: str, current_user: UserModel):
    # Check permission in context
    if not await has_permission(current_user, "lead:assign", entity_id):
        raise HTTPException(403, "Cannot assign leads")
    
# 3. Conditional Logic
if await has_permission(user, "commission:approve"):
    # Show approval button
    commission.status = "pending_approval"
else:
    # Auto-approve if no approval required
    commission.status = "approved"
```

### Performance Considerations

1. **Permission Caching**: Resolved permissions are cached in Redis with entity-specific keys
2. **Bulk Validation**: Validate all permissions in a single query when creating/updating roles
3. **Lazy Loading**: Only load and validate custom permissions when actually checking them
4. **Index Strategy**: Indexes on `name`, `entity_id`, and `is_active` for fast lookups

## Security Architecture

### 1. Token Security
- JWT with RS256 signing
- Short-lived access tokens (15 min)
- Long-lived refresh tokens (30 days)
- Refresh token rotation

### 2. API Security
- HTTPS only
- CORS configuration per platform
- Rate limiting per API key
- Request signing for sensitive operations

### 3. Data Security
- Bcrypt password hashing
- Encrypted database connections
- Audit logging for all operations
- Data isolation between platforms

## Integration Patterns

### 1. Direct API Integration

```javascript
// Platform's backend service
class AuthClient {
  async validateUser(token) {
    const response = await fetch(`${AUTH_API}/v1/auth/validate`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    return response.json()
  }
  
  async checkPermission(userId, permission, context) {
    const response = await fetch(
      `${AUTH_API}/v1/users/${userId}/check-permission`,
      {
        method: 'POST',
        body: JSON.stringify({ permission, context })
      }
    )
    return response.json()
  }
}
```

### 2. SDK Integration (Future)

```python
# Python SDK example
from outlabs_auth import AuthClient

client = AuthClient(api_key="platform_key")

# Validate user
user = client.validate_token(token)

# Check permission
can_edit = client.check_permission(
    user_id=user.id,
    permission="lead:edit",
    context="entity_miami_office"
)
```

### 3. Webhook Integration

Platforms can subscribe to events:
- User created/updated/deleted
- Role assigned/removed
- Entity membership changed
- Permission updated

## Scalability Considerations

### 1. Caching Strategy
- Redis for token validation
- Permission cache with TTL
- Entity hierarchy cache

### 2. Database Optimization
- Indexed queries for permission checks
- Denormalized permission paths
- Read replicas for queries

### 3. API Performance
- Connection pooling
- Async request handling
- Batch operations support

## Deployment Architecture

### Production Setup
```
Load Balancer
    ├── API Server 1
    ├── API Server 2
    └── API Server N
         │
    MongoDB Cluster
    Redis Cluster
```

### Development Setup
```
Single API Server
    │
MongoDB Instance
Redis Instance
```

#### Future: SessionManagementModel (for Multi-Device Control)

To support future requirements like per-device logout, a session model will be introduced. This will not require changes to the core authentication flow but will augment it.

```python
class SessionManagementModel(BaseDocument):
    user: Link[UserModel]
    refresh_token_family: str  # A unique ID linking all rotated refresh tokens for one session
    device_info: str          # User-Agent, etc.
    ip_address: str
    last_active: datetime
    created_at: datetime
```

## Monitoring & Observability

### 1. Metrics
- API response times
- Token validation performance
- Permission check latency
- Database query performance

### 2. Logging
- Structured JSON logs
- Correlation IDs for request tracking
- Audit logs for security events

### 3. Alerts
- Failed login attempts
- Permission denied events
- System performance degradation
- Token validation failures