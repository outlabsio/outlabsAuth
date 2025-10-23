# Entity Hierarchy

**Tags**: #enterprise #entity-system #hierarchy #organization

Building complete organizational structures with entity hierarchies.

---

## Overview

Entity hierarchies allow you to model organizational structures with nested entities that mirror real-world relationships. This guide covers how to design, build, and manage these hierarchies.

**Prerequisites**: [[50-Entity-System|Entity System Overview]], [[51-Entity-Types|Entity Types]]

**Key Concepts**:
- Hierarchies use parent-child relationships
- Closure table enables O(1) ancestor/descendant queries
- Validation prevents cycles and enforces depth limits
- Tree permissions propagate down the hierarchy

---

## Hierarchy Basics

### Parent-Child Relationships

```python
# Create parent
company = await auth.entity_service.create_entity(
    name="acme_corp",
    display_name="Acme Corporation",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="company"
)

# Create child
engineering = await auth.entity_service.create_entity(
    name="engineering",
    display_name="Engineering Department",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="department",
    parent_id=str(company.id)  # Link to parent
)
```

**Key Points**:
- Entities without `parent_id` are **root entities**
- Entities with `parent_id` form a **tree structure**
- Each entity can have **one parent** (not a graph)
- Entities can have **multiple children**

### Hierarchy Depth

```python
# Example 5-level hierarchy
Platform → Organization → Department → Team → Project
```

**Default Limits**:
- Maximum depth: **10 levels** (configurable)
- Enforced at creation time
- Prevents excessively deep hierarchies

**Configure Maximum Depth**:
```python
auth = EnterpriseRBAC(
    database=db,
    max_entity_depth=5  # Override default
)
```

---

## Common Hierarchy Patterns

### Pattern 1: Corporate Hierarchy

**Structure**: Company → Division → Department → Team

```python
# Root: Company
acme = await auth.entity_service.create_entity(
    name="acme_corp",
    display_name="Acme Corporation",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="company"
)

# Level 2: Divisions
engineering = await auth.entity_service.create_entity(
    name="engineering",
    display_name="Engineering Division",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="division",
    parent_id=str(acme.id)
)

sales = await auth.entity_service.create_entity(
    name="sales",
    display_name="Sales Division",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="division",
    parent_id=str(acme.id)
)

# Level 3: Departments
backend = await auth.entity_service.create_entity(
    name="backend",
    display_name="Backend Engineering",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="department",
    parent_id=str(engineering.id)
)

# Level 4: Teams
platform_team = await auth.entity_service.create_entity(
    name="platform_team",
    display_name="Platform Team",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="team",
    parent_id=str(backend.id)
)
```

**Result**:
```
Acme Corp
├── Engineering Division
│   └── Backend Engineering
│       └── Platform Team
└── Sales Division
```

**Use Case**: Traditional corporate structure with clear reporting lines.

### Pattern 2: Multi-Tenant SaaS

**Structure**: Platform → Workspace → Project → Resource

```python
# Root: Platform (implicit, or explicit root entity)
platform = await auth.entity_service.create_entity(
    name="platform",
    display_name="Our SaaS Platform",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="platform"
)

# Level 2: Customer workspaces
customer_workspace = await auth.entity_service.create_entity(
    name="customer_workspace",
    display_name="Customer Inc Workspace",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="workspace",
    parent_id=str(platform.id)
)

# Level 3: Projects within workspace
project_alpha = await auth.entity_service.create_entity(
    name="project_alpha",
    display_name="Project Alpha",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="project",
    parent_id=str(customer_workspace.id)
)

# Level 4: Resources within project
api_resource = await auth.entity_service.create_entity(
    name="api_prod",
    display_name="Production API",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="resource",
    parent_id=str(project_alpha.id)
)
```

**Result**:
```
Platform
└── Customer Inc Workspace
    └── Project Alpha
        └── Production API
```

