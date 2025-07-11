# Entity Type Flexibility Changes

This document describes the changes made to simplify the entity type system in outlabsAuth, allowing platforms to use their own naming conventions for entities.

## Change Summary

**Date**: 2025-07-10  
**Type**: Architectural Simplification  
**Impact**: Medium - Changes entity validation logic and UI but maintains backward compatibility

## Motivation

The original system enforced strict entity types (platform, organization, branch, team, etc.) which didn't fit all business models. For example:
- A platform might prefer "department" over "branch"
- Another might use "region" → "office" → "squad" instead of "organization" → "branch" → "team"
- The rigid types forced unnatural naming on diverse business structures

## Changes Made

### 1. Backend Changes

#### Entity Model (`api/models/entity_model.py`)
- Added `display_name` field for user-friendly entity names
- Entity type remains but is now flexible (accepts any string value)
- No changes to database structure required

#### Entity Schema (`api/schemas/entity_schema.py`)
- Updated entity type validation to only lowercase the value (no restricted list)
- Added `display_name` to create/update schemas

#### Entity Service (`api/services/entity_service.py`)
- Removed strict hierarchy rules based on entity type
- Simplified to single rule: Access groups cannot have structural children
- Any structural entity can now have any other structural entity as children
- Updated entity creation to include display_name

#### Role Service (`api/services/role_service.py`)
- Changed from entity-type-based role creation to entity-class-based
- Roles now use the entity's display name for user-friendly role names
- Role names are generated based on the entity's system name

#### System Service (`api/services/system_service.py`)
- Removed `assignable_at_types` restrictions from system roles
- Roles can now be assigned at any entity level
- Initialization still uses traditional types for the root platform

### 2. Frontend Changes

#### Entity Drawer (`admin-ui/src/components/entities/entity-drawer.tsx`)
- Changed entity type from dropdown to text input field
- Added suggestions for common types but allows custom values
- Automatically converts input to lowercase for consistency
- Removed hardcoded hierarchy validation matching backend changes

### 3. What Stayed the Same

- Entity class distinction (STRUCTURAL vs ACCESS_GROUP) - this serves a real purpose
- Database indexes and query patterns
- Permission system and inheritance
- API endpoints and contracts
- System initialization process

## Migration Notes

### For Existing Systems
- All existing entities continue to work as before
- No database migration required
- Traditional entity types (platform, organization, etc.) still valid

### For New Implementations
- Can use any entity type names that make sense for the business
- Entity types should be lowercase, single words or underscored (e.g., "department", "cost_center")
- Use display_name for user-facing labels

## Examples

### Before (Rigid)
```json
{
  "name": "west_region",
  "entity_type": "branch",  // Must be from predefined list
  "entity_class": "STRUCTURAL"
}
```

### After (Flexible)
```json
{
  "name": "west_region", 
  "display_name": "West Region",
  "entity_type": "region",  // Can be any string
  "entity_class": "STRUCTURAL"
}
```

## Benefits

1. **Flexibility**: Platforms can use terminology that matches their business
2. **Simplicity**: Less validation code to maintain
3. **User Experience**: Users see familiar terms instead of forced conventions

## Special Handling for "platform" Entity Type

While entity types are flexible, the system has special handling for entities with `entity_type: "platform"`:
- Cannot have a parent entity
- Their platform_id is set to their own ID
- Used for platform-level management

However, top-level entities are NOT required to use "platform" as their type. You can create a top-level entity with any type (e.g., "organization", "company", "network").

## Entity Type Autocomplete Feature (Added 2025-07-10)

To help maintain consistency while preserving flexibility, we added an autocomplete feature for entity types.

### Backend Implementation

#### New Endpoint: GET /v1/entities/entity-types
- Returns distinct entity types used in the system with usage counts
- Uses MongoDB aggregation for efficient querying
- Platform-scoped to maintain data isolation
- Merges predefined suggestions with actual usage

#### Service Method: `get_distinct_entity_types()`
- Aggregates entity types by platform and class
- Tracks usage frequency and last used date
- Sorts by popularity and recency
- Limited to top 50 types for performance

### Frontend Implementation

#### EntityTypeCombobox Component
- Searchable dropdown with type-ahead functionality
- Shows "Recently Used" section with actual usage counts
- Shows "Common Types" section with predefined suggestions
- Allows creating new custom types on the fly
- Automatically formats input (lowercase with underscores)

#### React Query Integration
- 5-minute cache for performance
- Lazy loading (only fetches when dropdown opens)
- Platform-aware suggestions

### Usage Example

```typescript
<EntityTypeCombobox
  value={entityType}
  onChange={setEntityType}
  entityClass="STRUCTURAL"
  platformId={currentPlatformId}
  placeholder="Select or type entity type..."
/>
```

### Benefits of Autocomplete

1. **Consistency**: Encourages reuse of existing entity types
2. **Discovery**: Users can see what types others have used
3. **Flexibility**: Still allows any custom type to be created
4. **Analytics**: Shows usage patterns across the platform
5. **Performance**: Cached suggestions reduce API calls

## Potential Issues and Solutions

### Issue: Frontend TypeScript Errors
The frontend may show TypeScript errors where EntityType enum was expected.

**Solution**: Changed entity_type to accept string type in form definitions.

### Issue: Existing Code Expecting Specific Types
Some code might check for specific entity types like "platform" or "organization".

**Solution**: The traditional types still work. Only new custom types are additions.

### Issue: Role Creation Logic
Roles were created based on entity type (platform_admin, org_admin, etc.).

**Solution**: Roles now created based on entity class and use the entity's name/display_name.

### Issue: UI Components Expecting Enum
Some UI components might expect EntityType enum values.

**Solution**: Updated to accept string values while maintaining backward compatibility.

## Best Practices Going Forward

1. **Use Descriptive Types**: Choose entity types that clearly describe the entity's purpose
2. **Keep It Simple**: Use single words or underscored names (e.g., "department", "cost_center")
3. **Document Your Types**: Each platform should document their entity type conventions
4. **Use Display Names**: Always provide user-friendly display names for entities

## Notes on Permissions

During system initialization, some custom permissions are created with traditional resource names (organization, team, project). These are permission resource identifiers, not entity type restrictions. Platforms can:
- Use these permissions as-is (they work regardless of entity types)
- Create additional custom permissions with their preferred terminology
- The permission system remains flexible and not tied to specific entity types

## System Initialization

The initialization process remains unchanged:
1. Creates root platform entity (using traditional "platform" type)
2. Creates system roles without entity type restrictions
3. Creates custom permissions for common operations
4. Creates the first superuser account

The initialization works perfectly with the new flexible entity system.

## Testing Checklist

- [x] Create entity with custom type via API
- [x] Create entity with custom type via UI
- [x] Verify traditional types still work
- [x] Check role creation with custom entity types
- [x] Validate permission inheritance works regardless of type
- [x] Ensure system initialization completes successfully
- [x] Verify system initialization creates root platform
- [x] Confirm custom permissions are created
- [x] Check that first superuser can log in

## Seed Scripts and Test Data

The existing seed scripts (`scripts/seed_database.py`) continue to use traditional entity types (platform, organization, branch, team) for demonstration purposes. This is intentional to show the traditional usage pattern and these scripts work without modification.

New platforms can create their own seed scripts using custom entity types as needed.

## Rollback Plan

If issues arise, the changes can be reverted by:
1. Re-adding entity type validation in the schema
2. Reverting UI to use dropdown instead of text input
3. No database changes needed - data remains compatible