# Hybrid Authorization Guide (RBAC + ReBAC + ABAC)

## Overview

outlabsAuth now implements a powerful hybrid authorization model that combines:

- **RBAC (Role-Based Access Control)**: The "What" - Roles define base permissions
- **ReBAC (Relationship-Based Access Control)**: The "Where" - Entity relationships provide context
- **ABAC (Attribute-Based Access Control)**: The "When" and "How" - Conditions provide granular control

This evolution addresses the limitations of static permissions by enabling context-aware, attribute-based authorization while maintaining backward compatibility.

## Key Concepts

### 1. Conditional Permissions

Permissions can now include conditions that must be met for the permission to be granted:

```json
{
  "name": "invoice:approve",
  "display_name": "Approve Invoices",
  "conditions": [
    {
      "attribute": "resource.value",
      "operator": "LESS_THAN_OR_EQUAL",
      "value": 50000
    }
  ]
}
```

### 2. Policy Evaluation Flow

When checking permissions, the system now:

1. **RBAC Check**: Does the user have a role granting the permission?
2. **ReBAC Check**: Is the user's entity relationship valid?
3. **ABAC Check**: Do the conditions evaluate to true?

All three checks must pass for access to be granted.

### 3. Attribute Sources

Attributes can come from multiple sources:

- **User Attributes**: `user.department`, `user.level`, `user.custom_attributes.*`
- **Resource Attributes**: `resource.value`, `resource.status`, `resource.owner`
- **Environment Attributes**: `environment.time`, `environment.ip_address`
- **Entity Attributes**: `entity.type`, `entity.location`, `entity.metadata.*`

## Creating Conditional Permissions

### API Example

```bash
POST /v1/permissions/
{
  "name": "purchase_order:approve",
  "display_name": "Approve Purchase Orders",
  "description": "Approve POs with spending limits",
  "conditions": [
    {
      "attribute": "resource.amount",
      "operator": "LESS_THAN",
      "value": 10000
    },
    {
      "attribute": "user.department",
      "operator": "EQUALS",
      "value": "finance"
    }
  ]
}
```

### Supported Operators

- `EQUALS`: Exact match
- `NOT_EQUALS`: Not equal
- `LESS_THAN`: Numeric less than
- `LESS_THAN_OR_EQUAL`: Numeric less than or equal
- `GREATER_THAN`: Numeric greater than
- `GREATER_THAN_OR_EQUAL`: Numeric greater than or equal
- `IN`: Value in list
- `NOT_IN`: Value not in list
- `CONTAINS`: String/array contains
- `STARTS_WITH`: String starts with
- `ENDS_WITH`: String ends with
- `REGEX_MATCH`: Regular expression match

## Checking Permissions with Context

### Basic Check (Backward Compatible)

```python
# Traditional check - works with non-conditional permissions
result = await check_permission(
    user_id="user_123",
    permission="lead:read",
    entity_id="ent_miami"
)
```

### Contextual Check with Resource Attributes

```python
# New contextual check with resource attributes
result = await check_permission(
    user_id="user_123",
    permission="invoice:approve",
    entity_id="ent_miami",
    resource_attributes={
        "type": "invoice",
        "value": 4999,
        "currency": "USD",
        "department": "sales"
    }
)
```

### API Endpoint

```bash
POST /v1/permissions/check
{
  "permission": "purchase_order:approve",
  "context": {
    "entity_id": "ent_miami_office"
  },
  "resource_attributes": {
    "type": "purchase_order",
    "amount": 5000,
    "vendor": "ABC Corp",
    "category": "office_supplies"
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
        "condition": "resource.amount < 10000",
        "result": "passed"
      },
      {
        "condition": "user.department == finance",
        "result": "passed"
      }
    ]
  }
}
```

## Real-World Examples

### 1. Spending Limits by Role

```json
{
  "name": "expense:approve",
  "conditions": [
    {
      "attribute": "resource.amount",
      "operator": "LESS_THAN_OR_EQUAL",
      "value": {
        "ref": "user.spending_limit"
      }
    }
  ]
}
```

### 2. Time-Based Access

```json
{
  "name": "report:export",
  "conditions": [
    {
      "attribute": "environment.time.hour",
      "operator": "GREATER_THAN_OR_EQUAL",
      "value": 9
    },
    {
      "attribute": "environment.time.hour",
      "operator": "LESS_THAN",
      "value": 17
    }
  ]
}
```

### 3. Geographic Restrictions