**Use Case**: SaaS applications with isolated customer workspaces.

### Pattern 3: Geographic Hierarchy

**Structure**: Global → Region → Country → Office

```python
# Root: Global
global_org = await auth.entity_service.create_entity(
    name="global",
    display_name="Global Organization",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="global"
)

# Level 2: Regions
north_america = await auth.entity_service.create_entity(
    name="north_america",
    display_name="North America",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="region",
    parent_id=str(global_org.id)
)

# Level 3: Countries
usa = await auth.entity_service.create_entity(
    name="usa",
    display_name="United States",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="country",
    parent_id=str(north_america.id)
)

# Level 4: Offices
sf_office = await auth.entity_service.create_entity(
    name="sf_office",
    display_name="San Francisco Office",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="office",
    parent_id=str(usa.id)
)
```

**Result**:
```
Global Organization
└── North America
    └── United States
        └── San Francisco Office
```

**Use Case**: Global companies with distributed operations.

### Pattern 4: Project-Based Hierarchy

**Structure**: Organization → Program → Project → Task Group

```python
# Root: Organization
org = await auth.entity_service.create_entity(
    name="dev_agency",
    display_name="Development Agency",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="organization"
)

# Level 2: Programs
product_program = await auth.entity_service.create_entity(
    name="product_dev",
    display_name="Product Development Program",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="program",
    parent_id=str(org.id)
)

# Level 3: Projects
mobile_app = await auth.entity_service.create_entity(
    name="mobile_app",
    display_name="Mobile App Project",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="project",
    parent_id=str(product_program.id)
)

# Level 4: Task groups
backend_tasks = await auth.entity_service.create_entity(
    name="backend_tasks",
    display_name="Backend Development Tasks",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="task_group",
    parent_id=str(mobile_app.id)
)
```

**Result**:
```
Development Agency
└── Product Development Program
    └── Mobile App Project
        └── Backend Development Tasks
```

**Use Case**: Project management and consulting firms.

### Pattern 5: Matrix Organization

**Structure**: STRUCTURAL hierarchy + ACCESS_GROUP cross-cutting

```python
# STRUCTURAL hierarchy (reporting line)
company = await auth.entity_service.create_entity(
    name="company",
    display_name="Company",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="company"
)

engineering = await auth.entity_service.create_entity(
    name="engineering",
    display_name="Engineering",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="department",
    parent_id=str(company.id)
)

# ACCESS_GROUP cross-cutting (project teams)
project_alpha = await auth.entity_service.create_entity(
    name="project_alpha",
    display_name="Project Alpha Team",
    entity_class=EntityClass.ACCESS_GROUP,
    entity_type="project_team",
    parent_id=str(company.id)  # Can attach to any structural entity
)

# Users can be members of both:
# - Engineering (structural - their department)
# - Project Alpha (access_group - their project team)
```

**Result**:
```
Company
├── Engineering (STRUCTURAL)
└── Project Alpha Team (ACCESS_GROUP)
```

**Use Case**: Matrix organizations where employees report to departments but work on cross-functional projects.

---

## Building Hierarchies

### Step-by-Step Process

**Step 1: Design Your Structure**

```python
# Plan your entity types and hierarchy
"""
Organization (company)
├── Departments (department)
│   └── Teams (team)
└── Projects (project) [ACCESS_GROUP]
"""
```

**Step 2: Create Root Entity**

```python
root = await auth.entity_service.create_entity(
    name="root",
    display_name="Root Organization",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="company",
    description="Root entity for the organization"
)
```

**Step 3: Build Hierarchy Levels**

```python
# Level 2
dept = await auth.entity_service.create_entity(
    name="engineering",
    display_name="Engineering",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="department",
    parent_id=str(root.id)
)

# Level 3
team = await auth.entity_service.create_entity(
    name="backend_team",
    display_name="Backend Team",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="team",
    parent_id=str(dept.id)
)
```

