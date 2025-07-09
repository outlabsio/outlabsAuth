# outlabsAuth Architecture Plan: Unified Entity Model

> **Note**: This document is for developers working on outlabsAuth itself. For platform integration documentation, see [docs/README.md](./docs/README.md).

## Executive Summary

This plan outlines the architecture for a flexible authentication and authorization system that supports multiple platforms with varying organizational structures. The system uses a **Unified Entity Model** where entities are classified as either **Structural Entities** (organizational hierarchy) or **Access Groups** (flexible collections), eliminating the need for a separate groups system.

### Related Documentation
- [Project Overview](./docs/PROJECT_OVERVIEW.md) - What outlabsAuth is and why
- [Architecture Guide](./docs/ARCHITECTURE.md) - Technical architecture details
- [API Specification](./docs/API_SPECIFICATION.md) - Complete API reference
- [Integration Guide](./docs/INTEGRATION_GUIDE.md) - How platforms integrate

### Key Innovation: Entity Classification
- **Structural Entities**: Form the organizational hierarchy (Organization, Division, Branch, Team)
- **Access Groups (as Entities)**: Flexible collections within structural entities (functional groups, permission groups, project groups)
- **Single Model**: Everything is an Entity - vastly simpler to build and maintain

### Decision: Strategic Rewrite
Given the fundamental architectural improvements, we recommend a **strategic rewrite** that:
- Preserves the service layer patterns and dependency injection from current system
- Implements the unified Entity model from scratch
- Provides clean migration path for existing data

## Core Architecture: Unified Entity Model

### The Entity Model
```python
class EntityModel(BaseDocument):
    # Core fields
    name: str
    platform_id: str  # Root platform this entity belongs to
    parent_entity: Optional[Link["EntityModel"]]
    
    # Classification
    entity_class: EntityClass  # 'structural' or 'access_group'
    entity_type: EntityType    # 'organization', 'team', 'functional_group', 'project_group', etc.
    
    # Flexible metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Access control
    status: str = "active"  # active, archived, suspended
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    
    # Platform-specific rules
    allowed_child_classes: List[EntityClass] = Field(default_factory=list)
    allowed_child_types: List[EntityType] = Field(default_factory=list)
```

### Entity Types

#### Structural Entities
These form the organizational hierarchy - the "folders" of your system:
- `platform` - Root platform (Diverse, uaya, etc.)
- `organization` - Major organizational unit
- `division` - Business division or department
- `branch` - Geographic or functional branch
- `team` - Smallest structural unit

#### Access Groups (as Entities)
These are flexible collections within structural entities - like "labels" with permissions:
- `functional_group` - Specialist groups (e.g., "Luxury Condo Specialists")
- `permission_group` - Permission-based groups (e.g., "Miami Admins")
- `project_group` - Temporary project teams
- `role_group` - Groups that automatically grant roles
- `access_group` - General purpose access control

## How It Works: Real-World Scenarios

### Scenario 1: Miami Office Specialist Group
*"Miami wants to create a group for agents that serve a certain purpose"*

```json
{
  "entity_id": "ent_luxury_condo_specialists",
  "name": "Luxury Condo Specialists",
  "platform_id": "plat_diverse_leads",
  "parent_entity_id": "ent_miami_office",
  "entity_class": "access_group",
  "entity_type": "functional_group",
  "metadata": {
    "description": "Agents specializing in luxury waterfront properties",
    "created_by": "miami_manager"
  }
}
```

**Why it works**: It's scoped within Miami Office, can have specific permissions (access to luxury listings), and members are easily managed.

### Scenario 2: Admin Permission Group
*"Agents who also work as administrators"*

```json
{
  "entity_id": "ent_miami_admins",
  "name": "Miami Admins",
  "platform_id": "plat_diverse_leads",
  "parent_entity_id": "ent_miami_office",
  "entity_class": "access_group",
  "entity_type": "permission_group",
  "roles_attached": ["role_local_admin"],
  "metadata": {
    "permissions_granted": ["user:manage_client", "reports:view_all"]
  }
}
```

**Why it works**: Add agents to this entity, they automatically get admin permissions. Remove them, permissions are revoked.

### Scenario 3: Temporary Marketing Project
*"Create temporary groups for marketing campaigns"*

