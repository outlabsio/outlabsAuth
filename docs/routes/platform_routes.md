# Platform Management Routes Documentation

## Overview

The Platform Management Routes provide endpoints for platform-level operations, including cross-client analytics and business intelligence. These endpoints are designed for PropertyHub-style platforms where platform staff need to manage multiple client companies.

**Base URL**: `/v1/platform`

## Authentication

All platform routes require authentication via Bearer token. Additionally, most endpoints require platform staff privileges with appropriate permissions.

```bash
Authorization: Bearer <access_token>
```

## Platform Staff Requirements

Platform routes are restricted to users with:

- `is_platform_staff: true`
- Appropriate platform-specific permissions
- Valid platform scope

---

## Endpoints

### 1. Get Platform Analytics

Retrieve comprehensive business intelligence and analytics across all client accounts managed by the platform.

**Endpoint**: `GET /v1/platform/analytics`

**Permissions Required**:

- `platform:view_analytics`
- User must be platform staff

**Parameters**: None

**Response**:

```json
{
  "total_clients": 4,
  "total_users": 12,
  "platform_staff_count": 3,
  "client_breakdown": [
    {
      "name": "ACME Real Estate",
      "description": "Independent real estate brokerage using PropertyHub",
      "user_count": 3
    },
    {
      "name": "Elite Properties",
      "description": "Luxury real estate firm using PropertyHub",
      "user_count": 2
    },
    {
      "name": "Downtown Realty",
      "description": "Urban real estate specialists using PropertyHub",
      "user_count": 1
    }
  ]
}
```

**Status Codes**:

- `200 OK`: Analytics retrieved successfully
- `401 Unauthorized`: Invalid or missing authentication token
- `403 Forbidden`: User is not platform staff or lacks `platform:view_analytics` permission
- `500 Internal Server Error`: Server error during analytics calculation

**Example Request**:

```bash
curl -X GET "http://localhost:8030/v1/platform/analytics" \
  -H "Authorization: Bearer <platform_admin_token>" \
  -H "Content-Type: application/json"
```

**Example Response**:

```json
{
  "total_clients": 4,
  "total_users": 12,
  "platform_staff_count": 3,
  "client_breakdown": [
    {
      "name": "ACME Real Estate",
      "description": "Independent real estate brokerage using PropertyHub",
      "user_count": 3
    },
    {
      "name": "Elite Properties",
      "description": "Luxury real estate firm using PropertyHub",
      "user_count": 2
    },
    {
      "name": "Downtown Realty",
      "description": "Urban real estate specialists using PropertyHub",
      "user_count": 1
    },
    {
      "name": "PropertyHub Platform",
      "description": "PropertyHub SaaS platform for real estate management",
      "user_count": 3
    }
  ]
}
```

---

## Business Intelligence Features

### Analytics Capabilities

The platform analytics endpoint provides:

1. **Client Overview**:

   - Total number of managed client accounts
   - Individual client account user counts
   - Client account descriptions and metadata

2. **User Metrics**:

   - Total users across all clients
   - Platform staff count
   - User distribution across client accounts

3. **Platform Health**:
   - Active client accounts
   - User engagement metrics
   - Platform utilization statistics

### Use Cases

**Platform Management**:

- Monitor client account growth
- Track user adoption across clients
- Identify high-value client accounts

**Business Intelligence**:

- Generate executive dashboards
- Create client success metrics
- Support sales and marketing decisions

**Customer Success**:

- Identify clients needing support
- Monitor user activity patterns
- Proactive client engagement

---

## Security & Access Control

### Platform Staff Validation

The platform analytics endpoint includes comprehensive security checks:

1. **Authentication Verification**: Valid JWT token required
2. **Platform Staff Check**: User must have `is_platform_staff: true`
3. **Permission Validation**: Must have `platform:view_analytics` permission
4. **Cross-Client Access**: Platform staff can view data across all managed clients

### Data Protection

- **Client Isolation**: While platform staff can see aggregate data, individual client data remains protected
- **Permission-Based Access**: Granular permissions control what platform staff can access
- **Audit Trail**: All platform analytics access is logged for security compliance

---

## Error Handling

### Common Error Responses

**403 Forbidden - Not Platform Staff**:

```json
{
  "detail": "Platform analytics access restricted to platform staff."
}
```

**403 Forbidden - Missing Permission**:

```json
{
  "detail": "Insufficient permissions. Required: platform:view_analytics"
}
```

**500 Internal Server Error**:

```json
{
  "detail": "Internal server error during analytics calculation"
}
```

---

## Integration Examples

### Python Client Example

```python
import requests

def get_platform_analytics(access_token):
    """Fetch platform analytics for business intelligence"""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    response = requests.get(
        "http://localhost:8030/v1/platform/analytics",
        headers=headers
    )

    if response.status_code == 200:
        analytics = response.json()
        print(f"Total Clients: {analytics['total_clients']}")
        print(f"Total Users: {analytics['total_users']}")
        return analytics
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None

# Usage
analytics = get_platform_analytics(platform_admin_token)
```

### JavaScript Client Example

```javascript
async function getPlatformAnalytics(accessToken) {
  try {
    const response = await fetch("/v1/platform/analytics", {
      method: "GET",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "Content-Type": "application/json",
      },
    });

    if (response.ok) {
      const analytics = await response.json();
      console.log(`Total Clients: ${analytics.total_clients}`);
      console.log(`Total Users: ${analytics.total_users}`);
      return analytics;
    } else {
      console.error(`Error: ${response.status} - ${await response.text()}`);
      return null;
    }
  } catch (error) {
    console.error("Network error:", error);
    return null;
  }
}

// Usage
const analytics = await getPlatformAnalytics(platformAdminToken);
```

---

## Best Practices

### Performance Considerations

1. **Caching**: Consider implementing caching for analytics data that doesn't change frequently
2. **Pagination**: For large platforms, consider paginating client breakdown data
3. **Rate Limiting**: Implement rate limiting for analytics endpoints to prevent abuse

### Monitoring & Logging

1. **Access Logging**: Log all platform analytics access for audit purposes
2. **Performance Monitoring**: Track response times for analytics calculations
3. **Error Tracking**: Monitor and alert on analytics endpoint errors

### Future Enhancements

Potential future additions to platform analytics:

- Time-series data for trend analysis
- Advanced filtering and querying capabilities
- Export functionality for business reports
- Real-time analytics updates
- Custom dashboard creation

---

## Related Documentation

- [Client Account Routes](client_account_routes.md) - For enhanced client onboarding
- [Auth Routes](auth_routes.md) - For platform staff authentication
- [Permission Routes](permission_routes.md) - For platform permission management
- [User Routes](user_routes.md) - For cross-client user management
