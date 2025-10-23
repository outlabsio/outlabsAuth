# Entity System

**Tags**: #enterprise-rbac #entity-system #hierarchy #organizational-structure

Complete guide to OutlabsAuth's entity system for hierarchical authorization.

---

## What is the Entity System?

The **entity system** is the foundation of EnterpriseRBAC, providing hierarchical organizational structure for access control.

**Entity**: An organizational unit or access group in the hierarchy.

**Examples**:
- Company, Department, Team (organizational structure)
- Project, Workspace, Folder (resource hierarchy)
- Admin Group, Viewer Group (access groups)

---

## Why Use Entities?

### Without Entities (SimpleRBAC)

```python
# Flat structure
user.roles = ["editor", "moderator"]

# Problems:
# - Can't express "editor in Team A, viewer in Team B"
# - Can't grant "manager of entire department"
# - Can't organize by department/team
```

### With Entities (EnterpriseRBAC)

```python
# Hierarchical structure
Company
├── Engineering
│   ├── Backend Team
│   │   user: developer
│   └── Frontend Team
│       user: lead
└── Sales
    user: manager

# Benefits:
# ✅ User has different roles in different teams
# ✅ Manager can access entire department
# ✅ Clear organizational structure
```

---

## Entity Classification

Entities are classified into two types:

### 1. STRUCTURAL Entities

**Purpose**: Organizational hierarchy (org chart)

**Characteristics**:
- `entity_class = "structural"`
- Forms organizational tree
- Users typically don't have direct memberships
- Used for tree permissions

**Examples**:
- Company, Organization
- Department, Division
- Office, Location

```python
company = await auth.entity_service.create_entity(
    name="Acme Corp",
    entity_class="structural",
    entity_type="company"
)

engineering = await auth.entity_service.create_entity(
    name="Engineering",
    entity_class="structural",
    entity_type="department",
    parent_id=company.id
)
```

### 2. ACCESS_GROUP Entities

**Purpose**: Permission boundaries where work happens

**Characteristics**:
- `entity_class = "access_group"`
- Direct user memberships
- Where permissions are checked
- Leaf nodes in hierarchy

**Examples**:
- Team, Squad, Pod
- Project, Workspace
- Repository, Folder

```python
backend_team = await auth.entity_service.create_entity(
    name="Backend Team",
    entity_class="access_group",
    entity_type="team",
    parent_id=engineering.id
)

project_alpha = await auth.entity_service.create_entity(
    name="Project Alpha",
    entity_class="access_group",
    entity_type="project",
    parent_id=backend_team.id
)
```

---

## Entity Model

### Schema

```python
class EntityModel(Document):
    """Entity model with hierarchy support"""

    # Identity
    name: str                    # System name (lowercase_underscores)
    display_name: str            # User-friendly name
    slug: str                    # URL-friendly identifier (unique)
    description: Optional[str]   # Description

    # Classification
    entity_class: EntityClass    # STRUCTURAL or ACCESS_GROUP
    entity_type: str            # Flexible: "company", "team", "project"

    # Hierarchy
    parent_id: Optional[str]    # Parent entity ID

    # Lifecycle
    status: str = "active"       # active, inactive, archived
    valid_from: Optional[datetime]  # Valid from date
    valid_until: Optional[datetime] # Valid until date

    # Permissions (optional)
    direct_permissions: List[str] = []

    # Metadata
    metadata: Dict[str, Any] = {}

    # Configuration
    allowed_child_classes: List[EntityClass] = []
    allowed_child_types: List[str] = []
    max_members: Optional[int] = None
```

### Properties

```python
# Helper properties
entity.is_structural          # True if STRUCTURAL
entity.is_access_group        # True if ACCESS_GROUP
entity.is_active()           # Check if currently active
```

---

## Creating Entities

### Basic Creation

```python
# Create entity
entity = await auth.entity_service.create_entity(
    name="backend_team",
    display_name="Backend Team",
    entity_class="access_group",
    entity_type="team",
    parent_id=engineering_dept.id,
    description="Backend development team",
    metadata={
        "slack_channel": "#backend-team",
        "location": "San Francisco"
    }
)
```

### Hierarchy Creation

