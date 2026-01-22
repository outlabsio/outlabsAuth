"""
Permission Scope Enforcement Tests (DD-054)

Tests that entity-local roles only grant permissions within entity context,
while global and org-scoped roles work without entity context.

Mental model:
- Global role (is_global=True) → permissions work everywhere
- Org-scoped role (root_entity_id set, scope_entity_id=NULL) → permissions work globally within org
- Entity-local role (scope_entity_id set) → permissions only work in entity context
"""

import pytest
import pytest_asyncio

from outlabs_auth.core.config import AuthConfig
from outlabs_auth.models.sql.closure import EntityClosure
from outlabs_auth.models.sql.entity import Entity
from outlabs_auth.models.sql.entity_membership import EntityMembership
from outlabs_auth.models.sql.enums import EntityClass, MembershipStatus, RoleScope
from outlabs_auth.models.sql.permission import Permission
from outlabs_auth.models.sql.role import Role
from outlabs_auth.models.sql.user import User
from outlabs_auth.models.sql.user_role_membership import UserRoleMembership
from outlabs_auth.services.permission import PermissionService


@pytest_asyncio.fixture
async def permission_service(auth_config: AuthConfig) -> PermissionService:
    return PermissionService(config=auth_config, observability=None)


# =============================================================================
# Helper Functions
# =============================================================================


async def _create_permission(session, name: str) -> Permission:
    """Create a permission with the given name."""
    perm = Permission(
        name=name,
        display_name=name,
        description=name,
        is_system=True,
        is_active=True,
    )
    session.add(perm)
    await session.flush()
    return perm


async def _create_global_role(session, name: str, perms: list[Permission]) -> Role:
    """Create a global role (works everywhere)."""
    role = Role(
        name=name,
        display_name=name,
        description=name,
        is_system_role=False,
        is_global=True,  # Global role
    )
    role.permissions = perms
    session.add(role)
    await session.flush()
    return role


async def _create_entity_local_role(
    session,
    name: str,
    perms: list[Permission],
    scope_entity: Entity,
    scope: RoleScope = RoleScope.ENTITY_ONLY,
) -> Role:
    """Create an entity-local role (only works in entity context)."""
    role = Role(
        name=name,
        display_name=name,
        description=name,
        is_system_role=False,
        is_global=False,
        scope_entity_id=scope_entity.id,  # Entity-local
        scope=scope,
    )
    role.permissions = perms
    session.add(role)
    await session.flush()
    return role


async def _create_org_scoped_role(
    session, name: str, perms: list[Permission], root_entity: Entity
) -> Role:
    """Create an org-scoped role (works globally within the org)."""
    role = Role(
        name=name,
        display_name=name,
        description=name,
        is_system_role=False,
        is_global=False,
        root_entity_id=root_entity.id,  # Scoped to org
        scope_entity_id=None,  # Not entity-local
    )
    role.permissions = perms
    session.add(role)
    await session.flush()
    return role


async def _create_entity(session, slug: str, parent: Entity | None = None) -> Entity:
    """Create an entity with optional parent."""
    entity = Entity(
        name=slug,
        display_name=slug,
        slug=slug,
        description=slug,
        entity_class=EntityClass.STRUCTURAL,
        entity_type="test",
        parent_id=parent.id if parent else None,
        depth=(parent.depth + 1) if parent else 0,
        status="active",
    )
    entity.update_path(parent.path if parent else None)
    session.add(entity)
    await session.flush()
    return entity


async def _add_closure_self(session, entity: Entity) -> None:
    """Add self-referencing closure row for an entity."""
    session.add(EntityClosure(ancestor_id=entity.id, descendant_id=entity.id, depth=0))
    await session.flush()


async def _add_closure_rows(session, parent: Entity, child: Entity) -> None:
    """Add closure rows for parent-child relationship."""
    # Self references
    session.add(EntityClosure(ancestor_id=parent.id, descendant_id=parent.id, depth=0))
    session.add(EntityClosure(ancestor_id=child.id, descendant_id=child.id, depth=0))
    # Parent-child relationship
    session.add(EntityClosure(ancestor_id=parent.id, descendant_id=child.id, depth=1))
    await session.flush()


