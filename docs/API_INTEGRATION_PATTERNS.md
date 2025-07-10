# API Integration Patterns

This document outlines common patterns and best practices for integrating your platform with OutlabsAuth. These patterns are derived from real implementations and represent proven approaches to authentication, authorization, and identity management.

## Table of Contents
1. [Authentication Patterns](#authentication-patterns)
2. [Authorization Patterns](#authorization-patterns)
3. [Entity Management Patterns](#entity-management-patterns)
4. [User Management Patterns](#user-management-patterns)
5. [Permission Checking Patterns](#permission-checking-patterns)
6. [Synchronization Patterns](#synchronization-patterns)
7. [Error Handling Patterns](#error-handling-patterns)
8. [Performance Optimization](#performance-optimization)

## Authentication Patterns

### Pattern 1: Direct Authentication

**Use Case**: User logs in directly to your platform

```javascript
class AuthService {
    constructor() {
        this.outlabsAuthUrl = process.env.OUTLABS_AUTH_URL;
        this.platformId = process.env.PLATFORM_ID;
    }
    
    async login(email, password) {
        try {
            // 1. Authenticate with OutlabsAuth
            const authResponse = await fetch(`${this.outlabsAuthUrl}/v1/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: new URLSearchParams({
                    username: email,
                    password: password
                })
            });
            
            if (!authResponse.ok) {
                const error = await authResponse.json();
                throw new AuthError(error.detail);
            }
            
            const { access_token, refresh_token, user } = await authResponse.json();
            
            // 2. Get user's permissions for this platform
            const permsResponse = await fetch(
                `${this.outlabsAuthUrl}/v1/users/${user.id}/permissions?platform_id=${this.platformId}`,
                { headers: { 'Authorization': `Bearer ${access_token}` } }
            );
            
            const permissions = await permsResponse.json();
            
            // 3. Create platform session
            const session = await this.createPlatformSession({
                userId: user.id,
                accessToken: access_token,
                refreshToken: refresh_token,
                permissions: permissions
            });
            
            return { user, session, permissions };
            
        } catch (error) {
            this.handleAuthError(error);
        }
    }
}
```

### Pattern 2: Token Refresh

**Use Case**: Automatically refresh expired tokens

```javascript
class TokenManager {
    async makeAuthenticatedRequest(url, options = {}) {
        let token = await this.getAccessToken();
        
        const makeRequest = async (authToken) => {
            return fetch(url, {
                ...options,
                headers: {
                    ...options.headers,
                    'Authorization': `Bearer ${authToken}`
                }
            });
        };
        
        let response = await makeRequest(token);
        
        // If token expired, refresh and retry
        if (response.status === 401) {
            const refreshToken = await this.getRefreshToken();
            
            const refreshResponse = await fetch(`${this.outlabsAuthUrl}/v1/auth/refresh`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ refresh_token: refreshToken })
            });
            
            if (refreshResponse.ok) {
                const { access_token } = await refreshResponse.json();
                await this.saveAccessToken(access_token);
                
                // Retry original request
                response = await makeRequest(access_token);
            } else {
                // Refresh failed, redirect to login
                this.redirectToLogin();
            }
        }
        
        return response;
    }
}
```

### Pattern 3: SSO Integration

**Use Case**: Platform uses SSO (Google, Microsoft, etc.)

```javascript
class SSOAuthService {
    async handleSSOCallback(ssoToken, provider) {
        // 1. Validate SSO token with provider
        const ssoUser = await this.validateSSOToken(ssoToken, provider);
        
        // 2. Check if user exists in OutlabsAuth
        let outlabsUser = await this.findUserByEmail(ssoUser.email);
        
        if (!outlabsUser) {
            // 3. Create user in OutlabsAuth
            outlabsUser = await this.createUser({
                email: ssoUser.email,
                profile: {
                    first_name: ssoUser.given_name,
                    last_name: ssoUser.family_name,
                    picture: ssoUser.picture
                },
                auth_provider: provider,
                auth_provider_id: ssoUser.sub
            });
            
            // 4. Add to default entity
            await this.addToDefaultEntity(outlabsUser.id);
        }
        
        // 5. Create session token
        const sessionToken = await this.createSessionToken(outlabsUser.id);
        
        return { user: outlabsUser, token: sessionToken };
    }
}
```

## Authorization Patterns

### Pattern 1: Middleware-Based Permission Checking

**Use Case**: Check permissions before processing requests

```javascript
// Express middleware example
function requirePermission(permission) {
    return async (req, res, next) => {
        try {
            const token = req.headers.authorization?.split(' ')[1];
            if (!token) {
                return res.status(401).json({ error: 'No token provided' });
            }
            
            // Check permission with OutlabsAuth
            const response = await fetch(`${OUTLABS_AUTH_URL}/v1/permissions/check`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    permission: permission,
                    resource_type: req.params.resourceType,
                    resource_id: req.params.resourceId
                })
            });
            
            if (response.ok) {
                const { allowed, reason } = await response.json();
                if (allowed) {
                    next();
                } else {
                    res.status(403).json({ error: 'Insufficient permissions', reason });
                }
            } else {
                res.status(403).json({ error: 'Permission check failed' });
            }
        } catch (error) {
            res.status(500).json({ error: 'Authorization error' });
        }
    };
}

