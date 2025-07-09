# outlabsAuth: Enterprise Authentication & Authorization Platform

## What is outlabsAuth?

outlabsAuth is a **standalone authentication and authorization platform** that provides identity management and access control as a service. It does **NOT** handle any business logic for the platforms that use it - it purely manages:

- **Authentication**: Who are you? (login, logout, tokens)
- **Authorization**: What can you do? (permissions, roles, access control)
- **Identity Management**: User accounts, profiles, and organizational structures

Think of it as "Auth0 meets AWS IAM" - a centralized service that multiple platforms can use for their authentication needs.

## Core Concept: Platform Agnostic

outlabsAuth is designed to serve multiple, completely different platforms:

- **Diverse Leads**: A real estate lead management system (might be built in Nuxt.js)
- **Referral Brokerage**: A referral network platform (might use React + FastAPI)
- **uaya**: A social platform (might be a mobile app with Flutter)
- **qdarte**: An art marketplace (might be built in Next.js)

Each platform has its own:
- Business logic
- User interface
- Database (for business data)
- API endpoints (for business operations)

But they all share:
- User authentication through outlabsAuth
- Permission checking through outlabsAuth
- User management through outlabsAuth

## How Platforms Integrate

### 1. API Integration
Platforms make API calls to outlabsAuth for:
```python
# Authenticate a user
POST /v1/auth/login
Response: { access_token, refresh_token, user_info }

# Check permissions
GET /v1/users/{user_id}/permissions?context=entity_123
Response: ["lead:create", "lead:read", "report:view"]

# Create users (if platform has permission)
POST /v1/users/
Body: { email, password, entity_id, platform_id }
```

### 2. Admin UI Options
Platforms have two choices for admin interfaces:

**Option A: Use outlabsAuth Admin UI**
- Platform admins log into outlabsAuth directly
- Manage users, roles, permissions through our UI
- Best for smaller platforms or early stages

**Option B: Build Custom Admin UI**
- Platform builds its own user management interface
- Uses outlabsAuth APIs behind the scenes
- Provides seamless experience for their users
- Example: Diverse Leads might have a "Team Management" section that internally calls outlabsAuth APIs

### 3. Token-Based Authentication
```javascript
// In a Nuxt.js app (Diverse Leads)
async function checkUserAccess(resource) {
  const token = localStorage.getItem('auth_token')
  
  // Call outlabsAuth to validate token and get permissions
  const response = await fetch('https://auth.outlabs.com/v1/users/me/permissions', {
    headers: { Authorization: `Bearer ${token}` }
  })
  
  const permissions = await response.json()
  return permissions.includes(`${resource}:read`)
}
```

## Key Features

### 1. Multi-Platform Support
- Each platform is isolated
- Users can belong to multiple platforms
- Permissions are platform-specific

### 2. Flexible Entity Structure
- Platforms define their own organizational hierarchy
- Support for simple (flat) to complex (multi-level) structures
- Entities can be structural (departments) or access groups (project teams)

### 3. Granular Permissions
- Resource-based permissions (user:create, lead:delete)
- **Custom permissions**: Platforms can define their own permissions
- System permissions for core operations
- Hierarchical permission inheritance (for system permissions)
- Context-aware permission checking
- Permission validation and management APIs

### 4. Enterprise Features
- SSO/SAML support (future)
- Audit logging
- API rate limiting
- Multi-factor authentication

## What outlabsAuth Does NOT Do

1. **Business Logic**: 
   - Doesn't know what a "lead" is in Diverse
   - Doesn't process payments for qdarte
   - Doesn't handle social features for uaya

2. **Data Storage**:
   - Only stores auth-related data (users, roles, permissions)
   - Platforms store their own business data

3. **UI/UX**:
   - Provides admin UI for auth management only
   - Platforms build their own user-facing interfaces

## Architecture Benefits

### For Platform Developers
- Don't reinvent authentication
- Focus on business logic
- Enterprise-grade security out of the box
- Scalable permission system

### For System Administrators
- Central user management
- Consistent security policies
- Single audit trail
- Cross-platform user insights

### For End Users
- Single sign-on across platforms (optional)
- Consistent permission model
- Secure authentication

## Real-World Example

**Scenario**: Maria is a real estate agent using Diverse Leads

1. **Morning Login**:
   - Maria opens Diverse Leads app
   - App redirects to outlabsAuth login
   - Maria enters credentials
   - outlabsAuth validates and returns tokens
   - Diverse Leads app stores tokens

2. **Viewing Leads**:
   - Maria clicks "View Leads"
   - Diverse Leads checks with outlabsAuth: "Can Maria view leads?"
   - outlabsAuth responds: "Yes, she has lead:read permission"
   - Diverse Leads shows the leads (from its own database)

3. **Admin Creates New Team**:
   - Miami manager logs into Diverse Leads
   - Goes to "Team Management" (custom UI)
   - Creates "Luxury Specialists" team
   - Behind scenes: Diverse Leads calls outlabsAuth API to create entity

This separation ensures:
- outlabsAuth handles auth complexity
- Diverse Leads focuses on real estate features
- Clean, maintainable architecture