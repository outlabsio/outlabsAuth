# EnterpriseRBAC - Hierarchical Role-Based Access Control

**Tags**: #authorization #enterprise-rbac #hierarchy #tree-permissions #advanced

Complete guide to using EnterpriseRBAC for hierarchical role-based access control with entity hierarchy and tree permissions.

---

## What is EnterpriseRBAC?

EnterpriseRBAC is a **hierarchical role-based access control** system for applications with organizational structures (companies, departments, teams, projects).

**Use When**:
- ✅ Hierarchical organization (company → departments → teams)
- ✅ Need tree permissions (grant access to entire subtrees)
- ✅ Context-aware roles (different permissions per entity type)
- ✅ Complex authorization requirements
- ✅ Multi-tenant SaaS applications

**Don't Use When**:
- ❌ Flat organizational structure
- ❌ Simple role-based permissions
- ❌ Want simplest possible API

**For simpler use cases**, use [[41-SimpleRBAC|SimpleRBAC]] instead.

---

## Architecture

```
┌───────────────────────────────────────────────────────────┐
│                   Entity Hierarchy                         │
│                                                            │
│              Acme Corp (company)                          │
│                     │                                      │
│          ┌──────────┴──────────┐                          │
│          ▼                     ▼                          │
│    Engineering            Sales                           │
│    (department)          (department)                     │
│          │                     │                          │
│     ┌────┴────┐           ┌────┴────┐                    │
│     ▼         ▼           ▼         ▼                    │
│  Backend  Frontend    Enterprise SMB                      │
│  Team     Team        Sales      Sales                    │
│  (team)   (team)      (team)     (team)                  │
│     │         │           │         │                     │
│     ▼         ▼           ▼         ▼                     │
│  Project  Project    Deal      Deal                       │
│  Alpha    Beta       X         Y                          │
│                                                            │
└───────────────────────────────────────────────────────────┘
                            │
                            │
┌───────────────────────────────────────────────────────────┐
│                 Entity Memberships                         │
│                                                            │
│  User "john@acme.com" is:                                 │
│  • "developer" in Backend Team                            │
│  • "lead" in Project Alpha                                │
│                                                            │
│  User "jane@acme.com" is:                                 │
│  • "manager" in Engineering Dept                          │
│                                                            │
└───────────────────────────────────────────────────────────┘
                            │
                            │
┌───────────────────────────────────────────────────────────┐
│                    Roles & Permissions                     │
│                                                            │
│  "developer" role:                                        │
│  • project:read, project:update                           │
│  • code:read, code:write                                  │
│                                                            │
│  "manager" role (context-aware):                          │
│  • In department: report:read_tree, budget:manage        │
│  • In team: task:assign, pr:approve                       │
│  • In project: settings:update, member:manage             │
│                                                            │
└───────────────────────────────────────────────────────────┘
                            │
                            │
┌───────────────────────────────────────────────────────────┐
│                  Tree Permissions                          │
│                                                            │
│  Grant "project:read_tree" at Engineering Dept            │
│  → User can read ALL projects in:                         │
│    • Backend Team (Project Alpha)                         │
│    • Frontend Team (Project Beta)                         │
│                                                            │
│  Entire subtree access with one permission!               │
│                                                            │
└───────────────────────────────────────────────────────────┘
```

**Flow**: Entity Hierarchy → Memberships → Roles → Permissions (context-aware + tree)

---

## Quick Start

### Step 1: Install

```bash
pip install outlabs-auth
```

### Step 2: Initialize

```python
from fastapi import FastAPI, Depends
from motor.motor_asyncio import AsyncIOMotorClient
from outlabs_auth import EnterpriseRBAC

# FastAPI app
app = FastAPI(title="Enterprise App")

# MongoDB connection
mongo_client = AsyncIOMotorClient("mongodb://localhost:27017")
db = mongo_client["enterprise_app"]

# Initialize EnterpriseRBAC
auth = EnterpriseRBAC(
    database=db,
    enable_context_aware_roles=True,  # Optional: roles adapt by entity type
    enable_abac=True,  # Optional: attribute-based access control
    enable_caching=True,  # Optional: Redis caching
    redis_url="redis://localhost:6379"  # If caching enabled
)

# Initialize database on startup
@app.on_event("startup")
async def startup():
    await auth.initialize()
```