**Step 4: Add Cross-Cutting Groups (Optional)**

```python
# ACCESS_GROUP for cross-functional work
project = await auth.entity_service.create_entity(
    name="mobile_project",
    display_name="Mobile App Project",
    entity_class=EntityClass.ACCESS_GROUP,
    entity_type="project",
    parent_id=str(root.id)
)
```

**Step 5: Assign Users to Entities**

```python
# Add user to structural entity
await auth.membership_service.add_member(
    entity_id=str(team.id),
    user_id=str(user.id),
    role_ids=[developer_role.id]
)

# Add user to access group
await auth.membership_service.add_member(
    entity_id=str(project.id),
    user_id=str(user.id),
    role_ids=[contributor_role.id]
)
```

### Bulk Creation Pattern

```python
async def build_company_hierarchy(auth: EnterpriseRBAC):
    """Build complete company hierarchy in one go"""

    # Root
    company = await auth.entity_service.create_entity(
        name="acme_corp",
        display_name="Acme Corporation",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="company"
    )

    # Divisions
    divisions = {}
    for div_name in ["engineering", "sales", "marketing"]:
        divisions[div_name] = await auth.entity_service.create_entity(
            name=div_name,
            display_name=div_name.title(),
            entity_class=EntityClass.STRUCTURAL,
            entity_type="division",
            parent_id=str(company.id)
        )

    # Departments under Engineering
    departments = {}
    for dept_name in ["backend", "frontend", "mobile"]:
        departments[dept_name] = await auth.entity_service.create_entity(
            name=f"{dept_name}_dept",
            display_name=f"{dept_name.title()} Department",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
            parent_id=str(divisions["engineering"].id)
        )

    # Teams under Backend
    for team_name in ["platform", "api", "data"]:
        await auth.entity_service.create_entity(
            name=f"{team_name}_team",
            display_name=f"{team_name.title()} Team",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=str(departments["backend"].id)
        )

    return company
```

---

## Querying Hierarchies

### Get Entity Path

Get all ancestors from root to entity:

```python
# Get path
path = await auth.entity_service.get_entity_path(entity_id)

# Example output
# [<Company>, <Division>, <Department>, <Team>]

# Display path
path_str = " → ".join([e.display_name for e in path])
# "Acme Corporation → Engineering → Backend Department → Platform Team"
```

**Performance**: O(1) using closure table.

### Get All Descendants

Get all entities under a parent:

```python
# Get all descendants
descendants = await auth.entity_service.get_descendants(entity_id)

# Filter by type
teams = await auth.entity_service.get_descendants(
    entity_id,
    entity_type="team"
)
```

**Performance**: O(1) using closure table.

### Get Direct Children

Get only immediate children:

```python
# Get direct children only
children = await auth.entity_service.get_children(entity_id)

# Example: Get all departments under a division
departments = await auth.entity_service.get_children(division.id)
```

**Performance**: O(1) single query.

### Complete Traversal Example

```python
async def print_hierarchy(auth: EnterpriseRBAC, entity_id: str, indent: int = 0):
    """Recursively print entity hierarchy"""
    entity = await auth.entity_service.get_entity(entity_id)
    print("  " * indent + f"└── {entity.display_name} ({entity.entity_type})")

    children = await auth.entity_service.get_children(entity_id)
    for child in children:
        await print_hierarchy(auth, str(child.id), indent + 1)

# Usage
await print_hierarchy(auth, root_entity_id)

# Output:
# └── Acme Corporation (company)
#   └── Engineering (division)
#     └── Backend Department (department)
#       └── Platform Team (team)
#   └── Sales (division)
```

---

## Hierarchy Validation

### Automatic Validation Rules

**Rule 1: No Cycles**
```python
# This will fail - cannot create cycle
try:
    # Try to make parent a child of its own descendant
    await auth.entity_service.update_entity(
        parent.id,
        parent_id=child.id  # ❌ Creates cycle
    )
except InvalidInputError:
    # Error: Would create circular hierarchy
    pass
```

