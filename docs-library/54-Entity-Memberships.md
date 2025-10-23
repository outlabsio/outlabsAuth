# Entity Memberships

**Tags**: #enterprise #memberships #users #roles #assignment

User assignment patterns and membership management in entity hierarchies.

---

## Overview

Entity memberships connect users to entities with assigned roles. This is how users gain access to specific parts of your organizational hierarchy and acquire context-specific permissions.

**Prerequisites**: [[50-Entity-System|Entity System]], [[51-Entity-Types|Entity Types]], [[52-Entity-Hierarchy|Entity Hierarchy]]

**Key Concepts**:
- Memberships link Users → Entities → Roles
- Users can belong to multiple entities
- Each membership can have multiple roles
- Memberships support time-based validity
- Permissions are derived from membership roles

---

## Membership Basics

### The Membership Model

```python
class EntityMembershipModel(BaseDocument):
    """User's membership in an entity with assigned roles"""

    # Relationships
    user: Link[UserModel]           # The user
    entity: Link[EntityModel]       # The entity
    roles: List[Link[RoleModel]]    # Multiple roles

    # Metadata
    joined_at: datetime             # When user joined
    joined_by: Optional[Link[UserModel]]  # Who added them

    # Time-based validity (optional)
    valid_from: Optional[datetime]  # Start date
    valid_until: Optional[datetime] # End date

    # Status
    is_active: bool                 # Active or deactivated
```

### How Memberships Work

```
User "alice"
  └─ Member of "Backend Team" entity
      └─ With roles: ["developer", "team_lead"]
          └─ Gets permissions from both roles
```

**Key Points**:
- One membership = One user in one entity
- Each membership can have **multiple roles**
- Roles determine what the user can do in that entity
- Users can have memberships in many entities

---

## Adding Members

### Basic Member Addition

```python
# Add user to entity with a single role
membership = await auth.membership_service.add_member(
    entity_id=str(team.id),
    user_id=str(user.id),
    role_ids=[str(developer_role.id)]
)

print(f"User {user.email} added to {team.display_name}")
```

### Multiple Roles Per Member

```python
# Add user with multiple roles
membership = await auth.membership_service.add_member(
    entity_id=str(team.id),
    user_id=str(user.id),
    role_ids=[
        str(developer_role.id),
        str(team_lead_role.id),
        str(reviewer_role.id)
    ]
)

# User now has permissions from all three roles in this entity
```

**Use Case**: Senior team member who is both a developer and a team lead.

### Time-Based Memberships

```python
from datetime import datetime, timedelta

# Add contractor with expiration date
membership = await auth.membership_service.add_member(
    entity_id=str(project.id),
    user_id=str(contractor.id),
    role_ids=[str(contractor_role.id)],
    valid_from=datetime.utcnow(),
    valid_until=datetime.utcnow() + timedelta(days=90)  # 90-day contract
)

# After 90 days, membership.is_currently_valid() returns False
```

**Use Cases**:
- Contractors with fixed-term contracts
- Temporary project assignments
- Internships with defined duration
- Access that starts in the future

### Track Who Added Member

```python
# Record who added the member
membership = await auth.membership_service.add_member(
    entity_id=str(team.id),
    user_id=str(new_member.id),
    role_ids=[str(developer_role.id)],
    joined_by=str(manager.id)  # Track who added them
)

# Later, audit trail
if membership.joined_by:
    manager = await membership.joined_by.fetch()
    print(f"Added by: {manager.email}")
```

---

## Updating Memberships

### Change User's Roles

```python
# Update roles (replaces existing roles)
membership = await auth.membership_service.update_member_roles(
    entity_id=str(team.id),
    user_id=str(user.id),
    role_ids=[
        str(senior_developer_role.id),  # Promoted from developer
        str(team_lead_role.id)          # Added team lead
    ]
)

print(f"Updated roles for {user.email}")
```

**Common Scenarios**:
- **Promotion**: Replace junior role with senior role
- **Add Responsibility**: Add team_lead to existing developer role
- **Remove Responsibility**: Remove admin role, keep developer role

