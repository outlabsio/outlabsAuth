# outlabsAuth Integration Guide

## Overview

This guide explains how to integrate your platform with outlabsAuth. Whether you're building a web app, mobile app, or API service, this guide will help you implement authentication and authorization using outlabsAuth.

## Integration Approaches

### 1. Direct API Integration
Best for: Full control over authentication flow, custom implementations

### 2. SDK Integration (Coming Soon)
Best for: Rapid development, standard authentication patterns

### 3. OAuth2/OIDC Integration (Future)
Best for: Standard SSO implementations, third-party integrations

## Quick Start

### Step 1: Register Your Platform

Contact outlabsAuth administrators to register your platform and receive:
- `platform_id`: Your unique platform identifier
- `api_key`: For server-to-server communication (if applicable)
- `allowed_origins`: For CORS configuration

### Step 2: Implement Authentication

#### Web Application Example (JavaScript/React)

```javascript
// auth-service.js
class AuthService {
  constructor() {
    this.baseURL = process.env.REACT_APP_AUTH_API || 'https://api.auth.outlabs.com'
    this.platformId = process.env.REACT_APP_PLATFORM_ID
  }

  async login(email, password) {
    const response = await fetch(`${this.baseURL}/v1/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        email,
        password,
        platform_id: this.platformId
      })
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.error.message)
    }

    const data = await response.json()
    
    // Store tokens securely
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    
    return data.user
  }

  async refreshToken() {
    const refreshToken = localStorage.getItem('refresh_token')
    
    const response = await fetch(`${this.baseURL}/v1/auth/refresh`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        refresh_token: refreshToken
      })
    })

    if (!response.ok) {
      // Refresh failed, redirect to login
      this.logout()
      throw new Error('Session expired')
    }

    const data = await response.json()
    localStorage.setItem('access_token', data.access_token)
    
    return data.access_token
  }

  async makeAuthenticatedRequest(url, options = {}) {
    let accessToken = localStorage.getItem('access_token')
    
    const makeRequest = async (token) => {
      return fetch(url, {
        ...options,
        headers: {
          ...options.headers,
          'Authorization': `Bearer ${token}`
        }
      })
    }

    let response = await makeRequest(accessToken)
    
    // If 401, try refreshing token
    if (response.status === 401) {
      accessToken = await this.refreshToken()
      response = await makeRequest(accessToken)
    }
    
    return response
  }

  logout() {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    window.location.href = '/login'
  }
}

export default new AuthService()
```

#### Backend Service Example (Python/FastAPI)

```python
# auth_client.py
import httpx
from functools import wraps
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

