# Entity Routes Documentation

## Overview

Entity routes handle all operations related to the unified entity system, including structural entities (organizations, divisions, teams) and access groups (functional groups, permission groups).

> **Important**: Entity operations support tree permissions. See the [Tree Permissions Guide](../TREE_PERMISSIONS_GUIDE.md) for detailed information about how tree permissions work.

## Endpoints

### Get Entity Type Suggestions

**GET** `/v1/entities/entity-types`

Retrieves distinct entity types that have been used in the system, along with predefined suggestions. This endpoint supports the flexible entity type system, allowing platforms to use custom organizational structures.

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `platform_id` | string | Yes (for non-system users) | Filter suggestions by platform |
| `entity_class` | string | No | Filter by entity class (STRUCTURAL or ACCESS_GROUP) |

#### Response

```json
{
  "suggestions": [
    {
      "entity_type": "organization",
      "count": 5,
      "last_used": "2025-07-10T22:56:37.783000",
      "is_predefined": false
    },
    {
      "entity_type": "department",
      "count": 0,
      "is_predefined": true
    }
  ],
  "total": 11
}
```

#### Response Fields

- `suggestions`: Array of entity type suggestions
  - `entity_type`: The entity type name (lowercase with underscores)
  - `count`: Number of times this type has been used
  - `last_used`: ISO timestamp of when this type was last used (optional)
  - `is_predefined`: Boolean indicating if this is a system-suggested type
- `total`: Total number of suggestions returned

#### Authentication

Requires authenticated user. Non-system users must provide `platform_id`.

#### Example

