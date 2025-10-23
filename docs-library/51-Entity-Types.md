# Entity Types - STRUCTURAL vs ACCESS_GROUP

**Tags**: #enterprise-rbac #entity-types #organizational-design #access-control

Deep dive into OutlabsAuth's two entity classifications and when to use each.

---

## Overview

OutlabsAuth uses a **unified entity model** with two classifications:

1. **STRUCTURAL** - Organizational hierarchy (org chart)
2. **ACCESS_GROUP** - Permission boundaries (where work happens)

**Design Philosophy**: "Everything is an entity" - no separate groups table, no separate org structure. Simple, elegant, powerful.

---

## The Two Entity Classes

### STRUCTURAL Entities

**Purpose**: Organizational structure and hierarchy

**Characteristics**:
- `entity_class = "structural"`
- Represents organizational containers
- Users typically don't have direct memberships here
- Used primarily for tree permissions
- Forms the "org chart"

**Common Types**:
- Company, Organization
- Department, Division, Business Unit
- Office, Location, Region

**Visual Metaphor**: The "folders" in an org chart

```
Company (STRUCTURAL)
├── Engineering Dept (STRUCTURAL)
├── Sales Dept (STRUCTURAL)
└── Operations Dept (STRUCTURAL)
```

### ACCESS_GROUP Entities

**Purpose**: Permission boundaries where actual work happens

**Characteristics**:
- `entity_class = "access_group"`
- Users have direct memberships with roles
- Where permissions are actually checked
- Leaf nodes where work gets done
- The "teams" people belong to

**Common Types**:
- Team, Squad, Pod, Group
- Project, Workspace
- Repository, Folder
- Channel, Space

**Visual Metaphor**: The "rooms" where people work

```
Engineering Dept (STRUCTURAL)
├── Backend Team (ACCESS_GROUP) ← Users are members here
├── Frontend Team (ACCESS_GROUP) ← Users are members here
└── DevOps Team (ACCESS_GROUP) ← Users are members here
```

---

## Why Two Classifications?

### The Problem Without Classification

Without distinction, you face:

```python
# Is this an org unit or a team?
entity = Entity(name="Engineering")

# Can users be members? Should they be?
await add_member(entity, user, "developer")  # ???

# Does this make sense organizationally?
# Unclear!
```

**Issues**:
- ⚠️ Unclear where users should be members
- ⚠️ Organizational structure vs work groups confused
- ⚠️ Tree permissions applied incorrectly
- ⚠️ Can't distinguish org chart from team structure

### The Solution With Classification

With explicit classification:

```python
# Organization structure (STRUCTURAL)
engineering = Entity(
    name="Engineering",
    entity_class="structural",  # Clear: This is org structure
    entity_type="department"
)

# Work group (ACCESS_GROUP)
backend_team = Entity(
    name="Backend Team",
    entity_class="access_group",  # Clear: This is where users belong
    entity_type="team",
    parent_id=engineering.id
)

# Now it's clear
await add_member(engineering, user, "manager")  # ❌ Typically not done
await add_member(backend_team, user, "developer")  # ✅ This makes sense!
```

**Benefits**:
- ✅ Clear organizational intent
- ✅ Obvious where users should be members
- ✅ Correct tree permission application
- ✅ Clean separation of concerns

---

## Detailed Comparison

### Side-by-Side

| Aspect | STRUCTURAL | ACCESS_GROUP |
|--------|-----------|--------------|
| **Purpose** | Organizational hierarchy | Permission boundaries |
| **Memberships** | Rare (only managers) | Common (all team members) |
| **Tree Permissions** | Granted here | Inherited from ancestors |
| **Visual** | Folders/containers | Rooms/workspaces |
| **Examples** | Company, Dept, Division | Team, Project, Workspace |
| **In Org Chart** | Structure | Leaf nodes |
| **User Question** | "Where do I report?" | "What team am I on?" |

### Decision Tree

```
Is this entity...

A container for other entities?
├─ YES → Is it where users actually work?
│         ├─ YES → ACCESS_GROUP
│         └─ NO  → STRUCTURAL
└─ NO  → Does it represent organizational structure?
          ├─ YES → STRUCTURAL
          └─ NO  → ACCESS_GROUP
```

---

## Real-World Examples

### Example 1: Corporate Hierarchy

