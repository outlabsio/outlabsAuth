# EnterpriseRBAC Example - Project Management System

This example demonstrates hierarchical RBAC using OutlabsAuth's **EnterpriseRBAC** preset with entity hierarchy and tree permissions.

## Features

- ✅ Entity hierarchy (Company → Department → Team)
- ✅ Multiple roles per user in different entities
- ✅ Tree permissions (manage descendants)
- ✅ Entity-scoped permission checking
- ✅ Closure table for O(1) queries
- ✅ Complex organizational structures

## Entity Hierarchy

```
Acme Corporation (company)
├── Engineering Department (department)
│   ├── Backend Team (team)
│   └── Frontend Team (team)
└── Sales Department (department)
```

## Roles & Permissions

### CEO
- `*:*` - Full system access
- Assigned at company level

### Department Manager
- `entity:read` - Read entity info
- `entity:update` - Update entity info
- `entity:create_tree` - Create entities in subtree (all departments/teams below)
- `entity:update_tree` - Update entities in subtree
- `user:read` - Read user info
- `user:manage_tree` - Manage users in all descendant entities
- `project:*` - Full project management

### Team Lead
- `entity:read` - Read entity info
- `entity:update` - Update this entity
- `user:read` - Read user info
- `project:*` - Full project management in this team

### Developer
- `entity:read` - Read entity info
- `user:read` - Read user info
- `project:read` - Read projects
- `project:update` - Update projects

## Tree Permissions Explained

**Tree permissions apply to descendants only**, not the entity where assigned:

```python
# Department Manager at Engineering Department
role.permissions = [
    "entity:create_tree",  # Can create teams under Engineering
    "entity:update_tree",  # Can update Backend Team, Frontend Team
    "user:manage_tree",    # Can manage users in Backend/Frontend teams
]

# To also manage the Engineering Department itself:
role.permissions = [
    "entity:update",       # Update Engineering Department
    "entity:update_tree"   # Update teams below
]
```

## Installation

```bash
# Install OutlabsAuth (when published)
pip install outlabs-auth

# Or install from local development
cd ../..
pip install -e .

# Install additional dependencies
pip install fastapi uvicorn motor beanie
```

## Running the Example

```bash
# Make sure MongoDB is running
docker run -d -p 27017:27017 --name mongodb mongo:latest

# Run the application
python main.py

# Or use uvicorn directly
uvicorn main:app --reload --port 8001
```

The API will be available at `http://localhost:8001`

## API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8001/docs
- **ReDoc**: http://localhost:8001/redoc

## Example Usage

### 1. Register and Login

```bash
# Register
curl -X POST http://localhost:8001/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "alice@acme.com",
    "username": "alice",
    "password": "SecurePass123!",
    "full_name": "Alice Johnson"
  }'

# Save the access_token from response
TOKEN="your_access_token_here"
```

### 2. List Entities

```bash
curl -X GET http://localhost:8001/entities \
  -H "Authorization: Bearer $TOKEN"
```

Response shows the hierarchy:
```json
[
  {
    "id": "...",
    "name": "acme_corp",
    "display_name": "Acme Corporation",
    "entity_class": "structural",
    "entity_type": "company",
    "parent_id": null
  },
  {
    "id": "...",
    "name": "engineering",
    "display_name": "Engineering Department",
    "entity_class": "structural",
    "entity_type": "department",
    "parent_id": "..."  // Points to acme_corp
  }
]
```

### 3. Get Entity Hierarchy

```bash
# Get full hierarchy for Engineering Department
curl -X GET http://localhost:8001/entities/{engineering_id}/hierarchy \
  -H "Authorization: Bearer $TOKEN"
```

Response:
```json
{
  "path": [
    {"id": "...", "name": "Acme Corporation", "type": "company"},
    {"id": "...", "name": "Engineering Department", "type": "department"}
  ],
  "descendants": [
    {"id": "...", "name": "Backend Team", "type": "team"},
    {"id": "...", "name": "Frontend Team", "type": "team"}
  ]
}
```

### 4. Add Member to Entity

First, you need to become a manager. In a real scenario, an admin would assign this role.

```bash
# As a user with user:manage permission, add a member to Backend Team
curl -X POST http://localhost:8001/entities/{backend_team_id}/members \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "{user_id}",
    "role_ids": ["{developer_role_id}"]
  }'
```

### 5. Create a Project

```bash
# Create a project in Backend Team
curl -X POST http://localhost:8001/entities/{backend_team_id}/projects \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "API Redesign",
    "description": "Redesign the REST API",
    "budget": 50000,
    "deadline": "2025-12-31T00:00:00Z"
  }'
```

### 6. List Projects

```bash
curl -X GET http://localhost:8001/entities/{backend_team_id}/projects \
  -H "Authorization: Bearer $TOKEN"
```

## Permission Scenarios

### Scenario 1: Department Manager

A Department Manager at Engineering can:
- ✅ Read Engineering Department (`entity:read`)
- ✅ Update Engineering Department (`entity:update`)
- ✅ Create teams under Engineering (`entity:create_tree`)
- ✅ Update Backend Team and Frontend Team (`entity:update_tree`)
- ✅ Manage users in Backend and Frontend teams (`user:manage_tree`)
- ✅ Create projects in any team (`project:*`)
- ❌ Cannot manage Sales Department (different branch)

### Scenario 2: Team Lead

A Team Lead at Backend Team can:
- ✅ Read Backend Team (`entity:read`)
- ✅ Update Backend Team (`entity:update`)
- ✅ View team members (`user:read`)
- ✅ Create/update/delete projects in Backend Team (`project:*`)
- ❌ Cannot create new teams (no `entity:create_tree`)
- ❌ Cannot manage Frontend Team (sibling entity)
- ❌ Cannot manage Engineering Department (parent entity)