```bash
curl -X GET "https://api.outlabsauth.com/v1/entities/entity-types?platform_id=123&entity_class=STRUCTURAL" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

### Create Entity

**POST** `/v1/entities/`

Creates a new entity in the system.

#### Request Body

```json
{
  "name": "North America",
  "display_name": "North America Region",
  "description": "North American operations",
  "entity_class": "STRUCTURAL",
  "entity_type": "region",
  "parent_entity_id": "parent-entity-id",
  "status": "active"
}
```

#### Request Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Unique identifier name (lowercase, no spaces) |
| `display_name` | string | No | User-friendly display name |
| `description` | string | No | Entity description |
| `entity_class` | string | Yes | Either "STRUCTURAL" or "ACCESS_GROUP" |
| `entity_type` | string | Yes | Flexible type (e.g., "department", "region", "sector") |
| `parent_entity_id` | string | No | ID of parent entity |
| `status` | string | No | Entity status (default: "active") |

#### Important Notes on Entity Types

- **Flexible Types**: Entity types are now flexible strings, not limited to predefined values
- **Naming Convention**: Use lowercase with underscores (e.g., "north_region", "sales_team")
- **Platform Customization**: Each platform can define its own organizational structure
- **Examples**: "sector", "division", "bureau", "chapter", "zone", "district"
- **Special Type**: "platform" - If used, the entity cannot have a parent and gets special platform handling
- **Top-Level Entities**: Can use any entity_type, not restricted to "platform"

#### Response

```json
{
  "id": "687045258586dafcd2cc2a63",
  "name": "north_america",
  "display_name": "North America Region",
  "description": "North American operations",
  "entity_class": "STRUCTURAL",
  "entity_type": "region",
  "parent_entity_id": "parent-entity-id",
  "platform_id": "platform-id",
  "status": "active",
  "direct_permissions": [],
  "config": {},
  "created_at": "2025-07-10T22:56:37.783000",
  "updated_at": "2025-07-10T22:56:37.783000"
}
```

#### Authentication

Requires one of:
- `entity:create` permission in the parent entity (to create a sibling)
- `entity:create_tree` permission in any ancestor of the parent entity (to create descendants)
- `entity:create_all` permission (platform-wide access)

---

### Get Entity

**GET** `/v1/entities/{entity_id}`

Retrieves a single entity by ID.

#### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `entity_id` | string | Yes | The entity ID |

#### Response

Returns the entity object with all fields.

#### Authentication

Requires `entity:read` permission or membership in the entity.

---

### Update Entity

**PUT** `/v1/entities/{entity_id}`

Updates an existing entity.

#### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `entity_id` | string | Yes | The entity ID |

#### Request Body

Same as create entity, but all fields are optional. Only provided fields will be updated.

#### Authentication

Requires one of:
- `entity:update` permission in the entity itself
- `entity:update_tree` permission in any ancestor entity (parent, grandparent, etc.)
- `entity:update_all` permission (platform-wide access)

Note: `entity:update_tree` only allows updating descendant entities, not the entity where it's assigned.

---

### Delete Entity

**DELETE** `/v1/entities/{entity_id}`

Soft deletes an entity (marks as archived).

#### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `entity_id` | string | Yes | The entity ID |

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `cascade` | boolean | No | Delete all child entities (default: false) |

#### Authentication

Requires one of:
- `entity:update` permission in the entity itself
- `entity:update_tree` permission in any ancestor entity (parent, grandparent, etc.)
- `entity:update_all` permission (platform-wide access)

Note: `entity:update_tree` only allows updating descendant entities, not the entity where it's assigned.

---

### Search Entities

**GET** `/v1/entities/`

Search and filter entities with pagination.

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | No | Search in name, display_name, description |
| `entity_class` | string | No | Filter by entity class |
| `entity_type` | string | No | Filter by entity type |
| `status` | string | No | Filter by status |
| `parent_entity_id` | string | No | Filter by parent entity (use "null" for root entities) |
| `platform_id` | string | No | Filter by platform |
| `include_children` | boolean | No | Include child entities |
| `page` | integer | No | Page number (default: 1) |
| `page_size` | integer | No | Items per page (default: 20, max: 100) |

#### Response

```json
{
  "items": [...],
  "total": 50,
  "page": 1,
  "page_size": 20,
  "total_pages": 3
}
```

#### Authentication

Requires authenticated user. Results are filtered by user permissions.

---

### Get Entity Tree

**GET** `/v1/entities/{entity_id}/tree`

Retrieves an entity and all its children as a hierarchical tree structure.

#### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `entity_id` | string | Yes | The root entity ID |

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `max_depth` | integer | No | Maximum depth to traverse (default: 10, max: 20) |

#### Response

```json
{
  "id": "entity-id",
  "name": "root_entity",
  "display_name": "Root Entity",
  "entity_class": "STRUCTURAL",
  "entity_type": "organization",
  "children": [
    {
      "id": "child-id",
      "name": "child_entity",
      "entity_type": "department",
      "children": []
    }
  ]
}
```

#### Authentication

Requires `entity:read` permission.

---

### Get Entity Path

**GET** `/v1/entities/{entity_id}/path`

Returns the full path from root to the specified entity.

#### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `entity_id` | string | Yes | The entity ID |

#### Response

Array of entities from root to the specified entity.

#### Authentication

Requires `entity:read` permission.

---

## Entity Classes

### STRUCTURAL
Represents organizational hierarchy:
- Can have both structural and access group children
- Examples: platform, organization, department, division, team, office, region

### ACCESS_GROUP
Represents permission-based groupings:
- Can only have other access groups as children
- Cannot have structural entities as children
- Examples: admin_group, viewer_group, special_access, beta_testers

## Hierarchy Rules

1. **Structural entities** can contain:
   - Other structural entities
   - Access groups

2. **Access groups** can only contain:
   - Other access groups

3. **Maximum depth**: 10 levels

## Best Practices

1. **Entity Types**: Use descriptive, lowercase names with underscores
2. **Consistency**: Reuse existing entity types when possible (use the entity-types endpoint)
3. **Hierarchy**: Plan your organizational structure carefully
4. **Permissions**: Entity permissions cascade down the hierarchy