# External API Integration Guide

This comprehensive guide covers how to integrate your application with OutlabsAuth, a centralized authentication and authorization service that provides JWT-based authentication, hierarchical RBAC, and multi-tenant platform isolation.

## Table of Contents

1. [Overview](#overview)
2. [Getting Started](#getting-started)
3. [Authentication Methods](#authentication-methods)
4. [Core API Endpoints](#core-api-endpoints)
5. [Entity Management](#entity-management)
6. [Permission System](#permission-system)
7. [Integration Patterns](#integration-patterns)
8. [Error Handling](#error-handling)
9. [Security Best Practices](#security-best-practices)
10. [Rate Limiting](#rate-limiting)

## Overview

OutlabsAuth is a FastAPI-based authentication service that provides:

- **JWT-based Authentication**: Secure token-based auth with refresh token support
- **Hierarchical RBAC**: Role-based access control with permission inheritance
- **Multi-tenant Isolation**: Complete platform separation for SaaS applications
- **Flexible Entity System**: Adaptable to any organizational structure
- **RESTful API**: Well-documented endpoints following REST conventions

### Key Concepts

1. **Platforms**: Top-level isolation boundaries (your application is a platform)
2. **Entities**: Organizational units (companies, divisions, teams) or access groups
3. **Roles**: Collections of permissions assigned to users within entities
4. **Permissions**: Granular access controls (resource:action format)

## Getting Started

### Prerequisites

- API endpoint: `https://api.auth.outlabs.com` (production) or `http://localhost:8030` (development)
- Platform credentials (platform_id and API key)
- HTTPS for production deployments

### Initial Setup

1. **Register Your Platform**: Contact OutlabsAuth to register your platform and receive:
   - Platform ID (e.g., `plat_property_hub`)
   - API Key (e.g., `plat_property_hub_sk_live_xyz123`)

2. **Configure Your Application**:
   ```env
   OUTLABS_AUTH_URL=https://api.auth.outlabs.com
   OUTLABS_PLATFORM_ID=plat_property_hub
   OUTLABS_API_KEY=plat_property_hub_sk_live_xyz123
   ```

## Authentication Methods

### 1. User Authentication (Login)

For end-user authentication, use the login endpoint with email/password:

```http
POST /v1/auth/login/json
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePassword123!"
}
```

**Response**:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "f47c4d3b-1a2e-4e3d-9f6a...",
  "token_type": "bearer",
  "expires_in": 900
}
```

### 2. Mobile/API Authentication

For mobile apps or API clients, use the mobile endpoints:

```http
POST /v1/auth/mobile/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePassword123!",
  "device_info": {
    "device_id": "iPhone-12345",
    "app_version": "1.2.3"
  }
}
```

### 3. Server-to-Server Authentication

For backend services, use API key authentication:

```http
GET /v1/entities
X-API-Key: plat_property_hub_sk_live_xyz123
X-Entity-Context-Id: ent_miami_office
```

### 4. Token Refresh

Refresh expired access tokens:

```http
POST /v1/auth/mobile/refresh
Content-Type: application/json

{
  "refresh_token": "f47c4d3b-1a2e-4e3d-9f6a..."
}
```

## Core API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/auth/login/json` | User login with email/password |
| POST | `/v1/auth/mobile/login` | Mobile app login |
| POST | `/v1/auth/refresh` | Refresh access token (web) |
| POST | `/v1/auth/mobile/refresh` | Refresh access token (mobile) |
| POST | `/v1/auth/logout` | Logout and revoke tokens |
| GET | `/v1/auth/me` | Get current user info |
| POST | `/v1/auth/register` | Register new user |

### Users

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/users` | List users (with filters) |
| GET | `/v1/users/{id}` | Get user details |
| POST | `/v1/users` | Create user |
| PATCH | `/v1/users/{id}` | Update user |
| DELETE | `/v1/users/{id}` | Delete user |
| GET | `/v1/users/{id}/permissions` | Get user permissions |
| GET | `/v1/users/{id}/entities` | Get user entity memberships |

### Entities

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/entities` | List entities |
| GET | `/v1/entities/{id}` | Get entity details |
| POST | `/v1/entities` | Create entity |
| PATCH | `/v1/entities/{id}` | Update entity |
| DELETE | `/v1/entities/{id}` | Delete entity |
| GET | `/v1/entities/{id}/members` | List entity members |
| POST | `/v1/entities/{id}/members` | Add member to entity |
| GET | `/v1/entities/entity-types` | Get entity type suggestions |

### Roles & Permissions

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/roles` | List roles |
| POST | `/v1/roles` | Create role |
| GET | `/v1/permissions` | List permissions |
| POST | `/v1/permissions/check` | Check user permission |

## Entity Management

### Entity Classes

OutlabsAuth supports two entity classes:

1. **STRUCTURAL**: Forms organizational hierarchy
   - Can contain other structural entities or access groups
   - Examples: company, division, department, team

2. **ACCESS_GROUP**: Cross-cutting permission groups
   - Can only contain other access groups
   - Examples: admin_group, project_team, committee

### Creating an Entity Hierarchy

```javascript
// Create your platform's root entity
const platform = await fetch(`${OUTLABS_AUTH_URL}/v1/entities`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${accessToken}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    name: 'property_hub_platform',
    display_name: 'Property Hub',
    entity_type: 'platform',
    entity_class: 'structural'
  })
});

// Create a brokerage under the platform
const brokerage = await fetch(`${OUTLABS_AUTH_URL}/v1/entities`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${accessToken}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    name: 'sunshine_realty',
    display_name: 'Sunshine Realty',
    entity_type: 'brokerage',
    entity_class: 'structural',
    parent_entity_id: platform.id,
    metadata: {
      license_number: 'BRK-12345',
      address: '123 Main St, Miami, FL'
    }
  })
});
```

### Entity Type Flexibility

Entity types are flexible strings, allowing you to use terminology that fits your business:

```javascript
// Property industry example
{
  entity_type: 'brokerage'    // Top-level real estate company
  entity_type: 'office'       // Regional office
  entity_type: 'team'         // Agent team
  entity_type: 'listing_group' // Access group for listing committee
}

// Other industry examples
{
  entity_type: 'hospital'     // Healthcare
  entity_type: 'store'        // Retail
  entity_type: 'warehouse'    // Logistics
}
```

## Permission System

### Permission Format

Permissions follow the pattern: `resource:action[_scope]`

- **resource**: What you're accessing (e.g., `user`, `property`, `lead`)
- **action**: What you're doing (e.g., `create`, `read`, `update`, `delete`)
- **scope**: Optional scope modifier (`_tree` for hierarchical, `_all` for platform-wide)

### Permission Scopes

1. **Entity-Specific**: `property:view` - View properties in assigned entity only
2. **Tree/Hierarchical**: `property:view_tree` - View properties in all child entities
3. **Platform-Wide**: `property:view_all` - View all properties in platform

### Checking Permissions

```javascript
const checkPermission = async (userId, permission, entityId) => {
  const response = await fetch(`${OUTLABS_AUTH_URL}/v1/permissions/check`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      user_id: userId,
      permission: permission,
      entity_id: entityId
    })
  });
  
  const result = await response.json();
  return result.allowed;
};

