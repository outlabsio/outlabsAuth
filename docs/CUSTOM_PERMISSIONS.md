# Custom Permissions System (Enhanced with ABAC)

## Overview

outlabsAuth provides a powerful hybrid authorization system that combines RBAC (Role-Based), ReBAC (Relationship-Based), and ABAC (Attribute-Based) access control. Platforms can define business-specific permissions with optional conditions for granular, context-aware authorization.

## Key Concepts

### Permission Structure

Each permission follows a structured format:

```
resource:action
```

Examples:
- `lead:create` - Create new leads
- `invoice:approve` - Approve invoices
- `report:view_quarterly` - View quarterly reports

### Permission Components

```json
{
  "name": "invoice:approve",
  "display_name": "Approve Invoices",
  "description": "Allows approving invoices for payment processing",
  "resource": "invoice",
  "action": "approve",
  "scope": null,  // Optional: "team", "department", "organization"
  "entity_id": null,  // Optional: Specific to an entity
  "is_system": false,
  "is_active": true,
  "tags": ["finance", "accounting"],
  
  // NEW: ABAC Conditions (optional)
  "conditions": [
    {
      "attribute": "resource.value",
      "operator": "LESS_THAN_OR_EQUAL",
      "value": 50000
    },
    {
      "attribute": "resource.status",
      "operator": "EQUALS",
      "value": "pending_approval"
    }
  ],
  
  // DEPRECATED: Use conditions instead
  "metadata": {}
}
```

### Condition Structure

Each condition consists of:
- **attribute**: Path to the attribute (e.g., `resource.value`, `user.department`)
- **operator**: Comparison operator (e.g., `EQUALS`, `LESS_THAN`, `IN`)
- **value**: The value to compare against (static or dynamic reference)

## System vs Custom Permissions

### System Permissions

Built-in permissions that cannot be modified:
- `user:read`, `user:create`, `user:manage`
- `entity:read`, `entity:create`, `entity:manage`
- `role:read`, `role:create`, `role:manage`
- `permission:read`, `permission:create`, `permission:manage`

### Custom Permissions

Platform-specific permissions created by organizations:
- Can be created, updated, and deleted via API
- Scoped to entities (global or specific)
- Support metadata and tags
- Validated when assigned to roles

## API Endpoints

### List Available Permissions

```bash
GET /v1/permissions/available?entity_id=123&include_system=true

Response:
{
  "permissions": [
    {
      "id": "abc123",
      "name": "lead:create",
      "display_name": "Create Leads",
      "resource": "lead",
      "action": "create",
      "is_system": false,
      "tags": ["crm", "sales"]
    }
  ],
  "total": 45,
  "system_count": 41,
  "custom_count": 4
}
```

### Create Custom Permission

```bash
# Simple permission (backward compatible)
POST /v1/permissions/
{
  "name": "contract:view",
  "display_name": "View Contracts",
  "description": "Allows viewing contracts",
  "tags": ["legal", "contracts"]
}

# Conditional permission with ABAC
POST /v1/permissions/
{
  "name": "contract:sign",
  "display_name": "Sign Contracts",
  "description": "Allows digitally signing contracts with limits",
  "tags": ["legal", "contracts"],
  "conditions": [
    {
      "attribute": "resource.value",
      "operator": "LESS_THAN",
      "value": 1000000
    },
    {
      "attribute": "user.authorization_level",
      "operator": "GREATER_THAN_OR_EQUAL",
      "value": 3
    }
  ]
}
```

### Update Permission

```bash
PUT /v1/permissions/{permission_id}
{
  "display_name": "Sign Legal Contracts",
  "is_active": true,
  "metadata": {
    "requires_approval": true,
    "max_value": 5000000
  }
}
```

### Delete Permission

```bash
DELETE /v1/permissions/{permission_id}
```

Note: Cannot delete permissions that are currently assigned to roles.

### Validate Permissions

```bash
POST /v1/permissions/validate
{
  "permissions": ["user:read", "lead:create", "invalid:permission"]
}

Response:
{
  "valid": false,
  "errors": ["Invalid permission: invalid:permission"]
}
```

## Supported Condition Operators

### Comparison Operators
- `EQUALS`: Exact match (works with strings, numbers, booleans)
- `NOT_EQUALS`: Not equal to
- `LESS_THAN`: Numeric less than
- `LESS_THAN_OR_EQUAL`: Numeric less than or equal
- `GREATER_THAN`: Numeric greater than
- `GREATER_THAN_OR_EQUAL`: Numeric greater than or equal

### Collection Operators
- `IN`: Value exists in list
- `NOT_IN`: Value does not exist in list
- `CONTAINS`: Array/string contains value
- `NOT_CONTAINS`: Array/string does not contain value

### String Operators
- `STARTS_WITH`: String starts with value
- `ENDS_WITH`: String ends with value
- `REGEX_MATCH`: Matches regular expression

### Existence Operators
- `EXISTS`: Attribute exists (value should be true/false)
- `NOT_EXISTS`: Attribute does not exist

## Usage in Roles

### Creating Roles with Custom Permissions

```bash
POST /v1/roles/
{
  "name": "sales_manager",
  "display_name": "Sales Manager",
  "permissions": [
    "user:read",           // System permission
    "lead:create",         // Custom permission
    "lead:update",         // Custom permission
    "report:view_sales"    // Custom permission
  ]
}
```

### Permission Validation

When creating or updating roles, all permissions are validated:
1. System permissions are checked against the built-in list
2. Custom permissions are verified to exist and be active
3. Entity-scoped permissions are checked for accessibility

