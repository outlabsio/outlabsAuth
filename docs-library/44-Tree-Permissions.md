# Tree Permissions

**Tags**: #authorization #tree-permissions #hierarchical-access #enterprise-rbac

Complete guide to tree permissions in OutlabsAuth's EnterpriseRBAC.

---

## What are Tree Permissions?

**Tree permissions** grant access to an entire subtree of the entity hierarchy with a single permission.

**Format**: `resource:action_tree`

**Example**:
```
Company
├── Engineering
│   ├── Backend Team
│   │   └── Project Alpha
│   └── Frontend Team
│       └── Project Beta
```

Grant `project:read_tree` at Engineering → Access to **all projects** (Alpha + Beta + future projects)

---

## Why Tree Permissions?

### The Problem

Without tree permissions:

```python
# Grant access to every project individually
await grant_permission(user, project_alpha, "project:read")
await grant_permission(user, project_beta, "project:read")
await grant_permission(user, project_gamma, "project:read")
# ... repeat for every project
# ... new project? Must grant again!
```

**Issues**:
- ⚠️ Must grant permission on every resource
- ⚠️ New resources require new grants
- ⚠️ Hard to manage at scale
- ⚠️ Impossible to revoke efficiently

### The Solution

With tree permissions:

```python
# Grant once at parent level
await grant_permission(user, engineering_dept, "project:read_tree")

# User now has access to:
# - Project Alpha (in Backend Team)
# - Project Beta (in Frontend Team)
# - Project Gamma (when created later)
# - All future projects in Engineering!
```

**Benefits**:
- ✅ Single permission grant
- ✅ Automatic access to new resources
- ✅ Easy to manage
- ✅ Efficient revocation

---

## Permission Format

### Naming Convention

Add `_tree` suffix to action:

```python
# Regular permission: Single resource
"project:read"       # Read this project only

# Tree permission: Resource + descendants
"project:read_tree"  # Read this project AND all children
```

### Common Tree Permissions

```python
# Read access
"project:read_tree"     # View project + sub-projects
"folder:read_tree"      # View folder + subfolders
"report:read_tree"      # View report + sub-reports

# Management access
"project:manage_tree"   # Manage project + sub-projects
"folder:manage_tree"    # Manage folder + subfolders

# Custom actions
"document:approve_tree" # Approve document + sub-documents
"task:assign_tree"      # Assign task + sub-tasks
```

---

## How Tree Permissions Work

### Permission Resolution Algorithm

```
1. User requests access to resource (e.g., Project Alpha)
2. Get resource's entity_id
3. Get all ancestors of this entity (using closure table)
4. For each ancestor:
   a. Check if user has tree permission in that ancestor
   b. If yes, grant access
5. If no tree permission found, check direct permission
6. Return allow/deny
```

### Example Flow

```
Company
├── Engineering (depth: 1 from company)
│   ├── Backend Team (depth: 2 from company, 1 from engineering)
│   │   └── Project Alpha (depth: 3 from company, 2 from engineering, 1 from backend)
```

**Scenario**: User requests access to Project Alpha

```python
# User has project:read_tree at Engineering level

# Step 1: Get Project Alpha's ancestors
ancestors = await get_ancestors("project_alpha")
# Returns: [backend_team, engineering, company]

# Step 2: Check tree permissions in ancestors
for ancestor in ancestors:
    has_tree_perm = check_permission(
        user,
        "project:read_tree",
        ancestor.id
    )
    if has_tree_perm:
        return True  # Access granted!

# Step 3: Check direct permission in Project Alpha
has_direct_perm = check_permission(
    user,
    "project:read",
    "project_alpha"
)
return has_direct_perm
```

**Result**: ✅ Access granted (tree permission found at Engineering)

---

## Closure Table Pattern (DD-036)

### The Performance Problem

**Naive approach** (recursive queries):

```python
# BAD: N queries for depth N
async def get_ancestors(entity_id: str) -> List[Entity]:
    ancestors = []
    current = await Entity.get(entity_id)

    while current.parent_id:
        current = await Entity.get(current.parent_id)  # Database query!
        ancestors.append(current)

    return ancestors

# At depth 10: 10 sequential database queries per permission check!
```

**Problems**:
- ⚠️ O(N) database queries (N = depth)
- ⚠️ Sequential queries (high latency)
- ⚠️ Doesn't scale with deep hierarchies

### The Solution: Closure Table

**Pre-compute all ancestor-descendant relationships**:

```python
class EntityClosureModel(Document):
    """Stores all ancestor-descendant relationships."""
    ancestor_id: str      # Ancestor entity ID
    descendant_id: str    # Descendant entity ID
    depth: int           # Distance (0 = self, 1 = direct child, etc.)

    class Settings:
        indexes = [
            ("ancestor_id", "descendant_id"),  # Unique
            ("descendant_id", "depth"),        # Find ancestors
            ("ancestor_id", "depth")           # Find descendants
        ]
```

**Example data**:

For hierarchy: `Company → Engineering → Backend Team → Project Alpha`

```python
# Closure table entries:
[
    # Project Alpha relationships
    {"ancestor": "project_alpha", "descendant": "project_alpha", "depth": 0},  # Self
    {"ancestor": "backend_team", "descendant": "project_alpha", "depth": 1},
    {"ancestor": "engineering", "descendant": "project_alpha", "depth": 2},
    {"ancestor": "company", "descendant": "project_alpha", "depth": 3},

    # Backend Team relationships
    {"ancestor": "backend_team", "descendant": "backend_team", "depth": 0},  # Self
    {"ancestor": "engineering", "descendant": "backend_team", "depth": 1},
    {"ancestor": "company", "descendant": "backend_team", "depth": 2},

    # Engineering relationships
    {"ancestor": "engineering", "descendant": "engineering", "depth": 0},  # Self
    {"ancestor": "company", "descendant": "engineering", "depth": 1},

    # Company relationships
    {"ancestor": "company", "descendant": "company", "depth": 0},  # Self
]
```

**Optimized query** (single query):

```python
# GOOD: O(1) single query
async def get_ancestors(entity_id: str) -> List[str]:
    closures = await EntityClosureModel.find({
        "descendant_id": entity_id,
        "depth": {"$gt": 0}  # Exclude self
    }).sort("depth", 1).to_list()

    return [c.ancestor_id for c in closures]

# At any depth: 1 database query!
```

### Performance Comparison

| Hierarchy Depth | Recursive Queries | Closure Table | Improvement |
|----------------|------------------|---------------|-------------|
| 3 levels | 3 queries (~15ms) | 1 query (~1ms) | **15x** |
| 5 levels | 5 queries (~25ms) | 1 query (~1ms) | **25x** |
| 10 levels | 10 queries (~50ms) | 1 query (~1ms) | **50x** |

**Average improvement**: ~20x faster

### Closure Table Maintenance

#### On Entity Creation

```python
async def create_entity(name: str, parent_id: str = None):
    # Create entity
    entity = Entity(name=name, parent_id=parent_id)
    await entity.save()

    # Add self-reference
    await EntityClosure(
        ancestor_id=entity.id,
        descendant_id=entity.id,
        depth=0
    ).save()

    if parent_id:
        # Copy all of parent's ancestors
        parent_closures = await EntityClosure.find({
            "descendant_id": parent_id
        }).to_list()

        for closure in parent_closures:
            await EntityClosure(
                ancestor_id=closure.ancestor_id,
                descendant_id=entity.id,
                depth=closure.depth + 1
            ).save()

    return entity
```

#### On Entity Move

```python
async def move_entity(entity_id: str, new_parent_id: str):
    # Get all descendants
    descendants = await EntityClosure.find({
        "ancestor_id": entity_id
    }).to_list()

    # Remove old ancestor relationships (except self)
    await EntityClosure.delete_many({
        "descendant_id": {"$in": [d.descendant_id for d in descendants]},
        "depth": {"$gt": 0}
    })

    # Add new ancestor relationships
    new_parent_closures = await EntityClosure.find({
        "descendant_id": new_parent_id
    }).to_list()

    for descendant in descendants:
        for parent_closure in new_parent_closures:
            await EntityClosure(
                ancestor_id=parent_closure.ancestor_id,
                descendant_id=descendant.descendant_id,
                depth=parent_closure.depth + descendant.depth + 1
            ).save()
```

#### On Entity Deletion

```python
async def delete_entity(entity_id: str):
    # Delete entity
    await Entity.get(entity_id).delete()

    # Delete all closure entries
    await EntityClosure.delete_many({
        "$or": [
            {"ancestor_id": entity_id},
            {"descendant_id": entity_id}
        ]
    })
```

---

## Granting Tree Permissions

### Programmatic Grant

```python
# Grant tree permission at department level
await auth.permission_service.grant_tree_permission(
    user_id=manager.id,
    entity_id=engineering_dept.id,
    permission="project:read_tree"
)

# Manager can now read all projects in Engineering
```