### Add Role to Existing Membership

```python
# Get current membership
membership = await auth.membership_service.get_member(
    entity_id=str(team.id),
    user_id=str(user.id)
)

# Fetch current roles
current_role_ids = [str(role.id) for role in membership.roles]

# Add new role
new_role_ids = current_role_ids + [str(reviewer_role.id)]

# Update membership
await auth.membership_service.update_member_roles(
    entity_id=str(team.id),
    user_id=str(user.id),
    role_ids=new_role_ids
)
```

### Remove Role from Membership

```python
# Get current membership
membership = await auth.membership_service.get_member(
    entity_id=str(team.id),
    user_id=str(user.id)
)

# Remove specific role
remaining_roles = [
    str(role.id) for role in membership.roles
    if role.name != "team_lead"  # Remove team_lead
]

# Update membership
await auth.membership_service.update_member_roles(
    entity_id=str(team.id),
    user_id=str(user.id),
    role_ids=remaining_roles
)
```

---

## Removing Members

### Remove User from Entity

```python
# Soft delete (sets is_active=False)
await auth.membership_service.remove_member(
    entity_id=str(team.id),
    user_id=str(user.id)
)

print(f"User removed from {team.display_name}")
```

**What Happens**:
- Membership `is_active` set to `False`
- User loses all permissions in that entity
- Membership record preserved for audit trail
- Can be reactivated by adding member again

### Bulk Member Removal

```python
async def remove_all_members(auth: EnterpriseRBAC, entity_id: str):
    """Remove all members from an entity"""

    # Get all members
    members, total = await auth.membership_service.get_entity_members(
        entity_id,
        page=1,
        limit=1000
    )

    # Remove each member
    for membership in members:
        await auth.membership_service.remove_member(
            entity_id=entity_id,
            user_id=str(membership.user.id)
        )

    print(f"Removed {len(members)} members from entity")
```

---

## Querying Memberships

### Get Entity Members

```python
# Get all members of entity
members, total = await auth.membership_service.get_entity_members(
    entity_id=str(team.id),
    page=1,
    limit=50,
    active_only=True
)

print(f"Team has {total} members")

for membership in members:
    user = await membership.user.fetch()
    roles = await asyncio.gather(*[role.fetch() for role in membership.roles])
    role_names = [r.display_name for r in roles]
    print(f"- {user.email}: {', '.join(role_names)}")
```

**Output**:
```
Team has 5 members
- alice@company.com: Developer, Team Lead
- bob@company.com: Developer
- carol@company.com: Senior Developer
- dave@company.com: Developer, Reviewer
- eve@company.com: Developer
```

### Get User's Entities

```python
# Get all entities user belongs to
memberships, total = await auth.membership_service.get_user_entities(
    user_id=str(user.id),
    page=1,
    limit=50,
    active_only=True
)

print(f"User is member of {total} entities")

for membership in memberships:
    entity = await membership.entity.fetch()
    roles = await asyncio.gather(*[role.fetch() for role in membership.roles])
    role_names = [r.display_name for r in roles]
    print(f"- {entity.display_name} ({entity.entity_type}): {', '.join(role_names)}")
```

**Output**:
```
User is member of 3 entities
- Backend Team (team): Developer, Team Lead
- Mobile Project (project): Contributor
- Engineering Department (department): Member
```

### Filter by Entity Type

```python
# Get only team memberships
team_memberships, total = await auth.membership_service.get_user_entities(
    user_id=str(user.id),
    entity_type="team",
    active_only=True
)

print(f"User is member of {total} teams")
```

### Check Membership Status

```python
# Check if user is member
is_member = await auth.membership_service.is_member(
    entity_id=str(team.id),
    user_id=str(user.id),
    active_only=True
)

if is_member:
    print("User is an active member")
else:
    print("User is not a member")
```

### Get Member Count

