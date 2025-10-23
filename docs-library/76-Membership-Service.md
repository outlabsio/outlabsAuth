# 76-Membership-Service.md - MembershipService API Reference

Complete API reference for the **MembershipService** - entity membership and role assignment management (EnterpriseRBAC only).

---

## Overview

**MembershipService** manages user memberships in entities and their role assignments.

### Features

- ✅ Add/remove users from entities
- ✅ Multi-role assignments per entity
- ✅ Role management within entities
- ✅ Membership queries and listings

**Note:** MembershipService is only available in **EnterpriseRBAC** preset.

---

## Quick Reference

For complete examples and usage patterns, see:
- **61-EnterpriseRBAC-API.md** - Complete MembershipService guide with examples
- **54-Entity-Memberships.md** - Entity membership concepts and patterns

### Key Methods

```python
# Add/remove members
membership = await auth.membership_service.add_member(entity_id, user_id, role_ids, granted_by)
success = await auth.membership_service.remove_member(entity_id, user_id)

# Manage roles
membership = await auth.membership_service.add_roles_to_member(entity_id, user_id, role_ids)
membership = await auth.membership_service.remove_roles_from_member(entity_id, user_id, role_ids)

# Query memberships
membership = await auth.membership_service.get_membership(entity_id, user_id)
memberships = await auth.membership_service.get_user_memberships(user_id)
members = await auth.membership_service.get_entity_members(entity_id)
roles = await auth.membership_service.get_user_roles_in_entity(entity_id, user_id)
```

---

## Complete Documentation

See **61-EnterpriseRBAC-API.md** sections:
- **Membership Services** (lines 441-600)
- **Complete Application Example** (lines 601-850)

---

**Last Updated:** 2025-01-14
