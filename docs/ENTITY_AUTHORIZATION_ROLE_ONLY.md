# Entity Authorization Role-Only Decision Memo

**Date**: 2026-03-17
**Status**: Accepted

## Summary

Entity authorization remains role-only.

`entity.direct_permissions` is rejected and removed from the live API because the current authorization model already has explicit, auditable grant paths:

- direct user role memberships
- entity membership roles
- entity-local roles with `entity_only` or `hierarchy` scope
- auto-assigned entity-local roles

## Why direct entity permissions were rejected

Adding raw permissions to entities would create a parallel grant path without solving a real gap in the current design.

The main costs are:

- weaker auditability and explainability
- duplicated authorization semantics alongside roles
- unclear inheritance rules
- extra UI and API complexity for a use case already handled by entity-local roles

## Replacement model

Entity administration and access continue to be expressed through roles:

- use entity-local roles when a permission should exist only at one entity or subtree
- use auto-assigned roles when all members of an entity should inherit the same baseline access
- use direct user role memberships only for explicit exceptions

## Live role contract notes

The live role API and admin UI contract now follows these rules:

- `entity_type_permissions` is deprecated and removed from public role request/response payloads
- `assignable_at_types` is the persisted way to restrict where a role may be assigned in entity context
- `assignable_at_types=[]` means the role can be assigned at any entity type
- `assignable_at_types` affects entity role catalogs, membership role validation, and auto-assigned role application
- global role definitions are superuser-managed only; scoped admins manage only roles inside their resolved root/entity scope

## Metadata note

`entity.metadata` is not implemented as a persisted field in the live SQL model or API contract.
It remains future design intent only and should not reappear in runtime schemas until it is backed by real storage and tests.

## Revisit criteria

Reintroducing entity-owned permissions would require all of the following:

- a concrete admin workflow that entity-local roles cannot express cleanly
- explicit inheritance and precedence rules
- audited API and UI explainability
- persisted storage and end-to-end tests

## Related Decisions

- `DD-053`: Entity-local roles with scope control
- `DD-054`: Permission scope enforcement
- `DD-055`: Entity authorization stays role-only