// Usage
app.get('/api/leads/:id', requirePermission('lead:view'), async (req, res) => {
    // Handler code
});
```

### Pattern 2: Resource-Based Authorization

**Use Case**: Check permissions based on resource ownership

```javascript
class ResourceAuthorizer {
    async canAccessResource(userId, resourceType, resourceId, requiredPermission) {
        // 1. Get resource metadata
        const resource = await this.getResource(resourceType, resourceId);
        
        // 2. Get user's entity memberships
        const memberships = await this.getUserMemberships(userId);
        
        // 3. Check if user has permission in resource's entity context
        for (const membership of memberships) {
            // Direct entity match
            if (membership.entity_id === resource.entity_id) {
                if (membership.permissions.includes(requiredPermission)) {
                    return { allowed: true, context: 'direct' };
                }
            }
            
            // Check if user's entity is ancestor (for inherited permissions)
            const isAncestor = await this.checkEntityAncestor(
                membership.entity_id,
                resource.entity_id
            );
            
            if (isAncestor && membership.permissions.includes(requiredPermission + '_all')) {
                return { allowed: true, context: 'inherited' };
            }
        }
        
        return { allowed: false, reason: 'No permission in resource context' };
    }
}
```

### Pattern 3: Cached Permission Checking

**Use Case**: High-performance permission checks

```javascript
class CachedPermissionService {
    constructor() {
        this.cache = new Map();
        this.cacheTTL = 300000; // 5 minutes
    }
    
    async checkPermission(userId, permission, context) {
        const cacheKey = `${userId}:${permission}:${context || 'global'}`;
        
        // Check cache
        const cached = this.cache.get(cacheKey);
        if (cached && cached.expiry > Date.now()) {
            return cached.result;
        }
        
        // Fetch from OutlabsAuth
        const result = await this.fetchPermissionCheck(userId, permission, context);
        
        // Cache result
        this.cache.set(cacheKey, {
            result: result,
            expiry: Date.now() + this.cacheTTL
        });
        
        return result;
    }
    
    invalidateUserCache(userId) {
        // Clear all cache entries for user
        for (const [key] of this.cache) {
            if (key.startsWith(`${userId}:`)) {
                this.cache.delete(key);
            }
        }
    }
}
```

## Entity Management Patterns

### Pattern 1: Entity Creation with Validation

**Use Case**: Create entities with business rules

```javascript
class EntityManager {
    async createEntity(entityData, creatorId) {
        // 1. Validate business rules
        await this.validateEntityCreation(entityData, creatorId);
        
        // 2. Check creator's permissions
        const canCreate = await this.checkPermission(
            creatorId,
            'entity:create',
            entityData.parent_entity_id
        );
        
        if (!canCreate) {
            throw new ForbiddenError('Cannot create entity in this context');
        }
        
        // 3. Create in OutlabsAuth
        const entity = await this.outlabsAuth.post('/v1/entities/', {
            name: this.generateSystemName(entityData.display_name),
            display_name: entityData.display_name,
            entity_type: entityData.type,
            entity_class: entityData.class || 'structural',
            parent_entity_id: entityData.parent_entity_id,
            metadata: {
                created_by: creatorId,
                ...entityData.metadata
            }
        });
        
        // 4. Create related data in platform
        await this.createPlatformEntity({
            outlabs_entity_id: entity.id,
            ...entityData.platformSpecific
        });
        
        // 5. Set up default roles and permissions
        await this.setupDefaultRoles(entity.id, entityData.type);
        
        return entity;
    }
    
