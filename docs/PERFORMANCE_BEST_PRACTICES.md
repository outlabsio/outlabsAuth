# Performance Best Practices for outlabsAuth Integration

## 1. Overview

A fast, responsive user experience is critical for any application. While outlabsAuth provides robust, centralized authorization, a naive integration could lead to performance bottlenecks due to excessive API calls.

This document outlines the recommended integration pattern to ensure your application is both highly performant and secure. By following these best practices, you can minimize network latency and provide a seamless experience for your users.

## 2. The Recommended Two-Tier Caching Pattern

The core of a high-performance integration lies in a two-tier caching strategy. This pattern intelligently combines client-side caching for speed with real-time server checks for security and complex rule evaluation.

**The flow is simple: cache what you can, and check what you must.**

### Tier 1: Client-Side Pre-Fetch & Cache (For Speed)

For most standard permission checks (e.g., "should this 'Edit' button be visible?"), you can avoid a network call on every single check.

**The Pattern:**

1. **Fetch Permissions on Load**: When a user loads a page, a component, or starts a business process, make a single API call to the `GET /v1/users/me/permissions?context={entity_id}` endpoint.

2. **Receive Permission Set**: This call will return a list of all the simple, non-conditional permission strings the user has in that specific context (e.g., `["lead:read", "lead:create", "lead:assign"]`).

3. **Cache Locally**: Store this list of permissions in a short-lived, in-memory cache on your client's backend. The cache duration should be brief (e.g., 1-5 minutes) or scoped to a single user request to ensure data doesn't become too stale.

4. **Check In-Memory**: For the remainder of that user's session or request, perform permission checks against this cached list. This is incredibly fast as it requires no network latency.

**Example Implementation:**

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
    
    // 1. Return from cache if available and not expired
    if (cached && cached.timestamp > Date.now() - this.cacheTimeout) {
      return cached.permissions
    }

    // 2. Fetch from API if not in cache
    const response = await this.makeAuthenticatedRequest(
      `${this.baseURL}/v1/users/me/permissions${context ? `?context=${context}` : ''}`
    )
    
    const data = await response.json()
    
    // 3. Store in cache for next time
    this.permissionCache.set(cacheKey, {
      permissions: data.permissions,
      timestamp: Date.now()
    })
    
    return data.permissions
  }

  // Quick in-memory check
  async hasPermission(permission, context) {
    const permissions = await this.getPermissions(context)
    return permissions.includes(permission)
  }
}
```

### Tier 2: Server-Side Check (For Security & Complex Rules)

You should **always** perform a real-time, server-side check for:

- **Sensitive Operations**: Any critical action like deleting data, transferring ownership, or processing payments.
- **Conditional Permissions**: Any permission that relies on our new Attribute-Based Access Control (ABAC) rules (e.g., checking an invoice value).

**The Pattern:**

1. A user attempts a critical action (e.g., approving an invoice worth $25,000).

2. Your backend makes a specific, real-time API call to `POST /v1/permissions/check`.

3. Crucially, you pass the attributes of the resource being acted upon in the request body:

```json
{
  "permission": "invoice:approve",
  "context": {
    "entity_id": "ent_miami_office"
  },
  "resource_attributes": { 
    "value": 25000, 
    "currency": "USD",
    "status": "pending_approval"
  }
}
```

4. outlabsAuth evaluates this against any policies attached to the `invoice:approve` permission and returns a definitive `{"allowed": true/false}`.

**Example Implementation:**

```javascript
class SecureOperationService {
  async approveInvoice(invoiceId, approverUserId) {
    const invoice = await this.getInvoice(invoiceId)
    
    // Real-time permission check with resource context
    const permissionCheck = await authService.checkPermissionWithContext(
      'invoice:approve',
      { entity_id: invoice.entity_id },
      {
        value: invoice.amount,
        currency: invoice.currency,
        status: invoice.status,
        department: invoice.department
      }
    )
    
    if (!permissionCheck.allowed) {
      throw new ForbiddenError(
        `Cannot approve invoice: ${permissionCheck.reason}`
      )
    }
    
    // Proceed with the operation
    return await this.processApproval(invoice, approverUserId)
  }
}
```

### How We Keep This Fast

You might worry that this real-time check will be slow. However, our backend employs its own aggressive caching layer:

1. **Policy Result Caching**: We cache the outcome of specific permission checks based on user, permission, entity, and resource attributes.

2. **Smart Cache Keys**: The cache key includes a hash of the resource attributes, ensuring we cache each unique scenario.

3. **Short TTL**: Cache entries have a short time-to-live (1-5 minutes) to balance performance with data freshness.

4. **Permission Definition Caching**: Permission structures (including conditions) are cached with longer TTLs since they change infrequently.

## 3. Best Practices by Scenario

### UI Component Visibility

**Use Tier 1 Caching:**

```javascript
// React component example
function LeadManagementView() {
  const [permissions, setPermissions] = useState([])
  
  useEffect(() => {
    // Fetch permissions once on component mount
    authService.getPermissions(currentEntityId)
      .then(perms => setPermissions(perms))
  }, [currentEntityId])
  
  return (
    <div>
      {permissions.includes('lead:read') && <LeadList />}
      {permissions.includes('lead:create') && <CreateLeadButton />}
      {permissions.includes('lead:export') && <ExportButton />}
    </div>
  )
}
```

### API Endpoint Protection

**Use Both Tiers:**

```python
@router.post("/api/invoices/{invoice_id}/approve")
async def approve_invoice(
    invoice_id: str,
    current_user: User = Depends(get_current_user)
):
    # Tier 1: Quick check for basic permission
    if "invoice:approve" not in current_user.cached_permissions:
        raise HTTPException(403, "No approval permission")
    
    # Load the invoice
    invoice = await get_invoice(invoice_id)
    
    # Tier 2: Real-time check with resource context
    permission_result = await auth_client.check_permission(
        user_id=current_user.id,
        permission="invoice:approve",
        entity_id=invoice.entity_id,
        resource_attributes={
            "value": invoice.amount,
            "status": invoice.status,
            "department": invoice.department
        }
    )
    
    if not permission_result.allowed:
        raise HTTPException(403, permission_result.reason)
    
    # Process the approval
    return await process_invoice_approval(invoice)
