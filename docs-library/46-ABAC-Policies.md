# 46. ABAC Policies (Attribute-Based Access Control)

> **Quick Reference**: Implement fine-grained access control with conditional policies based on user attributes, resource attributes, and environmental context.

## Overview

**ABAC (Attribute-Based Access Control)** extends traditional RBAC with dynamic, context-aware access control based on attributes and conditions.

**Simple RBAC**:
```
User has "editor" role → Can edit posts
```

**ABAC**:
```
User has "editor" role
  AND user.department == resource.department
  AND time.is_business_hours == True
  → Can edit posts
```

**ABAC is an optional feature** in EnterpriseRBAC (opt-in via `enable_abac=True`).

---

## Why ABAC?

### Limitations of Pure RBAC

**RBAC Problem**:
```python
# Can't express:
# - "Users can only edit their own posts"
# - "Managers can approve budgets under $100,000"
# - "Users can only access data from their department"
# - "Admins can only perform actions during business hours"

# RBAC solution: Create many roles
roles = [
    "editor_own_posts",      # Can edit own posts
    "editor_all_posts",      # Can edit all posts
    "budget_approver_small", # < $100k
    "budget_approver_large", # Any amount
    "department_a_viewer",
    "department_b_viewer",
    ...
]
# 🚨 Role explosion!
```

### ABAC Solution

```python
# One role with dynamic conditions
editor_role = RoleModel(
    name="editor",
    permissions=["post:edit"],
    conditions=[
        Condition(
            attribute="resource.author_id",
            operator="equals",
            value="user.id"
        )
    ]
)
# ✅ Users can only edit their own posts
```

---

## When to Use ABAC

**✅ Use ABAC when**:
- Need attribute-based access control (department, region, budget level)
- Need time-based access control (business hours, weekdays)
- Need relationship-based access (own resources, same department)
- Need dynamic policies (runtime evaluation)
- Complex authorization rules that vary by context

**❌ Don't use when**:
- Simple static role-based permissions suffice
- Performance is critical (ABAC adds ~50-100ms overhead)
- Using SimpleRBAC (ABAC only works with EnterpriseRBAC)

---

## Setup

### Enable ABAC

```python
from outlabs_auth import EnterpriseRBAC

auth = EnterpriseRBAC(
    database=mongo_client,
    enable_abac=True  # 🔑 Opt-in feature
)
```

**Requirements**:
- ✅ Must use **EnterpriseRBAC** (not SimpleRBAC)
- ✅ Entity hierarchy must be enabled (automatic in EnterpriseRBAC)

---

## Condition Model

### Basic Condition

```python
from outlabs_auth.models.condition import Condition, ConditionOperator

condition = Condition(
    attribute="resource.department",  # What to check
    operator=ConditionOperator.EQUALS,  # How to compare
    value="engineering",  # Expected value
    description="User can only access engineering resources"  # Optional
)
```

**Condition Structure**:
```
attribute: "context.field"  # Dot-notation path
operator: Comparison operator
value: Expected value
description: Human-readable explanation (optional)
```

### Context Types

Conditions check attributes from 4 contexts:

| Context | Description | Example Attributes |
|---------|-------------|-------------------|
| **user** | User attributes | `user.id`, `user.department`, `user.role`, `user.clearance_level` |
| **resource** | Resource attributes | `resource.id`, `resource.department`, `resource.owner_id`, `resource.budget` |
| **env** | Environment attributes | `env.ip`, `env.location`, `env.user_agent` |
| **time** | Time-based attributes | `time.hour`, `time.day_of_week`, `time.is_business_hours` |

---

## Operators

### Equality Operators

```python
from outlabs_auth.models.condition import ConditionOperator

# Equals
Condition(attribute="user.department", operator=ConditionOperator.EQUALS, value="sales")

# Not Equals
Condition(attribute="user.status", operator=ConditionOperator.NOT_EQUALS, value="suspended")
```

### Comparison Operators (Numeric)

```python
# Less Than
Condition(attribute="resource.budget", operator=ConditionOperator.LESS_THAN, value=100000)

# Less Than or Equal
Condition(attribute="resource.budget", operator=ConditionOperator.LESS_THAN_OR_EQUAL, value=50000)

# Greater Than
Condition(attribute="user.clearance_level", operator=ConditionOperator.GREATER_THAN, value=5)

# Greater Than or Equal
Condition(attribute="user.age", operator=ConditionOperator.GREATER_THAN_OR_EQUAL, value=18)
```