```python
# Count active members
count = await auth.membership_service.get_entity_members_count(
    entity_id=str(team.id),
    active_only=True
)

print(f"Team has {count} active members")
```

---

## Common Patterns

### Pattern 1: Onboarding New Employee

```python
async def onboard_employee(
    auth: EnterpriseRBAC,
    email: str,
    department_id: str,
    team_id: str
):
    """
    Complete employee onboarding:
    1. Create user account
    2. Add to department
    3. Add to team
    4. Assign appropriate roles
    """

    # Create user
    user = await auth.user_service.create_user(
        email=email,
        password="temporary_password_to_reset",
        first_name="New",
        last_name="Employee"
    )

    # Get roles
    employee_role = await RoleModel.find_one(RoleModel.name == "employee")
    developer_role = await RoleModel.find_one(RoleModel.name == "developer")

    # Add to department
    await auth.membership_service.add_member(
        entity_id=department_id,
        user_id=str(user.id),
        role_ids=[str(employee_role.id)]
    )

    # Add to team
    await auth.membership_service.add_member(
        entity_id=team_id,
        user_id=str(user.id),
        role_ids=[str(developer_role.id)]
    )

    print(f"✅ Onboarded {email}")
    return user
```

### Pattern 2: Team Transfer

```python
async def transfer_to_team(
    auth: EnterpriseRBAC,
    user_id: str,
    old_team_id: str,
    new_team_id: str,
    new_role_ids: List[str]
):
    """
    Transfer user from one team to another
    """

    # Remove from old team
    await auth.membership_service.remove_member(
        entity_id=old_team_id,
        user_id=user_id
    )

    # Add to new team
    await auth.membership_service.add_member(
        entity_id=new_team_id,
        user_id=user_id,
        role_ids=new_role_ids
    )

    user = await UserModel.get(user_id)
    old_team = await EntityModel.get(old_team_id)
    new_team = await EntityModel.get(new_team_id)

    print(f"✅ Transferred {user.email} from {old_team.display_name} to {new_team.display_name}")
```

### Pattern 3: Project Team Assembly

```python
async def assemble_project_team(
    auth: EnterpriseRBAC,
    project_entity_id: str,
    team_composition: dict
):
    """
    Assemble cross-functional project team

    team_composition = {
        "project_lead": ["user_id_1"],
        "developer": ["user_id_2", "user_id_3"],
        "designer": ["user_id_4"],
        "qa": ["user_id_5"]
    }
    """

    for role_name, user_ids in team_composition.items():
        # Get role
        role = await RoleModel.find_one(RoleModel.name == role_name)
        if not role:
            print(f"⚠️  Role '{role_name}' not found, skipping")
            continue

        # Add each user
        for user_id in user_ids:
            await auth.membership_service.add_member(
                entity_id=project_entity_id,
                user_id=user_id,
                role_ids=[str(role.id)]
            )

            user = await UserModel.get(user_id)
            print(f"✅ Added {user.email} as {role.display_name}")

    # Show final team
    members, total = await auth.membership_service.get_entity_members(project_entity_id)
    print(f"\n🎯 Project team assembled: {total} members")
```

### Pattern 4: Temporary Access Grant

```python
async def grant_temporary_access(
    auth: EnterpriseRBAC,
    user_id: str,
    entity_id: str,
    role_ids: List[str],
    duration_days: int
):
    """
    Grant temporary access (e.g., for contractors, auditors)
    """
    from datetime import datetime, timedelta

    valid_until = datetime.utcnow() + timedelta(days=duration_days)

    membership = await auth.membership_service.add_member(
        entity_id=entity_id,
        user_id=user_id,
        role_ids=role_ids,
        valid_until=valid_until
    )

    user = await UserModel.get(user_id)
    entity = await EntityModel.get(entity_id)
    print(f"✅ Granted {user.email} temporary access to {entity.display_name}")
    print(f"   Expires: {valid_until.strftime('%Y-%m-%d %H:%M:%S')}")

    return membership
```

### Pattern 5: Role Progression (Promotion)