    generateSystemName(displayName) {
        return displayName
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, '_')
            .replace(/^_|_$/g, '')
            .substring(0, 50);
    }
}
```

### Pattern 2: Entity Hierarchy Navigation

**Use Case**: Navigate and display entity trees

```javascript
class EntityHierarchy {
    async getEntityTree(rootEntityId, maxDepth = 5) {
        const tree = await this.buildTree(rootEntityId, 0, maxDepth);
        return tree;
    }
    
    async buildTree(entityId, currentDepth, maxDepth) {
        if (currentDepth >= maxDepth) return null;
        
        // Get entity details
        const entity = await this.getEntity(entityId);
        
        // Get children
        const children = await this.getChildEntities(entityId);
        
        // Build tree node
        const node = {
            id: entity.id,
            name: entity.display_name,
            type: entity.entity_type,
            class: entity.entity_class,
            metadata: entity.metadata,
            children: []
        };
        
        // Recursively build children
        for (const child of children) {
            const childNode = await this.buildTree(
                child.id,
                currentDepth + 1,
                maxDepth
            );
            if (childNode) {
                node.children.push(childNode);
            }
        }
        
        return node;
    }
    
    async getUserAccessibleEntities(userId) {
        // Get all user memberships
        const memberships = await this.getUserMemberships(userId);
        
        // Build accessible entity list
        const accessible = new Set();
        
        for (const membership of memberships) {
            // Add direct membership
            accessible.add(membership.entity_id);
            
            // Add all ancestors (for upward navigation)
            const ancestors = await this.getEntityAncestors(membership.entity_id);
            ancestors.forEach(id => accessible.add(id));
            
            // Add all descendants if user has manage permission
            if (membership.permissions.includes('entity:manage')) {
                const descendants = await this.getEntityDescendants(membership.entity_id);
                descendants.forEach(id => accessible.add(id));
            }
        }
        
        return Array.from(accessible);
    }
}
```

## User Management Patterns

### Pattern 1: User Registration with Auto-Assignment

**Use Case**: New users automatically assigned to entities/roles

```javascript
class UserRegistrationService {
    async registerUser(registrationData) {
        // 1. Create user in OutlabsAuth
        const user = await this.outlabsAuth.post('/v1/users/', {
            email: registrationData.email,
            password: registrationData.password,
            profile: {
                first_name: registrationData.firstName,
                last_name: registrationData.lastName
            }
        });
        
        // 2. Determine initial entity placement
        const targetEntity = await this.determineInitialEntity(registrationData);
        
        // 3. Add to entity with appropriate role
        const role = await this.determineInitialRole(registrationData, targetEntity);
        
        await this.outlabsAuth.post('/v1/memberships/', {
            user_id: user.id,
            entity_id: targetEntity.id,
            role_ids: [role.id],
            metadata: {
                registration_source: registrationData.source,
                referral_code: registrationData.referralCode
            }
        });
        
        // 4. Create platform-specific profile
        await this.createPlatformProfile(user.id, registrationData);
        
        // 5. Send welcome email with role-specific content
        await this.sendWelcomeEmail(user, role, targetEntity);
        
        return user;
    }
    
