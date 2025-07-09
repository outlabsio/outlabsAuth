# outlabsAuth API Specification

## Base URL
```
Production: https://api.auth.outlabs.com
Development: http://localhost:8030
```

## Authentication

### Web Clients
Authentication is handled via HttpOnly cookies set by the server. Include CSRF token for state-changing requests:
```
X-CSRF-Token: <csrf_token>
```

### Mobile/Native Clients
Include Bearer token in Authorization header:
```
Authorization: Bearer <access_token>
X-Client-Type: mobile
```

### API Key Authentication
For server-to-server calls, use API key:
```
X-API-Key: plat_diverse_leads_sk_live_xyz123
```

## API Endpoints

### Authentication Endpoints

#### POST /v1/auth/login
Authenticate a user and receive tokens.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "secure_password",
  "platform_id": "plat_diverse_leads"  // Optional, for platform-specific login
}
```

**Response (Web Clients):**
```json
{
  "user": {
    "id": "user_123",
    "email": "user@example.com",
    "profile": {
      "first_name": "Maria",
      "last_name": "Garcia"
    },
    "entities": [
      {
        "id": "ent_miami_office",
        "name": "Miami Office",
        "entity_type": "branch",
        "role_in_entity": "member"
      }
    ]
  },
  "csrf_token": "f47c4d3b-1a2e-4e3d-9f6a...",
  "expires_in": 900
}

// Note: Access and refresh tokens are set as HttpOnly cookies
```

**Response (Mobile Clients):**
```json
{
  "user": {
    "id": "user_123",
    "email": "user@example.com",
    "profile": {
      "first_name": "Maria",
      "last_name": "Garcia"
    },
    "entities": [
      {
        "id": "ent_miami_office",
        "name": "Miami Office",
        "entity_type": "branch",
        "role_in_entity": "member"
      }
    ]
  },
  "tokens": {
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "refresh_token": "f47c4d3b-1a2e-4e3d-9f6a...",
    "token_type": "bearer",
    "expires_in": 900
  }
}
```

#### POST /v1/auth/refresh
Refresh an access token using a refresh token. Implements token rotation.

**Request (Mobile):**
```json
{
  "refresh_token": "f47c4d3b-1a2e-4e3d-9f6a..."
}
```

**Request (Web):**
```
// Refresh token sent automatically via cookie
```

**Response (Web):**
```json
{
  "csrf_token": "new_csrf_token_if_needed",
  "expires_in": 900
}

// Note: New tokens are set as HttpOnly cookies
```

**Response (Mobile):**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "new_f47c4d3b-1a2e...",  // New refresh token (rotation)
  "token_type": "bearer",
  "expires_in": 900
}
```

#### POST /v1/auth/logout
Invalidate a refresh token.

**Request:**
```json
{
  "refresh_token": "f47c4d3b-1a2e-4e3d-9f6a..."
}
```

**Response:**
```json
{
  "message": "Successfully logged out"
}
```

### User Management Endpoints

#### GET /v1/users/me
Get current user information.

**Response:**
```json
{
  "id": "user_123",
  "email": "user@example.com",
  "profile": {
    "first_name": "Maria",
    "last_name": "Garcia",
    "phone": "+1234567890",
    "avatar_url": "https://..."
  },
  "is_active": true,
  "created_at": "2024-01-15T10:00:00Z",
  "entities": [
    {
      "entity": {
        "id": "ent_miami_office",
        "name": "Miami Office",
        "entity_class": "structural",
        "entity_type": "branch"
      },
      "joined_at": "2024-01-20T10:00:00Z",
      "role_in_entity": "member"
    }
  ]
}
```

#### GET /v1/users/me/permissions
Get current user's permissions with optional context.

**Query Parameters:**
- `context` (optional): Entity ID for context-specific permissions
- `platform_id` (optional): Filter permissions by platform
- `include` (optional): Comma-separated list of additional data to include
  - `sources`: Include detailed source information for each permission

**Response (default):**
```json
{
  "permissions": [
    "lead:read",
    "lead:create",
    "user:read_self",
    "report:view_team"
  ]
}
```

**Response (with ?include=sources):**
```json
{
  "permissions": [
    "lead:read",
    "lead:create",
    "user:read_self",
    "report:view_team"
  ],
  "sources": {
    "lead:read": {
      "source": "entity",
      "entity_id": "ent_miami_office",
      "role": "agent"
    },
    "report:view_team": {
      "source": "group",
      "entity_id": "ent_team_leads",
      "role": "team_lead"
    }
  }
}
```