```python
async def promote_user(
    auth: EnterpriseRBAC,
    user_id: str,
    entity_id: str,
    from_role_name: str,
    to_role_name: str
):
    """
    Promote user from one role to another within same entity
    """

    # Get current membership
    membership = await auth.membership_service.get_member(entity_id, user_id)
    if not membership:
        raise ValueError("User is not a member of this entity")

    # Get role IDs
    from_role = await RoleModel.find_one(RoleModel.name == from_role_name)
    to_role = await RoleModel.find_one(RoleModel.name == to_role_name)

    # Build new role list (replace old with new)
    new_role_ids = [
        str(role.id) for role in membership.roles
        if role.name != from_role_name
    ]
    new_role_ids.append(str(to_role.id))

    # Update membership
    await auth.membership_service.update_member_roles(
        entity_id=entity_id,
        user_id=user_id,
        role_ids=new_role_ids
    )

    user = await UserModel.get(user_id)
    entity = await EntityModel.get(entity_id)
    print(f"✅ Promoted {user.email} from {from_role.display_name} to {to_role.display_name}")
    print(f"   Entity: {entity.display_name}")
```

### Pattern 6: Bulk Member Import

```python
async def bulk_import_members(
    auth: EnterpriseRBAC,
    entity_id: str,
    members: List[dict]
):
    """
    Import multiple members at once

    members = [
        {"email": "alice@company.com", "roles": ["developer"]},
        {"email": "bob@company.com", "roles": ["developer", "reviewer"]},
        ...
    ]
    """

    results = {
        "success": [],
        "failed": []
    }

    for member_data in members:
        try:
            # Find user by email
            user = await UserModel.find_one(UserModel.email == member_data["email"])
            if not user:
                results["failed"].append({
                    "email": member_data["email"],
                    "error": "User not found"
                })
                continue

            # Get role IDs
            role_ids = []
            for role_name in member_data["roles"]:
                role = await RoleModel.find_one(RoleModel.name == role_name)
                if role:
                    role_ids.append(str(role.id))

            if not role_ids:
                results["failed"].append({
                    "email": member_data["email"],
                    "error": "No valid roles found"
                })
                continue

            # Add member
            await auth.membership_service.add_member(
                entity_id=entity_id,
                user_id=str(user.id),
                role_ids=role_ids
            )

            results["success"].append(member_data["email"])

        except Exception as e:
            results["failed"].append({
                "email": member_data["email"],
                "error": str(e)
            })

    print(f"✅ Successfully imported {len(results['success'])} members")
    if results["failed"]:
        print(f"⚠️  Failed to import {len(results['failed'])} members")

    return results
```

---

## Advanced Membership Queries

### Get All User's Roles Across All Entities

```python
async def get_user_all_roles(auth: EnterpriseRBAC, user_id: str):
    """Get all unique roles user has across all entities"""

    # Get all memberships
    memberships, _ = await auth.membership_service.get_user_entities(user_id)

    # Collect all unique roles
    all_roles = set()
    for membership in memberships:
        for role_link in membership.roles:
            role = await role_link.fetch()
            all_roles.add(role.name)

    return list(all_roles)

# Usage
roles = await get_user_all_roles(auth, user_id)
print(f"User has these roles: {', '.join(roles)}")
```

### Get Members with Specific Role

```python
async def get_members_with_role(
    auth: EnterpriseRBAC,
    entity_id: str,
    role_name: str
):
    """Get all members who have a specific role in entity"""

    # Get role
    role = await RoleModel.find_one(RoleModel.name == role_name)
    if not role:
        return []

    # Get all members
    members, _ = await auth.membership_service.get_entity_members(entity_id)

    # Filter by role
    matching_members = []
    for membership in members:
        role_ids = [r.id for r in membership.roles]
        if role.id in role_ids:
            matching_members.append(membership)

    return matching_members

# Usage
team_leads = await get_members_with_role(auth, team_id, "team_lead")
print(f"Team has {len(team_leads)} team leads")
```