    async determineInitialEntity(registrationData) {
        // Example logic for entity assignment
        if (registrationData.inviteCode) {
            const invite = await this.getInvite(registrationData.inviteCode);
            return invite.target_entity;
        }
        
        if (registrationData.organizationId) {
            return this.getEntity(registrationData.organizationId);
        }
        
        // Default to platform-level entity
        return this.getDefaultEntity();
    }
}
```

### Pattern 2: Bulk User Management

**Use Case**: Import/manage many users at once

```javascript
class BulkUserManager {
    async importUsers(csvData, targetEntityId, importOptions) {
        const results = {
            success: [],
            errors: [],
            skipped: []
        };
        
        // Process in batches for performance
        const batches = this.createBatches(csvData, 50);
        
        for (const batch of batches) {
            const batchPromises = batch.map(async (userData) => {
                try {
                    // Check if user exists
                    const existingUser = await this.findUserByEmail(userData.email);
                    
                    if (existingUser && !importOptions.updateExisting) {
                        results.skipped.push({
                            email: userData.email,
                            reason: 'User already exists'
                        });
                        return;
                    }
                    
                    let user;
                    if (existingUser) {
                        // Update existing user
                        user = await this.updateUser(existingUser.id, userData);
                    } else {
                        // Create new user
                        user = await this.createUser(userData);
                    }
                    
                    // Add to entity
                    await this.addToEntity(user.id, targetEntityId, userData.role);
                    
                    results.success.push({
                        email: userData.email,
                        userId: user.id
                    });
                    
                } catch (error) {
                    results.errors.push({
                        email: userData.email,
                        error: error.message
                    });
                }
            });
            
            await Promise.all(batchPromises);
        }
        
        return results;
    }
}
```

## Permission Checking Patterns

### Pattern 1: Context-Aware Permission Checks

**Use Case**: Check permissions with resource context

```javascript
class ContextualPermissionChecker {
    async canPerformAction(userId, action, resource) {
        // 1. Determine required permission
        const permission = this.getRequiredPermission(action, resource.type);
        
        // 2. Get resource's entity context
        const resourceEntity = await this.getResourceEntity(resource);
        
        // 3. Check user's permission in context
        const checkResult = await this.outlabsAuth.post('/v1/permissions/check', {
            user_id: userId,
            permission: permission,
            entity_id: resourceEntity.id,
            resource_attributes: {
                owner_id: resource.owner_id,
                status: resource.status,
                value: resource.value
            }
        });
        
        return checkResult;
    }
    
    getRequiredPermission(action, resourceType) {
        const permissionMap = {
            'view': `${resourceType}:read`,
            'edit': `${resourceType}:update`,
            'delete': `${resourceType}:delete`,
            'approve': `${resourceType}:approve`,
            'assign': `${resourceType}:assign`
        };
        
        return permissionMap[action] || `${resourceType}:${action}`;
    }
}
```

### Pattern 2: Batch Permission Checking

**Use Case**: Check multiple permissions efficiently

```javascript
class BatchPermissionChecker {
    async checkMultiplePermissions(userId, permissionChecks) {
        // Build batch request
        const batchRequest = permissionChecks.map(check => ({
            permission: check.permission,
            entity_id: check.entityId,
            resource_type: check.resourceType,
            resource_id: check.resourceId
        }));
        
        // Single API call for all checks
        const response = await this.outlabsAuth.post('/v1/permissions/check-batch', {
            user_id: userId,
            checks: batchRequest
        });
        
        // Map results back
        const results = {};
        response.results.forEach((result, index) => {
            const check = permissionChecks[index];
            results[check.key || check.permission] = result;
        });
        
        return results;
    }
    
    // Usage example
    async loadDashboard(userId) {
        const permissionChecks = [
            { key: 'canViewReports', permission: 'report:view' },
            { key: 'canManageUsers', permission: 'user:manage' },
            { key: 'canApproveExpenses', permission: 'expense:approve' },
            { key: 'canEditSettings', permission: 'settings:update' }
        ];
        
        const permissions = await this.checkMultiplePermissions(userId, permissionChecks);
        
        return {
            showReports: permissions.canViewReports.allowed,
            showUserManagement: permissions.canManageUsers.allowed,
            showApprovals: permissions.canApproveExpenses.allowed,
            showSettings: permissions.canEditSettings.allowed
        };
    }
}
```

## Synchronization Patterns

### Pattern 1: Webhook-Based Sync

**Use Case**: Real-time updates between systems

```javascript
class WebhookSyncService {
    async setupWebhooks() {
        // Register webhooks with OutlabsAuth
        await this.outlabsAuth.post('/v1/webhooks/', {
            url: `${this.platformUrl}/webhooks/outlabs-auth`,
            events: [
                'user.created',
                'user.updated',
                'user.deleted',
                'membership.created',
                'membership.updated',
                'membership.deleted',
                'role.assigned',
                'role.removed',
                'permission.changed'
            ],
            secret: this.webhookSecret
        });
    }
    
    async handleWebhook(event, data, signature) {
        // 1. Verify webhook signature
        if (!this.verifySignature(event, data, signature)) {
            throw new Error('Invalid webhook signature');
        }
        
        // 2. Process based on event type
        switch (event) {
            case 'user.created':
                await this.handleUserCreated(data);
                break;
                
            case 'membership.created':
                await this.handleMembershipCreated(data);
                break;
                
            case 'permission.changed':
                await this.handlePermissionChanged(data);
                break;
                
            // ... other event handlers
        }
        
        // 3. Acknowledge receipt
        return { status: 'processed' };
    }
    