**Rule 2: Maximum Depth**
```python
# Default max depth: 10 levels
# This will fail if depth exceeded
try:
    level_11 = await auth.entity_service.create_entity(
        name="level_11",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="team",
        parent_id=level_10.id  # ❌ Exceeds depth
    )
except InvalidInputError as e:
    print(e.message)  # "Maximum hierarchy depth (10) reached"
```

**Rule 3: Entity Class Restrictions**
```python
# ACCESS_GROUP cannot have STRUCTURAL children
access_group = await auth.entity_service.create_entity(
    name="project_team",
    entity_class=EntityClass.ACCESS_GROUP,
    entity_type="project"
)

try:
    # Try to add STRUCTURAL child to ACCESS_GROUP
    structural = await auth.entity_service.create_entity(
        name="dept",
        entity_class=EntityClass.STRUCTURAL,  # ❌
        entity_type="department",
        parent_id=str(access_group.id)
    )
except InvalidInputError:
    # Error: Access groups cannot have structural children
    pass
```

### Custom Validation Rules

**Allowed Child Types**:

```python
# Configure allowed child types
company = await auth.entity_service.create_entity(
    name="company",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="company",
    allowed_child_types=["division", "department"]  # Only these types allowed
)

# This works
division = await auth.entity_service.create_entity(
    name="engineering",
    entity_type="division",  # ✅ Allowed
    parent_id=str(company.id)
)

# This fails
try:
    team = await auth.entity_service.create_entity(
        name="team",
        entity_type="team",  # ❌ Not in allowed_child_types
        parent_id=str(company.id)
    )
except InvalidInputError:
    # Error: Entity type 'team' not allowed as child of 'company'
    pass
```

**Allowed Child Classes**:

```python
# Only allow STRUCTURAL children
structural_entity = await auth.entity_service.create_entity(
    name="engineering",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="department",
    allowed_child_classes=[EntityClass.STRUCTURAL]
)

# ACCESS_GROUP children will be rejected
```

---

## Moving Entities

### Change Parent

```python
# Move entity to new parent
await auth.entity_service.update_entity(
    entity_id,
    parent_id=new_parent_id
)

# Closure table automatically updated
# Tree permissions recalculated
```

**What Happens**:
1. Old closure records deleted
2. New closure records created
3. All descendants updated
4. Cache invalidated

**Performance**: O(N) where N = number of descendants.

### Move Subtree

```python
# Moving an entity moves entire subtree
backend_dept = await auth.entity_service.get_entity(dept_id)

# Move department to new division
await auth.entity_service.update_entity(
    dept_id,
    parent_id=new_division_id
)

# All teams under backend_dept also moved
# Closure table maintains all relationships
```

**Result**:
```
Before:
Engineering Division
└── Backend Department
    └── Platform Team

Sales Division

After move:
Engineering Division

Sales Division
└── Backend Department
    └── Platform Team
```

---

## Deleting Entities

### Soft Delete (Default)

```python
# Soft delete (sets status to 'archived')
await auth.entity_service.delete_entity(entity_id)

# Entity still in database but not active
# Can be restored later
```

**Behavior**:
- Entity `status` set to `"archived"`
- Memberships deactivated
- Closure records deleted
- Entity no longer appears in queries

### Cascade Delete

```python
# Delete entity and all descendants
await auth.entity_service.delete_entity(
    entity_id,
    cascade=True  # Recursively delete children
)
```

**Warning**: This will archive the entire subtree!

**Example**:
```python
# Delete department cascades to teams
await auth.entity_service.delete_entity(dept_id, cascade=True)

# Before:
# Department
# ├── Team A
# └── Team B

# After: All archived
```

### Protection Against Orphans

