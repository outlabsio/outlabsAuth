# Permission Builder UI/UX Guide

## Overview

The Permission Builder is a critical UI component that makes the complex ABAC (Attribute-Based Access Control) system accessible to administrators without requiring technical knowledge of policy languages or condition syntax.

## Design Principles

1. **Progressive Disclosure**: Start simple, reveal complexity as needed
2. **Visual Clarity**: Use icons and colors to indicate permission states
3. **Immediate Feedback**: Show real-time validation and examples
4. **Context-Aware Help**: Provide tooltips and examples relevant to the current input

## UI Components

### 1. Permission Builder Main View

```
┌─────────────────────────────────────────────────────────────┐
│ Create New Permission                                     [X] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Basic Information                                           │
│ ─────────────────                                          │
│                                                             │
│ Display Name: [Approve Invoices              ]             │
│ Description:  [Allows approving invoices for payment       ]│
│                                                             │
│ Permission Naming                                           │
│ ─────────────────                                          │
│                                                             │
│ Resource:     [▼ invoice     ] → Action: [▼ approve    ]   │
│                                                             │
│ Generated ID: invoice:approve ✓                             │
│                                                             │
│ ℹ️ The resource and action are automatically derived from   │
│    the generated ID. They cannot be edited separately.     │
│                                                             │
│ Access Conditions (Optional)                           [+]  │
│ ────────────────────────────                               │
│                                                             │
│ Tags & Categories                                           │
│ ─────────────────                                          │
│                                                             │
│ Tags: [finance] [accounting] [+]                           │
│                                                             │
│ [Cancel]                                    [Create]        │
└─────────────────────────────────────────────────────────────┘
```

### 2. Condition Builder (Expanded State)

When user clicks on "Access Conditions" or the [+] button:

```
┌─────────────────────────────────────────────────────────────┐
│ Access Conditions                                       [-] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ℹ️ Conditions allow you to set rules for when this          │
│    permission is granted. All conditions must be true.     │
│                                                             │
│ ┌─────────────────────────────────────────────────────┐   │
│ │ Condition 1                                      [✕] │   │
│ ├─────────────────────────────────────────────────────┤   │
│ │                                                       │   │
│ │ When [▼ Invoice Value    ] [▼ is less than ] [$50000]│   │
│ │      ↓                      ↓                   ↓     │   │
│ │   Attribute              Operator            Value    │   │
│ └─────────────────────────────────────────────────────┘   │
│                                                             │
│ ┌─────────────────────────────────────────────────────┐   │
│ │ Condition 2                                      [✕] │   │
│ ├─────────────────────────────────────────────────────┤   │
│ │                                                       │   │
│ │ When [▼ Invoice Status   ] [▼ equals       ] [▼pending_approval]│
│ │                                                       │   │
│ └─────────────────────────────────────────────────────┘   │
│                                                             │
│ [+ Add Condition]                                           │
│                                                             │
│ Preview: This permission will be granted when:             │
│ • Invoice value is less than $50,000                       │
│ • Invoice status equals "pending_approval"                 │
└─────────────────────────────────────────────────────────────┘
```

### 3. Attribute Selector Dropdown

```
┌─────────────────────────────────────────┐
│ Select Attribute                        │
├─────────────────────────────────────────┤
│ 🔍 Search attributes...                 │
├─────────────────────────────────────────┤
│ Resource Attributes                     │
│ ├─ 📄 Invoice Value (resource.value)    │
│ ├─ 📊 Invoice Status (resource.status)  │
│ ├─ 🏢 Department (resource.department)  │
│ └─ 👤 Owner (resource.owner)            │
│                                         │
│ User Attributes                         │
│ ├─ 🏢 Department (user.department)      │
│ ├─ 📊 Level (user.level)                │
│ └─ 💰 Spending Limit (user.spending_limit)│
│                                         │
│ Entity Attributes                       │
│ ├─ 🏢 Type (entity.type)                │
│ └─ 📍 Location (entity.location)        │
│                                         │
│ Environment                             │
│ ├─ 🕐 Current Time (environment.time)   │
│ └─ 🌐 IP Address (environment.ip)       │
│                                         │
│ [+ Custom Attribute...]                 │
└─────────────────────────────────────────┘
```

### 4. Operator Selection

The operator dropdown changes based on the attribute type:

#### For Numeric Attributes:
```
┌──────────────────────┐
│ equals               │  → EQUALS
│ does not equal       │  → NOT_EQUALS
│ is less than         │  → LESS_THAN
│ is less than or equal│  → LESS_THAN_OR_EQUAL
│ is greater than      │  → GREATER_THAN
│ is greater than or equal│ → GREATER_THAN_OR_EQUAL
└──────────────────────┘
```