```json
{
  "entity_id": "ent_q4_marketing_campaign",
  "name": "Q4 Marketing Campaign - Sunshine",
  "platform_id": "plat_diverse_leads",
  "parent_entity_id": "ent_miami_office",
  "entity_class": "access_group",
  "entity_type": "project_group",
  "valid_from": "2024-10-01",
  "valid_until": "2024-12-31",
  "metadata": {
    "project_lead": "user_marketing_director",
    "budget_code": "MKT-2024-Q4",
    "cross_entity_members": ["ent_ny_office/user_123"]
  }
}
```

**Why it works**: Time-bounded, automatically expires, can include members from other offices if needed.

## Business Model Examples

### 1. Diverse Platform (Complex Multi-Level)

```yaml
Diverse Platform:
  entity_class: structural
  entity_type: platform
  children:
    
    # STRUCTURAL ENTITIES
    - Diverse Leads:
        entity_class: structural
        entity_type: organization
        children:
          - Miami Office:
              entity_class: structural
              entity_type: branch
              children:
                # ACCESS GROUPS within Miami
                - Miami VIP Handlers:
                    entity_class: access_group
                    entity_type: functional_group
                    permissions: [leads:vip_access]
                - Miami Admins:
                    entity_class: access_group
                    entity_type: permission_group
                    roles: [local_admin]
                - Q4 Campaign Team:
                    entity_class: access_group
                    entity_type: project_group
                    valid_until: 2024-12-31
          
          - Corporate Division:
              entity_class: structural
              entity_type: division
              children:
                - Enterprise Team:
                    entity_class: structural
                    entity_type: team
    
    # Sister company with different structure
    - Referral Brokerage:
        entity_class: structural
        entity_type: organization
        # Different structure...
```

### 2. uaya Platform (Simple Structure)

```yaml
uaya Platform:
  entity_class: structural
  entity_type: platform
  children:
    # Just access groups, no structural hierarchy
    - Administrators:
        entity_class: access_group
        entity_type: role_group
        roles: [admin]
    - Moderators:
        entity_class: access_group
        entity_type: role_group
        roles: [moderator]
    - Premium Users:
        entity_class: access_group
        entity_type: access_group
        permissions: [feature:premium_access]
```

### 3. Corporate Client Example

```yaml
ABC Brokerage:
  entity_class: structural
  entity_type: organization
  parent: Diverse Platform
  children:
    # STRUCTURAL
    - New York Branch:
        entity_class: structural
        entity_type: branch
    - California Branch:
        entity_class: structural
        entity_type: branch
        children:
          # ACCESS GROUPS
          - CA Compliance Team:
              entity_class: access_group
              entity_type: functional_group
          - Senior Brokers:
              entity_class: access_group
              entity_type: permission_group
```

## Key Benefits of Unified Model

### 1. Simplicity
- **Single Model**: Just Entities and EntityMemberships
- **No Groups Table**: Everything is an entity with a classification
- **Unified Permissions**: One system to check permissions

### 2. Flexibility
- **Infinite Nesting**: Access groups can contain other access groups
- **Cross-Entity Members**: Project groups can span offices
- **Time-Based**: Groups can auto-expire

### 3. Power
- **Role Inheritance**: Access groups can grant roles
- **Permission Aggregation**: Users get permissions from all their entities
- **Metadata Flexibility**: Each entity type can have custom fields

## Permission Resolution

```python
async def get_user_permissions(user: UserModel, context: EntityModel) -> Set[str]:
    permissions = set()
    
    # Get all user's entity memberships
    memberships = await EntityMembershipModel.find(
        EntityMembershipModel.user.id == user.id,
        fetch_links=True  # Populates entity and roles
    ).to_list()
    
    for membership in memberships:
        # Check if membership and entity are active
        if not membership.is_active() or not membership.entity.is_active():
            continue
            
        # Get permissions from roles assigned in this membership
        for role in membership.roles:
            permissions.update(role.permissions)
        
        # Get direct permissions from the entity (if any)
        if membership.entity.direct_permissions:
            permissions.update(membership.entity.direct_permissions)
        
        # Context-aware permissions: If user has access to parent, 
        # they may have permissions on children
        if membership.entity.is_ancestor_of(context):
            # Add hierarchical permissions based on entity type
            permissions.add(f"{context.entity_type}:read")
            if "manage" in str(membership.roles):  # If any management role
                permissions.add(f"{context.entity_type}:manage")
    
    return permissions
```

## Implementation Architecture

### Core Models