#### POST /v1/users/
Create a new user (requires admin permissions).

**Request:**
```json
{
  "email": "newuser@example.com",
  "password": "secure_password",
  "profile": {
    "first_name": "John",
    "last_name": "Doe"
  },
  "entity_id": "ent_miami_office",
  "platform_id": "plat_diverse_leads"
}
```

**Response:**
```json
{
  "id": "user_456",
  "email": "newuser@example.com",
  "profile": {
    "first_name": "John",
    "last_name": "Doe"
  },
  "created_at": "2024-01-15T10:00:00Z"
}
```

### User Invitation Endpoints

#### POST /v1/invitations/
Create an invitation for a new user.

**Request:**
```json
{
  "email": "newuser@example.com",
  "entity_id": "ent_miami_office",
  "role_ids": ["role_agent"],  // Optional: Pre-assign roles
  "expires_in_hours": 72,  // Optional: Default 72 hours
  "metadata": {  // Optional: Custom data
    "invited_by_name": "John Manager",
    "personal_message": "Welcome to the team!"
  }
}
```

**Response:**
```json
{
  "id": "inv_789",
  "email": "newuser@example.com",
  "entity": {
    "id": "ent_miami_office",
    "name": "Miami Office"
  },
  "roles": ["agent"],
  "expires_at": "2024-01-18T10:00:00Z",
  "created_at": "2024-01-15T10:00:00Z",
  "created_by": "user_123",
  "invitation_url": "https://auth.outlabs.com/invite/accept?token=eyJ..."
}
```

#### POST /v1/invitations/accept
Accept an invitation and create user account.

**Request:**
```json
{
  "invitation_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "password": "secure_password",
  "profile": {
    "first_name": "Jane",
    "last_name": "Smith",
    "phone": "+1234567890"
  }
}
```

**Response (Web):**
```json
{
  "user": {
    "id": "user_890",
    "email": "newuser@example.com",
    "profile": {
      "first_name": "Jane",
      "last_name": "Smith"
    }
  },
  "membership": {
    "entity_id": "ent_miami_office",
    "roles": ["agent"]
  },
  "csrf_token": "abc123..."
}

// Tokens set as HttpOnly cookies
```

**Response (Mobile):**
```json
{
  "user": {
    "id": "user_890",
    "email": "newuser@example.com",
    "profile": {
      "first_name": "Jane",
      "last_name": "Smith"
    }
  },
  "membership": {
    "entity_id": "ent_miami_office",
    "roles": ["agent"]
  },
  "tokens": {
    "access_token": "eyJ...",
    "refresh_token": "f47c...",
    "token_type": "bearer",
    "expires_in": 900
  }
}
```

#### GET /v1/invitations/{invitation_id}
Get invitation details (for displaying before acceptance).

**Response:**
```json
{
  "id": "inv_789",
  "email": "newuser@example.com",
  "entity": {
    "id": "ent_miami_office",
    "name": "Miami Office",
    "platform": {
      "id": "plat_diverse",
      "name": "Diverse Leads"
    }
  },
  "invited_by": {
    "name": "John Manager",
    "email": "john@example.com"
  },
  "expires_at": "2024-01-18T10:00:00Z",
  "status": "pending"  // pending, accepted, expired
}
```

### Entity Management Endpoints

#### GET /v1/entities/
List entities accessible to the user.

**Query Parameters:**
- `platform_id`: Filter by platform
- `entity_class`: Filter by class ("structural" or "access_group")
- `entity_type`: Filter by type ("organization", "team", "permission_group", etc.)
- `parent_id`: Filter by parent entity

**Response:**
```json
{
  "entities": [
    {
      "id": "ent_diverse_leads",
      "name": "Diverse Leads",
      "entity_class": "structural",
      "entity_type": "organization",
      "platform_id": "plat_diverse",
      "parent_entity_id": null,
      "metadata": {
        "employee_count": 150,
        "headquarters": "Miami, FL"
      },
      "member_count": 150,
      "child_count": 5
    },
    {
      "id": "ent_vip_handlers",
      "name": "VIP Handlers",
      "entity_class": "access_group",
      "entity_type": "functional_group",
      "platform_id": "plat_diverse",
      "parent_entity_id": "ent_miami_office",
      "metadata": {
        "description": "Agents handling VIP clients"
      },
      "member_count": 12
    }
  ],
  "total": 2
}
```

