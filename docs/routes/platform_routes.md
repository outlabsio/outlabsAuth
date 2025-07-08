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

- `client_account:read`
- User must have `is_platform_staff: true`

**Parameters**: None

**Response**:

```json
{
  "total_clients": 4,
  "total_users": 12,
  "platform_clients": 1,
  "real_estate_clients": 3,
  "platform_staff": 3,
  "client_users": 9,
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

**Response Fields**:

- `total_clients`: Total number of client accounts across the platform
- `total_users`: Total number of users across all client accounts
- `platform_clients`: Number of client accounts that are platform-owned (contain "Platform" in name)
- `real_estate_clients`: Number of real estate client accounts (non-platform clients)
- `platform_staff`: Number of users with `is_platform_staff: true`
- `client_users`: Number of regular client users (non-platform staff)
- `client_breakdown`: Array of client account details with user counts

**Status Codes**:

- `200 OK`: Analytics retrieved successfully
- `401 Unauthorized`: Invalid or missing authentication token
- `403 Forbidden`: User is not platform staff or lacks `client_account:read` permission
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
  "platform_clients": 1,
  "real_estate_clients": 3,
  "platform_staff": 3,
  "client_users": 9,
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
   - Separation between platform-owned and real estate clients
   - Individual client account user counts
   - Client account descriptions and metadata

2. **User Metrics**:

   - Total users across all clients
   - Platform staff count vs regular client users
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
- Separate platform operations from client operations

**Business Intelligence**:

- Generate executive dashboards
- Create client success metrics
- Support sales and marketing decisions
- Track platform vs client user ratios

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
3. **Permission Validation**: Must have `client_account:read` permission
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
  "detail": "You do not have permission to read client accounts."
}
```

**401 Unauthorized**:

```json
{
  "detail": "Could not validate credentials"
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
        print(f"Platform Staff: {analytics['platform_staff']}")
        print(f"Client Users: {analytics['client_users']}")

        # Print client breakdown
        for client in analytics['client_breakdown']:
            print(f"Client: {client['name']} - Users: {client['user_count']}")

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
      console.log(`Platform Staff: ${analytics.platform_staff}`);
      console.log(`Client Users: ${analytics.client_users}`);

      # Display client breakdown
      analytics.client_breakdown.forEach(client => {
        console.log(`${client.name}: ${client.user_count} users`);
      });

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

# Usage
const analytics = await getPlatformAnalytics(platformAdminToken);
```

---

## Dependencies and Services

### Core Services Used

The platform analytics endpoint utilizes the following services:

1. **ClientAccountService**:

   - `get_client_accounts()` - Retrieves all client accounts
   - Provides client metadata and hierarchical information

2. **UserService**:

   - `get_users()` - Retrieves all users across the platform
   - `get_user_effective_permissions()` - Validates user permissions

3. **Dependencies**:
   - `get_current_user` - Authenticates and retrieves current user context

### Permission System Integration

The endpoint integrates with the comprehensive permission system:

- Checks for `client_account:read` permission
- Validates `is_platform_staff` flag on user model
- Utilizes effective permissions calculation from user service

---

## Best Practices

### Performance Considerations

1. **Caching**: Consider implementing caching for analytics data that doesn't change frequently
2. **Pagination**: For large platforms, consider paginating client breakdown data
3. **Rate Limiting**: Implement rate limiting for analytics endpoints to prevent abuse
4. **Indexing**: Ensure proper database indexes on `is_platform_staff` and client relationships

### Monitoring & Logging

1. **Access Logging**: Log all platform analytics access for audit purposes
2. **Performance Monitoring**: Track response times for analytics calculations
3. **Error Tracking**: Monitor and alert on analytics endpoint errors
4. **Permission Violations**: Log attempts to access without proper permissions

### Security Considerations

1. **Principle of Least Privilege**: Only grant platform staff status when necessary
2. **Regular Audits**: Regularly review who has platform staff access
3. **Separation of Concerns**: Keep platform operations separate from client operations
4. **Data Classification**: Understand that platform analytics expose cross-client data

### Future Enhancements

Potential future additions to platform analytics:

- Time-series data for trend analysis
- Advanced filtering and querying capabilities
- Export functionality for business reports
- Real-time analytics updates
- Custom dashboard creation
- Client health scoring
- User activity patterns
- Growth metrics and forecasting

---

## Related Documentation

- [Client Account Routes](client_account_routes.md) - For enhanced client onboarding
- [Auth Routes](auth_routes.md) - For platform staff authentication
- [Permission Routes](permission_routes.md) - For platform permission management
- [User Routes](user_routes.md) - For cross-client user management
- [Settings Routes](settings_routes.md) - For system-level configuration management
- [Dependencies Documentation](../dependencies.md) - For authentication and permission dependencies
