# 75-Entity-Service.md - EntityService API Reference

Complete API reference for the **EntityService** - entity hierarchy management (EnterpriseRBAC only).

---

## Overview

**EntityService** manages hierarchical organizational structures with closure table pattern for O(1) ancestor/descendant queries.

### Features

- ✅ Entity CRUD operations
- ✅ Hierarchical entity relationships
- ✅ Closure table for O(1) tree queries
- ✅ Entity path traversal
- ✅ Descendant/ancestor lookups
- ✅ Cache invalidation

**Note:** EntityService is only available in **EnterpriseRBAC** preset.

---

## Quick Reference

For complete examples and usage patterns, see:
- **61-EnterpriseRBAC-API.md** - Complete EnterpriseRBAC guide with EntityService usage
- **42-Entity-Hierarchy.md** - Entity hierarchy concepts and patterns
- **53-Closure-Table.md** - Closure table implementation details

### Key Methods

```python
# Create & retrieve
entity = await auth.entity_service.create_entity(name, display_name, entity_class, entity_type, parent_id)
entity = await auth.entity_service.get_entity(entity_id)
entity = await auth.entity_service.get_entity_by_slug(slug)

# Update & delete
entity = await auth.entity_service.update_entity(entity_id, **updates)
success = await auth.entity_service.delete_entity(entity_id)

# Tree operations (O(1) with closure table)
descendants = await auth.entity_service.get_descendants(entity_id, max_depth)
children = await auth.entity_service.get_children(entity_id)
path = await auth.entity_service.get_entity_path(entity_id)

# Cache management
await auth.entity_service.invalidate_entity_cache(entity_id)
await auth.entity_service.invalidate_entity_tree_cache(entity_id)
```

---

## Complete Documentation

See **61-EnterpriseRBAC-API.md** sections:
- **Entity Services** (lines 283-440)
- **Complete Application Example** (lines 441-750)

---

**Last Updated:** 2025-01-14
