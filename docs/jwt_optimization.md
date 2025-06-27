# JWT Token Optimization Guide

## Overview

Your authentication system uses **enriched JWT tokens** by default that include user permissions, roles, and profile data directly in the token payload. This significantly reduces frontend API calls by providing all necessary authorization data upfront.

## Token Types

### Enriched Tokens (Standard Format)

```json
{
  "sub": "user_id",
  "client_account_id": "client_id",
  "jti": "refresh_token_id",
  "exp": 1719504000,
  "iat": 1719500400,

  "user": {
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "status": "active",
    "is_platform_staff": false,
    "platform_scope": null
  },

  "roles": [
    {
      "id": "role_id",
      "name": "admin",
      "scope": "client",
      "scope_id": "client_id"
    }
  ],

  "permissions": ["user:manage_client", "group:read_client", "role:read_client"],

  "scopes": ["client"],

  "session": {
    "is_main_client": true,
    "mfa_enabled": false,
    "locale": "en-US"
  }
}
```

### Basic Tokens (Minimal Format)

```json
{
  "sub": "user_id",
  "client_account_id": "client_id",
  "jti": "refresh_token_id",
  "exp": 1719504000,
  "iat": 1719500400
}
```

_Only used when explicitly requested via `use_enriched_tokens=false`_

## Usage Examples

### 1. Login (Enriched Tokens by Default)

```javascript
// Standard login - returns enriched token automatically
const response = await fetch("/v1/auth/login", {
  method: "POST",
  headers: { "Content-Type": "application/x-www-form-urlencoded" },
  body: "username=user@example.com&password=password123",
});

const { access_token } = await response.json();

// Decode token payload (JWT decode library)
const tokenData = jwt.decode(access_token);

// All user data is immediately available!
console.log("User roles:", tokenData.roles);
console.log("User permissions:", tokenData.permissions);
console.log("User profile:", tokenData.user);
```

### 2. Opt-out to Basic Tokens (if needed)

```javascript
// Explicitly request basic token (minimal size)
const response = await fetch("/v1/auth/login?use_enriched_tokens=false", {
  method: "POST",
  headers: { "Content-Type": "application/x-www-form-urlencoded" },
  body: "username=user@example.com&password=password123",
});
```

### 3. Permission Checking in Frontend

```javascript
// Check permissions without API calls (standard behavior)
function hasPermission(token, requiredPermission) {
  const decoded = jwt.decode(token);

  if (decoded.permissions) {
    // Use hierarchical permission checking
    return checkHierarchicalPermission(decoded.permissions, requiredPermission);
  } else {
    // Fallback to API call for basic tokens
    return checkPermissionViaAPI(requiredPermission);
  }
}

function checkHierarchicalPermission(userPermissions, required) {
  // Direct permission match
  if (userPermissions.includes(required)) return true;

  // Hierarchical checking
  const hierarchies = {
    "user:read_self": [],
    "user:read_client": ["user:read_self"],
    "user:manage_client": ["user:read_client", "user:read_self"],
    "user:manage_all": ["user:manage_client", "user:read_client", "user:read_self"],
  };

  for (const userPerm of userPermissions) {
    const included = hierarchies[userPerm] || [];
    if (included.includes(required)) return true;
  }

  return false;
}
```

### 4. React/Vue Permission Hook

```javascript
// React hook for permission checking
import { useAuth } from "./auth-context";

export function usePermissions() {
  const { token } = useAuth();
  const decoded = jwt.decode(token);

  const hasPermission = (permission) => {
    if (decoded?.permissions) {
      return checkHierarchicalPermission(decoded.permissions, permission);
    }
    return false; // Fallback for basic tokens
  };

  const hasAnyRole = (roleNames) => {
    if (decoded?.roles) {
      return decoded.roles.some((role) => roleNames.includes(role.name));
    }
    return false;
  };

  const isInScope = (scope) => {
    if (decoded?.scopes) {
      return decoded.scopes.includes(scope);
    }
    return false;
  };

  return {
    hasPermission,
    hasAnyRole,
    isInScope,
    userProfile: decoded?.user,
    isEnriched: !!decoded?.permissions,
  };
}
```

### 5. Token Information Endpoint

```javascript
// Check token capabilities
const tokenInfo = await fetch("/v1/auth/token-info", {
  headers: { Authorization: `Bearer ${accessToken}` },
}).then((r) => r.json());

if (tokenInfo.token_type === "enriched") {
  console.log("Using enriched token - all data available locally");
  console.log(`User has ${tokenInfo.permissions_count} permissions`);
} else {
  console.log("Using basic token - may need additional API calls");
}
```