```python
# Cannot delete entity with active children
try:
    await auth.entity_service.delete_entity(entity_id)
except InvalidInputError:
    # Error: Cannot delete entity with children
    # Use cascade=True to delete all children
    pass
```

---

## Performance Considerations

### Closure Table Benefits

**O(1) Queries**: All ancestor/descendant queries use single database lookup.

```python
# Before (recursive): O(depth) queries
ancestors = []
current = entity
while current.parent:
    current = await current.parent.fetch()
    ancestors.append(current)

# After (closure table): O(1) single query
ancestors = await auth.entity_service.get_entity_path(entity.id)
```

**Performance Comparison**:
| Operation | Without Closure Table | With Closure Table |
|-----------|---------------------|-------------------|
| Get ancestors | O(depth) ~50ms | O(1) ~1ms |
| Get descendants | O(N) ~100ms | O(1) ~5ms |
| Check if ancestor | O(depth) ~50ms | O(1) ~1ms |

**See**: [[53-Closure-Table|Closure Table Pattern]]

### Caching Strategy

**Redis Caching** (if enabled):

```python
auth = EnterpriseRBAC(
    database=db,
    enable_caching=True,
    redis_url="redis://localhost:6379"
)
```

**What's Cached**:
- Entity paths: 15 minutes TTL
- Descendants: 15 minutes TTL
- Automatic invalidation on changes

**Cache Keys**:
```python
entity:path:{entity_id}         # Ancestor path
entity:descendants:{entity_id}  # All descendants
```

### Query Optimization Tips

1. **Use Closure Table Queries**
   - `get_entity_path()` instead of recursive parent fetching
   - `get_descendants()` instead of recursive child traversal

2. **Enable Redis Caching**
   - Dramatically reduces database load
   - Sub-millisecond query times for cached paths

3. **Limit Hierarchy Depth**
   - Keep hierarchies reasonably flat (≤5 levels ideal)
   - Deep hierarchies (>10 levels) add complexity

4. **Batch Operations**
   - Create multiple entities in transactions
   - Use bulk queries when possible

---

## Best Practices

### Design Guidelines

**1. Keep It Flat When Possible**
```python
# Good: 3 levels
Company → Department → Team

# Avoid: 8 levels
Platform → Region → Country → State → City → Office → Floor → Room
```

**2. Use Meaningful Entity Types**
```python
# Good: Clear naming
entity_type="department"
entity_type="team"

# Bad: Generic naming
entity_type="group"
entity_type="container"
```

**3. Separate Structural from Access Groups**
```python
# STRUCTURAL: Organizational hierarchy
company → division → department → team

# ACCESS_GROUP: Cross-cutting permissions
project_teams, admin_groups, viewer_groups
```

**4. Validate at Creation**
```python
# Set allowed child types
company = await auth.entity_service.create_entity(
    name="company",
    entity_type="company",
    allowed_child_types=["division"]  # Enforce structure
)
```

**5. Document Your Structure**
```python
# In code comments or configuration
"""
Entity Hierarchy:
- company (root)
  - division (level 2)
    - department (level 3)
      - team (level 4)
        - project (level 5) [ACCESS_GROUP]
"""
```

### Migration Patterns

**Pattern: Flat to Hierarchical**

```python
# Before: Flat structure with SimpleRBAC
# Users → Roles → Permissions

# After: Hierarchical structure with EnterpriseRBAC
# Company → Departments → Teams
# Users → Memberships (in teams) → Roles → Permissions

# Migration steps:
# 1. Create entity hierarchy
# 2. Map users to appropriate entities
# 3. Assign roles within entity context
# 4. Test tree permissions
# 5. Remove global role assignments
```

**Pattern: Single to Multi-Tenant**

```python
# Before: Single organization
# Organization → Departments → Teams

# After: Multi-tenant platform
# Platform (root)
# ├── Tenant A Workspace
# │   └── Departments → Teams
# └── Tenant B Workspace
#     └── Departments → Teams
```

