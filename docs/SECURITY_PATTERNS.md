# Security Patterns & Best Practices

## Critical Security Updates

### 1. Token Storage: HttpOnly Cookies (NOT localStorage)

**❌ INSECURE Pattern (Vulnerable to XSS)**
```javascript
// DO NOT USE THIS
localStorage.setItem('access_token', data.access_token)
localStorage.setItem('refresh_token', data.refresh_token)
```

**✅ SECURE Pattern (HttpOnly Cookies)**

#### Backend: Set Secure Cookies
```python
# FastAPI example
from fastapi import Response
from datetime import timedelta

@router.post("/v1/auth/login")
async def login(credentials: LoginSchema, response: Response):
    # Validate credentials...
    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)
    
    # Set HttpOnly cookies
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,  # Prevents JavaScript access
        secure=True,    # HTTPS only
        samesite="lax", # CSRF protection
        max_age=900     # 15 minutes
    )
    
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=2592000  # 30 days
    )
    
    # Return user info (NOT tokens)
    return {
        "user": user.dict(),
        "expires_in": 900
    }
```

#### Frontend: Automatic Cookie Handling
```javascript
class SecureAuthService {
  constructor() {
    this.baseURL = process.env.REACT_APP_AUTH_API
  }

  async login(email, password) {
    const response = await fetch(`${this.baseURL}/v1/auth/login`, {
      method: 'POST',
      credentials: 'include',  // Include cookies automatically
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ email, password })
    })

    if (!response.ok) {
      throw new Error('Login failed')
    }

    // No token handling needed - cookies are set automatically
    const data = await response.json()
    return data.user
  }

  async makeAuthenticatedRequest(url, options = {}) {
    return fetch(url, {
      ...options,
      credentials: 'include',  // Cookies sent automatically
      headers: {
        ...options.headers,
        // No Authorization header needed
      }
    })
  }
}
```

### 2. API Key vs Bearer Token Usage

#### Bearer Token (User Context)
Used for actions taken on behalf of a specific user.

```python
# User creating an entity within their permissions
@router.post("/v1/entities/")
@requires_auth  # Validates Bearer token
async def create_entity(
    data: EntityCreateSchema,
    current_user: User = Depends(get_current_user)
):
    # Action performed in user's context
    return await entity_service.create_entity(data, current_user)
```

#### API Key (Platform/System Context)
Used for trusted server-to-server operations with no user context.

```python
# Platform syncing all permissions
@router.get("/v1/system/permissions/sync")
@requires_api_key  # Validates platform API key
async def sync_permissions(
    platform: Platform = Depends(validate_api_key)
):
    # System-level operation
    return await permission_service.get_all_permissions(platform.id)
```

**API Key Header Format:**
```
X-API-Key: plat_diverse_leads_sk_live_xyz123
```

### 3. Optimized Permission Checking

**Single API Call Pattern**

Instead of two round trips, the permission check uses the token directly:

```python
# Optimized endpoint - no user_id needed
@router.post("/v1/permissions/check")
async def check_permission(
    request: PermissionCheckRequest,
    current_user: User = Depends(get_current_user_from_token)
):
    # User is already extracted from token
    return {
        "allowed": await permission_service.check_permission(
            user=current_user,
            permission=request.permission,
            context=request.context
        )
    }
```

**Optimized Backend Integration:**
```python
# Single decorator for permission checks
def require_permission(permission: str):
    async def permission_checker(
        request: Request,
        token: str = Depends(get_token_from_cookie)
    ):
        # Single API call that validates token AND checks permission
        response = await auth_client.check_permission_with_token(
            token=token,
            permission=permission,
            context=extract_context(request)
        )
        
        if not response.allowed:
            raise HTTPException(403, "Permission denied")
        
        return response.user  # User data from the same call
    
    return permission_checker

# Usage
@app.get("/api/leads")
async def get_leads(user = Depends(require_permission("lead:read"))):
    # Single API call handled both auth and permission
    return {"leads": [...]}
```

### 4. CSRF Protection

With HttpOnly cookies, CSRF protection is critical:

```python
# Generate CSRF token on login
import secrets

@router.post("/v1/auth/login")
async def login(credentials: LoginSchema, response: Response):
    # ... authentication logic ...
    
    csrf_token = secrets.token_urlsafe(32)
    
    # Store CSRF token in session
    await redis.set(f"csrf:{user_id}", csrf_token, ex=3600)
    
    # Return CSRF token to client (NOT in cookie)
    return {
        "user": user.dict(),
        "csrf_token": csrf_token
    }
```

