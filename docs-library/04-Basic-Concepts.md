# Basic Concepts

**Tags**: #getting-started #concepts #terminology

Understanding these core concepts will help you use OutlabsAuth effectively.

---

## Authentication vs Authorization

### Authentication (AuthN)
**"Who are you?"**

The process of verifying a user's identity.

**Methods in OutlabsAuth**:
- Email/Password
- OAuth (Google, Facebook, GitHub)
- API Keys
- JWT Service Tokens

**Result**: User credentials → JWT access token

### Authorization (AuthZ)
**"What can you do?"**

The process of determining what an authenticated user is allowed to do.

**Methods in OutlabsAuth**:
- Role-Based Access Control (RBAC)
- Permission-Based Access Control
- Tree Permissions (hierarchical)
- Attribute-Based Access Control (ABAC)

**Result**: User + Permission + Context → Allow/Deny

---

## Core Concepts

### 1. User

A person or service that uses your application.

```python
{
    "id": "user_123",
    "email": "john@example.com",
    "is_active": true,
    "is_verified": true,
    "is_superuser": false,
    "created_at": "2025-01-23T10:00:00Z"
}
```

**Types**:
- **Regular User**: Normal application user
- **Verified User**: Email verified (can't login until verified if required)
- **Superuser**: Bypasses all permission checks (use sparingly!)
- **Service User**: For service-to-service communication

### 2. Role

A named collection of permissions.

```python
{
    "name": "editor",
    "description": "Can create and edit content",
    "permissions": [
        "content:create",
        "content:read",
        "content:update"
    ]
}
```

**Examples**:
- `admin` - Full access to everything
- `editor` - Can create and edit content
- `viewer` - Read-only access
- `moderator` - Can moderate user content

### 3. Permission

A specific action on a specific resource.

**Format**: `resource:action`

**Examples**:
- `user:read` - Can view users
- `user:create` - Can create users
- `user:update` - Can update users
- `user:delete` - Can delete users
- `project:read` - Can view projects
- `project:read_tree` - Can view project and all children (tree permission)

**Action Types**:
- `create` - Create new resources
- `read` - View resources
- `update` - Modify resources
- `delete` - Delete resources
- `read_tree` - Hierarchical read access
- `manage_tree` - Hierarchical full access

### 4. Entity (EnterpriseRBAC Only)

An organizational unit in the hierarchy.

```python
{
    "id": "entity_123",
    "name": "Engineering Department",
    "entity_type": "department",
    "parent_id": "company_root",
    "is_structural": true
}
```

**Types**:
- **STRUCTURAL**: Organizational container (company, department)
- **ACCESS_GROUP**: Permission boundary (team, project)

**Hierarchy Example**:
```
Company (STRUCTURAL)
├── Engineering (STRUCTURAL)
│   ├── Backend Team (ACCESS_GROUP)
│   └── Frontend Team (ACCESS_GROUP)
└── Sales (STRUCTURAL)
    └── Sales Team (ACCESS_GROUP)
```

### 5. Membership (EnterpriseRBAC Only)

Links a user to an entity with a specific role.

```python
{
    "user_id": "user_123",
    "entity_id": "backend_team",
    "role_name": "developer",
    "joined_at": "2025-01-23T10:00:00Z"
}
```

**Meaning**: User "user_123" is a "developer" in "backend_team"

---

## Authentication Concepts

### 6. JWT (JSON Web Token)

A cryptographically signed token containing user identity and claims.

**Access Token** (15 minutes):
```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyXzEyMyIsImV4cCI6MTY0MjU5NjAwMH0...
```

**Refresh Token** (30 days):
- Longer-lived token used to get new access tokens
- Stored securely (httpOnly cookie recommended)

**Claims**:
```json
{
  "sub": "user_123",        // Subject (user ID)
  "exp": 1642596000,        // Expiration timestamp
  "iat": 1642594200,        // Issued at timestamp
  "type": "access"          // Token type
}
```

### 7. API Key

A long-lived credential for programmatic access.

**Format**: `ola_1234567890abcdef1234567890abcdef`

**Structure**:
- `ola_` - Prefix (identifiable, scannable)
- `123456789...` - 12-character public ID
- Full key hashed with argon2id

**Usage**:
```bash
curl -H "X-API-Key: ola_1234567890abcdef..." https://api.example.com/users
```

**Features**:
- ✅ Hashed storage (argon2id)
- ✅ Rate limiting (per-key)
- ✅ Temporary locks (after failed attempts)
- ✅ Rotation support
- ✅ Revocation

### 8. OAuth State Token

A JWT token used for CSRF protection in OAuth flows.

**Purpose**: Prevent OAuth account hijacking attacks

**Contains**:
- `user_id` (for account linking)
- Expiration (10 minutes)
- Audience claim (prevents reuse)

**Stateless**: No database storage required!

---

## Authorization Concepts

### 9. RBAC (Role-Based Access Control)

Access control based on assigned roles.

**Flow**:
```
User → Has Role → Role Has Permissions → Check Permission
```

**Example**:
```python
# John has "editor" role
# "editor" role has "content:create" permission
# John tries to create content
# ✅ Allowed!
```

### 10. Tree Permissions (EnterpriseRBAC)

Hierarchical permissions that apply to entity subtrees.

**Example**:
```
Company
├── Engineering
│   ├── Backend Team
│   │   └── Project A
│   └── Frontend Team
│       └── Project B
```

**Grant** `project:read_tree` at "Engineering"
**Result**: User can read Project A AND Project B (entire subtree!)

**Use Cases**:
- Manager needs access to all team projects
- Department head needs reports from all teams
- Auditor needs view access to entire organization

### 11. Context-Aware Roles (EnterpriseRBAC)

Roles that change permissions based on entity type.

**Example**: "manager" role
- In **Department**: Can view all reports, manage budgets
- In **Team**: Can assign tasks, approve PRs
- In **Project**: Can edit settings, manage members

**Implementation**:
```python
{
    "name": "manager",
    "context_permissions": {
        "department": ["report:read", "budget:manage"],
        "team": ["task:assign", "pr:approve"],
        "project": ["settings:update", "member:manage"]
    }
}
```

### 12. ABAC (Attribute-Based Access Control)

Access control based on attributes and policies.

**Attributes**:
- **User attributes**: department, role, seniority
- **Resource attributes**: owner, created_at, sensitivity
- **Environment attributes**: time, location, IP

**Policy Example**:
```python
{
    "name": "Allow if owner or manager",
    "condition": {
        "or": [
            {"user.id": {"eq": "resource.owner_id"}},
            {"user.role": {"eq": "manager"}}
        ]
    }
}
```

---

## Key Patterns

### 13. Lifecycle Hooks

Overrideable methods for custom business logic.

**Example**:
```python
class MyUserService(UserService):
    async def on_after_register(self, user, request=None):
        # Send welcome email
        await email_service.send_welcome(user.email)

        # Create default workspace
        await workspace_service.create_default(user.id)

        # Track analytics
        await analytics.track("user_registered", user.id)
```

**Available Hooks**: 23 total
- User: 13 hooks (register, login, update, delete, verify, etc.)
- Role: 7 hooks (create, update, delete, assign, etc.)
- API Key: 6 hooks (create, use, rotate, revoke, etc.)

### 14. Transport/Strategy Pattern

Separation of credential delivery from validation.

**Transport**: How credentials are delivered
- BearerTransport: `Authorization: Bearer {token}`
- ApiKeyTransport: `X-API-Key: {key}`
- CookieTransport: Cookies
- HeaderTransport: Custom headers

**Strategy**: How credentials are validated
- JWTStrategy: Decode and validate JWT
- ApiKeyStrategy: Hash and compare API key
- ServiceTokenStrategy: Validate service token

**Composition**:
```python
backend = AuthBackend(
    name="jwt",
    transport=BearerTransport(),
    strategy=JWTStrategy(secret="secret")
)
```

### 15. Router Factories

Functions that generate pre-built FastAPI routers.

**Example**:
```python
# Generate auth router
auth_router = get_auth_router(auth)

# Returns router with:
# - POST /register
# - POST /login
# - POST /refresh
# - POST /logout
# - POST /forgot-password
# - POST /reset-password
```

**Benefits**:
- ✅ Rapid setup (2 lines)
- ✅ Consistent API
- ✅ Production-ready
- ✅ Customizable via parameters

---

## SimpleRBAC vs EnterpriseRBAC

### SimpleRBAC

**Best For**:
- Flat organizational structure
- Simple role-based permissions
- Quick setup and development

**Structure**:
```
Users → Roles → Permissions
```

**Example Use Cases**:
- Blog platforms
- Simple SaaS apps
- Internal tools
- APIs with basic auth

### EnterpriseRBAC

**Best For**:
- Hierarchical organizations
- Complex permission requirements
- Multi-tenant applications
- Enterprise software

**Structure**:
```
Entities (Hierarchy)
  ↓
Memberships (User → Entity → Role)
  ↓
Permissions (Context-aware)
```

**Example Use Cases**:
- Project management tools
- CRM systems
- Enterprise SaaS
- Multi-tenant platforms

---

## Common Workflows

### Workflow 1: User Registration & Login

```
1. User registers
   POST /auth/register
   ↓
2. User verifies email (optional)
   POST /auth/verify
   ↓
3. User logs in
   POST /auth/login
   ↓
4. Receive JWT tokens
   {access_token, refresh_token}
   ↓
5. Access protected routes
   Authorization: Bearer {access_token}
```

### Workflow 2: OAuth Login

```
1. Frontend requests authorization URL
   GET /auth/google/authorize
   ↓
2. User redirects to Google
   https://accounts.google.com/...
   ↓
3. User authenticates with Google
   ↓
4. Google redirects to callback
   GET /auth/google/callback?code=...
   ↓
5. Backend validates and creates/updates user
   ↓
6. Return JWT tokens
   {access_token, refresh_token}
```

### Workflow 3: Permission Check (SimpleRBAC)

```
1. User makes request
   DELETE /users/123
   ↓
2. Extract JWT from Authorization header
   ↓
3. Validate JWT signature and expiration
   ↓
4. Get user roles from database
   ↓
5. Get role permissions from database
   ↓
6. Check if "user:delete" in permissions
   ↓
7. Allow or deny request
```

### Workflow 4: Tree Permission Check (EnterpriseRBAC)

```
1. User requests access to Project A
   GET /projects/project_a
   ↓
2. Get project's entity_id
   ↓
3. Get all user's entity memberships
   ↓
4. For each membership:
   - Check direct permission in project's entity
   - Check tree permissions in ancestor entities
   ↓
5. Query closure table for ancestors
   ↓
6. Find "project:read_tree" in any ancestor
   ↓
7. ✅ Allow access!
```

---

## Security Principles

### 1. Defense in Depth
Multiple layers of security:
- JWT signature validation
- Token expiration checks
- Permission verification
- Rate limiting
- CSRF protection (OAuth)

### 2. Principle of Least Privilege
Users get minimum permissions needed:
- Start with no permissions
- Grant only what's needed
- Revoke unused permissions

### 3. Secure by Default
- API keys hashed at rest
- OAuth state tokens signed
- CSRF protection enabled
- Short JWT expiration (15 min)
- `associate_by_email` defaults to False

### 4. Audit Trail
Track security events:
- Login attempts (success/fail)
- Permission changes
- Role assignments
- API key usage
- OAuth account linking

---

## Performance Concepts

### Closure Table

O(1) tree queries using pre-computed ancestor relationships.

**Traditional Recursive Query**: O(n) - Slow!
**Closure Table**: O(1) - Fast! (~20x improvement)

See [[53-Closure-Table|Closure Table Deep Dive]]

### Redis Caching

Cache frequently accessed data:
- Permission checks (hit rate: ~95%)
- Role lookups (hit rate: ~98%)
- Entity hierarchies (hit rate: ~90%)

**Impact**: 10x-100x faster permission checks

### Redis Counters

Track API key usage without database writes:
- Counter in Redis (fast)
- Periodic flush to MongoDB (batched)
- 99%+ reduction in write operations

### Redis Pub/Sub

Invalidate caches across multiple instances:
- Permission change → Pub/Sub message
- All instances invalidate cache
- <100ms propagation time

---

## Next Steps

Now that you understand the basics:

1. **[[41-SimpleRBAC|SimpleRBAC Guide]]** - Start with flat RBAC
2. **[[42-EnterpriseRBAC|EnterpriseRBAC Guide]]** - Explore hierarchical RBAC
3. **[[30-OAuth-Overview|OAuth Overview]]** - Add social login
4. **[[110-Security-Best-Practices|Security Best Practices]]** - Secure your app

---

**Previous**: [[02-Quick-Start|← Quick Start]]
**Next**: [[41-SimpleRBAC|SimpleRBAC Guide →]]