```python
# Build organizational hierarchy
company = await auth.entity_service.create_entity(
    name="acme_corp",
    display_name="Acme Corp",
    entity_class="structural",
    entity_type="company"
)

engineering = await auth.entity_service.create_entity(
    name="engineering",
    display_name="Engineering",
    entity_class="structural",
    entity_type="department",
    parent_id=company.id
)

backend_team = await auth.entity_service.create_entity(
    name="backend_team",
    display_name="Backend Team",
    entity_class="access_group",
    entity_type="team",
    parent_id=engineering.id
)

project_alpha = await auth.entity_service.create_entity(
    name="project_alpha",
    display_name="Project Alpha",
    entity_class="access_group",
    entity_type="project",
    parent_id=backend_team.id
)
```

**Result**:
```
Company (Acme Corp)
└── Engineering
    └── Backend Team
        └── Project Alpha
```

### Auto-generated Fields

```python
# Slug is auto-generated from name
entity = await create_entity(
    name="Backend Team",
    # slug will be "backend-team"
)

# Or provide custom slug
entity = await create_entity(
    name="Backend Team",
    slug="backend"  # Custom slug
)
```

---

## Entity Operations

### Get Entity

```python
# By ID
entity = await auth.entity_service.get_entity(entity_id)

# By slug
entity = await auth.entity_service.get_entity_by_slug("backend-team")

# By name
entities = await auth.entity_service.find_entities(name="backend_team")
```

### Update Entity

```python
await auth.entity_service.update_entity(
    entity_id=entity.id,
    display_name="Backend Engineering Team",
    description="Updated description",
    metadata={
        "slack_channel": "#backend-eng",
        "location": "San Francisco"
    }
)
```

### Delete Entity

```python
# Delete entity and all memberships
await auth.entity_service.delete_entity(entity_id)

# Entity closure entries are also deleted
```

### List Entities

```python
# List all entities
entities = await auth.entity_service.list_entities()

# Filter by type
teams = await auth.entity_service.list_entities(entity_type="team")

# Filter by class
access_groups = await auth.entity_service.list_entities(
    entity_class="access_group"
)

# Filter by parent
children = await auth.entity_service.list_entities(parent_id=engineering.id)
```

---

## Entity Hierarchy Operations

### Get Parent

```python
parent = await auth.entity_service.get_parent(entity_id)
```

### Get Children

```python
# Get direct children only
children = await auth.entity_service.get_children(parent_id)

# Example: Engineering → [Backend Team, Frontend Team]
```

### Get Ancestors

```python
# Get all ancestors (parents, grandparents, etc.)
ancestors = await auth.entity_service.get_ancestors(entity_id)

# Returns list ordered by distance (nearest first)
# Example: Project Alpha → [Backend Team, Engineering, Company]
```

### Get Descendants

```python
# Get all descendants (children, grandchildren, etc.)
descendants = await auth.entity_service.get_descendants(entity_id)

# Example: Engineering → [Backend Team, Frontend Team, Project Alpha, Project Beta, ...]
```

### Get Root Entities

```python
# Get all root entities (no parent)
roots = await auth.entity_service.get_root_entities()

# Typically returns top-level companies/organizations
```

### Get Entity Path

```python
# Get path from root to entity
path = await auth.entity_service.get_entity_path(entity_id)

# Returns: [Company, Engineering, Backend Team, Project Alpha]
```

### Get Depth

```python
# Get entity depth in hierarchy (root = 0)
depth = await auth.entity_service.get_entity_depth(entity_id)

# Example: Project Alpha at depth 3
```

---

## Entity Memberships

### Add Member

```python
# Add user to entity with role
await auth.entity_service.add_member(
    entity_id=backend_team.id,
    user_id=user.id,
    role_name="developer"
)

# User is now "developer" in Backend Team
```

### Remove Member

```python
# Remove user from entity
await auth.entity_service.remove_member(
    entity_id=backend_team.id,
    user_id=user.id
)
```

### Update Member Role

```python
# Change user's role in entity
await auth.entity_service.update_member_role(
    entity_id=backend_team.id,
    user_id=user.id,
    new_role_name="lead"
)
```

### Get Entity Members

```python
# Get all members of entity
memberships = await auth.entity_service.get_entity_members(
    entity_id=backend_team.id
)

for membership in memberships:
    print(f"{membership.user_id}: {membership.role_name}")
```

### Get User Memberships

```python
# Get all entities user belongs to
memberships = await auth.entity_service.get_user_memberships(
    user_id=user.id
)

for membership in memberships:
    entity = await auth.entity_service.get_entity(membership.entity_id)
    print(f"{entity.display_name}: {membership.role_name}")
```