### Step 3: Create Entity Hierarchy

```python
# Create root entity (company)
company = await auth.entity_service.create_entity(
    name="Acme Corp",
    entity_type="company",
    is_structural=True  # STRUCTURAL (organizational container)
)

# Create departments
engineering = await auth.entity_service.create_entity(
    name="Engineering",
    entity_type="department",
    parent_id=company.id,
    is_structural=True
)

sales = await auth.entity_service.create_entity(
    name="Sales",
    entity_type="department",
    parent_id=company.id,
    is_structural=True
)

# Create teams (access groups)
backend_team = await auth.entity_service.create_entity(
    name="Backend Team",
    entity_type="team",
    parent_id=engineering.id,
    is_structural=False  # ACCESS_GROUP (permission boundary)
)

frontend_team = await auth.entity_service.create_entity(
    name="Frontend Team",
    entity_type="team",
    parent_id=engineering.id,
    is_structural=False
)

# Create projects
project_alpha = await auth.entity_service.create_entity(
    name="Project Alpha",
    entity_type="project",
    parent_id=backend_team.id,
    is_structural=False
)
```

### Step 4: Create Context-Aware Roles

```python
# Developer role (simple)
await auth.role_service.create_role(
    name="developer",
    permissions=[
        "project:read",
        "project:update",
        "code:read",
        "code:write",
    ]
)

# Manager role (context-aware)
await auth.role_service.create_role(
    name="manager",
    context_permissions={
        "department": [
            "report:read_tree",  # Tree permission!
            "budget:manage",
            "member:invite",
        ],
        "team": [
            "task:assign",
            "pr:approve",
            "member:manage",
        ],
        "project": [
            "settings:update",
            "member:manage",
            "project:archive",
        ]
    }
)
```

### Step 5: Add Users to Entities

```python
# Register user
user = await auth.user_service.create_user(
    email="john@acme.com",
    password="SecurePassword123!",
    is_verified=True
)

# Add to backend team as developer
await auth.entity_service.add_member(
    entity_id=backend_team.id,
    user_id=user.id,
    role_name="developer"
)

# Add to project alpha as lead
await auth.entity_service.add_member(
    entity_id=project_alpha.id,
    user_id=user.id,
    role_name="lead"
)
```

### Step 6: Grant Tree Permissions

```python
# Manager needs access to ALL projects in Engineering
manager_user = await auth.user_service.get_by_email("jane@acme.com")

# Grant tree permission at Engineering level
await auth.permission_service.grant_permission(
    user_id=manager_user.id,
    entity_id=engineering.id,
    permission="project:read_tree"
)

# Jane can now read:
# - Project Alpha (in Backend Team)
# - Project Beta (in Frontend Team)
# - Any future projects added to Engineering!
```

### Step 7: Protect Routes with Entity Context

```python
# Check permission in specific entity
@app.get("/projects/{project_id}")
async def get_project(
    project_id: str,
    ctx = Depends(auth.deps.require_permission(
        "project:read",
        entity_id_param="project_id"  # Extract entity_id from route param
    ))
):
    project = await get_project_from_db(project_id)
    return project

# Tree permission: Access entire subtree
@app.get("/departments/{dept_id}/all-projects")
async def get_all_dept_projects(
    dept_id: str,
    ctx = Depends(auth.deps.require_permission(
        "project:read_tree",
        entity_id=dept_id
    ))
):
    # User can see ALL projects under this department!
    projects = await get_department_projects(dept_id)
    return projects

# Context-aware role permissions
@app.post("/teams/{team_id}/assign-task")
async def assign_task(
    team_id: str,
    task_data: dict,
    ctx = Depends(auth.deps.require_permission(
        "task:assign",
        entity_id=team_id
    ))
):
    # Manager's "task:assign" permission only works in team context
    return await assign_task_to_member(team_id, task_data)
```