### Scenario 3: Developer

A Developer in Backend Team can:
- ✅ Read Backend Team info (`entity:read`)
- ✅ View team members (`user:read`)
- ✅ Read projects (`project:read`)
- ✅ Update projects (`project:update`)
- ❌ Cannot create projects (no `project:create`)
- ❌ Cannot delete projects (no `project:delete`)
- ❌ Cannot manage team settings or members

## Key Concepts Demonstrated

### 1. Entity Hierarchy with Closure Table

```python
# Create hierarchical entities
company = await auth.entity_service.create_entity(
    name="acme_corp",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="company",
)

dept = await auth.entity_service.create_entity(
    name="engineering",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="department",
    parent_id=str(company.id),  # Defines parent-child relationship
)

# Get path (O(1) via closure table)
path = await auth.entity_service.get_entity_path(dept.id)

# Get all descendants (O(1) via closure table)
descendants = await auth.entity_service.get_descendants(company.id)
```

### 2. Multiple Roles Per User

```python
# User can have different roles in different entities
await auth.membership_service.add_member(
    entity_id=engineering_dept_id,
    user_id=alice_id,
    role_ids=[dept_manager_role_id],  # Manager in Engineering
)

await auth.membership_service.add_member(
    entity_id=backend_team_id,
    user_id=alice_id,
    role_ids=[developer_role_id],  # Also a developer in Backend Team
)
```

### 3. Tree Permissions

```python
# Check if user can create entities in a subtree
has_perm = await auth.permission_service.check_permission(
    user_id=user_id,
    permission="entity:create_tree",
    entity_id=parent_entity_id,
)

# This checks if user has "entity:create_tree" in parent_entity_id
# OR in any ancestor of parent_entity_id
```

### 4. Entity-Scoped Permission Checks

```python
# Check permission in specific entity context
has_perm = await auth.permission_service.check_permission(
    user_id=user_id,
    permission="project:create",
    entity_id=team_id,
)

# Returns (bool, source) tuple
# source = "direct", "tree", or "all"
```

## Advanced Usage

### Create Access Groups

Access groups can span across structural hierarchy:

```python
# Create a cross-functional project group
project_alpha = await auth.entity_service.create_entity(
    name="project_alpha",
    entity_class=EntityClass.ACCESS_GROUP,  # Not structural
    entity_type="project_group",
    parent_id=str(company.id),
)

# Add members from different departments
await auth.membership_service.add_member(
    entity_id=project_alpha.id,
    user_id=backend_developer.id,
    role_ids=[developer_role.id],
)

await auth.membership_service.add_member(
    entity_id=project_alpha.id,
    user_id=frontend_developer.id,
    role_ids=[developer_role.id],
)
```

### Entity Context Header

For multi-entity users, specify context in requests:

```bash
curl -X GET http://localhost:8001/entities/{entity_id}/projects \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Entity-Context-Id: {backend_team_id}"
```

## Environment Variables

```bash
# MongoDB connection
MONGODB_URL=mongodb://localhost:27017

# Database name
DATABASE_NAME=project_mgmt_enterprise

# JWT secret key (change in production!)
SECRET_KEY=your-secret-key-change-in-production
```

## Testing Scenarios

### Test 1: Department Manager Creates Team

```bash
# As Engineering Manager, create a new team
curl -X POST http://localhost:8001/entities \
  -H "Authorization: Bearer $MANAGER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "devops_team",
    "display_name": "DevOps Team",
    "entity_class": "structural",
    "entity_type": "team",
    "parent_id": "{engineering_dept_id}",
    "description": "DevOps and infrastructure"
  }'

# ✅ Should succeed (has entity:create_tree in Engineering)
```

### Test 2: Team Lead Cannot Create Department

```bash
# As Backend Team Lead, try to create a department
curl -X POST http://localhost:8001/entities \
  -H "Authorization: Bearer $TEAMLEAD_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "hr_dept",
    "display_name": "HR Department",
    "entity_class": "structural",
    "entity_type": "department",
    "parent_id": "{company_id}"
  }'

# ❌ Should fail (403 - no permission to create at company level)
```

### Test 3: Cross-Department Access

```bash
# As Engineering Manager, try to access Sales Department
curl -X GET http://localhost:8001/entities/{sales_dept_id} \
  -H "Authorization: Bearer $ENG_MANAGER_TOKEN"

# ❌ Should fail (403 - no permission in Sales branch)
```

## Performance

With EnterpriseRBAC and closure table:

| Operation | Traditional Recursive | With Closure Table |
|-----------|----------------------|-------------------|
| Get entity path | 100ms (N queries) | 5ms (1 query) |
| Get descendants | 200ms (recursive) | 10ms (1 query) |
| Check tree permission | 50ms per ancestor | 5ms (1 query) |

## Production Considerations

1. **Index Optimization**: Ensure proper indexes on entity relationships
2. **Cache Entity Paths**: Cache frequently accessed paths
3. **Bulk Operations**: Use transactions for bulk membership changes
4. **Audit Logging**: Log entity and permission changes
5. **Soft Deletes**: Use soft deletes for entities (enabled by default)

## Next Steps

- Check out the **Full-Featured example** for ABAC conditions and Redis caching
- Read the [LIBRARY_ARCHITECTURE.md](../../docs/LIBRARY_ARCHITECTURE.md) for deep dive
- See [TREE_PERMISSIONS_GUIDE.md](../../docs/TREE_PERMISSIONS_GUIDE.md) for more on tree permissions

## License

MIT License - see LICENSE file for details