---

## Complete Example

### Building a Complete Organization

```python
async def build_complete_org(auth: EnterpriseRBAC):
    """
    Build a complete organizational hierarchy:

    Acme Corp
    ├── Engineering Division
    │   ├── Backend Department
    │   │   ├── Platform Team
    │   │   └── API Team
    │   └── Frontend Department
    │       └── Web Team
    ├── Sales Division
    │   └── Enterprise Sales Team
    └── [Cross-cutting] Mobile App Project (ACCESS_GROUP)
    """

    # Root: Company
    company = await auth.entity_service.create_entity(
        name="acme_corp",
        display_name="Acme Corporation",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="company",
        description="Root company entity",
        allowed_child_types=["division"]
    )

    # Level 2: Divisions
    engineering = await auth.entity_service.create_entity(
        name="engineering",
        display_name="Engineering Division",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="division",
        parent_id=str(company.id),
        allowed_child_types=["department"]
    )

    sales = await auth.entity_service.create_entity(
        name="sales",
        display_name="Sales Division",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="division",
        parent_id=str(company.id),
        allowed_child_types=["department", "team"]
    )

    # Level 3: Departments
    backend = await auth.entity_service.create_entity(
        name="backend",
        display_name="Backend Department",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="department",
        parent_id=str(engineering.id),
        allowed_child_types=["team"]
    )

    frontend = await auth.entity_service.create_entity(
        name="frontend",
        display_name="Frontend Department",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="department",
        parent_id=str(engineering.id),
        allowed_child_types=["team"]
    )

    # Level 4: Teams under Backend
    platform_team = await auth.entity_service.create_entity(
        name="platform_team",
        display_name="Platform Team",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="team",
        parent_id=str(backend.id)
    )

    api_team = await auth.entity_service.create_entity(
        name="api_team",
        display_name="API Team",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="team",
        parent_id=str(backend.id)
    )

    # Level 4: Teams under Frontend
    web_team = await auth.entity_service.create_entity(
        name="web_team",
        display_name="Web Team",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="team",
        parent_id=str(frontend.id)
    )

    # Level 4: Team directly under Sales
    enterprise_sales = await auth.entity_service.create_entity(
        name="enterprise_sales",
        display_name="Enterprise Sales Team",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="team",
        parent_id=str(sales.id)
    )

    # Cross-cutting: Project team (ACCESS_GROUP)
    mobile_project = await auth.entity_service.create_entity(
        name="mobile_project",
        display_name="Mobile App Project",
        entity_class=EntityClass.ACCESS_GROUP,
        entity_type="project",
        parent_id=str(company.id),
        description="Cross-functional mobile app development team"
    )

    # Print hierarchy
    print("\n=== Organizational Hierarchy ===\n")
    await print_hierarchy(auth, str(company.id))

    return {
        "company": company,
        "engineering": engineering,
        "sales": sales,
        "backend": backend,
        "frontend": frontend,
        "platform_team": platform_team,
        "api_team": api_team,
        "web_team": web_team,
        "enterprise_sales": enterprise_sales,
        "mobile_project": mobile_project
    }

async def print_hierarchy(auth: EnterpriseRBAC, entity_id: str, indent: int = 0):
    """Recursively print entity hierarchy"""
    entity = await auth.entity_service.get_entity(entity_id)
    class_marker = " [ACCESS_GROUP]" if entity.is_access_group else ""
    print("  " * indent + f"└── {entity.display_name} ({entity.entity_type}){class_marker}")

    children = await auth.entity_service.get_children(entity_id)
    for child in children:
        await print_hierarchy(auth, str(child.id), indent + 1)

# Usage
entities = await build_complete_org(auth)

# Output:
# === Organizational Hierarchy ===
#
# └── Acme Corporation (company)
#   └── Engineering Division (division)
#     └── Backend Department (department)
#       └── Platform Team (team)
#       └── API Team (team)
#     └── Frontend Department (department)
#       └── Web Team (team)
#   └── Sales Division (division)
#     └── Enterprise Sales Team (team)
#   └── Mobile App Project (project) [ACCESS_GROUP]
```

