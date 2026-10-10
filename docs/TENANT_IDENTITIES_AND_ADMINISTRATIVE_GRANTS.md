# Tenant identities and delegated customer administration

Date: 2026-10-10. Status: local implementation contract; not a released capability.
Runtime baseline: public a36, source `7ec9acf77f37ead0d7eb50347334224cc9d72e87`.
The isolated worktree starts at `3c8be781`, whose only addition is maintainer backlog documentation.

## Accepted product requirements

A customer has its own login identities. Reusing an email in two unrelated
customers must not merge accounts, passwords, recovery, sessions or memberships.
Within one corporate customer, an identity may participate in several practices
with different operational roles. Owning a customer identity does not by itself
authorize every practice operation in that customer.

Internal staff must be able to receive configurable administrative roles
for one practice, a corporate subtree, or all Managed Customers. The role determines
actions; its administrative grant determines targets. Staff retain their Internal
identity and do not become customer members to obtain this authority.

Customer roots remain independent Auth roots. An administrative group may list
them without changing parentage, identity ownership or closure tables. A corporate customer root
may have regions, branches and practices. A future structural Agents parent is
not equivalent to this administrative group: it requires an explicit tenant
boundary independent of the highest structural ancestor, including migration,
account ownership, login and scope guards. It is not activated by this change.

## Existing a36 behavior and its limits

Active direct system-wide roles widen `AccessScopeService` to every tree. They
still grant only their role permissions, but their reach includes Internal and
every customer. Ordinary direct roles and entity memberships cannot cross an
account's owning root. Consequently a36 cannot safely express a staff role
limited to another customer or to the Agents group.

The host also infers staff from an email domain and gives staff a business-scope
bypass. That cannot survive separate same-email customer identities. Staff must
be established from protected server-owned Internal-root identity, never email.

## Administrative grant contract

The planned persistent grant carries principal, role, exactly one target selector
(entity, subtree or administrative group), lifecycle, validity interval, grantor
and audit. It is separate from `EntityMembership` and `UserRoleMembership`.
A reusable system-wide role template attached to this grant does not grant
`is_global` to the user. Direct system-wide role assignments retain their existing
platform semantics for compatible consumers.

Authorization for action P at entity E must find **one** active, currently valid
grant whose selected targets contain E and whose active role authorizes P at E.
Never combine all visible targets with a separate union of all role permissions:
read at A plus update at B must deny update at A.

A subtree selector explicitly applies the template at each selected descendant;
the permission matcher evaluates the role at that target. This is distinct from
ordinary ancestor-membership inheritance and does not change its `_tree` rules.
Role and permission conditions must be evaluated against that same target and
fail closed when unresolved. Grant targets require current validated root and
closure data. Groups never include the Internal tenant, even if malformed group
input names it. Revoked, suspended, future, expired, malformed or unresolved grants
deny access. A supplied API-key boundary intersects the administrative target.

Credential, email, account status, sessions and personal-key changes authorize at
the account's owning customer root. Visibility of a member at one practice does
not grant control of its customer-wide credentials. Entity movement authorizes
both the source and destination, with existing populated-root protections intact.
Platform admins and system-wide authority remain separately protected.

Only protected grant-management authority can create or widen administrative
grants. The grantor must contain every delegated action at every delegated target;
recipients cannot extend their own authority or grant a platform-global role.

## Implementation stages and evidence

1. A typed, side-effect-free evaluator and negative/positive tests establish the
   action-and-target contract. It is a foundation, not an activated runtime path.
2. Persistent grant/group schema, management service, audit, transaction and
   cache invalidation must preserve that contract.
3. IAM and host routes use operation-specific targets; list SQL uses the scope
   for the requested action. Flat permission checks are preliminary only.
4. Tenant-qualified identity, provisioning, login, recovery, OTP, OAuth and
   audience/session behavior are qualified without changing legacy consumers.
5. Real PostgreSQL/Redis suites, migration replay and API integration prove the
   complete contract before public publication and downstream exact pins.

Required boundaries include standalone practices, corporate branches, unrelated roots,
all-Agents excluding Internal, read-A/update-B stitching, existing-session
revocation, expiry, source/destination moves, account-root mutations, same-email
external identities, API keys and unresolved scope. Persistent grant routes,
tenant-qualified identity schema and flow integration remain open. No publication,
deployment or production identity mutation is authorized by local preparation.