```python
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
from beanie import Document, Link
from pydantic import Field

class EntityClass(str, Enum):
    STRUCTURAL = "structural"
    ACCESS_GROUP = "access_group"

class EntityType(str, Enum):
    # Structural types
    PLATFORM = "platform"
    ORGANIZATION = "organization"
    DIVISION = "division"
    BRANCH = "branch"
    TEAM = "team"
    
    # Access group types
    FUNCTIONAL_GROUP = "functional_group"
    PERMISSION_GROUP = "permission_group"
    PROJECT_GROUP = "project_group"
    ROLE_GROUP = "role_group"
    ACCESS_GROUP = "access_group"

class EntityModel(BaseDocument):
    # Identity
    name: str
    slug: str = Field(..., description="URL-friendly identifier")
    
    # Classification
    entity_class: EntityClass
    entity_type: EntityType
    
    # Hierarchy
    platform_id: str
    parent_entity: Optional[Link["EntityModel"]] = None
    
    # Access control
    status: str = Field(default="active")
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    
    # Permissions and roles
    roles: List[Link["RoleModel"]] = Field(default_factory=list)
    direct_permissions: List[str] = Field(default_factory=list)
    
    # Flexible metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Configuration
    allowed_child_classes: List[EntityClass] = Field(default_factory=list)
    allowed_child_types: List[EntityType] = Field(default_factory=list)
    max_members: Optional[int] = None
    
    @property
    def is_structural(self) -> bool:
        return self.entity_class == EntityClass.STRUCTURAL
    
    @property
    def is_access_group(self) -> bool:
        return self.entity_class == EntityClass.ACCESS_GROUP
    
    def is_active(self) -> bool:
        if self.status != "active":
            return False
        now = datetime.utcnow()
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        return True

class RoleModel(BaseDocument):
    # Identity
    name: str  # e.g., "agent", "team_lead", "branch_manager"
    display_name: str
    description: str
    
    # Permissions this role grants
    permissions: List[str] = Field(default_factory=list)
    # e.g., ["lead:read", "lead:create", "report:view_team"]
    
    # Scoping - which entity owns this role
    entity: Link[EntityModel]
    
    # Where this role can be assigned
    assignable_at_types: List[EntityType] = Field(default_factory=list)
    # e.g., ["branch", "team"] means can be assigned at branch or team level
    
    # Metadata
    is_system_role: bool = Field(default=False)  # Platform-defined vs custom
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Link[UserModel]

class EntityMembershipModel(BaseDocument):
    user: Link[UserModel]
    entity: Link[EntityModel]
    
    # Roles assigned to user in THIS entity context
    roles: List[Link[RoleModel]] = Field(default_factory=list)
    
    # Membership metadata
    joined_at: datetime = Field(default_factory=datetime.utcnow)
    joined_by: Link[UserModel]
    
    # Time-based membership
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    
    class Settings:
        indexes = [
            [("user", 1), ("entity", 1)],  # Unique constraint
            [("entity", 1)],  # Fast entity member lookup
            [("user", 1)],  # Fast user membership lookup
        ]
```

### Service Layer

```python
class EntityService:
    @staticmethod
    async def create_entity(
        data: EntityCreateSchema,
        parent: Optional[EntityModel],
        current_user: UserModel
    ) -> EntityModel:
        # Validate entity type combinations
        if parent:
            if data.entity_class not in parent.allowed_child_classes:
                raise ValueError(f"Parent doesn't allow {data.entity_class} children")
            if data.entity_type not in parent.allowed_child_types:
                raise ValueError(f"Parent doesn't allow {data.entity_type} children")
        
        # Check permissions
        required_permission = "entity:create_structural" if data.entity_class == EntityClass.STRUCTURAL else "entity:create_group"
        await check_permissions(current_user, required_permission, parent)
        
        # Create entity
        entity = EntityModel(
            **data.dict(),
            platform_id=parent.platform_id if parent else data.platform_id,
            parent_entity=parent
        )
        
        return await entity.save()
    
    @staticmethod
    async def add_member(
        entity: EntityModel,
        user: UserModel,
        added_by: UserModel,
        role_in_entity: Optional[str] = None
    ) -> EntityMembershipModel:
        # Check if entity accepts members
        if entity.is_structural and entity.entity_type == EntityType.PLATFORM:
            raise ValueError("Cannot add members directly to platform")
        
        # Check permissions
        await check_permissions(added_by, "entity:manage_members", entity)
        
        # Check capacity
        if entity.max_members:
            current_count = await EntityMembershipModel.find(
                EntityMembershipModel.entity == entity.id
            ).count()
            if current_count >= entity.max_members:
                raise ValueError("Entity has reached maximum capacity")
        
        # Create membership
        membership = EntityMembershipModel(
            user=user,
            entity=entity,
            joined_by=added_by,
            role_in_entity=role_in_entity,
            valid_from=entity.valid_from,
            valid_until=entity.valid_until
        )
        
        return await membership.save()
```