### Collection Operators

```python
# IN - attribute value is in list
Condition(
    attribute="user.role",
    operator=ConditionOperator.IN,
    value=["admin", "superuser", "owner"]
)

# NOT_IN - attribute value is not in list
Condition(
    attribute="user.status",
    operator=ConditionOperator.NOT_IN,
    value=["banned", "suspended", "deleted"]
)

# CONTAINS - list attribute contains value
Condition(
    attribute="user.permissions",  # user.permissions is a list
    operator=ConditionOperator.CONTAINS,
    value="admin"
)

# NOT_CONTAINS - list attribute does not contain value
Condition(
    attribute="resource.tags",
    operator=ConditionOperator.NOT_CONTAINS,
    value="confidential"
)
```

### String Operators

```python
# Starts With
Condition(
    attribute="resource.filename",
    operator=ConditionOperator.STARTS_WITH,
    value="report_"
)

# Ends With
Condition(
    attribute="resource.filename",
    operator=ConditionOperator.ENDS_WITH,
    value=".pdf"
)

# Matches (Regex)
Condition(
    attribute="user.email",
    operator=ConditionOperator.MATCHES,
    value=r"^[a-z]+@company\.com$"
)
```

### Existence Operators

```python
# Exists (attribute is not None)
Condition(
    attribute="resource.approved_by",
    operator=ConditionOperator.EXISTS
    # No value needed
)

# Not Exists (attribute is None)
Condition(
    attribute="resource.deleted_at",
    operator=ConditionOperator.NOT_EXISTS
    # No value needed
)
```

### Boolean Operators

```python
# Is True
Condition(
    attribute="user.is_verified",
    operator=ConditionOperator.IS_TRUE
    # No value needed
)

# Is False
Condition(
    attribute="resource.is_archived",
    operator=ConditionOperator.IS_FALSE
    # No value needed
)
```

### Time-Based Operators

```python
# Before (datetime comparison)
Condition(
    attribute="resource.created_at",
    operator=ConditionOperator.BEFORE,
    value="2025-12-31T23:59:59Z"
)

# After (datetime comparison)
Condition(
    attribute="user.last_login",
    operator=ConditionOperator.AFTER,
    value="2025-01-01T00:00:00Z"
)
```

---

## Condition Groups

### AND Logic

```python
from outlabs_auth.models.condition import ConditionGroup

# All conditions must be true
group = ConditionGroup(
    conditions=[
        Condition(attribute="user.department", operator="equals", value="sales"),
        Condition(attribute="user.role", operator="equals", value="manager"),
        Condition(attribute="user.clearance_level", operator="greater_than", value=3)
    ],
    operator="AND",
    description="Sales managers with high clearance"
)

# Result: True only if ALL conditions pass
```

### OR Logic

```python
# Any condition can be true
group = ConditionGroup(
    conditions=[
        Condition(attribute="user.role", operator="equals", value="admin"),
        Condition(attribute="user.role", operator="equals", value="owner"),
        Condition(attribute="user.is_superuser", operator="is_true")
    ],
    operator="OR",
    description="Admins, owners, or superusers"
)

# Result: True if ANY condition passes
```

### Nested Groups (Complex Logic)

```python
# (user is admin OR owner) AND (resource budget < 100k OR user clearance > 5)

role = RoleModel(
    name="approver",
    permissions=["budget:approve"],
    condition_groups=[
        ConditionGroup(
            conditions=[
                Condition(attribute="user.role", operator="in", value=["admin", "owner"]),
            ],
            operator="AND"
        ),
        ConditionGroup(
            conditions=[
                Condition(attribute="resource.budget", operator="less_than", value=100000),
                Condition(attribute="user.clearance_level", operator="greater_than", value=5)
            ],
            operator="OR"
        )
    ]
)
```

---

## Creating Roles with ABAC

### Example 1: Department-Based Access

```python
# Users can only access resources from their own department
department_role = RoleModel(
    name="department_viewer",
    permissions=["resource:read"],
    conditions=[
        Condition(
            attribute="resource.department",
            operator="equals",
            value="user.department"  # 🔑 Compares user.department to resource.department
        )
    ]
)
await department_role.insert()
```

**Note**: OutlabsAuth resolves `"user.department"` dynamically during evaluation!

### Example 2: Own Resources Only