### Check Membership

```python
# Check if user is member of entity
is_member = await auth.entity_service.is_member(
    entity_id=backend_team.id,
    user_id=user.id
)
```

---

## Moving Entities

### Move to New Parent

```python
# Move Backend Team from Engineering to Platform
await auth.entity_service.move_entity(
    entity_id=backend_team.id,
    new_parent_id=platform_dept.id
)

# Closure table is automatically updated!
# All descendants maintain their relationships
```

### Move to Root

```python
# Move entity to become a root (no parent)
await auth.entity_service.move_entity(
    entity_id=entity.id,
    new_parent_id=None
)
```

---

## Entity Validation

### Prevent Cycles

```python
# Validation prevents creating cycles
try:
    # Try to make company a child of its own descendant
    await auth.entity_service.move_entity(
        entity_id=company.id,
        new_parent_id=backend_team.id  # backend_team is descendant of company!
    )
except CycleError:
    print("Cannot create cycle in hierarchy")
```

### Max Depth

```python
# Configure max depth
auth = EnterpriseRBAC(
    database=db,
    max_entity_depth=10  # Prevent hierarchies deeper than 10 levels
)

# Throws error if depth exceeded
```

### Allowed Child Types

```python
# Configure allowed child types
company = await auth.entity_service.create_entity(
    name="Acme Corp",
    entity_class="structural",
    entity_type="company",
    allowed_child_types=["department", "division"]  # Only these allowed
)

# Throws error if invalid child type
await auth.entity_service.create_entity(
    name="Team",
    entity_type="team",  # Not in allowed types!
    parent_id=company.id
)
# → Error: "team" not allowed as child of "company"
```

---

## Common Hierarchy Patterns

### Pattern 1: Corporate Hierarchy

```
Company
├── Engineering Department
│   ├── Backend Team
│   │   └── API Project
│   └── Frontend Team
│       └── UI Project
├── Sales Department
│   ├── Enterprise Team
│   └── SMB Team
└── Operations Department
    └── Support Team
```

```python
company = await create_entity("Company", "structural", "company")

engineering = await create_entity("Engineering", "structural", "department", company.id)
backend = await create_entity("Backend Team", "access_group", "team", engineering.id)
api_project = await create_entity("API Project", "access_group", "project", backend.id)

sales = await create_entity("Sales", "structural", "department", company.id)
enterprise = await create_entity("Enterprise Team", "access_group", "team", sales.id)
```

### Pattern 2: Multi-tenant SaaS

```
Platform (root)
├── Customer A (Organization)
│   ├── Engineering
│   │   └── Backend Team
│   └── Sales
│       └── Sales Team
└── Customer B (Organization)
    ├── Product
    │   └── Product Team
    └── Marketing
        └── Marketing Team
```

```python
platform = await create_entity("Platform", "structural", "platform")

customer_a = await create_entity("Customer A", "structural", "organization", platform.id)
eng_a = await create_entity("Engineering", "structural", "department", customer_a.id)
backend_a = await create_entity("Backend Team", "access_group", "team", eng_a.id)

customer_b = await create_entity("Customer B", "structural", "organization", platform.id)
```

### Pattern 3: Project Hierarchy

```
Workspace
├── Project Alpha
│   ├── Epic 1
│   │   ├── Story 1
│   │   └── Story 2
│   └── Epic 2
└── Project Beta
    └── Epic 3
```

```python
workspace = await create_entity("Workspace", "structural", "workspace")
project_alpha = await create_entity("Project Alpha", "access_group", "project", workspace.id)
epic_1 = await create_entity("Epic 1", "access_group", "epic", project_alpha.id)
story_1 = await create_entity("Story 1", "access_group", "story", epic_1.id)
```

### Pattern 4: File System

```
Documents
├── Engineering
│   ├── Backend
│   │   ├── Design Docs
│   │   └── API Specs
│   └── Frontend
│       └── UI Mockups
└── Sales
    └── Proposals
```

```python
docs = await create_entity("Documents", "structural", "root_folder")
engineering_folder = await create_entity("Engineering", "structural", "folder", docs.id)
backend_folder = await create_entity("Backend", "access_group", "folder", engineering_folder.id)
```

---

## Entity Metadata

### Using Metadata