---

## Entity System

### Entity Types

Two categories of entities:

#### 1. STRUCTURAL Entities (Organizational Containers)

**Purpose**: Organizational structure, not direct permission boundaries.

**Characteristics**:
- `is_structural=True`
- Users typically don't have direct memberships
- Used for tree permissions (grant at parent, access children)
- Examples: Company, Department, Division

**Example**:
```python
# Company (STRUCTURAL)
company = await auth.entity_service.create_entity(
    name="Acme Corp",
    entity_type="company",
    is_structural=True
)

# Department (STRUCTURAL)
engineering = await auth.entity_service.create_entity(
    name="Engineering",
    entity_type="department",
    parent_id=company.id,
    is_structural=True
)
```

#### 2. ACCESS_GROUP Entities (Permission Boundaries)

**Purpose**: Direct permission boundaries where users are members.

**Characteristics**:
- `is_structural=False`
- Users have direct memberships with roles
- Actual work happens here
- Examples: Team, Project, Workspace

**Example**:
```python
# Team (ACCESS_GROUP)
backend_team = await auth.entity_service.create_entity(
    name="Backend Team",
    entity_type="team",
    parent_id=engineering.id,
    is_structural=False
)

# Project (ACCESS_GROUP)
project = await auth.entity_service.create_entity(
    name="Project Alpha",
    entity_type="project",
    parent_id=backend_team.id,
    is_structural=False
)
```

### Entity Hierarchy Operations

#### Create Entity

```python
entity = await auth.entity_service.create_entity(
    name="Backend Team",
    entity_type="team",
    parent_id=engineering.id,
    is_structural=False,
    metadata={"slack_channel": "#backend-team"}  # Optional
)
```

#### Get Entity

```python
entity = await auth.entity_service.get_entity(entity_id)
print(entity.name)  # "Backend Team"
print(entity.entity_type)  # "team"
print(entity.parent_id)  # engineering.id
```

#### Update Entity

```python
await auth.entity_service.update_entity(
    entity_id=entity.id,
    name="Backend Engineering Team",
    metadata={"slack_channel": "#backend-eng"}
)
```

#### Delete Entity

```python
# Deletes entity and all memberships
await auth.entity_service.delete_entity(entity_id)
```

#### Get Children

```python
# Get direct children
children = await auth.entity_service.get_children(parent_id=engineering.id)
# Returns: [backend_team, frontend_team]
```

#### Get Descendants (Entire Subtree)

```python
# Get ALL descendants (children, grandchildren, etc.)
descendants = await auth.entity_service.get_descendants(
    entity_id=engineering.id
)
# Returns: [backend_team, frontend_team, project_alpha, project_beta, ...]
```

#### Get Ancestors

```python
# Get all ancestors (parent, grandparent, etc.)
ancestors = await auth.entity_service.get_ancestors(
    entity_id=project_alpha.id
)
# Returns: [backend_team, engineering, company]
```

#### Move Entity

```python
# Move Backend Team from Engineering to Different Dept
await auth.entity_service.move_entity(
    entity_id=backend_team.id,
    new_parent_id=platform_dept.id
)
# Closure table automatically updated!
```

### Entity Memberships

#### Add Member

```python
# Add user to entity with role
await auth.entity_service.add_member(
    entity_id=backend_team.id,
    user_id=user.id,
    role_name="developer"
)
```

#### Remove Member

```python
await auth.entity_service.remove_member(
    entity_id=backend_team.id,
    user_id=user.id
)
```

#### Update Member Role

```python
# Change role
await auth.entity_service.update_member_role(
    entity_id=backend_team.id,
    user_id=user.id,
    new_role_name="lead"
)
```

#### Get Entity Members

