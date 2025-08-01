# Session Management Patterns

This guide explains industry-standard patterns for managing sessions when using the proxy authentication pattern with OutlabsAuth. Each pattern has different trade-offs between security, complexity, and control.

## Table of Contents

1. [Overview](#overview)
2. [Pattern A: Platform-Managed Sessions](#pattern-a-platform-managed-sessions)
3. [Pattern B: Token Passthrough](#pattern-b-token-passthrough)
4. [Pattern C: Dual Session](#pattern-c-dual-session)
5. [Comparison Matrix](#comparison-matrix)
6. [Implementation Examples](#implementation-examples)
7. [Security Considerations](#security-considerations)
8. [Best Practices](#best-practices)

## Overview

When proxying authentication through your platform API to OutlabsAuth, you need to decide how to manage user sessions. The key question is: where do the JWT tokens live, and how do they flow between the frontend, your API, and OutlabsAuth?

### Key Principles

1. **Frontend Security**: Frontend should never have direct access to API keys
2. **Token Storage**: JWT tokens should be stored securely
3. **Session State**: Someone needs to manage session state and refresh
4. **User Experience**: Seamless authentication without multiple logins

## Pattern A: Platform-Managed Sessions

**Recommended for: Production applications, enterprise systems**

In this pattern, your platform creates and manages its own session cookies, while storing OutlabsAuth tokens server-side.

### Architecture
```
┌─────────────┐     ┌──────────────────┐     ┌──────────────┐
│   Browser   │────▶│  Property Hub API │────▶│ OutlabsAuth  │
│             │◀────│                   │◀────│              │
└─────────────┘     └──────────────────┘     └──────────────┘
       │                     │                       │
   HTTP-only            Server-side              JWT tokens
   session cookie       token storage           (never exposed)
```

### Implementation

```javascript
// Property Hub API - Session Management
class SessionManager {
  constructor(sessionStore, outlabsAuth) {
    this.sessions = sessionStore; // Redis, database, etc.
    this.outlabsAuth = outlabsAuth;
  }
  
  async createSession(email, password, req) {
    // 1. Authenticate with OutlabsAuth
    const authResult = await this.outlabsAuth.login(email, password);
    
    // 2. Create platform session
    const sessionId = crypto.randomUUID();
    const sessionData = {
      userId: authResult.user.id,
      email: authResult.user.email,
      outlabsTokens: {
        access: authResult.access_token,
        refresh: authResult.refresh_token,
        expiresAt: Date.now() + (authResult.expires_in * 1000)
      },
      platformData: {
        role: authResult.user.platformRole,
        permissions: authResult.user.permissions
      },
      createdAt: Date.now(),
      lastActivity: Date.now()
    };
    
    // 3. Store session server-side
    await this.sessions.set(`session:${sessionId}`, sessionData, {
      ttl: 24 * 60 * 60 // 24 hours
    });
    
    // 4. Set HTTP-only session cookie
    return {
      cookie: {
        name: 'platform_session',
        value: sessionId,
        httpOnly: true,
        secure: process.env.NODE_ENV === 'production',
        sameSite: 'lax',
        maxAge: 24 * 60 * 60 * 1000,
        path: '/'
      },
      user: {
        id: authResult.user.id,
        email: authResult.user.email,
        profile: authResult.user.profile
      }
    };
  }
  
  async getSession(sessionId) {
    const session = await this.sessions.get(`session:${sessionId}`);
    if (!session) return null;
    
    // Check if OutlabsAuth token needs refresh
    if (Date.now() >= session.outlabsTokens.expiresAt - 60000) {
      await this.refreshSession(sessionId, session);
    }
    
    return session;
  }
  
  async refreshSession(sessionId, session) {
    try {
      const newTokens = await this.outlabsAuth.refreshToken(
        session.outlabsTokens.refresh
      );
      
      // Update stored session
      session.outlabsTokens = {
        access: newTokens.access_token,
        refresh: newTokens.refresh_token,
        expiresAt: Date.now() + (newTokens.expires_in * 1000)
      };
      session.lastActivity = Date.now();
      
      await this.sessions.set(`session:${sessionId}`, session, {
        ttl: 24 * 60 * 60
      });
      
    } catch (error) {
      // Refresh failed, session is invalid
      await this.destroySession(sessionId);
      throw new Error('Session expired');
    }
  }
}

// Express middleware
app.use(async (req, res, next) => {
  const sessionId = req.cookies.platform_session;
  if (!sessionId) return next();
  
  try {
    const session = await sessionManager.getSession(sessionId);
    if (session) {
      req.session = session;
      // Update last activity
      session.lastActivity = Date.now();
      await sessionManager.updateActivity(sessionId);
    }
  } catch (error) {
    // Clear invalid cookie
    res.clearCookie('platform_session');
  }
  
  next();
});

// API endpoint that uses OutlabsAuth
app.get('/api/users/:id', requireAuth, async (req, res) => {
  // Make request to OutlabsAuth with stored token
  const response = await outlabsAuth.getUser(req.params.id, {
    token: req.session.outlabsTokens.access
  });
  
  res.json(response);
});
```

### Frontend Implementation

```javascript
// Frontend only knows about platform session
class PlatformAuthService {
  async login(email, password) {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      credentials: 'include', // Important for cookies
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    
    if (!response.ok) throw new Error('Login failed');
    
    // Session cookie is automatically set
    return response.json(); // Returns user info, not tokens
  }
  
  async makeAuthenticatedRequest(url, options = {}) {
    // Just include credentials, platform handles the rest
    return fetch(url, {
      ...options,
      credentials: 'include'
    });
  }
  
  async logout() {
    await fetch('/api/auth/logout', {
      method: 'POST',
      credentials: 'include'
    });
  }
}
```

## Pattern B: Token Passthrough

**Recommended for: Simple integrations, development environments**

In this pattern, OutlabsAuth tokens are passed through your platform to the frontend, but your platform validates and forwards them.

### Architecture
```
┌─────────────┐     ┌──────────────────┐     ┌──────────────┐
│   Browser   │────▶│  Property Hub API │────▶│ OutlabsAuth  │
│             │◀────│   (validates)     │◀────│              │
└─────────────┘     └──────────────────┘     └──────────────┘
       │                     │                       │
   JWT cookie           Forwards JWT              JWT tokens
   from OutlabsAuth     with API key
```

### Implementation

```javascript
// Property Hub API - Token Passthrough
class TokenPassthrough {
  constructor(outlabsAuth) {
    this.outlabsAuth = outlabsAuth;
  }
  
  async login(req, res) {
    const { email, password } = req.body;
    
    // Get tokens from OutlabsAuth
    const authResult = await this.outlabsAuth.login(email, password);
    
    // Pass tokens to frontend as cookies
    res.cookie('access_token', authResult.access_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: 15 * 60 * 1000 // 15 minutes
    });
    
    res.cookie('refresh_token', authResult.refresh_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: 30 * 24 * 60 * 60 * 1000 // 30 days
    });
    
    // Return user info
    res.json({
      user: authResult.user
    });
  }
  
  // Middleware to validate and forward tokens
  async validateToken(req, res, next) {
    const accessToken = req.cookies.access_token;
    if (!accessToken) {
      return res.status(401).json({ error: 'No token' });
    }
    
    try {
      // Validate token with OutlabsAuth
      const valid = await this.outlabsAuth.validateToken(accessToken);
      if (!valid) {
        throw new Error('Invalid token');
      }
      
      req.outlabsToken = accessToken;
      next();
    } catch (error) {
      // Try to refresh
      const refreshToken = req.cookies.refresh_token;
      if (refreshToken) {
        try {
          const newTokens = await this.outlabsAuth.refreshToken(refreshToken);
          
          // Set new cookies
          res.cookie('access_token', newTokens.access_token, {
            httpOnly: true,
            maxAge: 15 * 60 * 1000
          });
          res.cookie('refresh_token', newTokens.refresh_token, {
            httpOnly: true,
            maxAge: 30 * 24 * 60 * 60 * 1000
          });
          
          req.outlabsToken = newTokens.access_token;
          next();
        } catch (refreshError) {
          res.clearCookie('access_token');
          res.clearCookie('refresh_token');
          res.status(401).json({ error: 'Session expired' });
        }
      } else {
        res.status(401).json({ error: 'Invalid token' });
      }
    }
  }
}

// Proxy requests to OutlabsAuth
app.use('/api/outlabs/*', validateToken, async (req, res) => {
  const response = await outlabsAuth.request(req.path, {
    method: req.method,
    headers: {
      'Authorization': `Bearer ${req.outlabsToken}`,
      'X-API-Key': process.env.OUTLABS_API_KEY
    },
    body: req.body
  });
  
  res.status(response.status).json(response.data);
});
```

## Pattern C: Dual Session

**Recommended for: Hybrid architectures, gradual migrations**

In this pattern, the frontend maintains sessions with both your platform and OutlabsAuth.

### Architecture
```
┌─────────────┐     ┌──────────────────┐     ┌──────────────┐
│   Browser   │────▶│  Property Hub API │     │              │
│             │◀────│                   │     │ OutlabsAuth  │
│             │────────────────────────────────│              │
└─────────────┘     └──────────────────┘     └──────────────┘
       │                     │                       │
  Platform cookie +     Platform API            Direct calls
  OutlabsAuth token                            for some operations
```

### Implementation

```javascript
// Dual session setup
class DualSessionAuth {
  async login(req, res) {
    const { email, password } = req.body;
    
    // 1. Authenticate with OutlabsAuth
    const authResult = await this.outlabsAuth.login(email, password);
    
    // 2. Create platform session
    const platformSession = await this.createPlatformSession({
      userId: authResult.user.id,
      email: authResult.user.email,
      platformSpecificData: await this.loadPlatformData(authResult.user.id)
    });
    
    // 3. Set platform cookie
    res.cookie('platform_session', platformSession.id, {
      httpOnly: true,
      secure: true,
      sameSite: 'lax',
      maxAge: 24 * 60 * 60 * 1000
    });
    
    // 4. Return OutlabsAuth token for frontend storage
    res.json({
      user: authResult.user,
      platformSession: {
        id: platformSession.id,
        expiresAt: platformSession.expiresAt
      },
      outlabsAuth: {
        accessToken: authResult.access_token,
        expiresIn: authResult.expires_in,
        // Note: In production, consider not exposing refresh token
        refreshEndpoint: '/api/auth/refresh'
      }
    });
  }
}

// Frontend with dual sessions
class DualAuthService {
  constructor() {
    this.outlabsToken = null;
    this.tokenExpiry = null;
  }
  
  async login(email, password) {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      credentials: 'include', // For platform cookie
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    
    const data = await response.json();
    
    // Store OutlabsAuth token in memory (or secure storage)
    this.outlabsToken = data.outlabsAuth.accessToken;
    this.tokenExpiry = Date.now() + (data.outlabsAuth.expiresIn * 1000);
    
    return data.user;
  }
  
  async makeAuthenticatedRequest(url, options = {}) {
    // Check which API we're calling
    if (url.includes('/api/outlabs/')) {
      // Direct OutlabsAuth call
      return this.makeOutlabsRequest(url, options);
    } else {
      // Platform API call
      return fetch(url, {
        ...options,
        credentials: 'include' // Platform session cookie
      });
    }
  }
  
  async makeOutlabsRequest(url, options = {}) {
    // Check token expiry
    if (Date.now() >= this.tokenExpiry - 60000) {
      await this.refreshOutlabsToken();
    }
    
    return fetch(url, {
      ...options,
      headers: {
        ...options.headers,
        'Authorization': `Bearer ${this.outlabsToken}`
      }
    });
  }
}
```

## Comparison Matrix

| Feature | Pattern A (Platform-Managed) | Pattern B (Passthrough) | Pattern C (Dual) |
|---------|----------------------------|----------------------|-----------------|
| **Security** | ⭐⭐⭐⭐⭐ Excellent | ⭐⭐⭐ Good | ⭐⭐⭐ Good |
| **Implementation Complexity** | ⭐⭐⭐ Moderate | ⭐⭐ Simple | ⭐⭐⭐⭐ Complex |
| **Platform Control** | ⭐⭐⭐⭐⭐ Full | ⭐⭐ Limited | ⭐⭐⭐⭐ High |
| **Token Exposure** | Never exposed | In cookies | Partially exposed |
| **Session Management** | Platform handles | Shared responsibility | Dual management |
| **API Calls** | All proxied | All proxied | Some direct |
| **Performance** | Good (with caching) | Better | Best (direct calls) |
| **Debugging** | Easier | Moderate | Complex |
| **Recommended For** | Production systems | Simple integrations | Hybrid architectures |

## Implementation Examples

### Complete Example: Platform-Managed Sessions with Redis

```javascript
// server.js - Complete platform session implementation
const express = require('express');
const Redis = require('ioredis');
const cookieParser = require('cookie-parser');

const app = express();
const redis = new Redis();

app.use(express.json());
app.use(cookieParser());

class PlatformSessionManager {
  constructor(redisClient, outlabsAuthClient) {
    this.redis = redisClient;
    this.outlabsAuth = outlabsAuthClient;
  }
  
  // Create new session
  async createSession(authData, metadata = {}) {
    const sessionId = crypto.randomUUID();
    const session = {
      id: sessionId,
      userId: authData.user.id,
      email: authData.user.email,
      tokens: {
        access: authData.access_token,
        refresh: authData.refresh_token,
        expiresAt: Date.now() + (authData.expires_in * 1000)
      },
      metadata: {
        ...metadata,
        userAgent: metadata.userAgent,
        ipAddress: metadata.ipAddress,
        createdAt: Date.now(),
        lastActivity: Date.now()
      }
    };
    
    // Store in Redis with TTL
    await this.redis.setex(
      `session:${sessionId}`,
      24 * 60 * 60, // 24 hours
      JSON.stringify(session)
    );
    
    // Track active sessions per user
    await this.redis.sadd(`user:${authData.user.id}:sessions`, sessionId);
    
    return session;
  }
  
  // Get and refresh session if needed
  async getSession(sessionId) {
    const sessionData = await this.redis.get(`session:${sessionId}`);
    if (!sessionData) return null;
    
    const session = JSON.parse(sessionData);
    
    // Check if token needs refresh (5 minutes before expiry)
    if (Date.now() >= session.tokens.expiresAt - (5 * 60 * 1000)) {
      try {
        await this.refreshSession(session);
      } catch (error) {
        await this.destroySession(sessionId);
        return null;
      }
    }
    
    // Update activity
    session.metadata.lastActivity = Date.now();
    await this.updateSession(session);
    
    return session;
  }
  
  // Refresh OutlabsAuth tokens
  async refreshSession(session) {
    const newTokens = await this.outlabsAuth.refreshToken(
      session.tokens.refresh
    );
    
    session.tokens = {
      access: newTokens.access_token,
      refresh: newTokens.refresh_token,
      expiresAt: Date.now() + (newTokens.expires_in * 1000)
    };
    
    await this.updateSession(session);
  }
  
  // Update session in Redis
  async updateSession(session) {
    const ttl = await this.redis.ttl(`session:${session.id}`);
    await this.redis.setex(
      `session:${session.id}`,
      ttl > 0 ? ttl : 24 * 60 * 60,
      JSON.stringify(session)
    );
  }
  
  // Destroy session
  async destroySession(sessionId) {
    const sessionData = await this.redis.get(`session:${sessionId}`);
    if (sessionData) {
      const session = JSON.parse(sessionData);
      await this.redis.srem(`user:${session.userId}:sessions`, sessionId);
    }
    await this.redis.del(`session:${sessionId}`);
  }
  
  // Destroy all user sessions
  async destroyAllUserSessions(userId) {
    const sessions = await this.redis.smembers(`user:${userId}:sessions`);
    
    for (const sessionId of sessions) {
      await this.redis.del(`session:${sessionId}`);
    }
    
    await this.redis.del(`user:${userId}:sessions`);
  }
}

// Session middleware
const sessionManager = new PlatformSessionManager(redis, outlabsAuthClient);

app.use(async (req, res, next) => {
  const sessionId = req.cookies.platform_session;
  if (!sessionId) return next();
  
  const session = await sessionManager.getSession(sessionId);
  if (!session) {
    res.clearCookie('platform_session');
    return next();
  }
  
  req.session = session;
  next();
});

// Login endpoint
app.post('/api/auth/login', async (req, res) => {
  try {
    const { email, password } = req.body;
    
    // Authenticate with OutlabsAuth
    const authResult = await outlabsAuthClient.login(email, password);
    
    // Create platform session
    const session = await sessionManager.createSession(authResult, {
      userAgent: req.headers['user-agent'],
      ipAddress: req.ip
    });
    
    // Set session cookie
    res.cookie('platform_session', session.id, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: 24 * 60 * 60 * 1000
    });
    
    // Return user data (no tokens)
    res.json({
      user: authResult.user,
      sessionId: session.id
    });
    
  } catch (error) {
    res.status(401).json({ error: error.message });
  }
});

// Logout endpoint
app.post('/api/auth/logout', requireAuth, async (req, res) => {
  await sessionManager.destroySession(req.session.id);
  res.clearCookie('platform_session');
  res.json({ message: 'Logged out successfully' });
});

// Proxy authenticated requests
app.use('/api/*', requireAuth, async (req, res, next) => {
  try {
    // Forward to appropriate service with OutlabsAuth token
    const response = await makeAuthenticatedRequest(
      req.path,
      req.method,
      req.body,
      req.session.tokens.access
    );
    
    res.status(response.status).json(response.data);
  } catch (error) {
    next(error);
  }
});
```

## Security Considerations

### 1. Token Storage Security

```javascript
// Secure token storage for Pattern A
class SecureTokenStorage {
  constructor(encryptionKey) {
    this.key = Buffer.from(encryptionKey, 'hex');
  }
  
  encrypt(data) {
    const iv = crypto.randomBytes(16);
    const cipher = crypto.createCipheriv('aes-256-gcm', this.key, iv);
    
    const encrypted = Buffer.concat([
      cipher.update(JSON.stringify(data), 'utf8'),
      cipher.final()
    ]);
    
    const tag = cipher.getAuthTag();
    
    return Buffer.concat([iv, tag, encrypted]).toString('base64');
  }
  
  decrypt(encryptedData) {
    const buffer = Buffer.from(encryptedData, 'base64');
    
    const iv = buffer.slice(0, 16);
    const tag = buffer.slice(16, 32);
    const encrypted = buffer.slice(32);
    
    const decipher = crypto.createDecipheriv('aes-256-gcm', this.key, iv);
    decipher.setAuthTag(tag);
    
    const decrypted = Buffer.concat([
      decipher.update(encrypted),
      decipher.final()
    ]);
    
    return JSON.parse(decrypted.toString('utf8'));
  }
}
```

### 2. Session Security Headers

```javascript
// Security middleware
app.use((req, res, next) => {
  // Prevent clickjacking
  res.setHeader('X-Frame-Options', 'DENY');
  
  // Prevent MIME sniffing
  res.setHeader('X-Content-Type-Options', 'nosniff');
  
  // Enable strict transport security
  if (process.env.NODE_ENV === 'production') {
    res.setHeader(
      'Strict-Transport-Security',
      'max-age=31536000; includeSubDomains'
    );
  }
  
  next();
});
```

### 3. CSRF Protection

```javascript
// CSRF token generation and validation
class CSRFProtection {
  generateToken(sessionId) {
    const token = crypto.randomBytes(32).toString('base64url');
    // Store with session
    this.redis.setex(`csrf:${sessionId}`, 3600, token);
    return token;
  }
  
  async validateToken(sessionId, token) {
    const stored = await this.redis.get(`csrf:${sessionId}`);
    return stored === token;
  }
}

// Apply to state-changing operations
app.post('/api/*', async (req, res, next) => {
  const csrfToken = req.headers['x-csrf-token'];
  const valid = await csrf.validateToken(req.session?.id, csrfToken);
  
  if (!valid) {
    return res.status(403).json({ error: 'Invalid CSRF token' });
  }
  
  next();
});
```

## Best Practices

### 1. Session Timeout and Renewal

```javascript
// Implement sliding session window
class SessionTimeout {
  constructor(options = {}) {
    this.absoluteTimeout = options.absoluteTimeout || 24 * 60 * 60 * 1000; // 24h
    this.idleTimeout = options.idleTimeout || 30 * 60 * 1000; // 30m
  }
  
  shouldRenew(session) {
    const now = Date.now();
    const age = now - session.metadata.createdAt;
    const idle = now - session.metadata.lastActivity;
    
    // Absolute timeout
    if (age > this.absoluteTimeout) {
      return false; // Force re-authentication
    }
    
    // Idle timeout
    if (idle > this.idleTimeout) {
      return false; // Session expired
    }
    
    // Renew if more than halfway through idle period
    return idle > this.idleTimeout / 2;
  }
}
```

### 2. Device Tracking

```javascript
// Track sessions per device
class DeviceTracking {
  async trackDevice(userId, sessionId, deviceInfo) {
    const deviceId = this.generateDeviceId(deviceInfo);
    
    await this.redis.hset(
      `user:${userId}:devices`,
      deviceId,
      JSON.stringify({
        sessionId,
        lastSeen: Date.now(),
        ...deviceInfo
      })
    );
  }
  
  generateDeviceId(info) {
    // Create stable device ID from user agent and other factors
    const data = `${info.userAgent}:${info.platform}:${info.screenResolution}`;
    return crypto.createHash('sha256').update(data).digest('hex');
  }
}
```

### 3. Audit Logging

```javascript
// Comprehensive session audit logging
class SessionAuditLogger {
  async log(event, context) {
    const entry = {
      timestamp: new Date().toISOString(),
      event,
      sessionId: context.sessionId,
      userId: context.userId,
      ipAddress: context.ipAddress,
      userAgent: context.userAgent,
      metadata: context.metadata
    };
    
    // Store in audit log
    await this.auditStore.create(entry);
    
    // Real-time monitoring
    if (this.isSecurityEvent(event)) {
      await this.alertSecurityTeam(entry);
    }
  }
  
  isSecurityEvent(event) {
    return [
      'session_hijack_attempt',
      'concurrent_session_limit_exceeded',
      'suspicious_location_change',
      'token_refresh_failed'
    ].includes(event);
  }
}
```

## Conclusion

The choice of session management pattern depends on your specific requirements:

- **Pattern A (Platform-Managed)**: Best for production systems requiring maximum security and control
- **Pattern B (Token Passthrough)**: Suitable for simple integrations and development
- **Pattern C (Dual Session)**: Useful for gradual migrations or hybrid architectures

For most production applications, Pattern A provides the best balance of security, control, and user experience.