```python
# Store custom data
entity = await auth.entity_service.create_entity(
    name="Backend Team",
    entity_class="access_group",
    entity_type="team",
    metadata={
        "slack_channel": "#backend-team",
        "location": "San Francisco",
        "cost_center": "ENG-001",
        "manager_email": "manager@acme.com",
        "team_size": 12,
        "budget": 1500000,
        "tech_stack": ["Python", "FastAPI", "MongoDB"],
        "on_call_rotation": ["user_1", "user_2", "user_3"]
    }
)

# Query metadata
slack_channel = entity.metadata.get("slack_channel")
team_size = entity.metadata.get("team_size", 0)
```

### Update Metadata

```python
# Update metadata
await auth.entity_service.update_entity(
    entity_id=entity.id,
    metadata={
        **entity.metadata,
        "team_size": 15,  # Update
        "new_field": "value"  # Add
    }
)
```

---

## Entity Lifecycle

### Status Management

```python
# Create entity
entity = await auth.entity_service.create_entity(
    name="Project",
    entity_class="access_group",
    entity_type="project",
    status="active"
)

# Deactivate entity
await auth.entity_service.update_entity(
    entity_id=entity.id,
    status="inactive"
)

# Archive entity
await auth.entity_service.update_entity(
    entity_id=entity.id,
    status="archived"
)

# Check if active
if entity.is_active():
    # Entity is active
    pass
```

### Time-based Validity

```python
from datetime import datetime, timedelta

# Create entity with validity period
entity = await auth.entity_service.create_entity(
    name="Temporary Project",
    entity_class="access_group",
    entity_type="project",
    valid_from=datetime.utcnow(),
    valid_until=datetime.utcnow() + timedelta(days=90)
)

# Entity automatically inactive after 90 days
```

---

## Performance Considerations

### Closure Table

**All ancestor/descendant queries use closure table** for O(1) performance:

```python
# Fast (single query)
ancestors = await auth.entity_service.get_ancestors(entity_id)

# Fast (single query)
descendants = await auth.entity_service.get_descendants(entity_id)
```

See [[53-Closure-Table|Closure Table]] for details.

### Caching

**Enable Redis caching** for 10x-100x performance:

```python
auth = EnterpriseRBAC(
    database=db,
    enable_caching=True,
    redis_url="redis://localhost:6379"
)

# Cached:
# - Entity lookups
# - Ancestor/descendant lists
# - Entity paths
# - Membership queries
```

### Indexing

**Ensure proper indexes**:

```python
# Automatic indexes on:
# - entity.slug (unique)
# - entity.name
# - entity.parent_id
# - entity.entity_type
# - entity.entity_class
```

---

## Best Practices

### 1. Use Meaningful Entity Types

```python
# ✅ GOOD: Clear entity types
"company", "department", "team", "project"

# ❌ BAD: Generic types
"entity1", "group", "thing"
```

### 2. Structural vs Access Group

```python
# ✅ GOOD: Structural for org chart
engineering = await create_entity(
    "Engineering",
    "structural",
    "department"
)

# ✅ GOOD: Access group for permission boundary
team = await create_entity(
    "Backend Team",
    "access_group",
    "team",
    parent=engineering
)

# ❌ BAD: Access group for org structure
department = await create_entity(
    "Engineering",
    "access_group",  # Should be structural!
    "department"
)
```

### 3. Limit Hierarchy Depth

```python
# ✅ GOOD: Reasonable depth (5-7 levels)
Company → Department → Team → Project → Task

# ❌ BAD: Too deep (10+ levels)
Company → Division → SubDivision → Department → ...
```

### 4. Use Metadata for Flexibility

```python
# ✅ GOOD: Store custom data in metadata
entity.metadata = {
    "slack_channel": "#team",
    "cost_center": "ENG-001"
}

# ❌ BAD: Create custom model fields
# (Loses flexibility)
```

---

## Next Steps

- **[[51-Entity-Types|Entity Types]]** - STRUCTURAL vs ACCESS_GROUP deep dive
- **[[52-Entity-Hierarchy|Entity Hierarchy]]** - Building org structures
- **[[53-Closure-Table|Closure Table]]** - Performance optimization
- **[[54-Entity-Memberships|Entity Memberships]]** - User assignment

---

**Previous**: [[44-Tree-Permissions|← Tree Permissions]]
**Next**: [[51-Entity-Types|Entity Types →]]