**Frontend CSRF Usage:**
```javascript
class CSRFProtectedClient {
  constructor() {
    this.csrfToken = null
  }

  setCSRFToken(token) {
    this.csrfToken = token
  }

  async makeRequest(url, options = {}) {
    return fetch(url, {
      ...options,
      credentials: 'include',
      headers: {
        ...options.headers,
        'X-CSRF-Token': this.csrfToken  // Include with mutations
      }
    })
  }
}
```

### 5. Session Management

**Secure Session Configuration:**
```python
# Session settings
SESSION_CONFIG = {
    "cookie_name": "session_id",
    "cookie_httponly": True,
    "cookie_secure": True,  # HTTPS only
    "cookie_samesite": "lax",
    "cookie_max_age": 3600,  # 1 hour sliding window
}

# Redis session store
class SessionStore:
    async def create_session(self, user_id: str) -> str:
        session_id = secrets.token_urlsafe(32)
        session_data = {
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
            "last_activity": datetime.utcnow().isoformat()
        }
        
        await redis.setex(
            f"session:{session_id}",
            SESSION_CONFIG["cookie_max_age"],
            json.dumps(session_data)
        )
        
        return session_id
    
    async def validate_session(self, session_id: str) -> Optional[dict]:
        data = await redis.get(f"session:{session_id}")
        if not data:
            return None
            
        session = json.loads(data)
        
        # Update last activity
        session["last_activity"] = datetime.utcnow().isoformat()
        await redis.setex(
            f"session:{session_id}",
            SESSION_CONFIG["cookie_max_age"],
            json.dumps(session)
        )
        
        return session
```

### 6. Additional Security Headers

```python
# Security middleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.diverse-leads.com"],  # Specific origins only
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["X-CSRF-Token"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["api.auth.outlabs.com", "*.auth.outlabs.com"]
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response
```

### 7. Rate Limiting with Security Context

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

# Different limits for different contexts
limiter = Limiter(key_func=get_remote_address)

# Strict limit for auth endpoints
@app.post("/v1/auth/login")
@limiter.limit("5/minute")
async def login(request: Request, credentials: LoginSchema):
    # Track failed attempts
    attempts_key = f"login_attempts:{credentials.email}"
    attempts = await redis.incr(attempts_key)
    await redis.expire(attempts_key, 3600)  # 1 hour
    
    if attempts > 10:
        raise HTTPException(429, "Account temporarily locked")
    
    # ... authentication logic ...

# Higher limit for API key authenticated requests
@app.get("/v1/entities/")
@limiter.limit("1000/minute", key_func=get_api_key)
async def list_entities(api_key: str = Depends(validate_api_key)):
    # ... endpoint logic ...
```

## Security Checklist

### Authentication
- [ ] Use HttpOnly, Secure, SameSite cookies for tokens
- [ ] Implement CSRF protection for cookie-based auth
- [ ] Use secure session management with sliding expiration
- [ ] Track and limit failed login attempts
- [ ] Implement account lockout mechanisms

### API Security
- [ ] Differentiate Bearer token vs API key usage
- [ ] Implement rate limiting per endpoint type
- [ ] Add security headers to all responses
- [ ] Use HTTPS everywhere (enforce with HSTS)
- [ ] Validate and sanitize all inputs

### Token Management
- [ ] Keep JWT claims minimal (just identity)
- [ ] Implement token rotation for refresh tokens
- [ ] Use short expiration for access tokens (15 min)
- [ ] Store sensitive data server-side, not in tokens
- [ ] Implement token revocation lists for logout

### Infrastructure
- [ ] Use Redis for session/cache with TLS
- [ ] Encrypt database connections
- [ ] Implement audit logging for security events
- [ ] Use environment variables for secrets
- [ ] Regular security dependency updates

## Migration Guide: localStorage to HttpOnly Cookies

For existing implementations using localStorage:

1. **Backend Changes:**
   - Modify login endpoint to set HttpOnly cookies
   - Update middleware to read from cookies instead of Authorization header
   - Add CSRF token generation and validation

2. **Frontend Changes:**
   - Remove all localStorage token handling
   - Add `credentials: 'include'` to all fetch requests
   - Implement CSRF token management
   - Update error handling for cookie-based auth

3. **Transition Period:**
   - Support both patterns temporarily
   - Log which method each request uses
   - Gradually migrate all clients
   - Remove localStorage support after migration

This approach provides defense-in-depth security while maintaining a smooth developer experience.