```python
# Get all members of an entity
members = await auth.entity_service.get_entity_members(
    entity_id=backend_team.id
)

for membership in members:
    print(f"{membership.user_id}: {membership.role_name}")
```

#### Get User Memberships

```python
# Get all entities a user belongs to
memberships = await auth.entity_service.get_user_memberships(
    user_id=user.id
)

for membership in memberships:
    entity = await auth.entity_service.get_entity(membership.entity_id)
    print(f"{entity.name}: {membership.role_name}")
```

---

## Tree Permissions

Tree permissions allow granting access to **entire subtrees** of the entity hierarchy.

### Permission Naming

**Tree Permission Suffix**: `_tree`

**Examples**:
- `project:read_tree` - Read this project AND all child projects
- `report:read_tree` - Read this report AND all child reports
- `file:manage_tree` - Full access to this folder AND all subfolders

**Regular vs Tree**:
```python
# Regular permission: Access ONLY this entity
"project:read" → Can read Project Alpha

# Tree permission: Access this entity AND all descendants
"project:read_tree" → Can read:
  - Project Alpha
  - All sub-projects under Alpha
  - All tasks under Alpha
  - Etc.
```

### Granting Tree Permissions

```python
# Grant at Engineering dept level
await auth.permission_service.grant_permission(
    user_id=manager.id,
    entity_id=engineering.id,
    permission="project:read_tree"
)

# Manager can now read ALL projects in:
# - Backend Team (Project Alpha, Project Gamma)
# - Frontend Team (Project Beta, Project Delta)
# - Any future projects added to Engineering!
```

### Checking Tree Permissions

```python
# Check if user has tree permission
has_access = await auth.permission_service.check_tree_permission(
    user_id=manager.id,
    entity_id=project_alpha.id,
    permission="project:read_tree"
)
# Returns: True (manager has tree permission at Engineering level)
```

### How It Works (Performance)

**Closure Table** (DD-036) for O(1) ancestor queries:

```python
# Traditional recursive query (SLOW - O(n))
def get_ancestors_recursive(entity_id):
    ancestors = []
    current = entity_id
    while current:
        parent = get_parent(current)
        if parent:
            ancestors.append(parent)
        current = parent
    return ancestors

# Closure table query (FAST - O(1))
def get_ancestors_closure(entity_id):
    return db.query("""
        SELECT ancestor_id
        FROM entity_closure
        WHERE descendant_id = ?
    """, entity_id)
```

**Performance**:
- Without closure table: ~50-200ms (depends on tree depth)
- With closure table: ~5-10ms (single index lookup)
- **~20x improvement!**

### Tree Permission Use Cases

#### Use Case 1: Manager Access

```python
# Engineering Manager needs access to all team projects
await auth.permission_service.grant_permission(
    user_id=engineering_manager.id,
    entity_id=engineering_dept.id,
    permission="project:read_tree"
)

# Can now access:
# - All Backend Team projects
# - All Frontend Team projects
# - All future Engineering projects
```

#### Use Case 2: Auditor Access

```python
# Auditor needs view access to entire company
await auth.permission_service.grant_permission(
    user_id=auditor.id,
    entity_id=company_root.id,
    permission="document:read_tree"
)

# Can now read ALL documents in:
# - Engineering
# - Sales
# - Operations
# - Every department, team, project
```

#### Use Case 3: Project Archival

```python
# Archive entire project and all sub-tasks
@app.post("/projects/{project_id}/archive")
async def archive_project(
    project_id: str,
    ctx = Depends(auth.deps.require_permission(
        "project:manage_tree",
        entity_id=project_id
    ))
):
    # User has full tree access, can archive everything
    await archive_project_and_children(project_id)
    return {"status": "archived"}
```

---

## Context-Aware Roles

Context-aware roles have **different permissions depending on entity type**.

### Why Context-Aware Roles?

**Problem**: "Manager" means different things in different contexts:
- Manager of **Department**: Manages budget, reports
- Manager of **Team**: Assigns tasks, approves PRs
- Manager of **Project**: Updates settings, manages members