### Get Entity Hierarchy with Member Counts

```python
async def print_hierarchy_with_counts(
    auth: EnterpriseRBAC,
    entity_id: str,
    indent: int = 0
):
    """Print entity hierarchy showing member counts"""

    entity = await auth.entity_service.get_entity(entity_id)
    count = await auth.membership_service.get_entity_members_count(entity_id)

    print("  " * indent + f"└── {entity.display_name} ({count} members)")

    children = await auth.entity_service.get_children(entity_id)
    for child in children:
        await print_hierarchy_with_counts(auth, str(child.id), indent + 1)

# Usage
await print_hierarchy_with_counts(auth, root_entity_id)

# Output:
# └── Acme Corp (0 members)
#   └── Engineering Division (0 members)
#     └── Backend Department (0 members)
#       └── Platform Team (5 members)
#       └── API Team (3 members)
```

### Get User's Complete Access Map

```python
async def get_user_access_map(auth: EnterpriseRBAC, user_id: str):
    """
    Get complete map of user's access:
    - All entities they belong to
    - All roles in each entity
    - All permissions derived from those roles
    """

    memberships, _ = await auth.membership_service.get_user_entities(user_id)

    access_map = []

    for membership in memberships:
        entity = await membership.entity.fetch()

        # Get roles
        roles = await asyncio.gather(*[role.fetch() for role in membership.roles])

        # Get permissions from roles
        all_permissions = set()
        for role in roles:
            all_permissions.update(role.permissions)

        access_map.append({
            "entity": {
                "id": str(entity.id),
                "name": entity.display_name,
                "type": entity.entity_type
            },
            "roles": [r.display_name for r in roles],
            "permissions": list(all_permissions)
        })

    return access_map

# Usage
import json

access = await get_user_access_map(auth, user_id)
print(json.dumps(access, indent=2))

# Output:
# [
#   {
#     "entity": {
#       "id": "...",
#       "name": "Backend Team",
#       "type": "team"
#     },
#     "roles": ["Developer", "Team Lead"],
#     "permissions": [
#       "code:read", "code:write", "pr:create", "pr:approve",
#       "member:invite", "task:assign"
#     ]
#   },
#   ...
# ]
```

---

## Membership Validation

### Max Members Limit

```python
# Set max members on entity
entity = await auth.entity_service.create_entity(
    name="small_team",
    display_name="Small Team",
    entity_class=EntityClass.STRUCTURAL,
    entity_type="team",
    max_members=5  # Limit to 5 members
)

# Try to add 6th member
try:
    await auth.membership_service.add_member(
        entity_id=str(entity.id),
        user_id=str(user6.id),
        role_ids=[str(role.id)]
    )
except InvalidInputError as e:
    print(e.message)  # "Entity has reached maximum members limit (5)"
```

### Check Membership Validity

```python
# Get membership
membership = await auth.membership_service.get_member(entity_id, user_id)

# Check if currently valid
if membership.is_currently_valid():
    print("Membership is active and within validity period")
else:
    if not membership.is_active:
        print("Membership has been deactivated")
    elif membership.valid_from and datetime.utcnow() < membership.valid_from:
        print("Membership has not started yet")
    elif membership.valid_until and datetime.utcnow() > membership.valid_until:
        print("Membership has expired")
```

### Validate Role Assignment

```python
async def validate_role_assignment(
    auth: EnterpriseRBAC,
    entity_id: str,
    role_ids: List[str]
):
    """Validate that roles exist before assignment"""

    for role_id in role_ids:
        role = await RoleModel.get(role_id)
        if not role:
            raise ValueError(f"Role {role_id} not found")

    return True

# Usage
try:
    await validate_role_assignment(auth, entity_id, [role_id1, role_id2])
    # Proceed with member addition
except ValueError as e:
    print(f"Invalid role: {e}")
```

---

## FastAPI Integration

### Membership Management Endpoints

