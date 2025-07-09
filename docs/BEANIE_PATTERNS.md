# Beanie Link Patterns & Best Practices

## Overview

This document captures the patterns and best practices we've developed for working with Beanie's Link system in our current authentication platform. These patterns should be preserved in the new build to avoid the issues we initially encountered.

## Understanding Beanie Links

Beanie Links are references between documents in MongoDB, similar to foreign keys in relational databases. They provide:
- Lazy loading of related documents
- Type safety with generic typing
- Automatic ObjectId conversion
- Optional eager loading with `fetch_links=True`

## Key Patterns We Use

### 1. Model Definition with Links

```python
from beanie import Document, Link
from typing import List, Optional

class UserModel(BaseDocument):
    # Single Link reference
    client_account: Optional[Link["ClientAccountModel"]] = None
    
    # List of Links
    roles: List[Link["RoleModel"]] = Field(default_factory=list)
    groups: List[Link["GroupModel"]] = Field(default_factory=list)
```

**Important**: Always use `default_factory=list` for Link lists to avoid mutable default issues.

### 2. Fetching Documents with Links

#### Pattern: Using `fetch_links=True`

```python
# Fetch single document with all links populated
user = await UserModel.get(user_id, fetch_links=True)

# Fetch multiple documents with links
users = await UserModel.find(
    UserModel.client_account.id == client_id,
    fetch_links=True
).to_list()
```

**Critical**: The `fetch_links=True` parameter automatically populates all Link fields, converting them from ObjectIds to full documents.

### 3. Creating Documents with Links

#### Pattern: Convert IDs to Document References

```python
async def create_user(self, user_data: UserCreateSchema) -> UserModel:
    user_dict = user_data.model_dump(exclude={"password"})
    
    # Handle single Link reference
    if user_data.client_account_id:
        client_account = await ClientAccountModel.get(
            PydanticObjectId(user_data.client_account_id)
        )
        if client_account:
            user_dict["client_account"] = client_account
            del user_dict["client_account_id"]  # Remove the string ID
    
    # Handle Link lists
    roles_list = []
    if user_data.roles:
        for role_id_str in user_data.roles:
            role = await RoleModel.get(PydanticObjectId(role_id_str))
            if role:
                roles_list.append(role)
    user_dict["roles"] = roles_list
    
    # Create and save
    new_user = UserModel(**user_dict)
    await new_user.insert()
    return new_user
```

### 4. Working with Link IDs

#### Pattern: Extract IDs from Link Objects

```python
# When Links are populated (documents)
def convert_user_to_response(user: UserModel) -> Dict[str, Any]:
    user_dict = user.model_dump(by_alias=True)
    
    # Convert Link documents back to IDs for API response
    user_dict["roles"] = [
        str(role.id) for role in user.roles
    ] if user.roles else []
    
    # Handle optional single Link
    if user.client_account:
        user_dict["client_account_id"] = str(user.client_account.id)
    
    return user_dict
```

#### Pattern: Handle Both Link and ObjectId

```python
# Links might be documents or just ObjectIds depending on fetch_links
permission_ids = []
if role.permissions:
    for permission_link in role.permissions:
        if hasattr(permission_link, 'id'):
            # It's a populated document
            permission_ids.append(permission_link.id)
        else:
            # It's just an ObjectId
            permission_ids.append(permission_link)
```

### 5. Querying with Link Fields

#### Pattern: Query by Link ID

```python
# Query by Link reference ID
users = await UserModel.find(
    UserModel.client_account.id == client_account_id,
    fetch_links=True
).to_list()

# Query for documents with specific role
users_with_role = await UserModel.find(
    UserModel.roles.id == role_id
).to_list()
```

**Note**: You can query by `.id` even when links aren't fetched.

### 6. Updating Documents with Links

#### Pattern: Preserve Link References During Updates

```python
async def update_user_roles(user_id: str, new_role_ids: List[str]):
    user = await UserModel.get(user_id)
    
    # Convert IDs to Role documents
    new_roles = []
    for role_id in new_role_ids:
        role = await RoleModel.get(PydanticObjectId(role_id))
        if role:
            new_roles.append(role)
    
    # Update and save
    user.roles = new_roles
    await user.save()
```

### 7. Bulk Operations with Links

#### Pattern: Efficient Bulk Fetching

```python
async def get_users_with_permissions(user_ids: List[str]):
    # Fetch users
    users = await UserModel.find(
        UserModel.id.in_(user_ids),
        fetch_links=True  # This fetches roles
    ).to_list()
    
    # Collect all role IDs to fetch permissions in bulk
    all_role_ids = []
    for user in users:
        if user.roles:
            all_role_ids.extend([role.id for role in user.roles])
    
    # Fetch all permissions for all roles at once
    roles_with_perms = await RoleModel.find(
        RoleModel.id.in_(all_role_ids),
        fetch_links=True  # This fetches permissions
    ).to_list()
    
    # Build lookup map
    role_perm_map = {
        str(role.id): role.permissions 
        for role in roles_with_perms
    }
    
    return users, role_perm_map
```