**Solution**: One "manager" role with context-specific permissions.

### Creating Context-Aware Roles

```python
await auth.role_service.create_role(
    name="manager",
    permissions=[
        # Base permissions (work everywhere)
        "member:invite",
        "member:remove",
    ],
    context_permissions={
        # Additional permissions in department context
        "department": [
            "report:read_tree",
            "budget:manage",
            "headcount:plan",
        ],
        # Additional permissions in team context
        "team": [
            "task:assign",
            "pr:approve",
            "sprint:plan",
        ],
        # Additional permissions in project context
        "project": [
            "settings:update",
            "milestone:create",
            "release:deploy",
        ]
    }
)
```

### How It Works

```python
# User is "manager" in Engineering Dept
await auth.entity_service.add_member(
    entity_id=engineering_dept.id,
    user_id=manager.id,
    role_name="manager"
)

# In department context, manager has:
# - Base permissions: member:invite, member:remove
# - Department context: report:read_tree, budget:manage, headcount:plan
# Total: 5 permissions

# User is also "manager" in Backend Team
await auth.entity_service.add_member(
    entity_id=backend_team.id,
    user_id=manager.id,
    role_name="manager"
)

# In team context, manager has:
# - Base permissions: member:invite, member:remove
# - Team context: task:assign, pr:approve, sprint:plan
# Total: 5 permissions (different set!)
```

### Checking Context-Aware Permissions

```python
# Check permission in specific entity context
has_permission = await auth.permission_service.check_permission(
    user_id=manager.id,
    permission="task:assign",
    entity_id=backend_team.id  # Team context
)
# Returns: True (manager has task:assign in team context)

has_permission = await auth.permission_service.check_permission(
    user_id=manager.id,
    permission="task:assign",
    entity_id=engineering_dept.id  # Department context
)
# Returns: False (task:assign not available in department context)
```

---

## Complete Example: Project Management System

Here's a complete project management system with EnterpriseRBAC:

