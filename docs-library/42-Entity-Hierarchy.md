# Entity Hierarchy

**Complete guide to organizational structure and entity management in EnterpriseRBAC**

---

## Table of Contents

- [Overview](#overview)
- [Entity Concepts](#entity-concepts)
  - [Entity Classes](#entity-classes)
  - [Entity Types](#entity-types)
  - [Entity Relationships](#entity-relationships)
- [Creating Entity Hierarchies](#creating-entity-hierarchies)
  - [Basic Hierarchy](#basic-hierarchy)
  - [Complex Hierarchies](#complex-hierarchies)
  - [Access Groups](#access-groups)
- [Hierarchy Validation Rules](#hierarchy-validation-rules)
- [Closure Table Pattern](#closure-table-pattern)
- [Entity Operations](#entity-operations)
  - [CRUD Operations](#crud-operations)
  - [Traversal Operations](#traversal-operations)
  - [Bulk Operations](#bulk-operations)
- [Common Hierarchy Patterns](#common-hierarchy-patterns)
- [Performance Considerations](#performance-considerations)
- [Best Practices](#best-practices)
- [See Also](#see-also)

---

## Overview

**Entity Hierarchy** is the organizational structure in EnterpriseRBAC that represents departments, teams, projects, and other organizational units.

### Why Entity Hierarchy?

Entity hierarchy enables:
- ✅ **Organizational Structure**: Model real-world org charts
- ✅ **Scoped Permissions**: Different access per department/team
- ✅ **Permission Inheritance**: Tree permissions flow down hierarchy
- ✅ **Multi-Context Users**: Different roles in different entities
- ✅ **Flexible Organization**: Any depth, any structure

### Architecture

```
┌──────────────────────────────────────────────────────────┐
│  Entity Hierarchy (EnterpriseRBAC Only)                  │
├──────────────────────────────────────────────────────────┤
│  ACME Corporation (organization)                         │
│  ├── Engineering (department)                            │
│  │   ├── Backend Team (team)                            │
│  │   │   ├── Project Alpha (project)                    │
│  │   │   └── Project Beta (project)                     │
│  │   ├── Frontend Team (team)                           │
│  │   └── Senior Engineers (access group)                │
│  ├── Sales (department)                                  │
│  │   ├── West Region (team)                             │
│  │   └── East Region (team)                             │
│  └── Operations (department)                             │
└──────────────────────────────────────────────────────────┘
```

---

## Entity Concepts

### Entity Classes

Entities have **two classes** that define their purpose:

#### 1. STRUCTURAL

**Purpose:** Represent organizational structure.

**Characteristics:**
- Part of the org chart (department, team, project)
- Can have child entities
- Form tree hierarchy
- Used for scoped permissions

**Examples:**
- Organization
- Department
- Team
- Project
- Division
- Branch

```python
from outlabs_auth.models.entity import EntityClass

engineering = await auth.entity_service.create_entity(
    name="engineering",
    display_name="Engineering Department",
    entity_class=EntityClass.STRUCTURAL,  # Structural entity
    entity_type="department"
)
```

#### 2. ACCESS_GROUP

**Purpose:** Special permission groups (not part of org structure).

**Characteristics:**
- For granting special permissions
- Can be child of STRUCTURAL entity
- **Cannot have STRUCTURAL children** (rule violation)
- Grants additional permissions beyond org structure

**Examples:**
- Admins
- Senior Engineers
- Beta Testers
- Emergency Responders
- Executive Committee

```python
senior_engineers = await auth.entity_service.create_entity(
    name="senior_engineers",
    display_name="Senior Engineers",
    entity_class=EntityClass.ACCESS_GROUP,  # Access group
    entity_type="group",
    parent_id=str(engineering.id)  # Under engineering dept
)
```

**Hierarchy Rule:**
```
✅ STRUCTURAL → STRUCTURAL (allowed)
✅ STRUCTURAL → ACCESS_GROUP (allowed)
❌ ACCESS_GROUP → STRUCTURAL (NOT allowed)
✅ ACCESS_GROUP → ACCESS_GROUP (allowed)
```

### Entity Types

**Entity type** is a flexible string field representing the entity's purpose.

#### Standard Types

```python
# Common organizational types
"organization"   # Root company/org
"department"     # Department
"team"           # Team
"project"        # Project
"division"       # Division
"branch"         # Branch/location
"workspace"      # Workspace (SaaS)

# Access group types
"group"          # Generic access group
"committee"      # Committee
"cohort"         # Training cohort
```

#### Custom Types

Define your own types for your domain:

```python
# Healthcare
"hospital"
"department"
"unit"
"ward"

# Education
"university"
"college"
"department"
"program"

# Retail
"company"
"region"
"store"
"department"

# Manufacturing
"plant"
"line"
"station"
"shift"
```

### Entity Relationships

Entities form a **tree hierarchy** with parent-child relationships:

```python
# Parent-child relationship
org = create_entity("ACME", type="organization")          # Root
dept = create_entity("Engineering", parent=org)            # Child of org
team = create_entity("Backend", parent=dept)               # Child of dept
project = create_entity("Project A", parent=team)          # Child of team

# Resulting tree:
# org → dept → team → project
```

**Key Concepts:**
- **Root Entity**: No parent (e.g., organization)
- **Parent**: Direct ancestor
- **Child**: Direct descendant
- **Ancestors**: All entities above (parent, grandparent, etc.)
- **Descendants**: All entities below (children, grandchildren, etc.)
- **Siblings**: Entities with same parent
- **Path**: Sequence from root to entity

---

## Creating Entity Hierarchies

### Basic Hierarchy

#### Simple 3-Level Company

```python
from outlabs_auth.models.entity import EntityClass

# Level 0: Organization (root)
org = await auth.entity_service.create_entity(
    name="acme_corp",
    display_name="ACME Corporation",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="organization",
    description="Main organization"
)

# Level 1: Departments
engineering = await auth.entity_service.create_entity(
    name="engineering",
    display_name="Engineering Department",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="department",
    parent_id=str(org.id),
    metadata={"budget": 5000000, "headcount": 50}
)

sales = await auth.entity_service.create_entity(
    name="sales",
    display_name="Sales Department",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="department",
    parent_id=str(org.id),
    metadata={"budget": 3000000, "headcount": 30}
)

# Level 2: Teams
backend_team = await auth.entity_service.create_entity(
    name="backend_team",
    display_name="Backend Team",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="team",
    parent_id=str(engineering.id),
    metadata={"tech_stack": ["Python", "FastAPI", "MongoDB"]}
)

frontend_team = await auth.entity_service.create_entity(
    name="frontend_team",
    display_name="Frontend Team",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="team",
    parent_id=str(engineering.id),
    metadata={"tech_stack": ["React", "TypeScript", "Tailwind"]}
)
```

**Resulting Hierarchy:**
```
ACME Corporation
├── Engineering Department
│   ├── Backend Team
│   └── Frontend Team
└── Sales Department
```

### Complex Hierarchies

#### Multi-Level Company with Branches

```python
# Root
company = create_entity("TechCorp Global", type="organization")

# Level 1: Regions
na_region = create_entity("North America", type="region", parent=company)
eu_region = create_entity("Europe", type="region", parent=company)

# Level 2: Countries
usa = create_entity("USA", type="country", parent=na_region)
canada = create_entity("Canada", type="country", parent=na_region)
uk = create_entity("UK", type="country", parent=eu_region)

# Level 3: Offices
sf_office = create_entity("San Francisco", type="office", parent=usa)
ny_office = create_entity("New York", type="office", parent=usa)

# Level 4: Departments (in each office)
sf_engineering = create_entity("Engineering", type="department", parent=sf_office)
sf_sales = create_entity("Sales", type="department", parent=sf_office)

# Level 5: Teams
sf_backend = create_entity("Backend Team", type="team", parent=sf_engineering)
sf_frontend = create_entity("Frontend Team", type="team", parent=sf_engineering)

# Level 6: Projects
project_alpha = create_entity("Project Alpha", type="project", parent=sf_backend)
project_beta = create_entity("Project Beta", type="project", parent=sf_backend)
```

**Resulting Hierarchy:**
```
TechCorp Global
├── North America
│   ├── USA
│   │   ├── San Francisco
│   │   │   ├── Engineering
│   │   │   │   ├── Backend Team
│   │   │   │   │   ├── Project Alpha
│   │   │   │   │   └── Project Beta
│   │   │   │   └── Frontend Team
│   │   │   └── Sales
│   │   └── New York
│   └── Canada
└── Europe
    └── UK
```

### Access Groups

Access groups grant **additional permissions** beyond the org structure.

```python
# Create access group under engineering
senior_engineers = await auth.entity_service.create_entity(
    name="senior_engineers",
    display_name="Senior Engineers",
    entity_class=EntityClass.ACCESS_GROUP,  # Access group
    entity_type="group",
    parent_id=str(engineering.id),
    description="Senior engineers with elevated permissions"
)

# Create roles for access group
senior_role = await auth.role_service.create_role(
    name="senior_engineer",
    permissions=[
        "code:review_tree",      # Can review in all eng teams
        "architecture:approve",  # Can approve architecture
        "deployment:production"  # Can deploy to production
    ]
)

# Add members to access group
await auth.membership_service.add_member(
    entity_id=str(senior_engineers.id),
    user_id=str(alice.id),
    role_ids=[str(senior_role.id)]
)

# Alice gets senior permissions IN ADDITION to her team membership
```

**Access Group Use Cases:**
- **Administrative Groups**: Platform admins, super users
- **Seniority Levels**: Senior engineers, principal engineers
- **Special Access**: On-call team, incident responders
- **Cross-Functional**: Architecture committee, security team
- **Temporary**: Beta testers, pilot program participants

---

## Hierarchy Validation Rules

OutlabsAuth enforces these rules when creating entities:

### Rule 1: ACCESS_GROUP Cannot Have STRUCTURAL Children

```python
# ❌ INVALID: Structural entity under access group
access_group = create_entity("Admins", class=ACCESS_GROUP)

try:
    team = create_entity(
        "Team A",
        class=STRUCTURAL,
        parent=access_group  # ❌ Not allowed
    )
except InvalidInputError:
    # Error: Access groups cannot have structural entities as children
    pass

# ✅ VALID: Access group under access group
sub_group = create_entity(
    "Super Admins",
    class=ACCESS_GROUP,
    parent=access_group  # ✅ Allowed
)
```

### Rule 2: Maximum Depth Limit

Default max depth: **10 levels**

```python
# ❌ INVALID: Exceeds max depth
org = create_entity("Org")                       # Depth 0
l1 = create_entity("L1", parent=org)            # Depth 1
l2 = create_entity("L2", parent=l1)             # Depth 2
# ... (continue to depth 10)
l10 = create_entity("L10", parent=l9)           # Depth 10 (max)

try:
    l11 = create_entity("L11", parent=l10)      # Depth 11
except InvalidInputError:
    # Error: Maximum hierarchy depth (10) reached
    pass

# Configure custom max depth
auth = EnterpriseRBAC(
    database=db,
    max_entity_depth=15  # Custom max depth
)
```

### Rule 3: Allowed Child Types (Optional)

Restrict which entity types can be children:

```python
# Create department with allowed child types
dept = await auth.entity_service.create_entity(
    name="engineering",
    entity_type="department",
    allowed_child_types=["team", "group"]  # Only teams and groups allowed
)

# ✅ VALID: Team is allowed
team = create_entity("Backend", type="team", parent=dept)

# ❌ INVALID: Project not in allowed list
try:
    project = create_entity("Project A", type="project", parent=dept)
except InvalidInputError:
    # Error: Entity type 'project' not allowed as child of 'department'
    pass
```

### Rule 4: Unique Slugs

Entity slugs must be globally unique:

```python
# ❌ INVALID: Duplicate slug
org1 = create_entity("Engineering", slug="engineering")

try:
    org2 = create_entity("Engineering Dept", slug="engineering")
except InvalidInputError:
    # Error: Entity with slug 'engineering' already exists
    pass

# ✅ VALID: Auto-generated slugs
org1 = create_entity("Engineering")           # slug: engineering
org2 = create_entity("Engineering Department") # slug: engineering-department
```

---

## Closure Table Pattern

OutlabsAuth uses the **Closure Table Pattern** (DD-036) for **O(1) ancestor/descendant queries**.

### What is Closure Table?

A closure table stores **all ancestor-descendant relationships** with depth:

```python
# Hierarchy:
# org → dept → team → project

# Closure Table:
# ancestor_id  | descendant_id | depth
# -------------|---------------|-------
# org          | org           | 0      # Self-reference
# org          | dept          | 1      # Direct child
# org          | team          | 2      # Grandchild
# org          | project       | 3      # Great-grandchild
# dept         | dept          | 0      # Self-reference
# dept         | team          | 1      # Direct child
# dept         | project       | 2      # Grandchild
# team         | team          | 0      # Self-reference
# team         | project       | 1      # Direct child
# project      | project       | 0      # Self-reference
```

### Performance Benefits

**Without Closure Table** (recursive queries):
```python
# Get all descendants - O(n) recursive queries
descendants = []
queue = [org_id]
while queue:
    current = queue.pop(0)
    children = find_children(current)  # DB query per level
    descendants.extend(children)
    queue.extend(children)
```

**With Closure Table** (single query):
```python
# Get all descendants - O(1) single query
descendants = await EntityClosureModel.find(
    EntityClosureModel.ancestor_id == org_id,
    EntityClosureModel.depth > 0
).to_list()
```

**Performance Comparison:**
- **Get Descendants**: O(n) → O(1) (**20x faster**)
- **Get Ancestors**: O(n) → O(1) (**20x faster**)
- **Check Relationship**: O(n) → O(1) (**Instant**)

### Closure Table Maintenance

Closure table is **automatically maintained**:

```python
# Create entity - closure records auto-created
team = await auth.entity_service.create_entity(
    name="backend_team",
    parent_id=str(dept.id)
)
# Closure table updated automatically:
# - Self-reference added
# - All parent relationships added

# Delete entity - closure records auto-deleted
await auth.entity_service.delete_entity(str(team.id))
# Closure table updated automatically
```

---

## Entity Operations

### CRUD Operations

#### Create Entity

```python
entity = await auth.entity_service.create_entity(
    name="backend_team",
    display_name="Backend Team",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="team",
    parent_id=str(dept.id),
    description="Backend development team",
    slug="backend-team",  # Optional (auto-generated if omitted)
    metadata={"tech_stack": ["Python", "FastAPI"]},
    max_members=50,  # Optional max member limit
    allowed_child_types=["project"],  # Optional
    status="active"  # active/inactive/archived
)
```

#### Read Entity

```python
# Get by ID
entity = await auth.entity_service.get_entity(entity_id)

# Get by slug
entity = await auth.entity_service.get_entity_by_slug("backend-team")

# Check fields
print(entity.name)           # backend_team
print(entity.display_name)   # Backend Team
print(entity.entity_type)    # team
print(entity.entity_class)   # STRUCTURAL
print(entity.metadata)       # {"tech_stack": [...]}
```

#### Update Entity

```python
entity = await auth.entity_service.update_entity(
    entity_id,
    display_name="Backend Engineering Team",
    description="Updated description",
    metadata={"tech_stack": ["Python", "FastAPI", "PostgreSQL"]}
)
```

#### Delete Entity

```python
# Soft delete (status = archived)
await auth.entity_service.delete_entity(entity_id)

# Cascade delete (delete children recursively)
await auth.entity_service.delete_entity(
    entity_id,
    cascade=True  # Delete all descendants
)
```

### Traversal Operations

#### Get Path (Root to Entity)

```python
# Get path from root to entity
path = await auth.entity_service.get_entity_path(team_id)

# path = [org, dept, team]
for entity in path:
    print(f"{entity.display_name} ({entity.entity_type})")

# Output:
# ACME Corporation (organization)
# Engineering Department (department)
# Backend Team (team)
```

**Use Cases:**
- Breadcrumb navigation
- Permission inheritance checking
- Organizational context display

#### Get Descendants (All Children Below)

```python
# Get all descendants
descendants = await auth.entity_service.get_descendants(dept_id)
# Returns all teams, projects, etc. under department

# Filter by entity type
teams_only = await auth.entity_service.get_descendants(
    dept_id,
    entity_type="team"
)
```

**Use Cases:**
- Show all teams in department
- List all projects in organization
- Cascading operations

#### Get Children (Direct Children Only)

```python
# Get direct children
children = await auth.entity_service.get_children(dept_id)

# Only returns immediate children (teams)
# Does NOT return grandchildren (projects)
```

**Use Cases:**
- Show immediate sub-units
- Org chart level navigation

### Bulk Operations

#### Create Multiple Entities

```python
# Create org structure in bulk
entities = []

for dept_name in ["Engineering", "Sales", "Marketing"]:
    dept = await auth.entity_service.create_entity(
        name=dept_name.lower(),
        display_name=dept_name,
        entity_type="department",
        parent_id=str(org.id)
    )
    entities.append(dept)

    # Create teams under each department
    for team_name in ["Team A", "Team B"]:
        team = await auth.entity_service.create_entity(
            name=f"{dept_name.lower()}_{team_name.lower().replace(' ', '_')}",
            display_name=f"{dept_name} - {team_name}",
            entity_type="team",
            parent_id=str(dept.id)
        )
        entities.append(team)
```

---

## Common Hierarchy Patterns

### Pattern 1: Simple Company

```
Company
├── Engineering
├── Sales
└── Operations
```

```python
company = create_entity("ACME Corp", type="organization")
eng = create_entity("Engineering", type="department", parent=company)
sales = create_entity("Sales", type="department", parent=company)
ops = create_entity("Operations", type="department", parent=company)
```

### Pattern 2: Multi-Tier Organization

```
Corporation
├── Division A
│   ├── Department 1
│   │   ├── Team X
│   │   └── Team Y
│   └── Department 2
└── Division B
```

```python
corp = create_entity("Corp", type="organization")
div_a = create_entity("Division A", type="division", parent=corp)
dept_1 = create_entity("Department 1", type="department", parent=div_a)
team_x = create_entity("Team X", type="team", parent=dept_1)
```

### Pattern 3: Geographic Hierarchy

```
Global
├── North America
│   ├── USA
│   │   ├── California
│   │   │   ├── San Francisco Office
│   │   │   └── Los Angeles Office
│   │   └── New York
│   └── Canada
└── Europe
```

```python
global_org = create_entity("Global", type="organization")
na = create_entity("North America", type="region", parent=global_org)
usa = create_entity("USA", type="country", parent=na)
ca_state = create_entity("California", type="state", parent=usa)
sf_office = create_entity("San Francisco", type="office", parent=ca_state)
```

### Pattern 4: Matrix Organization

```
Company
├── Engineering (department)
│   ├── Backend Team
│   ├── Frontend Team
│   └── Senior Engineers (access group)
├── Product (department)
│   └── Product Managers (access group)
└── Cross-Functional Teams (access group)
    ├── Platform Team (access group)
    └── Security Team (access group)
```

```python
# Structural hierarchy
company = create_entity("Company", type="organization")
eng = create_entity("Engineering", type="department", parent=company)
backend = create_entity("Backend", type="team", parent=eng)

# Access groups for cross-functional teams
cross_func = create_entity(
    "Cross-Functional Teams",
    class=ACCESS_GROUP,
    parent=company
)
platform_team = create_entity(
    "Platform Team",
    class=ACCESS_GROUP,
    parent=cross_func
)
```

### Pattern 5: Project-Based

```
Organization
├── Active Projects
│   ├── Project Alpha
│   ├── Project Beta
│   └── Project Gamma
└── Archived Projects
    └── Project Legacy
```

```python
org = create_entity("Organization", type="organization")
active = create_entity("Active Projects", type="folder", parent=org)
project_a = create_entity("Project Alpha", type="project", parent=active)
project_b = create_entity("Project Beta", type="project", parent=active)
```

---

## Performance Considerations

### 1. Closure Table Benefits

```python
# O(1) queries for common operations
path = await get_entity_path(entity_id)          # Single query
descendants = await get_descendants(entity_id)   # Single query
```

### 2. Redis Caching (Optional)

```python
# Enable Redis caching for entity paths
auth = EnterpriseRBAC(
    database=db,
    enable_caching=True,
    redis_url="redis://localhost:6379",
    cache_entity_ttl=3600  # Cache for 1 hour
)

# First call - queries database
path = await auth.entity_service.get_entity_path(team_id)

# Second call - from Redis cache (instant)
path = await auth.entity_service.get_entity_path(team_id)
```

### 3. Invalidate Cache on Changes

```python
# After updating entity
await auth.entity_service.update_entity(entity_id, display_name="New Name")

# Invalidate cache
await auth.entity_service.invalidate_entity_cache(entity_id)

# After major hierarchy changes
await auth.entity_service.invalidate_entity_tree_cache(org_id)
```

### 4. Lazy Loading for Large Trees

```python
# Get only what you need
children = await auth.entity_service.get_children(dept_id)  # Direct only

# vs

descendants = await auth.entity_service.get_descendants(dept_id)  # Entire subtree
```

---

## Best Practices

### 1. Plan Your Hierarchy First

```python
# ✅ Good: Clear structure
Organization → Department → Team → Project

# ❌ Bad: Ad-hoc without plan
Organization → Team → Department → Project → Team
```

### 2. Use Consistent Naming

```python
# ✅ Good: Consistent naming convention
"engineering_dept"
"engineering_backend_team"
"engineering_backend_project_alpha"

# ❌ Bad: Inconsistent
"eng"
"BackendTeam"
"PROJ_ALPHA"
```

### 3. Limit Hierarchy Depth

```python
# ✅ Good: 3-5 levels
Org → Dept → Team → Project (4 levels)

# ❌ Bad: Too deep
Org → Region → Country → State → City → Office → Floor → Dept → Team → Project
```

### 4. Use Metadata for Attributes

```python
# ✅ Good: Store additional data in metadata
entity = create_entity(
    "Engineering",
    metadata={
        "budget": 5000000,
        "headcount": 50,
        "location": "San Francisco",
        "cost_center": "CC-1001"
    }
)

# ❌ Bad: Create new entity types for attributes
create_entity("Engineering-Budget-5M", type="department_with_budget")
```

### 5. Soft Delete Entities

```python
# ✅ Good: Soft delete (status = archived)
await auth.entity_service.delete_entity(entity_id)
# Can be restored, maintains history

# ❌ Bad: Hard delete
await EntityModel.find_one(id=entity_id).delete()
# Permanent, breaks relationships
```

### 6. Document Entity Types

```python
# Document your entity type conventions
ENTITY_TYPES = {
    "organization": "Top-level company or organization",
    "department": "Functional department within organization",
    "team": "Team within department",
    "project": "Specific project or initiative",
    "group": "Access group for special permissions"
}
```

---

## See Also

- **[41. RBAC Patterns](41-RBAC-Patterns.md)** - Role-based access control
- **[43. Tree Permissions](43-Tree-Permissions.md)** - Hierarchical permission inheritance
- **[12. Data Models](12-Data-Models.md)** - Entity model schema
- **[13. Service Layer](13-Service-Layer.md)** - EntityService API reference
- **[40. Authorization Overview](40-Authorization-Overview.md)** - Complete authorization guide

---

**Last Updated:** 2025-01-23
**Applies To:** OutlabsAuth v1.0+ (EnterpriseRBAC only)
**Related Design Decisions:** DD-005 (Entity Hierarchy), DD-036 (Closure Table), DD-037 (Redis Cache Invalidation)