```python
"""
Traditional corporate structure
"""

# Company level (STRUCTURAL)
acme_corp = await create_entity(
    name="Acme Corporation",
    entity_class="structural",
    entity_type="company"
)

# Department level (STRUCTURAL)
engineering = await create_entity(
    name="Engineering",
    entity_class="structural",
    entity_type="department",
    parent_id=acme_corp.id
)

sales = await create_entity(
    name="Sales",
    entity_class="structural",
    entity_type="department",
    parent_id=acme_corp.id
)

# Team level (ACCESS_GROUP) - Where people work
backend_team = await create_entity(
    name="Backend Team",
    entity_class="access_group",
    entity_type="team",
    parent_id=engineering.id
)

frontend_team = await create_entity(
    name="Frontend Team",
    entity_class="access_group",
    entity_type="team",
    parent_id=engineering.id
)

# Add users to teams (ACCESS_GROUP)
await add_member(backend_team, john, "developer")
await add_member(backend_team, jane, "lead")
await add_member(frontend_team, alice, "developer")

# Add department manager (rare STRUCTURAL membership)
await add_member(engineering, bob, "department_head")
```

**Visualization**:
```
Acme Corporation [STRUCTURAL]
├── Engineering [STRUCTURAL]
│   ├── Bob (Department Head) ← Rare: membership in STRUCTURAL
│   ├── Backend Team [ACCESS_GROUP]
│   │   ├── John (Developer)
│   │   └── Jane (Lead)
│   └── Frontend Team [ACCESS_GROUP]
│       └── Alice (Developer)
└── Sales [STRUCTURAL]
```

### Example 2: Project-Based Organization

```python
"""
Project-centric structure
"""

# Workspace (STRUCTURAL)
workspace = await create_entity(
    name="Product Development",
    entity_class="structural",
    entity_type="workspace"
)

# Projects (ACCESS_GROUP) - Where work happens
project_alpha = await create_entity(
    name="Project Alpha",
    entity_class="access_group",
    entity_type="project",
    parent_id=workspace.id
)

project_beta = await create_entity(
    name="Project Beta",
    entity_class="access_group",
    entity_type="project",
    parent_id=workspace.id
)

# Sub-projects or epics (ACCESS_GROUP)
epic_1 = await create_entity(
    name="Epic 1: User Authentication",
    entity_class="access_group",
    entity_type="epic",
    parent_id=project_alpha.id
)

# Users belong to projects
await add_member(project_alpha, developer, "contributor")
await add_member(project_alpha, pm, "project_manager")
await add_member(epic_1, developer, "assignee")
```

### Example 3: Multi-Tenant SaaS

```python
"""
SaaS with multiple customer organizations
"""

# Platform root (STRUCTURAL)
platform = await create_entity(
    name="SaaS Platform",
    entity_class="structural",
    entity_type="platform"
)

# Customer organizations (STRUCTURAL)
customer_a = await create_entity(
    name="Customer A",
    entity_class="structural",
    entity_type="organization",
    parent_id=platform.id,
    metadata={"tenant_id": "tenant_a"}
)

customer_b = await create_entity(
    name="Customer B",
    entity_class="structural",
    entity_type="organization",
    parent_id=platform.id,
    metadata={"tenant_id": "tenant_b"}
)

# Customer A's structure
eng_a = await create_entity(
    name="Engineering",
    entity_class="structural",
    entity_type="department",
    parent_id=customer_a.id
)

team_a = await create_entity(
    name="Backend Team",
    entity_class="access_group",
    entity_type="team",
    parent_id=eng_a.id
)

# Customer A's users only see their org
await add_member(team_a, user_a, "developer")
```

### Example 4: Geographic Hierarchy

```python
"""
Location-based organization
"""

# Global company (STRUCTURAL)
global_corp = await create_entity(
    name="Global Corp",
    entity_class="structural",
    entity_type="company"
)

# Regions (STRUCTURAL)
north_america = await create_entity(
    name="North America",
    entity_class="structural",
    entity_type="region",
    parent_id=global_corp.id
)

# Offices (STRUCTURAL)
sf_office = await create_entity(
    name="San Francisco Office",
    entity_class="structural",
    entity_type="office",
    parent_id=north_america.id
)

# Teams in office (ACCESS_GROUP)
sf_engineering = await create_entity(
    name="SF Engineering Team",
    entity_class="access_group",
    entity_type="team",
    parent_id=sf_office.id
)

# Users belong to teams
await add_member(sf_engineering, developer, "developer")
```

---

## When to Use Each

### Use STRUCTURAL When

**✅ Building organizational hierarchy**:
```python
# Company → Department → Division
company = Entity(entity_class="structural", entity_type="company")
```

**✅ Creating geographic containers**:
```python
# Region → Country → Office
region = Entity(entity_class="structural", entity_type="region")
```

**✅ Defining business units**:
```python
# Business Unit → Product Line
business_unit = Entity(entity_class="structural", entity_type="business_unit")
```

**✅ Users won't have direct memberships** (except managers):
```python
# Department is structure, not a team
engineering_dept = Entity(entity_class="structural", entity_type="department")
# Only dept head is member, not all engineers
```