```python
# Users can only edit their own posts
own_resource_role = RoleModel(
    name="editor_own",
    permissions=["post:edit", "post:delete"],
    conditions=[
        Condition(
            attribute="resource.author_id",
            operator="equals",
            value="user.id"  # 🔑 Compares resource.author_id to current user.id
        )
    ]
)
await own_resource_role.insert()
```

### Example 3: Budget Approval with Limits

```python
# Managers can approve budgets under $100,000
budget_approver_role = RoleModel(
    name="budget_approver_small",
    permissions=["budget:approve"],
    conditions=[
        Condition(
            attribute="user.role",
            operator="equals",
            value="manager"
        ),
        Condition(
            attribute="resource.amount",
            operator="less_than",
            value=100000
        )
    ]
)
await budget_approver_role.insert()
```

### Example 4: Time-Restricted Access

```python
# Admins can only perform sensitive operations during business hours
business_hours_admin = RoleModel(
    name="business_hours_admin",
    permissions=["user:delete", "data:export", "system:configure"],
    conditions=[
        Condition(
            attribute="time.hour",
            operator="greater_than_or_equal",
            value=9
        ),
        Condition(
            attribute="time.hour",
            operator="less_than",
            value=17
        ),
        Condition(
            attribute="time.day_of_week",
            operator="not_in",
            value=["saturday", "sunday"]
        )
    ]
)
await business_hours_admin.insert()
```

### Example 5: Regional Access

```python
# Regional managers can only access data from their region
regional_manager = RoleModel(
    name="regional_manager",
    permissions=["sales:read_tree", "report:generate"],
    condition_groups=[
        ConditionGroup(
            conditions=[
                Condition(attribute="user.role", operator="equals", value="manager"),
                Condition(attribute="user.region", operator="equals", value="resource.region")
            ],
            operator="AND"
        )
    ]
)
await regional_manager.insert()
```

---

## Permission Checking with ABAC

### How ABAC Evaluation Works

```
1. User makes request
   ↓
2. Get user's roles
   ↓
3. Get permissions from roles
   ↓
4. For each permission:
   a. Check if user has the permission
   b. Evaluate ABAC conditions
   c. All conditions must pass
   ↓
5. Allow or Deny
```

### Permission Check Flow

```python
# User: john@acme.com
# Role: department_viewer
# Permission: resource:read
# Condition: resource.department == user.department

Context:
  user = {"id": "123", "department": "engineering"}
  resource = {"id": "456", "department": "engineering"}

Evaluation:
  1. User has permission "resource:read"? ✅ Yes
  2. Evaluate condition: resource.department == user.department
     → "engineering" == "engineering" ✅ True
  3. All conditions pass? ✅ Yes
  4. ALLOW access

---

Context:
  user = {"id": "123", "department": "engineering"}
  resource = {"id": "789", "department": "sales"}

Evaluation:
  1. User has permission "resource:read"? ✅ Yes
  2. Evaluate condition: resource.department == user.department
     → "sales" == "engineering" ❌ False
  3. All conditions pass? ❌ No
  4. DENY access
```

### FastAPI Integration

```python
from fastapi import Depends, HTTPException
from outlabs_auth.dependencies import AuthDeps

deps = AuthDeps(auth)

@app.get("/resources/{resource_id}")
async def get_resource(
    resource_id: str,
    auth_result = Depends(deps.require_permission("resource:read"))
):
    """
    Permission check with ABAC evaluation.

    ABAC automatically evaluates conditions when checking permission!
    """
    # Get resource
    resource = await get_resource_from_db(resource_id)

    # Build ABAC context
    user = auth_result["metadata"]["user"]
    context = {
        "user": {
            "id": user["id"],
            "department": user.get("department"),
            "role": user.get("role")
        },
        "resource": {
            "id": resource.id,
            "department": resource.department,
            "owner_id": resource.owner_id
        }
    }

    # Check permission with ABAC context
    has_permission = await auth.permission_service.check_permission(
        user_id=user["id"],
        permission="resource:read",
        context=context  # 🔑 ABAC context
    )

    if not has_permission:
        raise HTTPException(403, "Access denied by ABAC policy")

    return resource
```

---

## Complete Use Cases

### Use Case 1: Department-Based Document Access