### API Structure

```python
# RESTful endpoints
/v1/platforms/
/v1/entities/                              # All entities (filtered by permissions)
/v1/entities/structural/                   # Only structural entities
/v1/entities/groups/                       # Only access groups
/v1/entities/{entity_id}/
/v1/entities/{entity_id}/children/
/v1/entities/{entity_id}/members/
/v1/entities/{entity_id}/add-member/
/v1/entities/{entity_id}/remove-member/

# Role management
/v1/entities/{entity_id}/roles/            # Roles defined for this entity
/v1/entities/{entity_id}/roles/create/     # Create role for entity
/v1/roles/{role_id}/                       # Get/update/delete role
/v1/entities/{entity_id}/members/{user_id}/roles/  # Assign/remove roles

# User endpoints
/v1/users/{user_id}/entities/              # All entities user belongs to
/v1/users/{user_id}/memberships/           # Detailed memberships with roles
/v1/users/{user_id}/permissions/           # Computed permissions
/v1/users/{user_id}/roles/                 # All roles across all entities
```

## Frontend Implementation

### Entity Tree Component
```typescript
// Unified tree showing both structural and access groups
<EntityTree
  rootEntity={platform}
  showAccessGroups={true}
  onSelectEntity={(entity) => {
    if (entity.entity_class === 'structural') {
      showStructuralEntityDetails(entity)
    } else {
      showAccessGroupDetails(entity)
    }
  }}
  renderNode={(entity) => (
    <div className="flex items-center gap-2">
      <EntityIcon type={entity.entity_type} />
      <span>{entity.name}</span>
      {entity.entity_class === 'access_group' && (
        <Badge variant="secondary" size="sm">
          {entity.metadata.member_count} members
        </Badge>
      )}
    </div>
  )}
/>
```

### Quick Group Creation
```typescript
// Simple UI for creating access groups within current context
<QuickGroupCreate
  parentEntity={currentEntity}
  groupTypes={['functional_group', 'permission_group', 'project_group']}
  onSuccess={(newGroup) => {
    toast.success(`Created ${newGroup.name}`)
    refreshEntityTree()
  }}
/>
```

## Migration Strategy

### From Current System (ClientAccount → Entity)
```python
# Migration script
async def migrate_to_entity_model():
    # 1. Migrate platforms
    for platform in await ClientAccountModel.find(
        ClientAccountModel.is_platform_root == True
    ).to_list():
        await EntityModel(
            name=platform.name,
            entity_class=EntityClass.STRUCTURAL,
            entity_type=EntityType.PLATFORM,
            platform_id=str(platform.id),
            metadata={
                "migrated_from": "client_account",
                "original_id": str(platform.id)
            }
        ).save()
    
    # 2. Migrate organizations
    for org in await ClientAccountModel.find(
        ClientAccountModel.is_platform_root == False
    ).to_list():
        parent_entity = await EntityModel.find_one(
            EntityModel.metadata.original_id == str(org.created_by_client_id)
        )
        
        await EntityModel(
            name=org.name,
            entity_class=EntityClass.STRUCTURAL,
            entity_type=EntityType.ORGANIZATION,
            platform_id=org.platform_id,
            parent_entity=parent_entity,
            metadata={
                "migrated_from": "client_account",
                "original_id": str(org.id)
            }
        ).save()
    
    # 3. Migrate existing groups if any
    # 4. Update user memberships
```

## Benefits Over Hybrid Model

### Simpler Implementation
- One model instead of two (Entity vs Entity+Group)
- One membership table instead of two
- Unified permission checking

### More Flexible
- Access groups can contain other access groups
- Structural entities can have access groups as children
- Everything follows the same patterns

### Better UX
- Users understand "everything is an entity"
- Consistent UI patterns for all entity types
- Natural hierarchy visualization

## Decision: Build New System

Given the elegance of this unified model, we recommend:
1. **Build the new Entity system from scratch**
2. **Run in parallel with current system initially**
3. **Migrate data once stable**
4. **Deprecate old system**

This approach is cleaner than trying to refactor the existing system to support this fundamentally different model.

## Next Steps

1. **Validate Architecture**: Ensure this meets all current and future needs
2. **Build Prototype**: Create minimal Entity system to validate approach
3. **Design UI/UX**: Create mockups for entity management interface
4. **Plan API Migration**: Design backwards-compatible API strategy
5. **Create Timeline**: Detailed implementation schedule