### Via Role Assignment

```python
# Create role with tree permissions
await auth.role_service.create_role(
    name="department_manager",
    permissions=[
        "project:read_tree",
        "report:read_tree",
        "team:manage"
    ]
)

# Assign role at department level
await auth.entity_service.add_member(
    entity_id=engineering_dept.id,
    user_id=manager.id,
    role_name="department_manager"
)

# Manager has tree permissions in entire department
```

### Via Context-Aware Roles

```python
# Create context-aware role
await auth.role_service.create_role(
    name="manager",
    context_permissions={
        "department": [
            "project:read_tree",
            "report:read_tree",
            "budget:manage"
        ],
        "team": [
            "task:assign",
            "pr:approve"
        ]
    }
)

# Assign as manager in department
await auth.entity_service.add_member(
    entity_id=engineering_dept.id,
    user_id=manager.id,
    role_name="manager"
)

# In department context, manager gets tree permissions
```

---

## Checking Tree Permissions

### In Routes

```python
# Check tree permission in route
@app.get("/departments/{dept_id}/all-projects")
async def get_all_dept_projects(
    dept_id: str,
    ctx = Depends(auth.deps.require_permission(
        "project:read_tree",
        entity_id=dept_id
    ))
):
    # User has tree permission, can access all projects
    descendants = await auth.entity_service.get_descendants(dept_id)
    project_ids = [d.id for d in descendants if d.entity_type == "project"]

    projects = await get_projects(project_ids)
    return projects
```

### Programmatically

```python
# Check if user has tree permission for specific resource
has_tree_access = await auth.permission_service.check_tree_permission(
    user_id=user.id,
    entity_id=project_alpha.id,
    permission="project:read_tree"
)

if has_tree_access:
    # User has tree permission at some ancestor
    return await get_project(project_alpha.id)
else:
    raise HTTPException(403, "Access denied")
```

---

## Use Cases

### Use Case 1: Manager Access to All Team Projects

```python
"""
Manager needs access to all projects in their team,
including future projects.
"""

# Hierarchy
company = await create_entity("Company")
engineering = await create_entity("Engineering", parent=company)
backend_team = await create_entity("Backend Team", parent=engineering)
project_alpha = await create_entity("Project Alpha", parent=backend_team)

# Grant tree permission at team level
await grant_tree_permission(
    manager.id,
    backend_team.id,
    "project:read_tree"
)

# Manager can now:
# ✅ Read Project Alpha
# ✅ Read any new project added to Backend Team
# ✅ Without additional grants!
```

### Use Case 2: Department Head Reports

```python
"""
Department head needs reports from all teams and projects
in their department.
"""

# Grant at department level
await grant_tree_permission(
    dept_head.id,
    engineering_dept.id,
    "report:read_tree"
)

# Department head can:
# ✅ Read reports from Backend Team
# ✅ Read reports from Frontend Team
# ✅ Read reports from all projects
# ✅ Access new team reports automatically
```

### Use Case 3: Auditor Access

```python
"""
Auditor needs read-only access to entire organization.
"""

# Grant at company root
await grant_tree_permission(
    auditor.id,
    company_root.id,
    "document:read_tree"
)

# Auditor can:
# ✅ Read all documents in every department
# ✅ Read all documents in every team
# ✅ Read all documents in every project
# ✅ Read new documents automatically
```

### Use Case 4: Project Archival

```python
"""
Archive entire project and all sub-tasks.
"""

@app.post("/projects/{project_id}/archive")
async def archive_project(
    project_id: str,
    ctx = Depends(auth.deps.require_permission(
        "project:manage_tree",
        entity_id_param="project_id"
    ))
):
    # User has manage_tree permission
    # Can archive project and all descendants

    descendants = await auth.entity_service.get_descendants(project_id)

    for entity in [project_id] + descendants:
        await archive_entity(entity.id)

    return {"status": "archived", "count": len(descendants) + 1}
```

### Use Case 5: Folder Permissions

```python
"""
Grant access to folder and all subfolders.
"""

# File hierarchy
root_folder = await create_entity("Documents", type="folder")
engineering_folder = await create_entity("Engineering", parent=root_folder)
backend_folder = await create_entity("Backend", parent=engineering_folder)

# Grant tree permission
await grant_tree_permission(
    user.id,
    engineering_folder.id,
    "file:read_tree"
)

# User can:
# ✅ Read all files in Engineering folder
# ✅ Read all files in Backend folder
# ✅ Read all files in any new subfolder
```

---

## Tree Permission vs Direct Permission