```python
# main.py
from fastapi import FastAPI, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
from outlabs_auth import EnterpriseRBAC
from outlabs_auth.routers import get_auth_router, get_users_router
from pydantic import BaseModel
from typing import List
from datetime import datetime

app = FastAPI(title="Project Management API")

# MongoDB
mongo_client = AsyncIOMotorClient("mongodb://localhost:27017")
db = mongo_client["project_mgmt"]

# Auth with all features
auth = EnterpriseRBAC(
    database=db,
    enable_context_aware_roles=True,
    enable_abac=True,
    enable_caching=True,
    redis_url="redis://localhost:6379"
)

# Task schema
class Task(BaseModel):
    id: str
    title: str
    description: str
    project_id: str
    assignee_id: str
    status: str
    created_at: datetime

# Initialize
@app.on_event("startup")
async def startup():
    await auth.initialize()

    # Create entity hierarchy
    try:
        # Company
        company = await auth.entity_service.create_entity(
            name="TechCorp",
            entity_type="company",
            is_structural=True
        )

        # Engineering department
        engineering = await auth.entity_service.create_entity(
            name="Engineering",
            entity_type="department",
            parent_id=company.id,
            is_structural=True
        )

        # Backend team
        backend = await auth.entity_service.create_entity(
            name="Backend Team",
            entity_type="team",
            parent_id=engineering.id,
            is_structural=False
        )

        # Projects
        api_project = await auth.entity_service.create_entity(
            name="API v2",
            entity_type="project",
            parent_id=backend.id,
            is_structural=False
        )

        # Create roles
        await auth.role_service.create_role(
            name="developer",
            permissions=["task:read", "task:update", "code:write"]
        )

        await auth.role_service.create_role(
            name="lead",
            permissions=["task:read", "task:create", "task:assign", "task:delete"]
        )

        await auth.role_service.create_role(
            name="manager",
            context_permissions={
                "department": ["report:read_tree", "budget:manage"],
                "team": ["task:assign", "member:manage"],
                "project": ["settings:update", "milestone:create"]
            }
        )

    except Exception as e:
        print(f"Setup already complete or error: {e}")

# Auth routes
app.include_router(get_auth_router(auth), prefix="/auth", tags=["auth"])
app.include_router(get_users_router(auth), prefix="/users", tags=["users"])

# Project routes
@app.get("/projects/{project_id}/tasks")
async def list_tasks(
    project_id: str,
    ctx = Depends(auth.deps.require_permission(
        "task:read",
        entity_id_param="project_id"
    ))
):
    """List tasks in project (requires task:read in project)"""
    tasks_collection = db["tasks"]
    tasks = await tasks_collection.find({"project_id": project_id}).to_list(100)
    return tasks

@app.post("/projects/{project_id}/tasks")
async def create_task(
    project_id: str,
    title: str,
    description: str,
    ctx = Depends(auth.deps.require_permission(
        "task:create",
        entity_id_param="project_id"
    ))
):
    """Create task (requires task:create in project - lead or manager)"""
    user = ctx.metadata.get("user")
    tasks_collection = db["tasks"]

    task = {
        "title": title,
        "description": description,
        "project_id": project_id,
        "assignee_id": None,
        "status": "todo",
        "created_by": user.id,
        "created_at": datetime.utcnow()
    }

    result = await tasks_collection.insert_one(task)
    task["_id"] = str(result.inserted_id)
    return task

@app.post("/projects/{project_id}/tasks/{task_id}/assign")
async def assign_task(
    project_id: str,
    task_id: str,
    assignee_id: str,
    ctx = Depends(auth.deps.require_permission(
        "task:assign",
        entity_id_param="project_id"
    ))
):
    """Assign task (requires task:assign in project - lead or manager in team context)"""
    tasks_collection = db["tasks"]

    # Verify assignee is member of project
    project = await auth.entity_service.get_entity(project_id)
    memberships = await auth.entity_service.get_user_memberships(assignee_id)

    is_member = any(m.entity_id == project_id for m in memberships)
    if not is_member:
        raise HTTPException(400, "Assignee must be project member")

    await tasks_collection.update_one(
        {"_id": task_id, "project_id": project_id},
        {"$set": {"assignee_id": assignee_id, "status": "assigned"}}
    )

    return {"status": "assigned"}

@app.patch("/projects/{project_id}/tasks/{task_id}")
async def update_task(
    project_id: str,
    task_id: str,
    status: str = None,
    description: str = None,
    ctx = Depends(auth.deps.require_permission(
        "task:update",
        entity_id_param="project_id"
    ))
):
    """Update task (requires task:update in project - developers and above)"""
    user = ctx.metadata.get("user")
    tasks_collection = db["tasks"]

    task = await tasks_collection.find_one({"_id": task_id})
    if not task:
        raise HTTPException(404, "Task not found")

    # Only assignee or lead can update
    is_assignee = task.get("assignee_id") == user.id
    has_lead_role = await auth.permission_service.check_permission(
        user.id,
        "task:assign",
        entity_id=project_id
    )

    if not (is_assignee or has_lead_role):
        raise HTTPException(403, "Can only update your own tasks")

    update_data = {}
    if status:
        update_data["status"] = status
    if description:
        update_data["description"] = description

    await tasks_collection.update_one(
        {"_id": task_id},
        {"$set": update_data}
    )

    return {"status": "updated"}

# Department-level reports (tree permissions)
@app.get("/departments/{dept_id}/report")
async def department_report(
    dept_id: str,
    ctx = Depends(auth.deps.require_permission(
        "report:read_tree",
        entity_id=dept_id
    ))
):
    """Get department report (requires report:read_tree - manager in department)"""

    # Get all projects in department (tree query!)
    descendants = await auth.entity_service.get_descendants(dept_id)
    project_ids = [d.id for d in descendants if d.entity_type == "project"]

    # Get all tasks across all projects
    tasks_collection = db["tasks"]
    all_tasks = await tasks_collection.find({
        "project_id": {"$in": project_ids}
    }).to_list(1000)

    # Aggregate stats
    total_tasks = len(all_tasks)
    completed = len([t for t in all_tasks if t["status"] == "done"])
    in_progress = len([t for t in all_tasks if t["status"] == "in_progress"])

    return {
        "department_id": dept_id,
        "total_projects": len(project_ids),
        "total_tasks": total_tasks,
        "completed_tasks": completed,
        "in_progress_tasks": in_progress,
        "completion_rate": completed / total_tasks if total_tasks > 0 else 0
    }

# Admin routes
@app.post("/entities/{entity_id}/members")
async def add_member(
    entity_id: str,
    user_id: str,
    role_name: str,
    ctx = Depends(auth.deps.require_permission(
        "member:manage",
        entity_id=entity_id
    ))
):
    """Add member to entity (requires member:manage in entity)"""
    await auth.entity_service.add_member(entity_id, user_id, role_name)
    return {"status": "member added"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## Advanced Features

### ABAC Policies (Attribute-Based Access Control)

Add conditional permissions based on attributes:

```python
# Create policy: Allow if owner OR manager
policy = {
    "name": "Allow task update if owner or manager",
    "resource": "task:update",
    "condition": {
        "or": [
            # User is task owner
            {"user.id": {"eq": "resource.assignee_id"}},
            # OR user is manager
            {"user.role": {"in": ["manager", "lead"]}}
        ]
    }
}