```

### Batch Operations

**Optimize API Calls:**

```javascript
// Bad: Multiple API calls
async function checkMultiplePermissions() {
  const canRead = await authService.checkPermission('lead:read')
  const canCreate = await authService.checkPermission('lead:create')
  const canDelete = await authService.checkPermission('lead:delete')
}

// Good: Single API call
async function checkMultiplePermissions() {
  const permissions = await authService.getPermissions(entityId)
  const canRead = permissions.includes('lead:read')
  const canCreate = permissions.includes('lead:create')
  const canDelete = permissions.includes('lead:delete')
}
```

## 4. Cache Invalidation Strategies

### When to Invalidate Client Cache

1. **User Role Changes**: Clear cache when user's roles are modified
2. **Entity Switch**: Clear cache when user switches to a different entity context
3. **Time-Based**: Automatic expiration after 5 minutes
4. **Explicit Logout**: Clear all cached data on logout

```javascript
class CacheManager {
  invalidateUserPermissions() {
    this.permissionCache.clear()
  }
  
  onRoleChange() {
    this.invalidateUserPermissions()
    // Optionally notify UI components to refresh
    eventBus.emit('permissions-changed')
  }
  
  onEntitySwitch(newEntityId) {
    // Only clear cache for the old entity, keep others
    const keysToDelete = []
    for (const [key, value] of this.permissionCache) {
      if (!key.includes(newEntityId)) {
        keysToDelete.push(key)
      }
    }
    keysToDelete.forEach(key => this.permissionCache.delete(key))
  }
}
```

## 5. Performance Monitoring

Track these metrics to ensure optimal performance:

```javascript
// Track cache performance
const metrics = {
  cacheHits: 0,
  cacheMisses: 0,
  apiCallDuration: [],
  cacheHitRate: function() {
    const total = this.cacheHits + this.cacheMisses
    return total > 0 ? this.cacheHits / total : 0
  }
}

// Wrap your permission checks
async function checkPermissionWithMetrics(permission, context) {
  const startTime = Date.now()
  
  // Try cache first
  const cached = await getFromCache(permission, context)
  if (cached !== null) {
    metrics.cacheHits++
    return cached
  }
  
  // Cache miss - make API call
  metrics.cacheMisses++
  const result = await authService.checkPermission(permission, context)
  
  metrics.apiCallDuration.push(Date.now() - startTime)
  
  return result
}
```

## 6. Common Pitfalls to Avoid

### 1. Over-Caching
**Problem**: Caching permissions for too long (hours/days)
**Solution**: Keep cache TTL short (5 minutes max)

### 2. Under-Caching
**Problem**: Making API calls for every button/component
**Solution**: Batch fetch permissions on page load

### 3. Forgetting Context
**Problem**: Not passing resource attributes for conditional permissions
**Solution**: Always include resource context for sensitive operations

### 4. Client-Side Only Checks
**Problem**: Relying solely on cached permissions for critical operations
**Solution**: Always validate server-side for mutations

## 7. Implementation Checklist

- [ ] Implement client-side permission caching with 5-minute TTL
- [ ] Create helper functions for common permission checks
- [ ] Add real-time checks for all mutation operations
- [ ] Include resource attributes for conditional permissions
- [ ] Set up cache invalidation on role/entity changes
- [ ] Monitor cache hit rates and API call latency
- [ ] Document which permissions require real-time checks
- [ ] Train developers on when to use each tier

## 8. Conclusion: The Best of Both Worlds

By implementing this two-tier pattern, your application gets:

- **Speed**: The vast majority of permission checks for UI elements are performed instantly from an in-memory cache.
- **Security**: Critical actions and complex business rules are always validated against the central, authoritative source in real-time.
- **Scalability**: Your application avoids being "chatty" and minimizes the load on both your own services and the outlabsAuth API.

Adopting this strategy is the key to a successful and performant integration with the outlabsAuth platform.