class OutlabsAuthClient:
    def __init__(self, base_url: str, platform_id: str):
        self.base_url = base_url
        self.platform_id = platform_id
        self.client = httpx.AsyncClient()
    
    async def validate_token(self, token: str) -> dict:
        """Validate an access token and return user info."""
        response = await self.client.get(
            f"{self.base_url}/v1/users/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        return response.json()
    
    async def check_permission(
        self, 
        user_id: str, 
        permission: str, 
        context: dict = None
    ) -> bool:
        """Check if a user has a specific permission."""
        response = await self.client.post(
            f"{self.base_url}/v1/permissions/check",
            json={
                "user_id": user_id,
                "permission": permission,
                "context": context or {}
            }
        )
        
        if response.status_code != 200:
            return False
        
        result = response.json()
        return result["allowed"]
    
    async def get_user_permissions(
        self, 
        token: str, 
        context: str = None
    ) -> list:
        """Get all permissions for a user."""
        params = {}
        if context:
            params["context"] = context
        
        response = await self.client.get(
            f"{self.base_url}/v1/users/me/permissions",
            headers={"Authorization": f"Bearer {token}"},
            params=params
        )
        
        if response.status_code != 200:
            return []
        
        result = response.json()
        return result["permissions"]

# FastAPI dependencies
security = HTTPBearer()
auth_client = OutlabsAuthClient(
    base_url="https://api.auth.outlabs.com",
    platform_id="plat_your_platform"
)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Dependency to get current authenticated user."""
    user = await auth_client.validate_token(credentials.credentials)
    return user

def require_permission(permission: str):
    """Decorator to require specific permission."""
    async def permission_checker(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        # Add other dependencies if you need context
    ):
        user = await auth_client.validate_token(credentials.credentials)
        
        has_permission = await auth_client.check_permission(
            user_id=user["id"],
            permission=permission
        )
        
        if not has_permission:
            raise HTTPException(
                status_code=403, 
                detail=f"Permission '{permission}' required"
            )
        
        return user
    
    return permission_checker

# Usage in your FastAPI routes
from fastapi import FastAPI, Depends

app = FastAPI()

@app.get("/api/leads")
async def get_leads(user = Depends(require_permission("lead:read"))):
    # User has lead:read permission
    return {"leads": [...]}

@app.post("/api/leads")
async def create_lead(
    lead_data: dict,
    user = Depends(require_permission("lead:create"))
):
    # User has lead:create permission
    return {"lead": {...}}
```

### Step 3: Define Custom Permissions

Before implementing permission checking, you need to define your platform's custom permissions.

#### Creating Custom Permissions

```javascript
// Define your platform's permissions
const platformPermissions = [
  {
    name: "lead:create",
    display_name: "Create Leads",
    description: "Allows creating new lead records",
    tags: ["sales", "crm"]
  },
  {
    name: "lead:assign",
    display_name: "Assign Leads",
    description: "Allows assigning leads to agents",
    tags: ["sales", "management"]
  },
  {
    name: "report:view_sales",
    display_name: "View Sales Reports",
    description: "Allows viewing sales performance reports",
    tags: ["reporting", "analytics"]
  }
]

// Create permissions during platform setup
async function setupPlatformPermissions() {
  for (const permission of platformPermissions) {
    await authService.makeAuthenticatedRequest(
      `${authService.baseURL}/v1/permissions`,
      {
        method: 'POST',
        body: JSON.stringify(permission)
      }
    )
  }
}
```

#### Backend Permission Creation (Python)

```python
# Define custom permissions for your platform
async def create_platform_permissions():
    permissions = [
        {
            "name": "invoice:approve",
            "display_name": "Approve Invoices",
            "description": "Allows approving invoices for payment",
            "tags": ["finance", "approval"],
            "metadata": {
                "requires_2fa": True,
                "max_amount": 10000
            }
        },
        {
            "name": "commission:calculate",
            "display_name": "Calculate Commissions",
            "description": "Allows calculating agent commissions",
            "tags": ["finance", "sales"]
        }
    ]
    
    for perm_data in permissions:
        response = await auth_client.post(
            f"{base_url}/v1/permissions",
            json=perm_data
        )
        if response.status_code != 201:
            logger.error(f"Failed to create permission: {perm_data['name']}")
```

### Step 4: Implement Permission Checking

#### Frontend Permission Checking

```javascript
// PermissionGate component (React)
import { useState, useEffect } from 'react'
import authService from './auth-service'

export function PermissionGate({ permission, context, children, fallback }) {
  const [hasPermission, setHasPermission] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    checkPermission()
  }, [permission, context])

  const checkPermission = async () => {
    try {
      const response = await authService.makeAuthenticatedRequest(
        `${authService.baseURL}/v1/users/me/permissions?context=${context}`
      )
      const data = await response.json()
      setHasPermission(data.permissions.includes(permission))
    } catch (error) {
      setHasPermission(false)
    } finally {
      setLoading(false)
    }
  }

  if (loading) return <div>Loading...</div>
  
  return hasPermission ? children : (fallback || null)
}

// Usage
<PermissionGate permission="lead:delete" context={entityId}>
  <button onClick={deleteLead}>Delete Lead</button>
</PermissionGate>
```

#### Caching Permissions

```javascript
// Enhanced auth service with permission caching
class AuthServiceWithCache extends AuthService {
  constructor() {
    super()
    this.permissionCache = new Map()
    this.cacheTimeout = 5 * 60 * 1000 // 5 minutes
  }

  async getPermissions(context) {
    const cacheKey = `permissions:${context || 'global'}`
    const cached = this.permissionCache.get(cacheKey)
    
    if (cached && cached.timestamp > Date.now() - this.cacheTimeout) {
      return cached.permissions
    }

    const response = await this.makeAuthenticatedRequest(
      `${this.baseURL}/v1/users/me/permissions${context ? `?context=${context}` : ''}`
    )
    
    const data = await response.json()
    
    this.permissionCache.set(cacheKey, {
      permissions: data.permissions,
      timestamp: Date.now()
    })
    
    return data.permissions
  }

  hasPermission(permissions, required) {
    if (Array.isArray(required)) {
      return required.every(p => permissions.includes(p))
    }
    return permissions.includes(required)
  }

  clearPermissionCache() {
    this.permissionCache.clear()
  }
}
```

### Step 4: Handle User Management

#### Creating Users from Your Platform

```javascript
// Admin function to create users
async function createUser(userData) {
  const response = await fetch(`${AUTH_API}/v1/users/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${adminToken}`,
    },
    body: JSON.stringify({
      email: userData.email,
      password: userData.password,
      profile: {
        first_name: userData.firstName,
        last_name: userData.lastName,
      },
      entity_id: userData.entityId, // Assign to entity
      platform_id: PLATFORM_ID,
    })
  })

  if (!response.ok) {
    throw new Error('Failed to create user')
  }

  return response.json()
}
```

#### Managing Entity Memberships

```javascript
// Add user to a group/team
async function addUserToEntity(userId, entityId, role = 'member') {
  const response = await fetch(
    `${AUTH_API}/v1/entities/${entityId}/members`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${adminToken}`,
      },
      body: JSON.stringify({
        user_id: userId,
        role_in_entity: role,
      })
    }
  )

  return response.json()
}
```

## Best Practices

### 1. Token Management
- Store tokens securely (HttpOnly cookies for web, secure storage for mobile)
- Implement automatic token refresh
- Clear tokens on logout
- Handle token expiration gracefully

### 2. Permission Checking
- Cache permissions for performance
- Check permissions on both frontend and backend
- Use permission gates in UI for better UX
- Always validate permissions server-side

### 3. Error Handling
- Implement retry logic for network failures
- Handle authentication errors gracefully
- Provide clear error messages to users
- Log authentication issues for debugging

### 4. Security
- Always use HTTPS in production
- Validate tokens on every request
- Implement CSRF protection
- Use secure password policies

## Common Integration Patterns

### 1. Single Page Application (SPA)

```javascript
// App.js
function App() {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Check if user is logged in on app load
    const checkAuth = async () => {
      try {
        const userData = await authService.getCurrentUser()
        setUser(userData)
      } catch (error) {
        // Not logged in
      } finally {
        setLoading(false)
      }
    }
    
    checkAuth()
  }, [])

  if (loading) return <LoadingScreen />
  
  return (
    <AuthContext.Provider value={{ user, setUser }}>
      {user ? <AuthenticatedApp /> : <LoginScreen />}
    </AuthContext.Provider>
  )
}
```

### 2. Server-Side Rendering (SSR)

```python
# Middleware for SSR frameworks (e.g., Next.js API routes)
async def auth_middleware(request):
    token = request.cookies.get('access_token')
    
    if not token:
        return None
    
    try:
        user = await auth_client.validate_token(token)
        request.state.user = user
        return user
    except:
        return None
```

### 3. Mobile Application

```swift
// iOS/Swift example
class AuthManager {
    static let shared = AuthManager()
    private let baseURL = "https://api.auth.outlabs.com"
    
    func login(email: String, password: String) async throws -> User {
        let url = URL(string: "\(baseURL)/v1/auth/login")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body = [
            "email": email,
            "password": password,
            "platform_id": Config.platformId
        ]
        request.httpBody = try JSONEncoder().encode(body)
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw AuthError.loginFailed
        }
        
        let authResponse = try JSONDecoder().decode(AuthResponse.self, from: data)
        
        // Store tokens in Keychain
        try KeychainManager.save(authResponse.accessToken, for: .accessToken)
        try KeychainManager.save(authResponse.refreshToken, for: .refreshToken)
        
        return authResponse.user
    }
}
```

## Troubleshooting

### Common Issues

1. **CORS Errors**
   - Ensure your domain is in the allowed origins
   - Check that credentials are included in requests

2. **Token Expiration**
   - Implement automatic token refresh
   - Handle 401 responses properly

3. **Permission Denied**
   - Verify user has required permissions
   - Check context is being passed correctly

4. **Rate Limiting**
   - Implement request queuing
   - Cache responses where appropriate

## Support

For integration support:
- Documentation: https://docs.outlabs.com/auth
- API Status: https://status.outlabs.com
- Support Email: auth-support@outlabs.com