```python
# Create role with department restriction
document_viewer = RoleModel(
    name="document_viewer",
    permissions=["document:read", "document:download"],
    conditions=[
        Condition(
            attribute="resource.department",
            operator="equals",
            value="user.department"
        )
    ]
)
await document_viewer.insert()

# Assign role to user
await auth.membership_service.create_membership(
    user_id=user_id,
    entity_id=entity_id,
    role_ids=[document_viewer.id]
)

# Check permission
user = await UserModel.get(user_id)
document = await Document.get(document_id)

context = {
    "user": {"id": str(user.id), "department": user.department},
    "resource": {"id": str(document.id), "department": document.department}
}

can_access = await auth.permission_service.check_permission(
    user_id=str(user.id),
    permission="document:read",
    context=context
)

# Result:
# ✅ True if user.department == document.department
# ❌ False otherwise
```

### Use Case 2: Budget Approval with Tiered Limits

```python
# Small budget approver (< $50k)
small_approver = RoleModel(
    name="approver_small",
    permissions=["budget:approve"],
    conditions=[
        Condition(attribute="resource.amount", operator="less_than", value=50000)
    ]
)

# Medium budget approver (< $500k)
medium_approver = RoleModel(
    name="approver_medium",
    permissions=["budget:approve"],
    conditions=[
        Condition(attribute="resource.amount", operator="less_than", value=500000)
    ]
)

# Large budget approver (any amount)
large_approver = RoleModel(
    name="approver_large",
    permissions=["budget:approve"]
    # No conditions - can approve any amount
)

# Assign roles based on user level
junior_manager_roles = [small_approver.id]
senior_manager_roles = [small_approver.id, medium_approver.id]
executive_roles = [small_approver.id, medium_approver.id, large_approver.id]
```

### Use Case 3: Time-Restricted Admin Access

```python
# Admin role with business hours restriction
business_hours_admin = RoleModel(
    name="admin_business_hours",
    permissions=["user:*", "data:*", "system:*"],
    condition_groups=[
        ConditionGroup(
            conditions=[
                # Business hours: 9 AM - 5 PM, Monday-Friday
                Condition(attribute="time.hour", operator="greater_than_or_equal", value=9),
                Condition(attribute="time.hour", operator="less_than", value=17),
                Condition(attribute="time.is_weekend", operator="is_false")
            ],
            operator="AND",
            description="Business hours only (9 AM - 5 PM, Mon-Fri)"
        )
    ]
)

# Permission check automatically includes time context
context = auth.policy_engine.create_context(
    user={"id": user_id, "role": "admin"},
    resource={"id": resource_id}
    # time context auto-generated!
)

can_perform = await auth.permission_service.check_permission(
    user_id=user_id,
    permission="data:export",
    context=context
)

# Result:
# ✅ True if current time is 9 AM - 5 PM, Monday-Friday
# ❌ False if outside business hours or weekend
```

### Use Case 4: Own Resources Plus Manager Override

```python
# Users can edit own posts OR if they're a manager
editor_role = RoleModel(
    name="editor",
    permissions=["post:edit"],
    condition_groups=[
        ConditionGroup(
            conditions=[
                # Condition 1: Own post
                Condition(attribute="resource.author_id", operator="equals", value="user.id"),
            ],
            operator="OR"
        ),
        ConditionGroup(
            conditions=[
                # Condition 2: Manager role
                Condition(attribute="user.role", operator="equals", value="manager")
            ],
            operator="OR"
        )
    ]
)

# Result:
# ✅ True if resource.author_id == user.id (own post)
# ✅ True if user.role == "manager" (manager override)
# ❌ False otherwise
```

---

## Policy Evaluation Engine

### Manual Evaluation

```python
from outlabs_auth.services.policy_engine import PolicyEvaluationEngine

engine = PolicyEvaluationEngine()

# Create context
context = {
    "user": {
        "id": "123",
        "department": "engineering",
        "role": "developer"
    },
    "resource": {
        "id": "456",
        "department": "engineering",
        "budget": 75000
    },
    "time": {
        "hour": 14,
        "day_of_week": "tuesday",
        "is_business_hours": True
    }
}

# Evaluate single condition
condition = Condition(
    attribute="resource.department",
    operator="equals",
    value="engineering"
)

result = engine.evaluate_condition(condition, context)
# result = True

# Evaluate condition group
group = ConditionGroup(
    conditions=[
        Condition(attribute="user.department", operator="equals", value="engineering"),
        Condition(attribute="resource.budget", operator="less_than", value=100000)
    ],
    operator="AND"
)

result = engine.evaluate_condition_group(group, context)
# result = True (both conditions pass)
```