## Common Pitfalls & Solutions

### Pitfall 1: Forgetting `fetch_links=True`

**Problem**: Links remain as ObjectIds, causing AttributeError when accessing properties.

```python
# BAD - Links not fetched
user = await UserModel.get(user_id)
print(user.client_account.name)  # AttributeError!

# GOOD - Links fetched
user = await UserModel.get(user_id, fetch_links=True)
print(user.client_account.name)  # Works!
```

### Pitfall 2: Not Handling Optional Links

**Problem**: Null pointer exceptions when Link is None.

```python
# BAD
client_name = user.client_account.name

# GOOD
client_name = user.client_account.name if user.client_account else None
```

### Pitfall 3: Mixing IDs and Documents

**Problem**: Schema validation errors when mixing ObjectIds and document objects.

```python
# BAD - Mixing types
user.roles = [role_id_1, role_document_2]  # Type error!

# GOOD - Consistent types
role_docs = []
for role_id in role_ids:
    role = await RoleModel.get(role_id)
    if role:
        role_docs.append(role)
user.roles = role_docs
```

### Pitfall 4: Circular References

**Problem**: Infinite loops when models reference each other.

```python
# Solution: Use forward references and careful fetch_links usage
class UserModel(Document):
    groups: List[Link["GroupModel"]] = []

class GroupModel(Document):
    members: List[Link["UserModel"]] = []
    
# Fetch only one direction at a time
group = await GroupModel.get(group_id, fetch_links=True)
# group.members are populated, but group.members[0].groups are not
```

## Performance Considerations

### 1. Selective Link Fetching

Future Beanie versions support selective fetching:
```python
# Only fetch specific links (future feature)
user = await UserModel.get(
    user_id, 
    fetch_links=["client_account", "roles"]  # Don't fetch groups
)
```

### 2. Query Optimization

```python
# Use projection to exclude large link lists when not needed
users = await UserModel.find().project(
    UserModel.groups
).to_list()  # Excludes groups field entirely
```

### 3. Caching Strategies

```python
# Cache frequently accessed linked documents
@lru_cache(maxsize=100)
async def get_role_cached(role_id: str):
    return await RoleModel.get(role_id, fetch_links=True)
```

## Migration to New System

For the new Entity-based system, apply these patterns:

### 1. Entity Model with Links

```python
class EntityModel(BaseDocument):
    # Parent entity link
    parent_entity: Optional[Link["EntityModel"]] = None
    
    # Role assignments
    roles: List[Link["RoleModel"]] = Field(default_factory=list)
    
    # Direct permissions (if not using permission links)
    direct_permissions: List[str] = Field(default_factory=list)
```

### 2. EntityMembership with Links

```python
class EntityMembershipModel(BaseDocument):
    user: Link["UserModel"]
    entity: Link["EntityModel"]
    joined_by: Link["UserModel"]
    
    class Settings:
        indexes = [
            [("user", 1), ("entity", 1)],  # Compound unique index
        ]
```

### 3. Efficient Permission Resolution

```python
async def get_user_permissions(user_id: str) -> Set[str]:
    # Get all memberships with entities populated
    memberships = await EntityMembershipModel.find(
        EntityMembershipModel.user.id == user_id,
        fetch_links=True  # Populates entity
    ).to_list()
    
    # Collect all entity IDs
    entity_ids = [m.entity.id for m in memberships if m.entity]
    
    # Fetch all entities with roles in one query
    entities = await EntityModel.find(
        EntityModel.id.in_(entity_ids),
        fetch_links=True  # Populates roles
    ).to_list()
    
    # Aggregate permissions
    permissions = set()
    for entity in entities:
        if entity.direct_permissions:
            permissions.update(entity.direct_permissions)
        if entity.roles:
            for role in entity.roles:
                # Assume role.permissions is already populated
                permissions.update(role.permissions)
    
    return permissions
```

## Best Practices Summary

1. **Always use `fetch_links=True`** when you need to access linked document properties
2. **Handle optional Links** with proper null checks
3. **Convert IDs to documents** before assigning to Link fields
4. **Use consistent types** - don't mix ObjectIds and documents
5. **Be mindful of circular references** - fetch only what you need
6. **Batch operations** when dealing with multiple documents
7. **Cache frequently accessed** linked documents
8. **Use proper indexes** on Link reference fields
9. **Handle both populated and non-populated** Link states
10. **Clean up string IDs** from schemas after converting to Links

## Testing Patterns

```python
# Test fixture for creating linked documents
@pytest.fixture
async def user_with_roles():
    # Create role first
    role = await RoleModel(name="test_role").insert()
    
    # Create user with role link
    user = await UserModel(
        email="test@example.com",
        roles=[role]  # Pass document, not ID
    ).insert()
    
    # Return with links fetched
    return await UserModel.get(user.id, fetch_links=True)

# Test Link queries
async def test_find_users_by_role(role):
    users = await UserModel.find(
        UserModel.roles.id == role.id
    ).to_list()
    assert len(users) > 0
```

These patterns have been battle-tested in our current system and should be carried forward to ensure smooth development of the new platform.