### Comparison

| Aspect | Direct Permission | Tree Permission |
|--------|------------------|-----------------|
| **Scope** | Single resource | Resource + descendants |
| **Format** | `resource:action` | `resource:action_tree` |
| **Grant location** | On resource itself | On ancestor |
| **New resources** | Must grant again | Automatic access |
| **Use case** | Specific access | Hierarchical access |
| **Performance** | O(1) check | O(1) check (with closure table) |

### When to Use Each

**Use Direct Permission when**:
- ✅ Access to specific resource only
- ✅ Fine-grained control needed
- ✅ Resource not in hierarchy

**Use Tree Permission when**:
- ✅ Access to resource and children
- ✅ Manager/admin access patterns
- ✅ Automatic access to new resources
- ✅ Hierarchical organization

### Combining Both

```python
# Grant tree permission at department
await grant_tree_permission(
    manager.id,
    engineering.id,
    "project:read_tree"
)

# But explicitly deny specific project
await deny_permission(
    manager.id,
    secret_project.id,
    "project:read"
)

# Manager can:
# ✅ Read all projects in Engineering
# ❌ Except secret_project (explicit deny)
```

---

## Caching Tree Permissions

### Redis Caching

**Cache ancestor lookups** for performance:

```python
import redis.asyncio as redis

class EntityService:
    def __init__(self, database, redis_url: str = None):
        self.database = database
        self.redis = redis.from_url(redis_url) if redis_url else None

    async def get_ancestors(self, entity_id: str) -> List[str]:
        if self.redis:
            # Check cache
            cache_key = f"entity_ancestors:{entity_id}"
            cached = await self.redis.get(cache_key)

            if cached:
                return json.loads(cached)

        # Query closure table
        closures = await EntityClosure.find({
            "descendant_id": entity_id,
            "depth": {"$gt": 0}
        }).to_list()

        ancestor_ids = [c.ancestor_id for c in closures]

        if self.redis:
            # Cache for 15 minutes
            await self.redis.setex(
                cache_key,
                900,
                json.dumps(ancestor_ids)
            )

        return ancestor_ids
```

### Cache Invalidation

```python
# Invalidate on hierarchy changes
async def move_entity(entity_id: str, new_parent_id: str):
    # Move entity
    await _move_entity_logic(entity_id, new_parent_id)

    # Invalidate caches
    if self.redis:
        # Invalidate moved entity
        await self.redis.delete(f"entity_ancestors:{entity_id}")

        # Invalidate all descendants
        descendants = await self.get_descendants(entity_id)
        for desc in descendants:
            await self.redis.delete(f"entity_ancestors:{desc.id}")

        # Publish cache invalidation via Pub/Sub (DD-037)
        await self.redis.publish("entity_hierarchy_changed", entity_id)
```

---

## Best Practices

### 1. Use Tree Permissions for Hierarchies

```python
# ✅ GOOD: Tree permission for hierarchy
await grant_tree_permission(manager, department, "project:read_tree")

# ❌ BAD: Individual grants
for project in projects:
    await grant_permission(manager, project, "project:read")
```

### 2. Grant at Appropriate Level

```python
# ✅ GOOD: Grant at team level for team-wide access
await grant_tree_permission(manager, team, "task:read_tree")

# ❌ BAD: Grant at company level (too broad)
await grant_tree_permission(manager, company, "task:read_tree")
```

### 3. Use Context-Aware Roles

```python
# ✅ GOOD: Manager role with tree permissions in department context
await create_role(
    "manager",
    context_permissions={
        "department": ["project:read_tree", "report:read_tree"]
    }
)
```

### 4. Monitor Permission Scope

```python
# Track tree permission usage
async def audit_tree_permissions():
    users_with_tree_perms = await get_users_with_tree_permissions()

    for user in users_with_tree_perms:
        scope_size = await calculate_scope_size(user)

        if scope_size > 1000:  # Alert on large scope
            await alert(f"User {user.id} has tree access to {scope_size} resources")
```

---

## Next Steps

- **[[50-Entity-System|Entity System]]** - Understanding entity hierarchy
- **[[53-Closure-Table|Closure Table]]** - Deep dive into performance
- **[[45-Context-Aware-Roles|Context-Aware Roles]]** - Role adaptation
- **[[42-EnterpriseRBAC|EnterpriseRBAC]]** - Complete guide

---

**Previous**: [[43-Permissions-System|← Permissions System]]
**Next**: [[45-Context-Aware-Roles|Context-Aware Roles →]]