#### POST /v1/entities/
Create a new entity with optional initial members.

**Request:**
```json
{
  "name": "California Branch",
  "entity_class": "structural",
  "entity_type": "branch",
  "parent_entity_id": "ent_diverse_leads",
  "platform_id": "plat_diverse",
  "metadata": {
    "location": "Los Angeles, CA",
    "timezone": "PST"
  },
  "initial_members": [  // Optional: Add members during creation
    {
      "user_id": "user_creator",
      "role_ids": ["role_branch_manager"]
    }
  ]
}
```

**Response:**
```json
{
  "id": "ent_california_branch",
  "name": "California Branch",
  "entity_class": "structural",
  "entity_type": "branch",
  "created_at": "2024-01-15T10:00:00Z",
  "members": [
    {
      "user_id": "user_creator",
      "roles": ["branch_manager"],
      "joined_at": "2024-01-15T10:00:00Z"
    }
  ]
}
```

#### POST /v1/entities/{entity_id}/members
Add a member to an entity with optional role assignment.

**Request:**
```json
{
  "user_id": "user_123",
  "role_ids": ["role_agent"],  // Optional: Assign roles immediately
  "valid_until": "2024-12-31T23:59:59Z"  // Optional for temporary membership
}
```

**Response:**
```json
{
  "membership_id": "mem_456",
  "user_id": "user_123",
  "entity_id": "ent_vip_handlers",
  "roles": [
    {
      "id": "role_agent",
      "name": "agent",
      "display_name": "Real Estate Agent"
    }
  ],
  "joined_at": "2024-01-15T10:00:00Z",
  "joined_by": "user_admin",
  "valid_until": "2024-12-31T23:59:59Z"
}
```

### Role Management Endpoints

#### GET /v1/entities/{entity_id}/roles
List roles defined for a specific entity.

**Response:**
```json
{
  "roles": [
    {
      "id": "role_agent",
      "name": "agent",
      "display_name": "Real Estate Agent",
      "description": "Standard agent with lead management permissions",
      "permissions": [
        "lead:read",
        "lead:create",
        "lead:update_own",
        "client:read"
      ],
      "entity_id": "ent_miami_office",
      "assignable_at_types": ["branch", "team"],
      "is_system_role": false,
      "created_at": "2024-01-10T10:00:00Z"
    }
  ],
  "total": 1
}
```

#### POST /v1/entities/{entity_id}/roles
Create a new role for an entity.

**Request:**
```json
{
  "name": "senior_agent",
  "display_name": "Senior Agent",
  "description": "Experienced agent with additional permissions",
  "permissions": [
    "lead:read",
    "lead:create",
    "lead:update",
    "lead:delete_own",
    "report:view_team"
  ],
  "assignable_at_types": ["branch", "team"]
}
```

**Response:**
```json
{
  "id": "role_senior_agent",
  "name": "senior_agent",
  "display_name": "Senior Agent",
  "entity_id": "ent_miami_office",
  "created_at": "2024-01-15T10:00:00Z"
}
```

#### POST /v1/entities/{entity_id}/members/{user_id}/roles
Assign roles to a user within an entity membership.

**Request:**
```json
{
  "role_ids": ["role_agent", "role_mentor"]
}
```

**Response:**
```json
{
  "membership_id": "mem_123",
  "user_id": "user_123",
  "entity_id": "ent_miami_office",
  "roles": [
    {
      "id": "role_agent",
      "name": "agent",
      "display_name": "Real Estate Agent"
    },
    {
      "id": "role_mentor",
      "name": "mentor",
      "display_name": "Team Mentor"
    }
  ],
  "updated_at": "2024-01-15T10:00:00Z",
  "updated_by": "user_admin"
}
```

#### GET /v1/users/{user_id}/roles
Get all roles assigned to a user across all entities.

**Response:**
```json
{
  "roles_by_entity": [
    {
      "entity": {
        "id": "ent_miami_office",
        "name": "Miami Office",
        "entity_type": "branch"
      },
      "roles": ["agent", "mentor"]
    },
    {
      "entity": {
        "id": "ent_vip_handlers",
        "name": "VIP Handlers",
        "entity_type": "functional_group"
      },
      "roles": ["vip_specialist"]
    }
  ],
  "total_roles": 3
}
```