async def _assign_user_role(session, user: User, role: Role) -> UserRoleMembership:
    """Assign a role to a user via UserRoleMembership."""
    membership = UserRoleMembership(
        user_id=user.id,
        role_id=role.id,
        status=MembershipStatus.ACTIVE,
    )
    session.add(membership)
    await session.flush()
    return membership


async def _assign_entity_membership(
    session, user: User, entity: Entity, roles: list[Role]
) -> EntityMembership:
    """Create entity membership with roles for a user."""
    membership = EntityMembership(
        user_id=user.id,
        entity_id=entity.id,
        status=MembershipStatus.ACTIVE,
    )
    membership.roles = roles
    session.add(membership)
    await session.flush()
    return membership


# =============================================================================
# DD-054: Global Role Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_global_role_grants_permission_without_entity_context(
    test_session, permission_service: PermissionService
):
    """
    DD-054: Global roles should grant permissions even without entity context.

    Setup:
    - User has a global role with "user:create" permission via UserRoleMembership

    Expected:
    - check_permission(user_id, "user:create") → TRUE (no entity_id provided)
    """
    user = User(email="global-test@example.com")
    test_session.add(user)
    await test_session.flush()

    perm = await _create_permission(test_session, "user:create")
    global_role = await _create_global_role(test_session, "global-admin", [perm])

    await _assign_user_role(test_session, user, global_role)

    # Check permission WITHOUT entity context
    has_permission = await permission_service.check_permission(
        test_session,
        user_id=user.id,
        permission="user:create",
        entity_id=None,  # No entity context
    )
    assert has_permission is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_global_role_grants_permission_with_entity_context(
    test_session, permission_service: PermissionService
):
    """
    DD-054: Global roles should also grant permissions when entity context is provided.

    Setup:
    - User has a global role with "user:create" permission

    Expected:
    - check_permission(user_id, "user:create", entity_id) → TRUE
    """
    user = User(email="global-with-entity@example.com")
    test_session.add(user)
    await test_session.flush()

    perm = await _create_permission(test_session, "user:read")
    global_role = await _create_global_role(test_session, "global-reader", [perm])
    await _assign_user_role(test_session, user, global_role)

    entity = await _create_entity(test_session, "some-entity")
    await _add_closure_self(test_session, entity)

    # Check permission WITH entity context
    has_permission = await permission_service.check_permission(
        test_session,
        user_id=user.id,
        permission="user:read",
        entity_id=entity.id,
    )
    assert has_permission is True