---

## Testing Hierarchies

```python
import pytest

@pytest.mark.asyncio
async def test_create_hierarchy(enterprise_auth):
    """Test creating multi-level hierarchy"""

    # Create 3-level hierarchy
    company = await enterprise_auth.entity_service.create_entity(
        name="test_company",
        display_name="Test Company",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="company"
    )

    dept = await enterprise_auth.entity_service.create_entity(
        name="test_dept",
        display_name="Test Department",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="department",
        parent_id=str(company.id)
    )

    team = await enterprise_auth.entity_service.create_entity(
        name="test_team",
        display_name="Test Team",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="team",
        parent_id=str(dept.id)
    )

    # Verify path
    path = await enterprise_auth.entity_service.get_entity_path(str(team.id))
    assert len(path) == 3
    assert path[0].id == company.id
    assert path[1].id == dept.id
    assert path[2].id == team.id

@pytest.mark.asyncio
async def test_hierarchy_validation(enterprise_auth):
    """Test hierarchy validation rules"""

    # Create access group
    access_group = await enterprise_auth.entity_service.create_entity(
        name="project",
        entity_class=EntityClass.ACCESS_GROUP,
        entity_type="project"
    )

    # Should fail: STRUCTURAL child of ACCESS_GROUP
    with pytest.raises(InvalidInputError):
        await enterprise_auth.entity_service.create_entity(
            name="dept",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
            parent_id=str(access_group.id)
        )

@pytest.mark.asyncio
async def test_get_descendants(enterprise_auth, org_hierarchy):
    """Test getting all descendants"""

    # Get all descendants of company
    descendants = await enterprise_auth.entity_service.get_descendants(
        org_hierarchy["company"].id
    )

    # Should include all divisions, departments, teams
    assert len(descendants) > 0

    # Filter by type
    teams = await enterprise_auth.entity_service.get_descendants(
        org_hierarchy["company"].id,
        entity_type="team"
    )

    assert all(e.entity_type == "team" for e in teams)
```

---

## Troubleshooting

### Common Issues

**Issue 1: Maximum depth exceeded**
```python
# Error: Maximum hierarchy depth (10) reached
# Solution: Reduce depth or increase limit
auth = EnterpriseRBAC(database=db, max_entity_depth=15)
```

**Issue 2: Circular reference detected**
```python
# Error: Cannot create circular hierarchy
# Solution: Verify parent_id doesn't create cycle
path = await auth.entity_service.get_entity_path(parent_id)
if entity_id in [str(e.id) for e in path]:
    # Would create cycle
    pass
```

**Issue 3: Cannot delete entity with children**
```python
# Error: Cannot delete entity with children
# Solution: Use cascade delete or remove children first
await auth.entity_service.delete_entity(entity_id, cascade=True)
```

**Issue 4: Slow hierarchy queries**
```python
# Problem: Recursive queries without closure table
# Solution: Verify closure table is maintained
closures = await EntityClosureModel.find(
    EntityClosureModel.ancestor_id == entity_id
).to_list()

if not closures:
    # Closure records missing - rebuild
    await auth.entity_service._create_closure_records(entity)
```

---

## Next Steps

- **[[54-Entity-Memberships|Entity Memberships]]** - Assign users to entities
- **[[44-Tree-Permissions|Tree Permissions]]** - Hierarchical access control
- **[[45-Context-Aware-Roles|Context-Aware Roles]]** - Role adaptation by entity type
- **[[73-Entity-Service|EntityService]]** - Service API reference

---

**Previous**: [[51-Entity-Types|← Entity Types]]
**Next**: [[54-Entity-Memberships|Entity Memberships →]]