```python
from fastapi import FastAPI, Depends, HTTPException
from outlabs_auth import EnterpriseRBAC
from outlabs_auth.dependencies import AuthDeps
from pydantic import BaseModel
from typing import List

app = FastAPI()
auth = EnterpriseRBAC(database=db)
deps = AuthDeps(auth)


class MembershipCreate(BaseModel):
    user_id: str
    role_ids: List[str]


class MembershipUpdate(BaseModel):
    role_ids: List[str]


# Add member to entity
@app.post("/entities/{entity_id}/members")
async def add_member(
    entity_id: str,
    data: MembershipCreate,
    current_user = Depends(deps.require_permission("member:add"))
):
    """Add member to entity (requires member:add permission)"""
    try:
        membership = await auth.membership_service.add_member(
            entity_id=entity_id,
            user_id=data.user_id,
            role_ids=data.role_ids,
            joined_by=str(current_user.id)
        )
        return {"message": "Member added", "membership_id": str(membership.id)}
    except Exception as e:
        raise HTTPException(400, str(e))


# Get entity members
@app.get("/entities/{entity_id}/members")
async def get_members(
    entity_id: str,
    page: int = 1,
    limit: int = 50,
    current_user = Depends(deps.require_permission("member:read"))
):
    """List entity members (requires member:read permission)"""
    members, total = await auth.membership_service.get_entity_members(
        entity_id=entity_id,
        page=page,
        limit=limit
    )

    return {
        "members": [
            {
                "user_id": str(m.user.id),
                "roles": [str(r.id) for r in m.roles],
                "joined_at": m.joined_at,
                "is_active": m.is_active
            }
            for m in members
        ],
        "total": total,
        "page": page,
        "limit": limit
    }


# Update member roles
@app.patch("/entities/{entity_id}/members/{user_id}")
async def update_member(
    entity_id: str,
    user_id: str,
    data: MembershipUpdate,
    current_user = Depends(deps.require_permission("member:update"))
):
    """Update member's roles (requires member:update permission)"""
    try:
        membership = await auth.membership_service.update_member_roles(
            entity_id=entity_id,
            user_id=user_id,
            role_ids=data.role_ids
        )
        return {"message": "Member updated", "membership_id": str(membership.id)}
    except Exception as e:
        raise HTTPException(400, str(e))


# Remove member
@app.delete("/entities/{entity_id}/members/{user_id}")
async def remove_member(
    entity_id: str,
    user_id: str,
    current_user = Depends(deps.require_permission("member:remove"))
):
    """Remove member from entity (requires member:remove permission)"""
    try:
        await auth.membership_service.remove_member(
            entity_id=entity_id,
            user_id=user_id
        )
        return {"message": "Member removed"}
    except Exception as e:
        raise HTTPException(400, str(e))


# Get user's entities
@app.get("/users/{user_id}/entities")
async def get_user_entities(
    user_id: str,
    page: int = 1,
    limit: int = 50,
    entity_type: str = None,
    current_user = Depends(deps.require_auth())
):
    """Get entities user belongs to"""
    # Only allow users to see their own entities (unless admin)
    if str(current_user.id) != user_id:
        # Check admin permission
        has_admin = await auth.permission_service.check_permission(
            str(current_user.id),
            "user:read_all"
        )
        if not has_admin:
            raise HTTPException(403, "Can only view your own entities")

    memberships, total = await auth.membership_service.get_user_entities(
        user_id=user_id,
        page=page,
        limit=limit,
        entity_type=entity_type
    )

    return {
        "entities": [
            {
                "entity_id": str(m.entity.id),
                "roles": [str(r.id) for r in m.roles],
                "joined_at": m.joined_at
            }
            for m in memberships
        ],
        "total": total,
        "page": page,
        "limit": limit
    }
```

---

## Best Practices

### 1. Membership Design

**Start with Clear Role Definitions**:
```python
# Define clear, non-overlapping roles
roles = [
    {"name": "viewer", "permissions": ["resource:read"]},
    {"name": "contributor", "permissions": ["resource:read", "resource:create"]},
    {"name": "maintainer", "permissions": ["resource:*", "member:invite"]},
    {"name": "admin", "permissions": ["*:*"]},
]
```