await auth.permission_service.create_abac_policy(policy)

# Now check with resource context
has_permission = await auth.permission_service.check_permission_with_context(
    user_id=user.id,
    permission="task:update",
    entity_id=project_id,
    resource={"assignee_id": "user_123"}
)
```

See [[46-ABAC-Policies|ABAC Policies Guide]] for details.

### Redis Caching

Enable Redis for massive performance improvements:

```python
auth = EnterpriseRBAC(
    database=db,
    enable_caching=True,
    redis_url="redis://localhost:6379"
)
```

**What's Cached**:
- Permission checks (95%+ hit rate)
- Role lookups (98%+ hit rate)
- Entity hierarchies (90%+ hit rate)
- Tree permission ancestors

**Performance**:
- Without Redis: ~20-50ms per tree permission check
- With Redis: ~1-5ms per tree permission check (cache hit)
- **10x-20x improvement!**

**Cache Invalidation**:
- Automatic via Redis Pub/Sub (DD-037)
- <100ms propagation across instances

See [[120-Redis-Integration|Redis Integration]] for details.

### Lifecycle Hooks

Override service methods for custom logic:

```python
from outlabs_auth.services import EntityService

class MyEntityService(EntityService):
    async def on_after_create_entity(self, entity, request=None):
        # Auto-create default roles
        if entity.entity_type == "project":
            await self.add_default_project_roles(entity.id)

        # Notify Slack
        await slack.send_message(
            f"New {entity.entity_type} created: {entity.name}"
        )

    async def on_after_add_member(self, membership, request=None):
        # Send welcome email
        user = await self.user_service.get_user(membership.user_id)
        entity = await self.get_entity(membership.entity_id)

        await email_service.send(
            to=user.email,
            subject=f"Welcome to {entity.name}!",
            body=f"You've been added as {membership.role_name}"
        )