    async handlePermissionChanged(data) {
        // Clear permission cache for affected user
        await this.permissionCache.invalidate(data.user_id);
        
        // Update platform-specific access
        await this.updatePlatformAccess(data.user_id);
        
        // Notify user if online
        await this.notifyUser(data.user_id, 'permissions_updated');
    }
}
```

### Pattern 2: Periodic Sync

**Use Case**: Batch synchronization for consistency

```javascript
class PeriodicSyncService {
    async performSync() {
        const syncReport = {
            users: { created: 0, updated: 0, errors: [] },
            memberships: { created: 0, updated: 0, errors: [] },
            entities: { created: 0, updated: 0, errors: [] }
        };
        
        try {
            // 1. Sync entities
            await this.syncEntities(syncReport);
            
            // 2. Sync users
            await this.syncUsers(syncReport);
            
            // 3. Sync memberships
            await this.syncMemberships(syncReport);
            
            // 4. Verify consistency
            await this.verifyConsistency(syncReport);
            
        } catch (error) {
            syncReport.error = error.message;
        }
        
        // 5. Log sync results
        await this.logSyncReport(syncReport);
        
        return syncReport;
    }
    
    async syncUsers(report) {
        // Get all users from OutlabsAuth
        const outlabsUsers = await this.getAllOutlabsUsers();
        const platformUsers = await this.getAllPlatformUsers();
        
        // Create map for efficient lookup
        const platformUserMap = new Map(
            platformUsers.map(u => [u.outlabs_user_id, u])
        );
        
        for (const outlabsUser of outlabsUsers) {
            try {
                const platformUser = platformUserMap.get(outlabsUser.id);
                
                if (!platformUser) {
                    // Create in platform
                    await this.createPlatformUser(outlabsUser);
                    report.users.created++;
                } else {
                    // Check for updates
                    if (this.needsUpdate(outlabsUser, platformUser)) {
                        await this.updatePlatformUser(outlabsUser, platformUser);
                        report.users.updated++;
                    }
                }
            } catch (error) {
                report.users.errors.push({
                    user_id: outlabsUser.id,
                    error: error.message
                });
            }
        }
    }
}
```

## Error Handling Patterns

### Pattern 1: Graceful Degradation

**Use Case**: Continue operating when auth service is unavailable

```javascript
class ResilientAuthService {
    async checkPermission(userId, permission, options = {}) {
        try {
            // Try to check with OutlabsAuth
            return await this.outlabsAuth.checkPermission(userId, permission);
            
        } catch (error) {
            // Log the error
            this.logger.error('Permission check failed', { error, userId, permission });
            
            // Check if we can use cached permissions
            if (options.allowCache) {
                const cached = await this.getCachedPermissions(userId);
                if (cached && cached.age < 3600000) { // 1 hour
                    return this.evaluatePermissionFromCache(cached, permission);
                }
            }
            
            // Check if this is a critical permission
            if (this.isCriticalPermission(permission)) {
                // Fail closed for critical permissions
                return { allowed: false, reason: 'Auth service unavailable' };
            }
            
            // For non-critical, check basic rules
            return this.checkBasicPermission(userId, permission);
        }
    }
    