# =============================================================================
# DD-054: Entity-Local Role Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_entity_local_role_denies_permission_without_entity_context(
    test_session, permission_service: PermissionService
):
    """
    DD-054: Entity-local roles should NOT grant permissions without entity context.

    This is the core fix for permission scope leakage.

    Setup:
    - Entity "Marketing" exists
    - Role "team-admin" is scoped to Marketing (scope_entity_id=marketing.id)
    - Role has "user:create" permission
    - User has role via UserRoleMembership

    Expected:
    - check_permission(user_id, "user:create") → FALSE (no entity_id provided)
    """
    user = User(email="entity-local-test@example.com")
    test_session.add(user)
    await test_session.flush()

    marketing = await _create_entity(test_session, "marketing")
    await _add_closure_self(test_session, marketing)

    perm = await _create_permission(test_session, "user:create")
    entity_local_role = await _create_entity_local_role(
        test_session, "marketing-admin", [perm], scope_entity=marketing
    )
    await _assign_user_role(test_session, user, entity_local_role)

    # Check permission WITHOUT entity context - should be DENIED
    has_permission = await permission_service.check_permission(
        test_session,
        user_id=user.id,
        permission="user:create",
        entity_id=None,  # No entity context
    )
    assert has_permission is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_entity_local_role_grants_permission_with_matching_entity_context(
    test_session, permission_service: PermissionService
):
    """
    DD-054: Entity-local roles should grant permissions when checked in correct entity context.

    Setup:
    - Entity "Marketing" exists
    - Role "team-admin" is scoped to Marketing
    - User has role and entity membership at Marketing

    Expected:
    - check_permission(user_id, "user:create", entity_id=marketing.id) → TRUE
    """
    user = User(email="entity-local-match@example.com")
    test_session.add(user)
    await test_session.flush()

    marketing = await _create_entity(test_session, "marketing-match")
    await _add_closure_self(test_session, marketing)

    perm = await _create_permission(test_session, "user:create")
    entity_local_role = await _create_entity_local_role(
        test_session, "marketing-admin-2", [perm], scope_entity=marketing
    )

    # Create entity membership (required for entity-context permission checks)
    await _assign_entity_membership(test_session, user, marketing, [entity_local_role])

    # Check permission WITH matching entity context
    has_permission = await permission_service.check_permission(
        test_session,
        user_id=user.id,
        permission="user:create",
        entity_id=marketing.id,
    )
    assert has_permission is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_entity_local_role_denies_permission_with_wrong_entity_context(
    test_session, permission_service: PermissionService
):
    """
    DD-054: Entity-local roles should NOT grant permissions in a different entity context.

    Setup:
    - Entity "Marketing" and "Sales" exist
    - Role "team-admin" is scoped to Marketing (entity_only)
    - User has membership at Marketing only

    Expected:
    - check_permission(user_id, "user:create", entity_id=sales.id) → FALSE
    """
    user = User(email="wrong-entity-test@example.com")
    test_session.add(user)
    await test_session.flush()

    marketing = await _create_entity(test_session, "marketing-wrong")
    sales = await _create_entity(test_session, "sales-wrong")
    await _add_closure_self(test_session, marketing)
    await _add_closure_self(test_session, sales)

    perm = await _create_permission(test_session, "user:create")
    entity_local_role = await _create_entity_local_role(
        test_session,
        "marketing-admin-3",
        [perm],
        scope_entity=marketing,
        scope=RoleScope.ENTITY_ONLY,
    )

    await _assign_entity_membership(test_session, user, marketing, [entity_local_role])

    # Check permission in WRONG entity context
    has_permission = await permission_service.check_permission(
        test_session,
        user_id=user.id,
        permission="user:create",
        entity_id=sales.id,  # Different entity!
    )
    assert has_permission is False


# =============================================================================
# DD-054: Entity-Local Role with Hierarchy Scope Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_entity_local_role_hierarchy_grants_in_descendant(
    test_session, permission_service: PermissionService
):
    """
    DD-054: Entity-local role with scope=hierarchy grants in descendant entities.

    Setup:
    - Parent entity "Engineering"
    - Child entity "Frontend" (descendant of Engineering)
    - Role "eng-lead" scoped to Engineering with scope=hierarchy
    - Role has "review:approve_tree" permission (tree permissions cascade to descendants)
    - User has membership at Engineering

    Expected:
    - check_permission(user_id, "review:approve", entity_id=frontend.id) → TRUE

    Note: The permission must be a _tree permission for inheritance to work.
    The role's scope=HIERARCHY determines IF the role can grant at descendants,
    but _tree permission semantics determine whether the permission cascades.
    """
    user = User(email="hierarchy-test@example.com")
    test_session.add(user)
    await test_session.flush()

    engineering = await _create_entity(test_session, "engineering-hier")
    frontend = await _create_entity(test_session, "frontend-hier", parent=engineering)
    await _add_closure_rows(test_session, engineering, frontend)

    # Use _tree permission - required for inheritance to descendants
    perm = await _create_permission(test_session, "review:approve_tree")
    hierarchy_role = await _create_entity_local_role(
        test_session,
        "eng-lead",
        [perm],
        scope_entity=engineering,
        scope=RoleScope.HIERARCHY,  # Role can grant to descendants
    )

    await _assign_entity_membership(test_session, user, engineering, [hierarchy_role])

    # Check base permission in descendant entity (tree permission grants base)
    has_permission = await permission_service.check_permission(
        test_session,
        user_id=user.id,
        permission="review:approve",  # Base permission (granted by _tree)
        entity_id=frontend.id,  # Child entity
    )
    assert has_permission is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_entity_local_role_entity_only_denies_in_descendant(
    test_session, permission_service: PermissionService
):
    """
    DD-054: Entity-local role with scope=entity_only does NOT grant in descendants.

    Setup:
    - Parent entity "Engineering"
    - Child entity "Frontend"
    - Role "eng-admin" scoped to Engineering with scope=entity_only
    - User has membership at Engineering

    Expected:
    - check_permission(user_id, "team:manage", entity_id=frontend.id) → FALSE
    """
    user = User(email="entity-only-test@example.com")
    test_session.add(user)
    await test_session.flush()

    engineering = await _create_entity(test_session, "engineering-only")
    frontend = await _create_entity(test_session, "frontend-only", parent=engineering)
    await _add_closure_rows(test_session, engineering, frontend)

    perm = await _create_permission(test_session, "team:manage")
    entity_only_role = await _create_entity_local_role(
        test_session,
        "eng-admin-only",
        [perm],
        scope_entity=engineering,
        scope=RoleScope.ENTITY_ONLY,  # Only at scope entity
    )

    await _assign_entity_membership(test_session, user, engineering, [entity_only_role])

    # Check permission in descendant - should be DENIED
    has_permission = await permission_service.check_permission(
        test_session,
        user_id=user.id,
        permission="team:manage",
        entity_id=frontend.id,  # Child entity
    )
    assert has_permission is False