// Example usage
const canCreateListing = await checkPermission(
  currentUser.id,
  'listing:create',
  officeEntityId
);
```

## Integration Patterns

### 1. User Registration with Auto-Assignment

```javascript
const registerUser = async (userData) => {
  // 1. Create user in OutlabsAuth
  const userResponse = await fetch(`${OUTLABS_AUTH_URL}/v1/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email: userData.email,
      password: userData.password,
      first_name: userData.firstName,
      last_name: userData.lastName,
      phone: userData.phone
    })
  });
  
  const user = await userResponse.json();
  
  // 2. Add user to appropriate entity
  const membershipResponse = await fetch(
    `${OUTLABS_AUTH_URL}/v1/entities/${userData.brokerageId}/members`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${adminToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        user_id: user.id,
        role_ids: [userData.roleId]
      })
    }
  );
  
  return user;
};
```

### 2. Session Management

```javascript
class AuthManager {
  constructor() {
    this.accessToken = null;
    this.refreshToken = null;
    this.tokenExpiry = null;
  }
  
  async makeAuthenticatedRequest(url, options = {}) {
    // Check if token needs refresh
    if (this.tokenExpiry && Date.now() >= this.tokenExpiry - 60000) {
      await this.refreshAccessToken();
    }
    
    const response = await fetch(url, {
      ...options,
      headers: {
        ...options.headers,
        'Authorization': `Bearer ${this.accessToken}`
      }
    });
    
    // Handle 401 with automatic retry
    if (response.status === 401) {
      await this.refreshAccessToken();
      return fetch(url, {
        ...options,
        headers: {
          ...options.headers,
          'Authorization': `Bearer ${this.accessToken}`
        }
      });
    }
    
    return response;
  }
  
  async refreshAccessToken() {
    const response = await fetch(`${OUTLABS_AUTH_URL}/v1/auth/mobile/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: this.refreshToken })
    });
    
    if (!response.ok) {
      throw new Error('Session expired - please login again');
    }
    
    const tokens = await response.json();
    this.accessToken = tokens.access_token;
    this.refreshToken = tokens.refresh_token;
    this.tokenExpiry = Date.now() + (tokens.expires_in * 1000);
  }
}
```

### 3. Entity Context Headers

When performing operations in a specific entity context:

```javascript
const createProperty = async (propertyData, entityId) => {
  const response = await fetch(`${YOUR_API_URL}/properties`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'X-Entity-Context-Id': entityId,  // Important for multi-tenant operations
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(propertyData)
  });
  
  return response.json();
};
```

## Error Handling

### Common Error Responses

```json
{
  "detail": "Incorrect email or password"
}
```

### Error Status Codes

| Status | Meaning | Action |
|--------|---------|--------|
| 400 | Bad Request | Check request format and required fields |
| 401 | Unauthorized | Token expired or invalid - refresh/re-login |
| 403 | Forbidden | User lacks required permissions |
| 404 | Not Found | Resource doesn't exist |
| 409 | Conflict | Resource already exists (e.g., duplicate email) |
| 429 | Too Many Requests | Rate limited - retry after delay |
| 500 | Server Error | Retry with exponential backoff |

### Error Handling Example

```javascript
const handleApiError = async (response) => {
  if (!response.ok) {
    const error = await response.json();
    
    switch (response.status) {
      case 401:
        // Token expired - try refresh
        await refreshToken();
        break;
      case 403:
        // Permission denied
        showError('You do not have permission to perform this action');
        break;
      case 429:
        // Rate limited
        const retryAfter = response.headers.get('Retry-After') || 60;
        await sleep(retryAfter * 1000);
        break;
      default:
        showError(error.detail || 'An error occurred');
    }
    
    throw new ApiError(response.status, error.detail);
  }
  
  return response;
};
```

## Security Best Practices

### 1. Token Storage

**Web Applications**:
- Let OutlabsAuth set HTTP-only cookies (most secure)
- Never store tokens in localStorage or sessionStorage

**Mobile Applications**:
- iOS: Use Keychain Services
- Android: Use Android Keystore
- React Native: Use secure storage libraries

### 2. API Key Security

- Store API keys in environment variables
- Never commit API keys to version control
- Use different keys for dev/staging/production
- Rotate keys periodically

### 3. HTTPS Requirement

- Always use HTTPS in production
- Implement certificate pinning for mobile apps
- Validate SSL certificates

### 4. Permission Checks

- Always verify permissions server-side
- Never trust client-side permission checks
- Use least-privilege principle

## Rate Limiting

OutlabsAuth implements rate limiting to prevent abuse:

- **Authentication endpoints**: 5 requests per minute per IP
- **API endpoints**: 1000 requests per hour per user
- **Bulk operations**: 10 requests per minute

### Handling Rate Limits

```javascript
const handleRateLimit = async (response) => {
  if (response.status === 429) {
    const retryAfter = response.headers.get('Retry-After');
    const waitTime = retryAfter ? parseInt(retryAfter) : 60;
    
    console.log(`Rate limited. Waiting ${waitTime} seconds...`);
    await new Promise(resolve => setTimeout(resolve, waitTime * 1000));
    
    return true; // Retry the request
  }
  return false;
};
```

## Next Steps

1. Review the [API Quick Start Guide](./API_QUICK_START_GUIDE.md) for code examples
2. For property hub platforms, see [Property Hub Integration Guide](./PROPERTY_HUB_INTEGRATION_GUIDE.md)
3. Explore [Platform Setup Guide](./PLATFORM_SETUP_GUIDE.md) for detailed platform configuration
4. Check [API Integration Patterns](./API_INTEGRATION_PATTERNS.md) for advanced patterns

## Support

For integration support:
- Documentation: https://docs.outlabs.com/auth
- API Reference: https://api.auth.outlabs.com/docs
- Support Email: support@outlabs.com