```json
{
  "name": "customer:view_pii",
  "conditions": [
    {
      "attribute": "user.location.country",
      "operator": "IN",
      "value": ["US", "CA"]
    },
    {
      "attribute": "resource.data_classification",
      "operator": "NOT_EQUALS",
      "value": "restricted"
    }
  ]
}
```

### 4. Multi-Level Approval

```json
{
  "name": "contract:sign",
  "conditions": [
    {
      "attribute": "resource.value",
      "operator": "LESS_THAN",
      "value": 100000
    },
    {
      "attribute": "resource.approval_count",
      "operator": "GREATER_THAN_OR_EQUAL",
      "value": 2
    }
  ]
}
```

## Complex Condition Logic

### AND Logic (Default)

All conditions in the array must pass:

```json
{
  "conditions": [
    { "attribute": "resource.status", "operator": "EQUALS", "value": "pending" },
    { "attribute": "user.department", "operator": "EQUALS", "value": "finance" }
  ]
}
```

### OR Logic (Using Groups)

Future enhancement for OR logic:

```json
{
  "condition_groups": [
    {
      "logic": "OR",
      "conditions": [
        { "attribute": "user.role", "operator": "EQUALS", "value": "admin" },
        { "attribute": "resource.owner", "operator": "EQUALS", "value": { "ref": "user.id" } }
      ]
    }
  ]
}
```

## Migration Strategy

### Phase 1: Backward Compatibility

- Existing permissions without conditions work exactly as before
- New permissions can optionally include conditions
- No changes required for existing integrations

### Phase 2: Gradual Adoption

1. **Identify Role Explosion**: Find roles that exist only for limit variations
2. **Consolidate with Conditions**: Replace multiple roles with one conditional permission
3. **Test Thoroughly**: Use the evaluation details to verify logic

### Phase 3: Advanced Usage

- Implement dynamic attributes from external systems
- Create reusable condition templates
- Build approval workflows with conditions

## Best Practices

### 1. Start Simple

Begin with basic numeric comparisons:

```json
{
  "attribute": "resource.value",
  "operator": "LESS_THAN",
  "value": 1000
}
```

### 2. Use Meaningful Attributes

Choose attribute names that are self-documenting:
- ✅ `resource.purchase_amount`
- ❌ `resource.val`

### 3. Consider Performance

- Conditions are evaluated on every check
- Cache results for expensive evaluations
- Minimize external attribute lookups

### 4. Audit and Monitoring

- Log condition evaluations for audit trails
- Monitor which conditions frequently fail
- Track performance of complex conditions

### 5. Security Considerations

- Validate all attribute paths to prevent injection
- Sanitize attribute values
- Limit condition complexity to prevent DoS

## Troubleshooting

### Permission Denied Despite Role

Check the evaluation details:

```json
{
  "allowed": false,
  "evaluation_details": {
    "rbac_check": "passed",
    "rebac_check": "passed",
    "conditions_evaluated": [
      {
        "condition": "resource.value < 5000",
        "result": "failed",
        "actual_value": 6000
      }
    ]
  }
}
```

### Debugging Conditions

Enable detailed logging:

```python
# In your platform
result = await check_permission(
    user_id="user_123",
    permission="invoice:approve",
    resource_attributes={"value": 10000},
    debug=True  # Returns detailed evaluation trace
)
```

### Common Issues

1. **Missing Attributes**: Ensure all required attributes are provided
2. **Type Mismatches**: Numbers vs strings in comparisons
3. **Null Values**: Handle missing attributes gracefully
4. **Case Sensitivity**: String comparisons are case-sensitive by default

## Future Enhancements

### 1. Condition Templates

Pre-defined conditions that can be reused:

```json
{
  "name": "invoice:approve",
  "condition_template": "spending_limit_check"
}
```

### 2. Dynamic Value References

Reference other attributes dynamically:

```json
{
  "attribute": "resource.amount",
  "operator": "LESS_THAN",
  "value": { "ref": "user.monthly_limit" }
}
```

### 3. External Attribute Providers

Fetch attributes from external systems:

```json
{
  "attribute": "external.risk_score",
  "operator": "LESS_THAN",
  "value": 70,
  "provider": "risk_assessment_api"
}
```

### 4. Time-Window Conditions

Conditions that consider historical data:

```json
{
  "attribute": "user.monthly_spend",
  "operator": "LESS_THAN",
  "value": 10000,
  "window": "current_month"
}
```

## Conclusion

The hybrid authorization model provides the flexibility needed for complex, real-world authorization scenarios while maintaining the simplicity of role-based access control. By combining RBAC, ReBAC, and ABAC, outlabsAuth can handle everything from simple "can read" checks to complex, context-aware business rules.