### Permission Management Endpoints

#### GET /v1/permissions/
List all permissions defined in the system.

**Query Parameters:**
- `platform_id`: Filter by platform
- `resource`: Filter by resource (e.g., "lead", "user")
- `action`: Filter by action (e.g., "create", "read")

**Response:**
```json
{
  "permissions": [
    {
      "id": "perm_lead_read",
      "name": "lead:read",
      "display_name": "View Leads",
      "description": "Ability to view lead information",
      "resource": "lead",
      "action": "read",
      "platform_id": "plat_diverse_leads"
    }
  ],
  "total": 1
}
```

#### POST /v1/permissions/check
Check if the authenticated user has a specific permission. User is identified from the provided token.

**Headers:**
```
Authorization: Bearer <access_token>
// OR cookie-based auth is used automatically
```

**Request:**
```json
{
  "permission": "lead:delete",
  "context": {
    "entity_id": "ent_miami_office",
    "resource_id": "lead_456"  // Optional: specific resource
  }
}
```

**Response:**
```json
{
  "allowed": true,
  "user": {  // User info included for single-call pattern
    "id": "user_123",
    "email": "user@example.com"
  },
  "reason": "Permission granted through role 'team_lead' in entity 'ent_miami_office'",
  "source": {
    "type": "role",
    "role_id": "role_team_lead",
    "entity_id": "ent_miami_office"
  }
}
```

### Platform Management Endpoints

#### GET /v1/platforms/
List platforms (system admins only).

**Response:**
```json
{
  "platforms": [
    {
      "id": "plat_diverse",
      "name": "Diverse",
      "slug": "diverse",
      "entity_config": {
        "allowed_types": ["organization", "division", "branch", "team"],
        "max_depth": 5,
        "allow_access_groups": true
      },
      "settings": {
        "sso_enabled": false,
        "mfa_required": false,
        "session_timeout": 3600
      },
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total": 1
}
```

## Error Responses

All errors follow a consistent format:

```json
{
  "error": {
    "code": "PERMISSION_DENIED",
    "message": "You do not have permission to perform this action",
    "details": {
      "required_permission": "user:create",
      "context": "ent_miami_office"
    }
  }
}
```

### Common Error Codes
- `AUTHENTICATION_FAILED`: Invalid credentials
- `TOKEN_EXPIRED`: Access token has expired
- `TOKEN_INVALID`: Token validation failed
- `PERMISSION_DENIED`: Insufficient permissions
- `RESOURCE_NOT_FOUND`: Requested resource doesn't exist
- `VALIDATION_ERROR`: Request validation failed
- `RATE_LIMIT_EXCEEDED`: Too many requests

## Security Headers

### Required Headers for State-Changing Requests (Web)
```
X-CSRF-Token: <csrf_token_from_login>
```

### Security Response Headers
All responses include:
```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
Content-Security-Policy: default-src 'self'
```

## Rate Limiting

API requests are rate limited based on the authentication method:
- Authentication endpoints: 5 requests per minute per IP
- Bearer token (user context): 1000 requests per minute
- API key (platform context): 10000 requests per minute
- Unauthenticated: 100 requests per minute per IP

Rate limit headers:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1640995200
```

## Pagination

List endpoints support pagination:

**Query Parameters:**
- `limit`: Number of results per page (default: 50, max: 100)
- `offset`: Number of results to skip

**Response Headers:**
```
X-Total-Count: 234
X-Page-Size: 50
X-Page-Number: 1
```

## Webhooks (Future)

Platforms can subscribe to events:

```json
POST /v1/webhooks/subscribe
{
  "platform_id": "plat_diverse_leads",
  "event_types": ["user.created", "user.role.assigned"],
  "endpoint_url": "https://diverse-leads.com/webhooks/auth",
  "secret": "webhook_secret_key"
}
```

Event payload:
```json
{
  "event_id": "evt_123",
  "event_type": "user.created",
  "timestamp": "2024-01-15T10:00:00Z",
  "platform_id": "plat_diverse_leads",
  "data": {
    "user_id": "user_456",
    "email": "newuser@example.com",
    "entity_id": "ent_miami_office"
  }
}