## Permission Evaluation

### Three-Layer Evaluation Process

When checking permissions, the system evaluates:

1. **RBAC Check**: Does the user have the permission through their roles?
2. **ReBAC Check**: Is the user's entity relationship valid for this context?
3. **ABAC Check**: Do all conditions evaluate to true?

All three checks must pass for access to be granted.

### Checking Permissions with Resource Context

```bash
POST /v1/permissions/check
{
  "permission": "invoice:approve",
  "context": {
    "entity_id": "ent_miami_office"
  },
  "resource_attributes": {
    "type": "invoice",
    "value": 45000,
    "status": "pending_approval",
    "department": "sales"
  }
}

Response:
{
  "allowed": true,
  "evaluation_details": {
    "rbac_check": "passed",
    "rebac_check": "passed",
    "conditions_evaluated": [
      {
        "condition": "resource.value <= 50000",
        "result": "passed"
      },
      {
        "condition": "resource.status == pending_approval",
        "result": "passed"
      }
    ]
  }
}
```

### Permission Expansion

Some permissions automatically include others:
- `resource:manage` includes `resource:read`, `resource:create`, `resource:update`, `resource:delete`
- `*:manage_all` includes all permissions for all resources

Note: Custom permissions do NOT automatically expand. If you want `lead:manage` to include other lead permissions, you must explicitly assign them.

## Best Practices

### 1. Naming Conventions

Use consistent naming:
- **Resource**: Singular noun (`lead`, `invoice`, `report`)
- **Action**: Verb (`create`, `read`, `update`, `delete`, `approve`, `sign`)
- **Scope**: When needed (`view_team`, `manage_department`)

### 2. Granularity

Balance between too many and too few permissions:
- ❌ Too broad: `system:all`
- ❌ Too specific: `lead:update_phone_number`
- ✅ Just right: `lead:update`

### 3. Resource Grouping

Group related permissions:
```
lead:create
lead:read
lead:update
lead:delete
lead:assign
lead:convert
```

### 4. Metadata Usage

Use metadata for business rules:
```json
{
  "name": "purchase:approve",
  "metadata": {
    "max_amount": 10000,
    "requires_2fa": true,
    "requires_manager_approval": true
  }
}
```

### 5. Entity Scoping

Create entity-specific permissions when needed:
- Global: `report:view_quarterly` (available to all entities)
- Entity-specific: `report:view_confidential` (only for specific organization)

## Examples by Industry

### CRM System with Conditional Permissions

```json
// Basic read permission
{
  "name": "lead:read",
  "display_name": "View Leads",
  "description": "View lead information"
}

// Conditional approval based on value
{
  "name": "deal:approve",
  "display_name": "Approve Deals",
  "conditions": [
    {
      "attribute": "resource.value",
      "operator": "LESS_THAN",
      "value": 100000
    }
  ]
}

// Commission approval with multiple conditions
{
  "name": "commission:approve",
  "display_name": "Approve Commissions",
  "conditions": [
    {
      "attribute": "resource.amount",
      "operator": "LESS_THAN_OR_EQUAL",
      "value": 50000
    },
    {
      "attribute": "resource.agent_tenure_months",
      "operator": "GREATER_THAN",
      "value": 6
    }
  ]
}
```

### E-commerce Platform
```
product:create       - Add new products
product:publish      - Publish products to store
inventory:manage     - Manage stock levels
order:view           - View orders
order:fulfill        - Process orders
order:refund         - Issue refunds
discount:create      - Create discount codes
report:view_revenue  - View revenue reports
```

### Healthcare System
```
patient:view         - View patient records
patient:update       - Update patient information
prescription:create  - Write prescriptions
prescription:approve - Approve prescriptions
appointment:schedule - Schedule appointments
report:view_clinical - View clinical reports
billing:submit       - Submit insurance claims
```

## Migration Guide

### From Hardcoded to Custom Permissions

1. **Audit Current Permissions**: List all hardcoded permission strings
2. **Create Custom Permissions**: Use the API to create each permission
3. **Update Roles**: Replace permission strings with validated custom permissions
4. **Test Thoroughly**: Verify permission checks still work
5. **Remove Hardcoded Checks**: Update application code to use dynamic permissions

### Example Migration

Before:
```python
if "lead:create" in user_permissions:  # Hardcoded string
    allow_lead_creation()
```

After:
```python
# Permissions now validated against custom permissions
if await has_permission(user, "lead:create"):
    allow_lead_creation()
```

## Troubleshooting

### Common Issues

1. **"Invalid permission" error**
   - Ensure the permission exists in the system
   - Check if it's active
   - Verify entity scope if applicable

2. **"Cannot delete permission"**
   - Check if any roles are using the permission
   - Remove from roles first, then delete

3. **Permission not working**
   - Verify the permission is assigned to user's role
   - Check entity membership and hierarchy
   - Ensure permission is active

### Debugging Commands

```bash
# Check user's effective permissions
GET /v1/users/{user_id}/permissions?entity_id=123

# Check role permissions
GET /v1/roles/{role_id}

# Validate permission set
POST /v1/permissions/validate
```

## Security Considerations

1. **Permission Creation**: Only users with `permission:create` can create new permissions
2. **Scope Limitations**: Entity-scoped permissions don't leak across organizations
3. **Audit Trail**: All permission changes should be logged
4. **Regular Review**: Periodically review and clean up unused permissions
5. **Principle of Least Privilege**: Grant minimum required permissions