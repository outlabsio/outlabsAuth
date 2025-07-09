# outlabsAuth Architecture Guide

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        External Platforms                         │
├─────────────────┬─────────────────┬─────────────┬───────────────┤
│  Diverse Leads  │ Referral Broker │     uaya    │    qdarte     │
│   (Nuxt.js)     │ (React+FastAPI) │ (Flutter)   │  (Next.js)    │
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
# Platform - Root of everything
PlatformModel:
  - id: str
  - name: str
  - slug: str
  - entity_config: EntityConfig
  - settings: dict

# Entity - Unified model for orgs and groups
EntityModel:
  - id: str
  - name: str
  - entity_class: "structural" | "access_group"
  - entity_type: "organization" | "team" | "permission_group" | etc
  - platform_id: str
  - parent_entity: Link[EntityModel]
  - metadata: dict

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

## Entity Hierarchy System

### Structural Entities
Form the organizational backbone:
```
Platform (Diverse)
└── Organization (Diverse Leads)
    ├── Branch (Miami Office)
    │   └── Team (Sales Team)
    └── Division (Corporate)
```

### Access Groups (as Entities)
Provide flexible permissions:
```
Miami Office
├── [Structural] Sales Team
├── [Access Group] VIP Handlers
├── [Access Group] Admin Group
└── [Access Group] Q4 Project Team
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
    # e.g., ["lead:read", "lead:create", "report:view_team"]
    
    # Scoping
    entity: Link[EntityModel]  # Which entity owns this role
    assignable_at_types: List[EntityType]  # Where it can be assigned
    # e.g., ["branch", "team"] means assignable at branch or team level
    
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