**Use Multiple Roles Wisely**:
```python
# Good: Composable roles
membership = await auth.membership_service.add_member(
    entity_id=team_id,
    user_id=user_id,
    role_ids=[developer_role, reviewer_role]  # Two distinct responsibilities
)

# Avoid: Redundant roles
# Don't assign both "admin" and "developer" if admin already has all developer permissions
```

### 2. Time-Based Access

**Always Set Expiration for Temporary Access**:
```python
# Good: Contractor with explicit end date
membership = await auth.membership_service.add_member(
    entity_id=project_id,
    user_id=contractor_id,
    role_ids=[contractor_role_id],
    valid_until=contract_end_date
)

# Bad: No expiration for temporary access
# (You'll forget to remove them!)
```

### 3. Audit Trail

**Always Track Who Made Changes**:
```python
# Always pass joined_by
membership = await auth.membership_service.add_member(
    entity_id=entity_id,
    user_id=user_id,
    role_ids=role_ids,
    joined_by=str(current_user.id)  # Important for auditing
)
```

### 4. Bulk Operations

**Use Transactions for Bulk Changes**:
```python
# When adding many members, validate first
async def add_members_safely(entity_id: str, members: List[dict]):
    # Validate all before adding any
    for member in members:
        user = await UserModel.get(member["user_id"])
        if not user:
            raise ValueError(f"User {member['user_id']} not found")

    # All validated, proceed with additions
    for member in members:
        await auth.membership_service.add_member(
            entity_id=entity_id,
            user_id=member["user_id"],
            role_ids=member["role_ids"]
        )
```

### 5. Permission Inheritance

**Remember: Permissions Come from Roles**:
```python
# User's effective permissions in entity =
# Union of all permissions from all roles in that membership

# Example:
# - developer role: ["code:read", "code:write", "pr:create"]
# - reviewer role: ["code:read", "pr:review", "pr:approve"]
# User with both roles gets: ["code:read", "code:write", "pr:create", "pr:review", "pr:approve"]
```

---

## Testing Memberships

```python
import pytest

@pytest.mark.asyncio
async def test_add_member(enterprise_auth, test_user, test_entity, test_role):
    """Test adding member to entity"""

    membership = await enterprise_auth.membership_service.add_member(
        entity_id=str(test_entity.id),
        user_id=str(test_user.id),
        role_ids=[str(test_role.id)]
    )

    assert membership.is_active
    assert len(membership.roles) == 1
    assert membership.roles[0].id == test_role.id


@pytest.mark.asyncio
async def test_multiple_roles(enterprise_auth, test_user, test_entity):
    """Test assigning multiple roles"""

    role1 = await RoleModel(name="developer", permissions=["code:write"]).insert()
    role2 = await RoleModel(name="reviewer", permissions=["pr:review"]).insert()

    membership = await enterprise_auth.membership_service.add_member(
        entity_id=str(test_entity.id),
        user_id=str(test_user.id),
        role_ids=[str(role1.id), str(role2.id)]
    )

    assert len(membership.roles) == 2


@pytest.mark.asyncio
async def test_time_based_membership(enterprise_auth, test_user, test_entity, test_role):
    """Test time-based membership validity"""
    from datetime import datetime, timedelta

    # Create membership that expires in 1 day
    membership = await enterprise_auth.membership_service.add_member(
        entity_id=str(test_entity.id),
        user_id=str(test_user.id),
        role_ids=[str(test_role.id)],
        valid_until=datetime.utcnow() + timedelta(days=1)
    )

    # Currently valid
    assert membership.is_currently_valid()

    # Mock expired membership
    membership.valid_until = datetime.utcnow() - timedelta(days=1)
    assert not membership.is_currently_valid()


@pytest.mark.asyncio
async def test_remove_member(enterprise_auth, test_user, test_entity, test_role):
    """Test removing member"""

    # Add member
    membership = await enterprise_auth.membership_service.add_member(
        entity_id=str(test_entity.id),
        user_id=str(test_user.id),
        role_ids=[str(test_role.id)]
    )

    assert membership.is_active

    # Remove member
    await enterprise_auth.membership_service.remove_member(
        entity_id=str(test_entity.id),
        user_id=str(test_user.id)
    )

    # Membership deactivated
    updated = await enterprise_auth.membership_service.get_member(
        str(test_entity.id),
        str(test_user.id)
    )

    assert not updated.is_active


@pytest.mark.asyncio
async def test_max_members_limit(enterprise_auth, test_entity, test_role):
    """Test max members limit enforcement"""

    # Set max_members
    test_entity.max_members = 2
    await test_entity.save()

    # Add 2 members (OK)
    user1 = await UserModel(email="user1@test.com", hashed_password="x").insert()
    user2 = await UserModel(email="user2@test.com", hashed_password="x").insert()

    await enterprise_auth.membership_service.add_member(
        str(test_entity.id), str(user1.id), [str(test_role.id)]
    )
    await enterprise_auth.membership_service.add_member(
        str(test_entity.id), str(user2.id), [str(test_role.id)]
    )

    # Try to add 3rd member (should fail)
    user3 = await UserModel(email="user3@test.com", hashed_password="x").insert()

    with pytest.raises(InvalidInputError) as exc_info:
        await enterprise_auth.membership_service.add_member(
            str(test_entity.id), str(user3.id), [str(test_role.id)]
        )

    assert "maximum members limit" in str(exc_info.value)
```