# Use custom service
auth = EnterpriseRBAC(
    database=db,
    entity_service_class=MyEntityService
)
```

See [[130-Hooks-Overview|Lifecycle Hooks]] for full list.

---

## Performance: Closure Table

The closure table pattern (DD-036) is key to EnterpriseRBAC performance.

### What is a Closure Table?

Pre-computed table of ALL ancestor/descendant relationships:

```python
# entity_closure collection
{
    "ancestor_id": "engineering_dept",
    "descendant_id": "project_alpha",
    "depth": 2
}
{
    "ancestor_id": "backend_team",
    "descendant_id": "project_alpha",
    "depth": 1
}
{
    "ancestor_id": "project_alpha",
    "descendant_id": "project_alpha",
    "depth": 0  # Self-reference
}
```

### Why It's Fast

**Without Closure Table** (Recursive Query):
```sql
-- Get all ancestors of project_alpha
WITH RECURSIVE ancestors AS (
    SELECT id, parent_id FROM entities WHERE id = 'project_alpha'
    UNION ALL
    SELECT e.id, e.parent_id FROM entities e
    INNER JOIN ancestors a ON e.id = a.parent_id
)
SELECT * FROM ancestors;
```
- **Complexity**: O(n) where n = tree depth
- **Queries**: 1 query per level (could be 5-10 queries)
- **Time**: ~50-200ms

**With Closure Table**:
```sql
-- Get all ancestors of project_alpha
SELECT ancestor_id FROM entity_closure WHERE descendant_id = 'project_alpha';
```
- **Complexity**: O(1)
- **Queries**: 1 query total
- **Time**: ~5-10ms

**Result**: ~20x improvement!

### Trade-offs

**Benefits**:
- ✅ 20x faster queries
- ✅ O(1) complexity
- ✅ Simple queries (no recursion)

**Costs**:
- ⚠️ Additional storage (~N² entries for N entities in worst case)
- ⚠️ More writes when hierarchy changes
- ⚠️ Closure table maintenance

**Verdict**: Worth it for EnterpriseRBAC! Hierarchy changes are rare compared to permission checks.

---

## Migration from SimpleRBAC

Upgrading from SimpleRBAC to EnterpriseRBAC is straightforward:

```python
# Before (SimpleRBAC)
from outlabs_auth import SimpleRBAC
auth = SimpleRBAC(database=db)

# After (EnterpriseRBAC)
from outlabs_auth import EnterpriseRBAC
auth = EnterpriseRBAC(database=db)
```

**What Changes**:
- ✅ All existing users, roles, permissions stay the same
- ✅ All existing routes continue to work
- ✅ Can now create entity hierarchy
- ✅ Can now use tree permissions
- ✅ Can now use context-aware roles

**No breaking changes!**

**Next Steps After Migration**:
1. Create entity hierarchy
2. Migrate user role assignments to entity memberships
3. Add tree permissions where needed
4. Optionally add context-aware role permissions

---

## API Reference

### EnterpriseRBAC Class

```python
class EnterpriseRBAC:
    def __init__(
        self,
        database: AsyncIOMotorDatabase,
        jwt_secret: str = None,
        jwt_algorithm: str = "HS256",
        enable_context_aware_roles: bool = True,
        enable_abac: bool = False,
        enable_caching: bool = False,
        redis_url: str = None,
        entity_service_class: Type[EntityService] = EntityService,
        **kwargs
    )
```

### Services

- `auth.user_service` - [[70-User-Service|UserService]]
- `auth.role_service` - [[71-Role-Service|RoleService]]
- `auth.permission_service` - [[72-Permission-Service|PermissionService]]
- `auth.entity_service` - [[75-Entity-Service|EntityService]] (EnterpriseRBAC only)
- `auth.api_key_service` - [[73-API-Key-Service|ApiKeyService]]
- `auth.auth_service` - [[74-Auth-Service|AuthService]]

### Dependencies

- `auth.deps.require_auth()` - [[81-Require-Auth|require_auth()]]
- `auth.deps.require_permission()` - [[82-Require-Permission|require_permission()]]
- `auth.deps.require_role()` - [[83-Require-Role|require_role()]]

---

## Next Steps

- **[[50-Entity-System|Entity System]]** - Deep dive into entities
- **[[44-Tree-Permissions|Tree Permissions]]** - Hierarchical access patterns
- **[[45-Context-Aware-Roles|Context-Aware Roles]]** - Role adaptation
- **[[151-Tutorial-Enterprise-App|Tutorial]]** - Build complete enterprise app

---

**Previous**: [[41-SimpleRBAC|← SimpleRBAC]]
**Next**: [[43-Permissions-System|Permissions System →]]