# =============================================================================
# DD-054: Org-Scoped Role Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_org_scoped_role_grants_permission_without_entity_context(
    test_session, permission_service: PermissionService
):
    """
    DD-054: Org-scoped roles (root_entity_id set, scope_entity_id=NULL) grant globally.

    These roles are scoped to an organization but are NOT entity-local.

    Setup:
    - Organization "Acme Corp" exists
    - Role "org-reader" has root_entity_id=acme.id, scope_entity_id=NULL
    - User has role via UserRoleMembership

    Expected:
    - check_permission(user_id, "report:view") → TRUE (no entity_id)
    """
    user = User(email="org-scoped-test@example.com")
    test_session.add(user)
    await test_session.flush()

    acme = await _create_entity(test_session, "acme-corp")
    await _add_closure_self(test_session, acme)

    perm = await _create_permission(test_session, "report:view")
    org_role = await _create_org_scoped_role(
        test_session, "org-reader", [perm], root_entity=acme
    )

    await _assign_user_role(test_session, user, org_role)

    # Check permission WITHOUT entity context
    has_permission = await permission_service.check_permission(
        test_session,
        user_id=user.id,
        permission="report:view",
        entity_id=None,
    )
    assert has_permission is True


# =============================================================================
# DD-054: Mixed Roles Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_mixed_roles_only_global_applies_without_context(
    test_session, permission_service: PermissionService
):
    """
    DD-054: When user has both global and entity-local roles,
    only global role permissions apply without entity context.

    Setup:
    - User has global role with "user:read_own" permission
    - User has entity-local role with "user:create" permission
    - Both assigned via UserRoleMembership

    Expected:
    - check_permission("user:read_own") → TRUE (from global role)
    - check_permission("user:create") → FALSE (entity-local role ignored)
    """
    user = User(email="mixed-roles-test@example.com")
    test_session.add(user)
    await test_session.flush()

    # Create entity for the entity-local role
    marketing = await _create_entity(test_session, "marketing-mixed")
    await _add_closure_self(test_session, marketing)

    # Global permission
    perm_read = await _create_permission(test_session, "user:read_own")
    global_role = await _create_global_role(test_session, "basic-user", [perm_read])

    # Entity-local permission
    perm_create = await _create_permission(test_session, "user:create")
    entity_local_role = await _create_entity_local_role(
        test_session, "team-lead", [perm_create], scope_entity=marketing
    )

    # Assign both roles to user
    await _assign_user_role(test_session, user, global_role)
    await _assign_user_role(test_session, user, entity_local_role)

    # Global role permission should work without entity context
    has_read = await permission_service.check_permission(
        test_session,
        user_id=user.id,
        permission="user:read_own",
        entity_id=None,
    )
    assert has_read is True

    # Entity-local role permission should NOT work without entity context
    has_create = await permission_service.check_permission(
        test_session,
        user_id=user.id,
        permission="user:create",
        entity_id=None,
    )
    assert has_create is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_mixed_roles_both_apply_with_entity_context(
    test_session, permission_service: PermissionService
):
    """
    DD-054: When user has both global and entity-local roles,
    both apply when entity context is provided.

    Setup:
    - User has global role with "user:read" permission
    - User has entity-local role at Marketing with "user:create" permission
    - User has entity membership at Marketing

    Expected:
    - check_permission("user:read", entity_id=marketing) → TRUE
    - check_permission("user:create", entity_id=marketing) → TRUE
    """
    user = User(email="mixed-with-context@example.com")
    test_session.add(user)
    await test_session.flush()

    marketing = await _create_entity(test_session, "marketing-both")
    await _add_closure_self(test_session, marketing)

    perm_read = await _create_permission(test_session, "user:read")
    global_role = await _create_global_role(test_session, "reader-role", [perm_read])

    perm_create = await _create_permission(test_session, "user:create")
    entity_local_role = await _create_entity_local_role(
        test_session, "creator-role", [perm_create], scope_entity=marketing
    )

    # Assign global role via UserRoleMembership
    await _assign_user_role(test_session, user, global_role)

    # Assign entity-local role via EntityMembership
    await _assign_entity_membership(test_session, user, marketing, [entity_local_role])

    # Both should work with entity context
    has_read = await permission_service.check_permission(
        test_session,
        user_id=user.id,
        permission="user:read",
        entity_id=marketing.id,
    )
    assert has_read is True

    has_create = await permission_service.check_permission(
        test_session,
        user_id=user.id,
        permission="user:create",
        entity_id=marketing.id,
    )
    assert has_create is True