### Auto-Generated Time Context

```python
# Time context is auto-generated
context = engine.create_context(
    user={"id": "123", "department": "sales"},
    resource={"id": "456", "amount": 50000}
)

print(context["time"])
# Output:
# {
#     "hour": 14,
#     "minute": 30,
#     "day_of_week": "tuesday",
#     "day_of_month": 23,
#     "month": 1,
#     "year": 2025,
#     "is_business_hours": True,
#     "is_weekend": False,
#     "timestamp": "2025-01-23T14:30:00"
# }
```

---

## Performance Considerations

### ABAC Overhead

| Operation | No ABAC | With ABAC | Overhead |
|-----------|---------|-----------|----------|
| **Simple permission** | ~10ms | ~60ms | +50ms |
| **Multiple conditions** | ~10ms | ~100ms | +90ms |
| **With caching** | ~10ms | ~15ms | +5ms |

### Optimization Strategies

#### 1. Cache ABAC Results

```python
auth = EnterpriseRBAC(
    database=db,
    enable_abac=True,
    enable_caching=True,  # Cache ABAC evaluation results
    redis_url="redis://localhost:6379"
)
```

#### 2. Minimize Conditions

```python
# ❌ Bad - too many conditions
role = RoleModel(
    permissions=["resource:read"],
    conditions=[
        Condition(...),  # 10+ conditions
        Condition(...),
        ...
    ]
)

# ✅ Good - fewer, more targeted conditions
role = RoleModel(
    permissions=["resource:read"],
    conditions=[
        Condition(attribute="resource.department", operator="equals", value="user.department")
    ]
)
```

#### 3. Use Condition Groups Wisely

```python
# ✅ Good - exit early with OR
group = ConditionGroup(
    conditions=[
        Condition(attribute="user.is_superuser", operator="is_true"),  # Check first
        Condition(attribute="resource.owner_id", operator="equals", value="user.id")
    ],
    operator="OR"  # Stops evaluating after first True
)

# ❌ Slower - AND requires all evaluations
group = ConditionGroup(
    conditions=[...many conditions...],
    operator="AND"  # Must evaluate all
)
```

---

## Testing ABAC Policies

### Test Condition Evaluation

```python
async def test_department_based_access():
    """Test department-based ABAC policy."""
    # Create role with condition
    role = RoleModel(
        name="department_viewer",
        permissions=["resource:read"],
        conditions=[
            Condition(
                attribute="resource.department",
                operator="equals",
                value="user.department"
            )
        ]
    )
    await role.insert()

    # Create user and resource
    user = await create_test_user(department="engineering")
    resource_same_dept = await create_test_resource(department="engineering")
    resource_other_dept = await create_test_resource(department="sales")

    # Test same department (should pass)
    context = {
        "user": {"id": str(user.id), "department": user.department},
        "resource": {"id": str(resource_same_dept.id), "department": resource_same_dept.department}
    }

    can_access = await auth.permission_service.check_permission(
        user_id=str(user.id),
        permission="resource:read",
        context=context
    )
    assert can_access is True

    # Test different department (should fail)
    context = {
        "user": {"id": str(user.id), "department": user.department},
        "resource": {"id": str(resource_other_dept.id), "department": resource_other_dept.department}
    }

    can_access = await auth.permission_service.check_permission(
        user_id=str(user.id),
        permission="resource:read",
        context=context
    )
    assert can_access is False
```

### Test Time-Based Policies

```python
async def test_business_hours_policy():
    """Test time-based ABAC policy."""
    # Create role with time restriction
    role = RoleModel(
        name="business_hours_admin",
        permissions=["data:export"],
        conditions=[
            Condition(attribute="time.is_business_hours", operator="is_true")
        ]
    )
    await role.insert()

    user = await create_test_user()

    # Test during business hours (should pass)
    context = {
        "user": {"id": str(user.id)},
        "time": {"hour": 14, "is_business_hours": True}
    }

    can_export = await auth.permission_service.check_permission(
        user_id=str(user.id),
        permission="data:export",
        context=context
    )
    assert can_export is True

    # Test outside business hours (should fail)
    context = {
        "user": {"id": str(user.id)},
        "time": {"hour": 22, "is_business_hours": False}
    }

    can_export = await auth.permission_service.check_permission(
        user_id=str(user.id),
        permission="data:export",
        context=context
    )
    assert can_export is False
```

---

## Best Practices

### 1. Start Simple

