# Permission Visual Examples

## Tree Permission Scope Visualization

### Example 1: Organization Admin with Mixed Permissions

```
ACME Corporation (Organization)
├── Role: org_admin
├── Permissions: ["entity:manage", "entity:manage_tree"]
├── Can access: ✅ ACME Corporation (due to entity:manage)
└── Can access: ✅ All entities below (due to entity:manage_tree)
    ├── Sales Division
    │   ├── North Region
    │   │   ├── Seattle Office
    │   │   └── Portland Office
    │   └── South Region
    │       ├── Los Angeles Office
    │       └── San Diego Office
    └── Engineering Division
        ├── Backend Team
        └── Frontend Team
```

### Example 2: Division Manager with Tree Permissions Only

```
ACME Corporation
└── Sales Division
    ├── Role: division_manager
    ├── Permissions: ["entity:read_tree", "entity:update_tree"]
    ├── Can access: ❌ Sales Division (no entity:read or entity:update)
    └── Can access: ✅ All entities below (due to *_tree permissions)
        ├── North Region
        │   ├── Seattle Office
        │   └── Portland Office
        └── South Region
            ├── Los Angeles Office
            └── San Diego Office
```

### Example 3: Regional Manager with Proper Permissions

```
ACME Corporation
└── Sales Division
    └── North Region
        ├── Role: regional_manager
        ├── Permissions: ["entity:read", "entity:update", "entity:read_tree", "entity:update_tree"]
        ├── Can access: ✅ North Region (due to entity:read and entity:update)
        └── Can access: ✅ All offices below (due to *_tree permissions)
            ├── Seattle Office
            └── Portland Office
```

## Common Role Permission Patterns

### Pattern 1: Full Entity Management (Entity + Descendants)
```yaml
role: "organization_admin"
permissions:
  # Direct entity access
  - "entity:read"
  - "entity:create"
  - "entity:update" 
  - "entity:delete"
  # Descendant access
  - "entity:read_tree"
  - "entity:create_tree"
  - "entity:update_tree"
  - "entity:delete_tree"
  # Or simply:
  - "entity:manage"      # Includes all direct permissions
  - "entity:manage_tree" # Includes all tree permissions
```

### Pattern 2: Read-Only Access (Entity + Descendants)
```yaml
role: "auditor"
permissions:
  - "entity:read"       # Read the assigned entity
  - "entity:read_tree"  # Read all descendants
  - "user:read"
  - "user:read_tree"
  - "role:read"
  - "role:read_tree"
```

### Pattern 3: Descendant-Only Management
```yaml
role: "subsidiary_coordinator"
permissions:
  - "entity:read"         # Can see their assigned entity
  - "entity:create_tree"  # Can create sub-entities
  - "entity:update_tree"  # Can update sub-entities
  - "entity:delete_tree"  # Can delete sub-entities
  # Note: Cannot modify the entity they're assigned to
```

### Pattern 4: Platform-Wide Access
```yaml
role: "system_admin"
permissions:
  - "entity:manage_all"   # Full access everywhere
  - "user:manage_all"
  - "role:manage_all"
```

## Permission Check Flow

When checking if a user can perform `entity:update` on Department X:

```
1. Check direct permission in Department X
   └── Has entity:update? → ✅ Allow
   
2. Check tree permissions in parent entities
   └── Parent: Division Y
       └── Has entity:update_tree? → ✅ Allow
   └── Grandparent: Organization Z
       └── Has entity:update_tree? → ✅ Allow
   └── Great-grandparent: Platform
       └── Has entity:update_tree? → ✅ Allow
       
3. Check platform-wide permissions
   └── Has entity:update_all anywhere? → ✅ Allow
   
4. No matching permissions → ❌ Deny
```

## Real-World Scenarios

### Scenario: Multi-Level Organization

```
TechCorp (Platform)
├── user: ceo@techcorp.com
├── role: platform_admin
├── permissions: ["entity:manage", "entity:manage_tree"]
│
├── TechCorp US (Organization)
│   ├── user: us-president@techcorp.com
│   ├── role: org_president
│   ├── permissions: ["entity:manage", "entity:manage_tree"]
│   │
│   ├── Engineering (Division)
│   │   ├── user: eng-vp@techcorp.com
│   │   ├── role: division_vp
│   │   ├── permissions: ["entity:read", "entity:update", "entity:manage_tree"]
│   │   │
│   │   ├── Backend Team
│   │   │   ├── user: backend-lead@techcorp.com
│   │   │   ├── role: team_lead
│   │   │   └── permissions: ["entity:manage", "user:manage"]
│   │   │
│   │   └── Frontend Team
│   │       ├── user: frontend-lead@techcorp.com
│   │       ├── role: team_lead
│   │       └── permissions: ["entity:manage", "user:manage"]
│   │
│   └── Sales (Division)
│       ├── user: sales-vp@techcorp.com
│       ├── role: division_vp
│       └── permissions: ["entity:read", "entity:update", "entity:manage_tree"]
│
└── TechCorp EU (Organization)
    ├── user: eu-president@techcorp.com
    ├── role: org_president
    └── permissions: ["entity:manage", "entity:manage_tree"]
```

**Permission Analysis**:
- `ceo@techcorp.com` can manage TechCorp platform AND all organizations/divisions/teams below
- `us-president@techcorp.com` can manage TechCorp US AND all divisions/teams below
- `eng-vp@techcorp.com` can read/update Engineering division AND fully manage all teams below
- `backend-lead@techcorp.com` can only manage the Backend Team (no tree permissions)
- Users in US organization cannot access EU organization (platform isolation)

## Key Takeaways

1. **Tree permissions cascade downward only** - they never grant access to the entity where assigned
2. **For full control**, assign both regular and tree permissions
3. **For descendant-only control**, assign only tree permissions
4. **Permission checks traverse upward** - checking each ancestor for tree permissions
5. **Platform permissions** (`*_all`) bypass the hierarchy entirely