    isCriticalPermission(permission) {
        const critical = [
            'payment:process',
            'user:delete',
            'data:export',
            'system:configure'
        ];
        return critical.includes(permission);
    }
}
```

### Pattern 2: Comprehensive Error Handling

**Use Case**: Handle all error scenarios gracefully

```javascript
class ErrorHandler {
    async handleAuthError(error, context) {
        // Categorize error
        const errorType = this.categorizeError(error);
        
        switch (errorType) {
            case 'INVALID_CREDENTIALS':
                return {
                    statusCode: 401,
                    message: 'Invalid email or password',
                    action: 'SHOW_LOGIN'
                };
                
            case 'TOKEN_EXPIRED':
                // Attempt refresh
                const refreshed = await this.attemptTokenRefresh(context);
                if (refreshed) {
                    return { statusCode: 200, action: 'RETRY', token: refreshed };
                }
                return {
                    statusCode: 401,
                    message: 'Session expired',
                    action: 'REDIRECT_LOGIN'
                };
                
            case 'INSUFFICIENT_PERMISSIONS':
                return {
                    statusCode: 403,
                    message: 'You do not have permission to perform this action',
                    requiredPermission: error.requiredPermission,
                    action: 'SHOW_PERMISSION_REQUEST'
                };
                
            case 'RATE_LIMITED':
                return {
                    statusCode: 429,
                    message: 'Too many requests',
                    retryAfter: error.retryAfter,
                    action: 'SHOW_RATE_LIMIT'
                };
                
            case 'SERVICE_UNAVAILABLE':
                return {
                    statusCode: 503,
                    message: 'Authentication service temporarily unavailable',
                    action: 'USE_OFFLINE_MODE'
                };
                
            default:
                // Log unknown errors
                this.logger.error('Unknown auth error', { error, context });
                return {
                    statusCode: 500,
                    message: 'An error occurred during authentication',
                    action: 'SHOW_ERROR'
                };
        }
    }
}
```

## Performance Optimization

### Pattern 1: Permission Prefetching

**Use Case**: Preload permissions for better performance

```javascript
class PermissionPrefetcher {
    async prefetchUserPermissions(userId, context) {
        // Identify likely needed permissions based on context
        const permissionsToFetch = this.predictPermissions(context);
        
        // Batch fetch all permissions
        const permissionPromises = permissionsToFetch.map(permission => 
            this.permissionCache.get(userId, permission)
        );
        
        const results = await Promise.all(permissionPromises);
        
        // Warm cache with results
        results.forEach((result, index) => {
            this.permissionCache.set(
                userId,
                permissionsToFetch[index],
                result
            );
        });
        
        return results;
    }
    
    predictPermissions(context) {
        const predictions = {
            'dashboard': [
                'dashboard:view',
                'report:view',
                'user:list',
                'notification:view'
            ],
            'user_management': [
                'user:list',
                'user:view',
                'user:create',
                'user:update',
                'role:list',
                'role:assign'
            ],
            'report_viewer': [
                'report:view',
                'report:export',
                'data:read'
            ]
        };
        
        return predictions[context] || [];
    }
}
```

### Pattern 2: Batch Operations

**Use Case**: Optimize bulk operations

```javascript
class BatchOperationOptimizer {
    async assignRoleToMultipleUsers(userIds, roleId, entityId) {
        // Instead of individual API calls
        // DON'T DO THIS:
        // for (const userId of userIds) {
        //     await this.assignRole(userId, roleId, entityId);
        // }
        
        // DO THIS: Single batch operation
        const batchOperation = {
            operation: 'role_assignment',
            role_id: roleId,
            entity_id: entityId,
            user_ids: userIds
        };
        
        const result = await this.outlabsAuth.post('/v1/batch-operations/', batchOperation);
        
        // Clear caches for affected users
        await this.permissionCache.invalidateMultiple(userIds);
        
        return result;
    }
    
    async createMultipleEntities(entitiesData) {
        // Validate all entities first
        const validationResults = await this.validateEntities(entitiesData);
        
        if (validationResults.errors.length > 0) {
            throw new ValidationError('Some entities failed validation', validationResults.errors);
        }
        
        // Create all entities in a transaction
        const transaction = await this.outlabsAuth.post('/v1/transactions/', {
            operations: entitiesData.map(entity => ({
                method: 'POST',
                endpoint: '/v1/entities/',
                data: entity
            }))
        });
        
        return transaction.results;
    }
}
```

## Best Practices Summary

### 1. Authentication
- Always use HTTPS
- Implement token refresh logic
- Store tokens securely
- Handle logout properly

### 2. Authorization
- Check permissions server-side
- Cache permission results
- Use middleware for consistency
- Fail closed for critical operations

### 3. Performance
- Batch API operations
- Implement caching strategically
- Prefetch likely permissions
- Use webhooks for real-time updates

### 4. Error Handling
- Graceful degradation
- Informative error messages
- Proper status codes
- Comprehensive logging

### 5. Integration
- Use environment variables for configuration
- Implement circuit breakers
- Version your API calls
- Monitor API usage

These patterns provide a foundation for building robust integrations with OutlabsAuth while maintaining security, performance, and reliability.