```python
# ✅ Good - start with simple conditions
Condition(attribute="resource.owner_id", operator="equals", value="user.id")

# ❌ Bad - overly complex from the start
ConditionGroup(
    conditions=[...10 nested conditions...],
    operator="AND"
)
```

### 2. Document Conditions

```python
# ✅ Good - clear description
Condition(
    attribute="resource.department",
    operator="equals",
    value="user.department",
    description="Users can only access resources from their own department"
)

# ❌ Bad - no description
Condition(
    attribute="resource.department",
    operator="equals",
    value="user.department"
)
```

### 3. Use Meaningful Attribute Names

```python
# ✅ Good - descriptive attributes
"user.department"
"resource.budget_amount"
"resource.approval_status"

# ❌ Bad - cryptic attributes
"user.dept"
"resource.amt"
"resource.status"
```

### 4. Validate Attribute Paths

```python
# ✅ Good - valid contexts
"user.department"    # ✅
"resource.budget"    # ✅
"time.hour"          # ✅
"env.ip"             # ✅

# ❌ Bad - invalid contexts
"department"         # ❌ Missing context
"user_department"    # ❌ Wrong format
"admin.role"         # ❌ Invalid context
```

### 5. Test All Scenarios

```python
# Test matrix for department-based access
test_cases = [
    {"user_dept": "eng", "resource_dept": "eng", "expected": True},
    {"user_dept": "eng", "resource_dept": "sales", "expected": False},
    {"user_dept": "sales", "resource_dept": "sales", "expected": True},
    {"user_dept": "sales", "resource_dept": "eng", "expected": False},
]

for case in test_cases:
    result = await test_access(case["user_dept"], case["resource_dept"])
    assert result == case["expected"]
```

---

## Common Patterns

### Pattern 1: Own Resource Access

```python
Condition(
    attribute="resource.owner_id",
    operator="equals",
    value="user.id"
)
```

### Pattern 2: Department-Based Access

```python
Condition(
    attribute="resource.department",
    operator="equals",
    value="user.department"
)
```

### Pattern 3: Budget Threshold

```python
Condition(
    attribute="resource.amount",
    operator="less_than",
    value=100000
)
```

### Pattern 4: Business Hours

```python
ConditionGroup(
    conditions=[
        Condition(attribute="time.hour", operator="greater_than_or_equal", value=9),
        Condition(attribute="time.hour", operator="less_than", value=17),
        Condition(attribute="time.is_weekend", operator="is_false")
    ],
    operator="AND"
)
```

### Pattern 5: Role + Attribute

```python
ConditionGroup(
    conditions=[
        Condition(attribute="user.role", operator="in", value=["manager", "admin"]),
        Condition(attribute="resource.status", operator="equals", value="pending")
    ],
    operator="AND"
)
```

---

## Summary

**ABAC in OutlabsAuth**:
- ✅ **Opt-in feature**: `enable_abac=True` in EnterpriseRBAC
- ✅ **Attribute-based**: User, resource, environment, time attributes
- ✅ **20+ operators**: Equality, comparison, collection, string, time, existence
- ✅ **Condition groups**: AND/OR logic with nested conditions
- ✅ **Policy engine**: Automatic evaluation with context
- ✅ **Performance**: ~50-100ms overhead, cacheable results
- ✅ **Testing**: Comprehensive test utilities

**When to Use**:
- Department/region-based access
- Own resource restrictions
- Budget approval limits
- Time-based access control
- Complex dynamic policies

---

## Next Steps

- **[40. Authorization Overview →](./40-Authorization-Overview.md)** - Authorization basics
- **[42. EnterpriseRBAC →](./42-EnterpriseRBAC.md)** - Hierarchical RBAC
- **[43. Permissions System →](./43-Permissions-System.md)** - Permission format
- **[45. Context-Aware Roles →](./45-Context-Aware-Roles.md)** - Role adaptation

---

## Further Reading

### ABAC Standards
- [NIST ABAC Guide](https://csrc.nist.gov/projects/attribute-based-access-control)
- [XACML (eXtensible Access Control Markup Language)](https://www.oasis-open.org/committees/xacml/)
- [ABAC vs RBAC Comparison](https://en.wikipedia.org/wiki/Attribute-based_access_control)

### Implementation Guides
- [Google Zanzibar (Relationship-Based AC)](https://research.google/pubs/pub48190/)
- [AWS IAM Policy Evaluation Logic](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic.html)
