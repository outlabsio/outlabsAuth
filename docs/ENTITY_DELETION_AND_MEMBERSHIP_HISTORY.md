# Entity Deletion and Membership History Design

**Date**: 2026-03-18
**Last Updated**: 2026-03-19
**Status**: Implemented current-state guidance
**Owners**: API team

## Purpose

This document describes the current entity archive, membership-history, and
related user-lifecycle behavior in the runtime.

The current contract is built around:

- archive-based entity lifecycle
- append-only membership history
- user-centric audit mirroring for membership and direct-role side effects
- retained user deletion for continuity of identity and history

## Entity Archive Contract

Entity deletion is archive semantics, not hard delete.

Current behavior:

- target entity `status` becomes `archived`
- descendant entities are archived when `cascade=true`
- delete remains invalid when active children exist and `cascade=false`
- closure-table links are removed as part of the archive workflow
- active memberships on affected entities are revoked
- direct user-role memberships rooted or scoped to archived entities are revoked

This workflow is service-centric and owned by `EntityService.delete_entity()`
plus the related membership/role services it calls.

## Membership History Contract

`entity_membership_history` is the canonical append-only store for entity
membership lifecycle.

Current event types:

- `created`
- `updated`
- `suspended`
- `reactivated`
- `revoked`
- `entity_archived`

Rendering rules:

- history is snapshot-first
- live joins are optional
- archived entities may still be linked when useful
- the stored snapshot must remain readable even if related live rows later
  change

## User-Centric Mirroring

Membership lifecycle is also mirrored into `user_audit_events` so the admin UI
can present a coherent user timeline without losing the specialized membership
history model.

Current result:

- `entity_membership_history` remains the canonical membership-specific store
- `user_audit_events` gives the user-centric cross-domain timeline
- direct-role revocations caused by entity archive are already visible in
  `user_audit_events`

There is still no separate direct-role history table. The user-audit timeline
is the current source for that explainability surface.

## Orphaned User Semantics

A user is considered orphaned when they have:

- zero active entity memberships
- at least one inactive or historical membership record

`root_entity_id` does not determine orphaned status. It remains an
organization-binding field, not a direct access grant.

## User Deletion Interplay

User deletion is retained delete in the current runtime:

- deleted users remain valid history subjects
- membership history remains coherent with the retained user row
- login, direct-role, and user-audit history remain linked to the retained
  identity
- restore is identity-only and does not automatically restore prior access

This is important because orphan discovery and admin investigation would both
degrade if user deletion physically removed the identity row by default.

## Referential Integrity And Retention Guidance

The current implementation favors strong referential integrity first.

Current FK implications:

- `entity_membership_history.membership_id` uses `ON DELETE CASCADE`
- `entity_membership_history.user_id` uses `ON DELETE CASCADE`
- `entity_membership_history.entity_id` uses `ON DELETE CASCADE`
- `entity_membership_history.root_entity_id` and `actor_user_id` use
  `ON DELETE SET NULL`

That is acceptable for the current archive-based lifecycle model, but the
retention-sensitive follow-up remains:

- if future hard purge is introduced, history tables may need to move toward
  `SET NULL` or UUID-only references for subject/context links
- snapshot-first rendering remains the non-negotiable rule regardless of FK
  strategy

## Role And Permission Lifecycle Around Entity Archive

Roles and permissions are now retained with lifecycle status rather than hard
delete.

Current implications:

- archived or otherwise non-active roles and permissions do not continue
  granting permissions
- archived or otherwise non-active roles cannot be assigned through normal
  membership or direct-role flows
- archived live rows can still support admin explainability when useful
- exact historical rendering still depends on stored snapshots and history rows,
  not just live retained definitions

## API Surfaces

Current admin-facing read surfaces related to this slice:

- `GET /v1/users/{user_id}/membership-history`
- orphaned-user discovery endpoints
- user audit timeline endpoints that include mirrored membership events

These endpoints are the supported read model for admin/UI consumers.

## Remaining Follow-Up

The main remaining work in this area is not the basic archive/history model.
It is:

- deciding whether retention-sensitive history tables should evolve away from
  `CASCADE` if hard purge is introduced later
- deciding whether a dedicated direct-role history table is ever needed beyond
  the current `user_audit_events` coverage