#### For String Attributes:
```
┌──────────────────────┐
│ equals               │  → EQUALS
│ does not equal       │  → NOT_EQUALS
│ starts with          │  → STARTS_WITH
│ ends with            │  → ENDS_WITH
│ contains             │  → CONTAINS
│ matches pattern      │  → REGEX_MATCH
└──────────────────────┘
```

#### For List/Array Attributes:
```
┌──────────────────────┐
│ contains             │  → CONTAINS
│ does not contain     │  → NOT_CONTAINS
│ is in list           │  → IN
│ is not in list       │  → NOT_IN
└──────────────────────┘
```

#### For Existence Checks:
```
┌──────────────────────┐
│ exists               │  → EXISTS
│ does not exist       │  → NOT_EXISTS
└──────────────────────┘
```

### 5. Value Input

The value input adapts based on the attribute and operator:

#### Numeric Input:
```
[$_________] 
```

#### Dropdown (for known values):
```
[▼ Select Status        ]
├─ pending_approval
├─ approved
├─ rejected
└─ cancelled
```

#### Multi-select (for IN/NOT_IN operators):
```
┌─────────────────────────┐
│ ☑ USA                   │
│ ☑ Canada                │
│ ☐ Mexico                │
│ ☐ Brazil                │
└─────────────────────────┘
```

#### Dynamic Reference:
```
[◉ Static Value] [○ User Attribute]
[$50000        ]

OR

[○ Static Value] [◉ User Attribute]
[▼ user.spending_limit ]
```

## Interactive Features

### 1. Real-time Validation

As users build conditions, show immediate feedback:

```
✓ Valid condition
⚠️ Attribute may not exist for all resources
❌ Invalid operator for this attribute type
```

**Validation Messages from Model:**

For Permission Name:
- ❌ "Permission name must follow 'resource:action' format"
- ❌ "Permission name must have exactly one colon"
- ❌ "Both resource and action must be non-empty"
- ❌ "Resource must contain only letters, numbers, underscores, hyphens, or asterisk"

For Condition Attributes:
- ❌ "Attribute must start with one of: user., resource., entity., environment."
- ❌ "Invalid attribute path format"
- ✓ "Valid attribute path"

For Operators:
- ✓ Valid operators: EQUALS, NOT_EQUALS, LESS_THAN, LESS_THAN_OR_EQUAL, GREATER_THAN, GREATER_THAN_OR_EQUAL, IN, NOT_IN, CONTAINS, NOT_CONTAINS, STARTS_WITH, ENDS_WITH, REGEX_MATCH, EXISTS, NOT_EXISTS

### 2. Condition Preview

Show a human-readable preview of the permission logic:

```
┌─────────────────────────────────────────────────────────┐
│ 👁️ Permission Preview                                    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ "Approve Invoices" will be granted when:               │
│                                                         │
│ ✓ User has the "invoice:approve" permission through    │
│   their role                                            │
│   AND                                                   │
│ ✓ Invoice value is less than $50,000                   │
│   AND                                                   │
│ ✓ Invoice status equals "pending_approval"             │
│                                                         │
│ Example: Maria (Finance Manager) can approve invoice    │
│ #1234 ($45,000) because all conditions are met.        │
└─────────────────────────────────────────────────────────┘
```

### 3. Test Your Permission

Allow admins to test the permission with sample data:

```
┌─────────────────────────────────────────────────────────┐
│ Test This Permission                                    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ Select User: [▼ Maria Garcia - Finance Manager      ]  │
│                                                         │
│ Resource Values:                                        │
│ • Invoice Value: [$_45000_]                            │
│ • Invoice Status: [▼ pending_approval ]                │
│                                                         │
│ [Test Permission]                                       │
│                                                         │
│ Result: ✅ Permission Granted                           │
│ • RBAC Check: ✓ User has invoice:approve role         │
│ • Condition 1: ✓ $45,000 < $50,000                    │
│ • Condition 2: ✓ pending_approval = pending_approval  │
└─────────────────────────────────────────────────────────┘
```

## Role Assignment UI Enhancement

When assigning permissions to roles, show visual indicators:

```
┌─────────────────────────────────────────────────────────┐
│ Assign Permissions to Role: Finance Manager             │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ Available Permissions:                                  │
│                                                         │
│ Finance & Accounting                                    │
│ ├─ ☐ invoice:create - Create Invoices                  │
│ ├─ ☑ invoice:read - View Invoices                      │
│ ├─ ☑ invoice:approve - Approve Invoices ⚡            │
│ │   └─ Has 2 conditions (hover for details)            │
│ └─ ☐ invoice:delete - Delete Invoices                  │
│                                                         │
│ Legend: ⚡ = Has conditions                             │
└─────────────────────────────────────────────────────────┘
```

## Tooltips and Help

### Contextual Help Examples:

**For Attribute Selection:**
```
┌─────────────────────────────────────┐
│ 💡 Invoice Value                    │
│                                     │
│ The total amount of the invoice in  │
│ the system's default currency.      │
│                                     │
│ Type: Number                        │
│ Example: 5000                       │
│ Path: resource.value                │
└─────────────────────────────────────┘
```

**For Operators:**
```
┌─────────────────────────────────────┐
│ 💡 Is Less Than                     │
│                                     │
│ Checks if the attribute value is    │
│ numerically less than the specified │
│ value.                              │
│                                     │
│ Example: 100 < 200 ✓                │
│         200 < 100 ✗                 │
└─────────────────────────────────────┘
```

## Best Practices for UI Implementation

### 1. Progressive Enhancement
- Start with simple permissions (no conditions)
- Show "Add Conditions" as an optional advanced feature
- Use accordions to hide/show complexity

### 2. Visual Hierarchy
- Use consistent icons for attribute types
- Color-code different condition states (valid, invalid, warning)
- Group related attributes together

### 3. Error Prevention
- Validate inputs in real-time
- Disable invalid operator/value combinations
- Show warnings for potentially problematic conditions

### 4. Performance Considerations
- Lazy-load attribute lists
- Cache common attribute/operator combinations
- Debounce validation checks

### 5. Accessibility
- Full keyboard navigation support
- ARIA labels for all interactive elements
- High contrast mode support
- Screen reader friendly condition descriptions

## Mobile Considerations

For mobile admin interfaces:

1. **Vertical Layout**: Stack condition components vertically
2. **Touch Targets**: Ensure 44px minimum touch targets
3. **Simplified Dropdowns**: Use native select elements
4. **Step-by-Step**: Break condition building into steps/screens

## Implementation Technologies

### Recommended Frontend Stack:
- **React/Vue/Angular**: For component architecture
- **Headless UI**: For accessible dropdown components
- **React Hook Form**: For form validation
- **Zod**: For schema validation
- **TailwindCSS**: For responsive styling

### State Management:
```typescript
// Matches the Python model structure
interface PermissionBuilderState {
  name: string;  // Auto-generated from resource:action
  displayName: string;
  description: string;
  resource: string;  // Auto-derived from name
  action: string;    // Auto-derived from name
  conditions: Condition[];
  tags: string[];
  isSystem: boolean;
  isActive: boolean;
  entityId?: string;
  isValid: boolean;
  validationErrors: ValidationError[];
}

interface Condition {
  attribute: string;  // Must start with user., resource., entity., or environment.
  operator: OperatorType;
  value: string | number | boolean | any[] | { [key: string]: any };
}

type OperatorType = 
  | 'EQUALS' 
  | 'NOT_EQUALS' 
  | 'LESS_THAN' 
  | 'LESS_THAN_OR_EQUAL'
  | 'GREATER_THAN' 
  | 'GREATER_THAN_OR_EQUAL' 
  | 'IN' 
  | 'NOT_IN'
  | 'CONTAINS' 
  | 'NOT_CONTAINS' 
  | 'STARTS_WITH' 
  | 'ENDS_WITH'
  | 'REGEX_MATCH' 
  | 'EXISTS' 
  | 'NOT_EXISTS';

// Validation function matching Python model
function validatePermissionName(name: string): string | null {
  if (!name.includes(':')) {
    return "Permission name must follow 'resource:action' format";
  }
  
  const parts = name.split(':');
  if (parts.length !== 2) {
    return "Permission name must have exactly one colon";
  }
  
  const [resource, action] = parts;
  if (!resource || !action) {
    return "Both resource and action must be non-empty";
  }
  
  const validPattern = /^[a-zA-Z0-9_-]+$/;
  if (resource !== '*' && !validPattern.test(resource)) {
    return "Resource must contain only letters, numbers, underscores, hyphens, or asterisk";
  }
  
  if (action !== '*' && !validPattern.test(action)) {
    return "Action must contain only letters, numbers, underscores, hyphens, or asterisk";
  }
  
  return null; // Valid
}
```

## Future Enhancements

### 1. Condition Templates
Pre-built condition sets for common scenarios:
- "Standard Approval Limits"
- "Business Hours Only"
- "Geographic Restrictions"

### 2. Visual Policy Builder
Drag-and-drop interface for complex condition logic:
- OR groups
- Nested conditions
- Visual flow charts

### 3. AI-Assisted Building
- Natural language to condition conversion
- "Create a permission that allows approving invoices under $50k"
- Suggested conditions based on resource type

### 4. Batch Operations
- Apply conditions to multiple permissions
- Clone and modify existing permissions
- Bulk enable/disable conditions

## Conclusion

The Permission Builder UI transforms the complex ABAC system into an intuitive interface that non-technical administrators can use confidently. By focusing on progressive disclosure, visual clarity, and immediate feedback, we ensure that the power of conditional permissions is accessible to all platform administrators.