---

## Troubleshooting

### Issue 1: Member Count Doesn't Match Expected

```python
# Check active vs inactive members
active_count = await auth.membership_service.get_entity_members_count(
    entity_id,
    active_only=True
)

total_count = await auth.membership_service.get_entity_members_count(
    entity_id,
    active_only=False
)

print(f"Active members: {active_count}")
print(f"Total (including inactive): {total_count}")
```

### Issue 2: User Has No Permissions in Entity

```python
# Debug user's membership and roles
membership = await auth.membership_service.get_member(entity_id, user_id)

if not membership:
    print("User is not a member of this entity")
elif not membership.is_active:
    print("Membership is deactivated")
elif not membership.is_currently_valid():
    print("Membership validity period has expired")
else:
    # Check roles
    roles = await asyncio.gather(*[role.fetch() for role in membership.roles])
    print(f"User has {len(roles)} roles:")
    for role in roles:
        print(f"  - {role.display_name}: {role.permissions}")
```

### Issue 3: Cannot Update Membership

```python
# Check if membership exists
membership = await auth.membership_service.get_member(entity_id, user_id)

if not membership:
    print("Membership not found - user is not a member of this entity")
    # Need to add member first
    await auth.membership_service.add_member(entity_id, user_id, role_ids)
else:
    # Update existing membership
    await auth.membership_service.update_member_roles(entity_id, user_id, role_ids)
```

### Issue 4: Max Members Limit Preventing Addition

```python
# Check current member count and limit
entity = await EntityModel.get(entity_id)
current = await auth.membership_service.get_entity_members_count(entity_id)

print(f"Max members: {entity.max_members}")
print(f"Current members: {current}")

if entity.max_members and current >= entity.max_members:
    # Either increase limit or remove inactive members
    entity.max_members = current + 10  # Increase limit
    await entity.save()
```

---

## Next Steps

- **[[44-Tree-Permissions|Tree Permissions]]** - Hierarchical permission inheritance
- **[[45-Context-Aware-Roles|Context-Aware Roles]]** - Roles that adapt by entity type
- **[[46-ABAC-Policies|ABAC Policies]]** - Attribute-based access control
- **[[74-Membership-Service|MembershipService]]** - Service API reference

---

**Previous**: [[52-Entity-Hierarchy|← Entity Hierarchy]]
**Next**: [[44-Tree-Permissions|Tree Permissions →]]