## Configuration

### Environment Variables

```bash
# JWT Settings
SECRET_KEY=your_secret_key
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Enriched Token Settings (now defaults)
MAX_JWT_SIZE_BYTES=8192  # 8KB limit
ENABLE_ENRICHED_TOKENS_BY_DEFAULT=true  # Default behavior
PERMISSION_CACHE_TTL_SECONDS=300  # 5 minutes
```

### API Parameters

| Parameter             | Description              | Default |
| --------------------- | ------------------------ | ------- |
| `use_enriched_tokens` | Include user data in JWT | `true`  |
| `use_cookies`         | Use HTTP-only cookies    | `false` |

## Performance Benefits

### API Call Reduction

**Standard Behavior (Enriched Tokens):**

```javascript
// Login
const { access_token } = await login();

// All data available in token - no additional calls needed!
const tokenData = jwt.decode(access_token);
const { user, permissions, roles } = tokenData;

// Total: 1 API call for complete user context
```

**Old Approach (Basic Tokens):**

```javascript
// Login
const { access_token } = await login();

// Get user profile (API call #1)
const user = await getUserProfile(access_token);

// Get user permissions (API call #2)
const permissions = await getUserPermissions(access_token);

// Get user roles (API call #3)
const roles = await getUserRoles(access_token);

// Total: 4 API calls for complete user context
```

### Performance Metrics

- **75% reduction** in auth-related API calls
- **Instant permission checking** without server roundtrips
- **Improved UX** with immediate role-based UI rendering
- **Reduced server load** on auth endpoints

## Security Considerations

### Token Size Management

1. **Automatic Optimization**: Hierarchical permission compression
2. **Size Limits**: 8KB maximum token size
3. **Fallback**: Automatically falls back to basic tokens if too large
4. **Monitoring**: Logs warnings for oversized tokens

### Permission Security

1. **Short Expiration**: 15-30 minutes recommended for enriched tokens
2. **Refresh Strategy**: New permissions fetched on token refresh
3. **Hierarchical Validation**: Server-side permission validation still required
4. **Scope Isolation**: Client permissions isolated by scope

### Best Practices

```javascript
// 1. Always validate permissions server-side
app.get("/sensitive-data", requirePermission("data:read"), (req, res) => {
  // Server validates regardless of JWT claims
});

// 2. Use short expiration for enriched tokens
const ENRICHED_TOKEN_EXPIRY = 15; // minutes

// 3. Implement permission caching with TTL
const permissionCache = new Map();
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

// 4. Graceful fallback for basic tokens
if (!tokenData.permissions) {
  // Fallback to API-based permission checking
  await checkPermissionViaAPI(permission);
}
```

## Migration from Basic Tokens

If you ever need to support basic tokens again:

### Opt-out Strategy

- Use `use_enriched_tokens=false` parameter
- Frontend can choose enriched or basic tokens
- Both token types supported simultaneously

### Environment Override

- Set `ENABLE_ENRICHED_TOKENS_BY_DEFAULT=false`
- Returns to opt-in behavior

## Troubleshooting

### Token Too Large

```javascript
// Check token size
const tokenSize = new TextEncoder().encode(accessToken).length;
console.log(`Token size: ${tokenSize} bytes`);

// If > 8KB, system automatically falls back to basic token
```

### Permission Issues

```javascript
// Debug permission resolution
const tokenData = jwt.decode(accessToken);
console.log("Available permissions:", tokenData.permissions);
console.log("Available scopes:", tokenData.scopes);
console.log("User roles:", tokenData.roles);
```

### Compatibility Issues

```javascript
// Check token capabilities
const tokenData = jwt.decode(accessToken);
if (tokenData.permissions) {
  // Use enriched features
} else {
  // Fallback to API calls
}
```

## API Reference

### Updated Endpoints

- `GET /v1/auth/token-info` - Get current token information
- `POST /v1/auth/login` - Login with enriched token (default)
- `POST /v1/auth/login?use_enriched_tokens=false` - Login with basic token
- `POST /v1/auth/refresh` - Refresh with enriched token (default)
- `POST /v1/auth/refresh?use_enriched_tokens=false` - Refresh with basic token

### Schemas

- `EnrichedTokenDataSchema` - Standard enriched token structure
- `TokenDataSchema` - Basic token structure (fallback)
- `EnrichedTokenUserSchema` - User data in token
- `EnrichedTokenRoleSchema` - Role data in token
- `EnrichedTokenSessionSchema` - Session metadata in token