# =============================================================================
# DD-054: Superuser Bypass Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_superuser_bypasses_all_scope_checks(
    test_session, permission_service: PermissionService
):
    """
    DD-054: Superusers should bypass all permission and scope checks.

    Setup:
    - Superuser with no roles assigned

    Expected:
    - check_permission("anything:at_all") → TRUE (superuser bypass)
    """
    superuser = User(email="superuser@example.com", is_superuser=True)
    test_session.add(superuser)
    await test_session.flush()

    # Check arbitrary permission without any roles
    has_permission = await permission_service.check_permission(
        test_session,
        user_id=superuser.id,
        permission="random:permission",
        entity_id=None,
    )
    assert has_permission is True


# =============================================================================
# DD-054: get_user_permissions Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_user_permissions_excludes_entity_local_when_requested(
    test_session, permission_service: PermissionService
):
    """
    DD-054: get_user_permissions(include_entity_local=False) should exclude
    permissions from entity-local roles.

    Setup:
    - User has global role with "perm:global"
    - User has entity-local role with "perm:local"

    Expected:
    - get_user_permissions(include_entity_local=True) returns both
    - get_user_permissions(include_entity_local=False) returns only global
    """
    user = User(email="get-perms-test@example.com")
    test_session.add(user)
    await test_session.flush()

    entity = await _create_entity(test_session, "get-perms-entity")
    await _add_closure_self(test_session, entity)

    perm_global = await _create_permission(test_session, "perm:global")
    global_role = await _create_global_role(
        test_session, "global-for-get", [perm_global]
    )

    perm_local = await _create_permission(test_session, "perm:local")
    local_role = await _create_entity_local_role(
        test_session, "local-for-get", [perm_local], scope_entity=entity
    )

    await _assign_user_role(test_session, user, global_role)
    await _assign_user_role(test_session, user, local_role)

    # With include_entity_local=True (default)
    all_perms = await permission_service.get_user_permissions(
        test_session, user.id, include_entity_local=True
    )
    assert "perm:global" in all_perms
    assert "perm:local" in all_perms

    # With include_entity_local=False
    global_only_perms = await permission_service.get_user_permissions(
        test_session, user.id, include_entity_local=False
    )
    assert "perm:global" in global_only_perms
    assert "perm:local" not in global_only_perms