**✅ Tree permissions will be granted here**:
```python
# Grant read_tree at department level
await grant_permission(manager, engineering_dept, "project:read_tree")
# Manager can see all projects in department
```

### Use ACCESS_GROUP When

**✅ Creating teams where users work**:
```python
# Backend Team, Frontend Team
backend_team = Entity(entity_class="access_group", entity_type="team")
```

**✅ Defining projects**:
```python
# Project Alpha, Project Beta
project = Entity(entity_class="access_group", entity_type="project")
```

**✅ Users will have direct memberships**:
```python
# All team members are members
await add_member(backend_team, developer1, "developer")
await add_member(backend_team, developer2, "developer")
await add_member(backend_team, lead, "lead")
```

**✅ This is where permissions are checked**:
```python
# Check if user can update project
has_perm = await check_permission(
    user,
    "project:update",
    entity_id=project.id  # ACCESS_GROUP entity
)
```

**✅ Creating workspaces or folders**:
```python
# Shared Workspace, Private Folder
workspace = Entity(entity_class="access_group", entity_type="workspace")
```

---

## Common Patterns

### Pattern 1: STRUCTURAL Container + ACCESS_GROUP Children

**Most common pattern**:

```python
# STRUCTURAL: Organization container
engineering = await create_entity(
    name="Engineering",
    entity_class="structural",
    entity_type="department"
)

# ACCESS_GROUP: Actual teams
backend = await create_entity(
    name="Backend Team",
    entity_class="access_group",
    entity_type="team",
    parent_id=engineering.id
)

frontend = await create_entity(
    name="Frontend Team",
    entity_class="access_group",
    entity_type="team",
    parent_id=engineering.id
)
```

**Result**:
```
Engineering [STRUCTURAL] ← Organization structure
├── Backend Team [ACCESS_GROUP] ← Where people work
└── Frontend Team [ACCESS_GROUP] ← Where people work
```

### Pattern 2: Nested ACCESS_GROUPs

**Projects within projects**:

```python
# Parent project (ACCESS_GROUP)
project = await create_entity(
    name="Project Alpha",
    entity_class="access_group",
    entity_type="project"
)

# Sub-project (ACCESS_GROUP)
subproject = await create_entity(
    name="API Development",
    entity_class="access_group",
    entity_type="subproject",
    parent_id=project.id
)

# Both are ACCESS_GROUPs, both can have members
await add_member(project, pm, "project_manager")
await add_member(subproject, dev, "developer")
```

### Pattern 3: Pure STRUCTURAL Hierarchy

**Geographic structure (no teams yet)**:

```python
company = Entity(entity_class="structural", entity_type="company")
region = Entity(entity_class="structural", entity_type="region", parent=company)
country = Entity(entity_class="structural", entity_type="country", parent=region)
office = Entity(entity_class="structural", entity_type="office", parent=country)

# Later, add teams as ACCESS_GROUPs
team = Entity(entity_class="access_group", entity_type="team", parent=office)
```

### Pattern 4: Matrix Organization

**User in multiple ACCESS_GROUPs**:

```python
# Functional team
backend_team = Entity(entity_class="access_group", entity_type="team")

# Project team
project_alpha = Entity(entity_class="access_group", entity_type="project")

# User is member of both
await add_member(backend_team, developer, "developer")
await add_member(project_alpha, developer, "contributor")

# Developer has roles in both contexts
```

---

## Tree Permissions and Entity Class

### STRUCTURAL Entities: Where Tree Permissions Are Granted

```python
# Grant tree permission at STRUCTURAL level
engineering_dept = Entity(entity_class="structural", entity_type="department")

await grant_permission(
    manager.id,
    engineering_dept.id,
    "project:read_tree"
)

# Manager can now read ALL projects in:
# - Backend Team
# - Frontend Team
# - Any future team in Engineering
```

**Why at STRUCTURAL level**:
- ✅ Spans multiple teams/projects
- ✅ Organizational scope
- ✅ Manager/director access pattern

### ACCESS_GROUP Entities: Where Direct Permissions Apply

```python
# Direct permission at ACCESS_GROUP level
backend_team = Entity(entity_class="access_group", entity_type="team")

await add_member(backend_team, developer, "developer")

# Developer has permissions in this specific team
# Based on "developer" role
```

**Why at ACCESS_GROUP level**:
- ✅ Team-specific access
- ✅ Project-specific permissions
- ✅ Individual contributor pattern

---

## Design Considerations

### Should STRUCTURAL Entities Have Members?

**Generally NO**, but exceptions exist:

```python
# ❌ Usually DON'T do this
department = Entity(entity_class="structural", entity_type="department")
await add_member(department, engineer, "developer")
# Why not? Department is structure, not a team

# ✅ Exception: Leadership roles
await add_member(department, dept_head, "department_head")
# OK: Department head needs org-wide access

# ✅ Better: Put engineers in teams
backend_team = Entity(
    entity_class="access_group",
    entity_type="team",
    parent_id=department.id
)
await add_member(backend_team, engineer, "developer")
```

### Can ACCESS_GROUP Entities Have ACCESS_GROUP Children?

**YES**, this is valid:

```python
# Project (ACCESS_GROUP)
project = Entity(entity_class="access_group", entity_type="project")

# Sub-project (ACCESS_GROUP)
subproject = Entity(
    entity_class="access_group",
    entity_type="subproject",
    parent_id=project.id
)

# Epic (ACCESS_GROUP)
epic = Entity(
    entity_class="access_group",
    entity_type="epic",
    parent_id=subproject.id
)

# All valid! Users can be members at any level
```

**Use cases**:
- Project → Sub-project → Task
- Workspace → Folder → Document
- Repository → Branch → Pull Request

### Mixing STRUCTURAL and ACCESS_GROUP

**Can ACCESS_GROUP be child of STRUCTURAL?** ✅ **YES** (most common)

```python
department = Entity(entity_class="structural", entity_type="department")
team = Entity(
    entity_class="access_group",
    entity_type="team",
    parent_id=department.id
)
```

**Can STRUCTURAL be child of ACCESS_GROUP?** ⚠️ **Rare, but possible**

```python
# Unusual but valid
organization = Entity(entity_class="access_group", entity_type="organization")
department = Entity(
    entity_class="structural",
    entity_type="department",
    parent_id=organization.id
)
# Why? Maybe organization is a workspace with departments as structure
```

---

## Migration Patterns

### From Flat to Hierarchical

```python
# BEFORE: Flat teams
backend_team = Entity(entity_class="access_group", entity_type="team")
frontend_team = Entity(entity_class="access_group", entity_type="team")

# AFTER: Add STRUCTURAL hierarchy
engineering = Entity(entity_class="structural", entity_type="department")

# Move teams under department
await move_entity(backend_team.id, engineering.id)
await move_entity(frontend_team.id, engineering.id)

# Now have hierarchy:
# Engineering [STRUCTURAL]
# ├── Backend Team [ACCESS_GROUP]
# └── Frontend Team [ACCESS_GROUP]
```

### From Simple to Matrix

```python
# Add functional teams (STRUCTURAL containers)
functional_org = Entity(entity_class="structural", entity_type="functional_org")
backend_practice = Entity(
    entity_class="access_group",
    entity_type="practice",
    parent_id=functional_org.id
)

# Add project teams (STRUCTURAL containers)
projects_org = Entity(entity_class="structural", entity_type="projects_org")
project_alpha = Entity(
    entity_class="access_group",
    entity_type="project",
    parent_id=projects_org.id
)

# User in both
await add_member(backend_practice, developer, "developer")
await add_member(project_alpha, developer, "contributor")
```

---

## Best Practices

### 1. Make Intent Clear

```python
# ✅ GOOD: Clear entity_class
engineering = Entity(
    name="Engineering",
    entity_class="structural",  # Clear intent
    entity_type="department"
)

# ❌ BAD: Ambiguous
engineering = Entity(
    name="Engineering",
    # entity_class missing - what is this?
)
```

### 2. STRUCTURAL for Org Chart

```python
# ✅ GOOD: Matches org chart
company → departments → teams

# ❌ BAD: Flat structure when org is hierarchical
company
teams (all flat)
```

### 3. ACCESS_GROUP for Teams

```python
# ✅ GOOD: Users are members
team = Entity(entity_class="access_group", entity_type="team")
await add_member(team, user, "developer")

# ❌ BAD: Users as members of structure
department = Entity(entity_class="structural", entity_type="department")
await add_member(department, user, "developer")  # Wrong level!
```

### 4. Consistent Naming

```python
# ✅ GOOD: Consistent types
STRUCTURAL: "company", "department", "division"
ACCESS_GROUP: "team", "project", "workspace"

# ❌ BAD: Inconsistent
STRUCTURAL: "company", "team", "thing"
ACCESS_GROUP: "department", "group", "entity"
```

---

## Next Steps

- **[[52-Entity-Hierarchy|Entity Hierarchy]]** - Building complete org structures
- **[[53-Closure-Table|Closure Table]]** - How hierarchy is stored
- **[[54-Entity-Memberships|Entity Memberships]]** - User assignment patterns
- **[[50-Entity-System|Entity System]]** - Complete overview

---

**Previous**: [[50-Entity-System|← Entity System]]
**Next**: [[52-Entity-Hierarchy|Entity Hierarchy →]]
