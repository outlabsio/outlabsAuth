# Conditional Permissions Examples

This document provides practical examples of creating and using conditional permissions in outlabsAuth.

## Example 1: Invoice Approval with Value Limits

Create a permission that allows approving invoices only under a certain value:

```bash
curl -X POST http://localhost:8030/v1/permissions \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "invoice:approve",
    "display_name": "Approve Invoices",
    "description": "Allows approving invoices with value and department restrictions",
    "entity_id": "507f1f77bcf86cd799439011",
    "tags": ["finance", "accounting"],
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
      },
      {
        "attribute": "resource.department",
        "operator": "IN",
        "value": ["finance", "accounting", "operations"]
      }
    ]
  }'
```

## Example 2: Document Access Based on Classification

Create a permission for accessing documents based on classification level:

```bash
curl -X POST http://localhost:8030/v1/permissions \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "document:read",
    "display_name": "Read Documents",
    "description": "Allows reading documents based on classification and user clearance",
    "conditions": [
      {
        "attribute": "resource.classification",
        "operator": "IN",
        "value": ["public", "internal", "confidential"]
      },
      {
        "attribute": "user.clearance_level",
        "operator": "GREATER_THAN_OR_EQUAL",
        "value": "resource.required_clearance"
      }
    ]
  }'
```

## Example 3: Time-Based Access Control

Create a permission that only works during business hours:

```bash
curl -X POST http://localhost:8030/v1/permissions \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "system:admin_access",
    "display_name": "Admin Access",
    "description": "Administrative access restricted to business hours",
    "conditions": [
      {
        "attribute": "environment.hour",
        "operator": "GREATER_THAN_OR_EQUAL",
        "value": 9
      },
      {
        "attribute": "environment.hour",
        "operator": "LESS_THAN",
        "value": 18
      },
      {
        "attribute": "environment.day_of_week",
        "operator": "NOT_IN",
        "value": ["saturday", "sunday"]
      }
    ]
  }'
```

## Example 4: Department-Based Budget Approval

Create a permission for department heads to approve budgets within their department:

```bash
curl -X POST http://localhost:8030/v1/permissions \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "budget:approve",
    "display_name": "Approve Department Budget",
    "description": "Allows department heads to approve budgets for their own department",
    "conditions": [
      {
        "attribute": "user.department",
        "operator": "EQUALS",
        "value": "resource.department"
      },
      {
        "attribute": "user.role",
        "operator": "IN",
        "value": ["department_head", "director", "vp"]
      },
      {
        "attribute": "resource.amount",
        "operator": "LESS_THAN_OR_EQUAL",
        "value": 100000
      }
    ]
  }'
```

## Checking Permissions with Context

Once you've created conditional permissions, check them by providing resource attributes:

```bash
curl -X POST http://localhost:8030/v1/permissions/check \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "permission": "invoice:approve",
    "entity_id": "507f1f77bcf86cd799439011",
    "resource_attributes": {
      "value": 25000,
      "status": "pending_approval",
      "department": "finance",
      "invoice_id": "INV-2024-001"
    }
  }'
```

### Response Example:

```json
{
  "allowed": true,
  "reason": "All conditions passed",
  "details": {
    "rbac_check": true,
    "rbac_source": "role",
    "evaluations": [
      {
        "attribute": "resource.value",
        "operator": "LESS_THAN_OR_EQUAL",
        "expected": 50000,
        "actual": 25000,
        "passed": true,
        "reason": "Condition evaluation successful"
      },
      {
        "attribute": "resource.status",
        "operator": "EQUALS",
        "expected": "pending_approval",
        "actual": "pending_approval",
        "passed": true,
        "reason": "Condition evaluation successful"
      },
      {
        "attribute": "resource.department",
        "operator": "IN",
        "expected": ["finance", "accounting", "operations"],
        "actual": "finance",
        "passed": true,
        "reason": "Condition evaluation successful"
      }
    ]
  }
}
```

## Available Operators

- **EQUALS**: Exact match (case-insensitive for strings)
- **NOT_EQUALS**: Not equal to
- **LESS_THAN**: Numeric less than
- **LESS_THAN_OR_EQUAL**: Numeric less than or equal
- **GREATER_THAN**: Numeric greater than
- **GREATER_THAN_OR_EQUAL**: Numeric greater than or equal
- **IN**: Value is in a list
- **NOT_IN**: Value is not in a list
- **CONTAINS**: String/array contains value
- **NOT_CONTAINS**: String/array does not contain value
- **STARTS_WITH**: String starts with value
- **ENDS_WITH**: String ends with value
- **REGEX_MATCH**: String matches regex pattern
- **EXISTS**: Attribute exists
- **NOT_EXISTS**: Attribute does not exist

## Available Attribute Namespaces

- **user.*** - User attributes (email, department, team, location, etc.)
- **resource.*** - Resource being accessed (any custom attributes)
- **entity.*** - Entity context (name, type, settings, etc.)
- **environment.*** - Environment context (time, day_of_week, hour, etc.)

## Best Practices

1. **Start Simple**: Begin with basic conditions and add complexity as needed
2. **Test Thoroughly**: Use the /v1/permissions/check endpoint to test your conditions
3. **Document Conditions**: Use clear descriptions explaining what the permission allows
4. **Use Appropriate Operators**: Choose the right operator for your use case
5. **Consider Performance**: Complex conditions with many attributes may impact performance
6. **Plan for Edge Cases**: Consider what happens when attributes are missing

## Integration Example

Here's how to integrate conditional permission checking in your application:

```python
# Python example
async def approve_invoice(invoice_id: str, user_token: str):
    # Get invoice details
    invoice = await get_invoice(invoice_id)
    
    # Check permission with resource context
    response = await auth_client.post(
        "/v1/permissions/check",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "permission": "invoice:approve",
            "entity_id": invoice.entity_id,
            "resource_attributes": {
                "value": invoice.amount,
                "status": invoice.status,
                "department": invoice.department,
                "created_by": invoice.created_by
            }
        }
    )
    
    result = response.json()
    
    if not result["allowed"]:
        raise PermissionDenied(result["reason"])
    
    # Proceed with approval
    await process_invoice_approval(invoice)
```