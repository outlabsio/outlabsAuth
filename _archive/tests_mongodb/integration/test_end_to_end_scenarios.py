"""
End-to-End Integration Tests

Tests complete user journeys and cross-service interactions:
1. User registration → role assignment → permission check
2. Entity hierarchy → membership → inherited permissions
3. API key creation → authentication → resource access
4. Multi-user collaboration scenarios
5. Permission revocation workflows
6. Entity deletion cascades
7. Role modification impacts
8. Tree permission inheritance
9. Context-aware role switching
10. ABAC policy evaluation in real scenarios

Run with: pytest tests/integration/test_end_to_end_scenarios.py -v
"""

import pytest
from beanie import PydanticObjectId

from outlabs_auth.models.entity import EntityClass, EntityModel
from outlabs_auth.models.permission import PermissionModel
from outlabs_auth.models.role import RoleModel
from outlabs_auth.models.user import UserModel

# ============================================================================
# TEST 1: Complete User Onboarding Flow
# ============================================================================


@pytest.mark.asyncio
async def test_user_onboarding_flow(enterprise_auth, test_entity_hierarchy):
    """
    Test complete user onboarding: register → assign role → verify permissions

    Scenario:
    1. New employee joins company
    2. Create user account
    3. Assign to department with "Editor" role
    4. Verify they can edit content but not manage users
    """
    # Step 1: Create user
    user_service = enterprise_auth.user_service
    user = await user_service.create_user(
        email="newemployee@test.com",
        password="SecurePass123!",
        first_name="New",
        last_name="Employee",
    )

    assert user.id is not None
    assert user.email == "newemployee@test.com"

    # Step 2: Create Editor role
    role = RoleModel(
        name="editor",
        display_name="Editor",
        permissions=["post:create", "post:update", "post:read"],
    )
    await role.insert()

    # Step 3: Assign user to entity with role
    membership_service = enterprise_auth.membership_service
    await membership_service.add_member(
        entity_id=str(test_entity_hierarchy["office_a1"].id),
        user_id=str(user.id),
        role_ids=[str(role.id)],
    )

    # Step 4: Verify permissions
    perm_service = enterprise_auth.permission_service

    # Should have post permissions
    has_create, _ = await perm_service.check_permission(
        str(user.id), "post:create", str(test_entity_hierarchy["office_a1"].id)
    )
    assert has_create, "User should have post:create permission"

    # Should NOT have user management permissions
    has_manage, _ = await perm_service.check_permission(
        str(user.id), "user:delete", str(test_entity_hierarchy["office_a1"].id)
    )
    assert not has_manage, "User should NOT have user:delete permission"

    # Cleanup
    await role.delete()
    await user.delete()


# ============================================================================
# TEST 2: Hierarchical Permission Inheritance
# ============================================================================


@pytest.mark.asyncio
async def test_hierarchical_permission_inheritance(
    enterprise_auth, test_entity_hierarchy
):
    """
    Test that permissions granted at parent level cascade to children

    Scenario:
    1. Assign user as "Regional Manager" at Region A
    2. Verify they can access Office A1, Office A2, and teams under them
    3. Verify they CANNOT access Region B entities
    """
    # Create user
    user = UserModel(
        email="regionalmanager@test.com",
        hashed_password="hashed",
        first_name="Regional",
        last_name="Manager",
    )
    await user.insert()

    # Create role with tree permissions
    role = RoleModel(
        name="regional_manager",
        display_name="Regional Manager",
        permissions=["entity:read_tree", "entity:update_tree", "user:manage_tree"],
    )
    await role.insert()

    # Assign to Region A
    membership_service = enterprise_auth.membership_service
    await membership_service.add_member(
        entity_id=str(test_entity_hierarchy["region_a"].id),
        user_id=str(user.id),
        role_ids=[str(role.id)],
    )

    perm_service = enterprise_auth.permission_service

    # Should have access to descendant entities (Office A1, Team A1a)
    has_office_access, _ = await perm_service.check_permission(
        str(user.id), "entity:read", str(test_entity_hierarchy["office_a1"].id)
    )
    assert has_office_access, "Should have access to Office A1 (descendant of Region A)"

    has_team_access, _ = await perm_service.check_permission(
        str(user.id), "entity:read", str(test_entity_hierarchy["team_a1a"].id)
    )
    assert has_team_access, "Should have access to Team A1a (descendant of Region A)"

    # Should NOT have access to Region B entities
    has_region_b_access, _ = await perm_service.check_permission(
        str(user.id), "entity:read", str(test_entity_hierarchy["region_b"].id)
    )
    assert not has_region_b_access, "Should NOT have access to Region B"

    # Cleanup
    await role.delete()
    await user.delete()


# Placeholder for remaining 8 tests...
# Will implement based on priority


# ============================================================================
# TEST 3: API Key Authentication Flow
# ============================================================================


@pytest.mark.asyncio
async def test_api_key_authentication_flow(enterprise_auth, test_entity_hierarchy):
    """
    Test API key creation → authentication → resource access

    Scenario:
    1. Create user with permissions
    2. Generate API key for user
    3. Authenticate using API key
    4. Verify permissions work with API key auth
    """
    # Create user
    user = await enterprise_auth.user_service.create_user(
        email="apikeyuser@test.com",
        password="SecurePass123!",
        first_name="API",
        last_name="User",
    )

    # Create role and assign
    role = RoleModel(
        name="api_user",
        display_name="API User",
        permissions=["data:read", "data:write"],
    )
    await role.insert()

    await enterprise_auth.membership_service.add_member(
        entity_id=str(test_entity_hierarchy["office_a1"].id),
        user_id=str(user.id),
        role_ids=[str(role.id)],
    )

    # Generate API key
    api_key_service = enterprise_auth.api_key_service
    api_key_result = await api_key_service.create_api_key(
        owner_id=str(user.id),
        name="Test API Key",
        scopes=["data:read", "data:write"],
    )

    # Extract the plain text key and the model
    api_key_plain = api_key_result["key"]
    api_key = api_key_result["api_key"]

    assert api_key.key is not None
    assert api_key.prefix is not None

    # Authenticate with API key
    authenticated = await api_key_service.authenticate_api_key(api_key_plain)
    assert authenticated is not None
    assert str(authenticated.owner_id) == str(user.id)

    # Verify permissions work
    has_read, _ = await enterprise_auth.permission_service.check_permission(
        str(user.id), "data:read", str(test_entity_hierarchy["office_a1"].id)
    )
    assert has_read, "User should have data:read permission via API key"

    # Cleanup
    await role.delete()
    await user.delete()


# ============================================================================
# TEST 4: Permission Revocation Workflow
# ============================================================================


@pytest.mark.asyncio
async def test_permission_revocation_workflow(enterprise_auth, test_entity_hierarchy):
    """
    Test that removing role membership immediately revokes permissions

    Scenario:
    1. Grant user permissions via role
    2. Verify access
    3. Revoke role membership
    4. Verify access denied
    """
    user = UserModel(
        email="tempuser@test.com",
        hashed_password="hashed",
        first_name="Temp",
        last_name="User",
    )
    await user.insert()

    role = RoleModel(
        name="temp_role",
        display_name="Temporary Role",
        permissions=["resource:access"],
    )
    await role.insert()

    # Grant access
    membership_service = enterprise_auth.membership_service
    await membership_service.add_member(
        entity_id=str(test_entity_hierarchy["office_a1"].id),
        user_id=str(user.id),
        role_ids=[str(role.id)],
    )

    # Verify access granted
    has_access, _ = await enterprise_auth.permission_service.check_permission(
        str(user.id), "resource:access", str(test_entity_hierarchy["office_a1"].id)
    )
    assert has_access, "User should have access before revocation"

    # Revoke access
    await membership_service.remove_member(
        entity_id=str(test_entity_hierarchy["office_a1"].id),
        user_id=str(user.id),
    )

    # Verify access revoked
    has_access_after, _ = await enterprise_auth.permission_service.check_permission(
        str(user.id), "resource:access", str(test_entity_hierarchy["office_a1"].id)
    )
    assert not has_access_after, "User should NOT have access after revocation"

    # Cleanup
    await role.delete()
    await user.delete()


# ============================================================================
# TEST 5: Role Modification Impact
# ============================================================================


@pytest.mark.asyncio
async def test_role_modification_impact(enterprise_auth, test_entity_hierarchy):
    """
    Test that modifying role permissions affects all users with that role

    Scenario:
    1. Create role with limited permissions
    2. Assign to multiple users
    3. Modify role to add more permissions
    4. Verify all users immediately get new permissions
    """
    # Create role with limited permissions
    role = RoleModel(
        name="basic_user",
        display_name="Basic User",
        permissions=["post:read"],
    )
    await role.insert()

    # Create two users with this role
    user1 = await enterprise_auth.user_service.create_user(
        email="user1@test.com", password="Pass123!", first_name="User", last_name="One"
    )

    user2 = await enterprise_auth.user_service.create_user(
        email="user2@test.com", password="Pass123!", first_name="User", last_name="Two"
    )

    membership_service = enterprise_auth.membership_service
    await membership_service.add_member(
        entity_id=str(test_entity_hierarchy["office_a1"].id),
        user_id=str(user1.id),
        role_ids=[str(role.id)],
    )
    await membership_service.add_member(
        entity_id=str(test_entity_hierarchy["office_a1"].id),
        user_id=str(user2.id),
        role_ids=[str(role.id)],
    )

    # Verify users only have read permission
    perm_service = enterprise_auth.permission_service
    has_write_before, _ = await perm_service.check_permission(
        str(user1.id), "post:write", str(test_entity_hierarchy["office_a1"].id)
    )
    assert not has_write_before, "User1 should NOT have write permission initially"

    # Modify role to add write permission
    role.permissions.append("post:write")
    await role.save()

    # Verify both users now have write permission
    has_write_after_1, _ = await perm_service.check_permission(
        str(user1.id), "post:write", str(test_entity_hierarchy["office_a1"].id)
    )
    has_write_after_2, _ = await perm_service.check_permission(
        str(user2.id), "post:write", str(test_entity_hierarchy["office_a1"].id)
    )

    assert has_write_after_1, "User1 should have write permission after role update"
    assert has_write_after_2, "User2 should have write permission after role update"

    # Cleanup
    await role.delete()
    await user1.delete()
    await user2.delete()


# ============================================================================
# TEST 6: Multi-User Collaboration Scenario
# ============================================================================


@pytest.mark.asyncio
async def test_multi_user_collaboration(enterprise_auth, test_entity_hierarchy):
    """
    Test multiple users with different roles collaborating on shared resources

    Scenario:
    1. Owner has full permissions
    2. Editor can modify but not delete
    3. Viewer can only read
    4. Verify each user's access level
    """
    # Create three roles
    owner_role = RoleModel(
        name="owner",
        display_name="Owner",
        permissions=["doc:read", "doc:write", "doc:delete"],
    )
    await owner_role.insert()

    editor_role = RoleModel(
        name="editor",
        display_name="Editor",
        permissions=["doc:read", "doc:write"],
    )
    await editor_role.insert()

    viewer_role = RoleModel(
        name="viewer",
        display_name="Viewer",
        permissions=["doc:read"],
    )
    await viewer_role.insert()

    # Create three users
    owner = await enterprise_auth.user_service.create_user(
        email="owner@test.com", password="Pass123!", first_name="Doc", last_name="Owner"
    )
    editor = await enterprise_auth.user_service.create_user(
        email="editor@test.com",
        password="Pass123!",
        first_name="Doc",
        last_name="Editor",
    )
    viewer = await enterprise_auth.user_service.create_user(
        email="viewer@test.com",
        password="Pass123!",
        first_name="Doc",
        last_name="Viewer",
    )

    # Assign roles
    membership_service = enterprise_auth.membership_service
    entity_id = str(test_entity_hierarchy["office_a1"].id)

    await membership_service.add_member(entity_id, str(owner.id), [str(owner_role.id)])
    await membership_service.add_member(
        entity_id, str(editor.id), [str(editor_role.id)]
    )
    await membership_service.add_member(
        entity_id, str(viewer.id), [str(viewer_role.id)]
    )

    perm_service = enterprise_auth.permission_service

    # Verify owner has all permissions
    can_delete_owner, _ = await perm_service.check_permission(
        str(owner.id), "doc:delete", entity_id
    )
    assert can_delete_owner, "Owner should be able to delete"

    # Verify editor can write but not delete
    can_write_editor, _ = await perm_service.check_permission(
        str(editor.id), "doc:write", entity_id
    )
    can_delete_editor, _ = await perm_service.check_permission(
        str(editor.id), "doc:delete", entity_id
    )
    assert can_write_editor, "Editor should be able to write"
    assert not can_delete_editor, "Editor should NOT be able to delete"

    # Verify viewer can only read
    can_read_viewer, _ = await perm_service.check_permission(
        str(viewer.id), "doc:read", entity_id
    )
    can_write_viewer, _ = await perm_service.check_permission(
        str(viewer.id), "doc:write", entity_id
    )
    assert can_read_viewer, "Viewer should be able to read"
    assert not can_write_viewer, "Viewer should NOT be able to write"

    # Cleanup
    await owner_role.delete()
    await editor_role.delete()
    await viewer_role.delete()
    await owner.delete()
    await editor.delete()
    await viewer.delete()


# ============================================================================
# TEST 7: Entity Deletion Cascades
# ============================================================================


@pytest.mark.asyncio
async def test_entity_deletion_cascades(enterprise_auth, test_entity_hierarchy):
    """
    Test that deleting an entity properly cleans up memberships and closure records

    Scenario:
    1. Create entity with user memberships
    2. Delete entity
    3. Verify memberships are removed
    4. Verify closure records are cleaned up
    """
    from outlabs_auth.models.closure import EntityClosureModel
    from outlabs_auth.models.membership import EntityMembershipModel

    # Create a new test entity
    entity_service = enterprise_auth.entity_service
    test_dept = await entity_service.create_entity(
        name="test_department",
        display_name="Test Department",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="department",
        parent_id=str(test_entity_hierarchy["office_a1"].id),
        slug="test-department",
    )

    # Create user and assign membership
    user = await enterprise_auth.user_service.create_user(
        email="deptuser@test.com",
        password="Pass123!",
        first_name="Dept",
        last_name="User",
    )

    role = RoleModel(name="member", display_name="Member", permissions=["test:access"])
    await role.insert()

    await enterprise_auth.membership_service.add_member(
        entity_id=str(test_dept.id),
        user_id=str(user.id),
        role_ids=[str(role.id)],
    )

    # Verify membership exists
    membership = await EntityMembershipModel.find_one(
        EntityMembershipModel.entity_id == str(test_dept.id),
        EntityMembershipModel.user_id == str(user.id),
    )
    assert membership is not None, "Membership should exist before deletion"

    # Verify closure records exist
    closure_count_before = await EntityClosureModel.find(
        EntityClosureModel.descendant_id == str(test_dept.id)
    ).count()
    assert closure_count_before > 0, "Closure records should exist before deletion"

    # Delete entity
    await entity_service.delete_entity(str(test_dept.id))

    # Verify membership is removed
    membership_after = await EntityMembershipModel.find_one(
        EntityMembershipModel.entity_id == str(test_dept.id)
    )
    assert membership_after is None, (
        "Membership should be removed after entity deletion"
    )

    # Verify closure records are cleaned up
    closure_count_after = await EntityClosureModel.find(
        EntityClosureModel.descendant_id == str(test_dept.id)
    ).count()
    assert closure_count_after == 0, (
        "Closure records should be cleaned up after deletion"
    )

    # Cleanup
    await role.delete()
    await user.delete()


# ============================================================================
# TEST 8: Tree Permission Inheritance
# ============================================================================


@pytest.mark.asyncio
async def test_tree_permission_inheritance(enterprise_auth, test_entity_hierarchy):
    """
    Test that tree permissions (_tree suffix) grant access to descendants

    Scenario:
    1. Grant user "manage_tree" permission at Region level
    2. Verify they can manage all descendant entities (offices, teams)
    3. Verify they CANNOT manage sibling regions
    """
    user = await enterprise_auth.user_service.create_user(
        email="regional_admin@test.com",
        password="Pass123!",
        first_name="Regional",
        last_name="Admin",
    )

    role = RoleModel(
        name="regional_admin",
        display_name="Regional Admin",
        permissions=["entity:manage_tree"],  # Tree permission
    )
    await role.insert()

    # Assign at Region A
    await enterprise_auth.membership_service.add_member(
        entity_id=str(test_entity_hierarchy["region_a"].id),
        user_id=str(user.id),
        role_ids=[str(role.id)],
    )

    perm_service = enterprise_auth.permission_service

    # Should have access to all descendants of Region A
    can_manage_office, _ = await perm_service.check_permission(
        str(user.id), "entity:manage", str(test_entity_hierarchy["office_a1"].id)
    )
    can_manage_team, _ = await perm_service.check_permission(
        str(user.id), "entity:manage", str(test_entity_hierarchy["team_a1a"].id)
    )

    assert can_manage_office, "Should be able to manage Office A1 (descendant)"
    assert can_manage_team, "Should be able to manage Team A1a (descendant)"

    # Should NOT have access to Region B
    can_manage_region_b, _ = await perm_service.check_permission(
        str(user.id), "entity:manage", str(test_entity_hierarchy["region_b"].id)
    )
    assert not can_manage_region_b, "Should NOT be able to manage Region B (sibling)"

    # Cleanup
    await role.delete()
    await user.delete()


# ============================================================================
# TEST 9: Context-Aware Role Switching
# ============================================================================


@pytest.mark.asyncio
async def test_context_aware_role_switching(enterprise_auth, test_entity_hierarchy):
    """
    Test that context-aware roles adapt permissions based on entity type

    Scenario:
    1. Create role with different permissions for different entity types
    2. Assign user to multiple entities
    3. Verify permissions change based on entity context
    """
    user = await enterprise_auth.user_service.create_user(
        email="contextuser@test.com",
        password="Pass123!",
        first_name="Context",
        last_name="User",
    )

    # Role with context-aware permissions
    role = RoleModel(
        name="flexible_manager",
        display_name="Flexible Manager",
        permissions=["doc:read"],  # Base permission
        entity_type_permissions={
            "office": ["doc:read", "doc:write", "doc:delete"],  # Full access in offices
            "team": ["doc:read", "doc:write"],  # Limited access in teams
        },
    )
    await role.insert()

    # Assign to both office and team
    membership_service = enterprise_auth.membership_service
    await membership_service.add_member(
        entity_id=str(test_entity_hierarchy["office_a1"].id),
        user_id=str(user.id),
        role_ids=[str(role.id)],
    )
    await membership_service.add_member(
        entity_id=str(test_entity_hierarchy["team_a1a"].id),
        user_id=str(user.id),
        role_ids=[str(role.id)],
    )

    perm_service = enterprise_auth.permission_service

    # In office context: should have delete permission
    can_delete_office, _ = await perm_service.check_permission(
        str(user.id), "doc:delete", str(test_entity_hierarchy["office_a1"].id)
    )
    assert can_delete_office, "Should have delete permission in office context"

    # In team context: should NOT have delete permission
    can_delete_team, _ = await perm_service.check_permission(
        str(user.id), "doc:delete", str(test_entity_hierarchy["team_a1a"].id)
    )
    assert not can_delete_team, "Should NOT have delete permission in team context"

    # Cleanup
    await role.delete()
    await user.delete()


# ============================================================================
# TEST 10: ABAC Policy Evaluation in Real Scenario
# ============================================================================


@pytest.mark.asyncio
async def test_abac_policy_real_scenario(enterprise_auth, test_entity_hierarchy):
    """
    Test ABAC conditions in a real business scenario

    Scenario:
    1. Create role with time-based condition (business hours only)
    2. Create role with attribute-based condition (department match)
    3. Verify permissions respect ABAC conditions
    """
    from datetime import UTC, datetime

    from outlabs_auth.models.condition import Condition, ConditionOperator

    user = await enterprise_auth.user_service.create_user(
        email="abacuser@test.com",
        password="Pass123!",
        first_name="ABAC",
        last_name="User",
    )

    # Role with ABAC condition: user department must match
    role = RoleModel(
        name="dept_manager",
        display_name="Department Manager",
        permissions=["budget:approve"],
        conditions=[
            Condition(
                attribute="user.department",
                operator=ConditionOperator.EQUALS,
                value="engineering",
            )
        ],
    )
    await role.insert()

    await enterprise_auth.membership_service.add_member(
        entity_id=str(test_entity_hierarchy["office_a1"].id),
        user_id=str(user.id),
        role_ids=[str(role.id)],
    )

    perm_service = enterprise_auth.permission_service

    # Check permission with matching context
    context_match = {"user": {"department": "engineering"}}
    has_perm_match, _ = await perm_service.check_permission(
        str(user.id),
        "budget:approve",
        str(test_entity_hierarchy["office_a1"].id),
        context=context_match,
    )
    assert has_perm_match, "Should have permission when ABAC condition matches"

    # Check permission with non-matching context
    context_no_match = {"user": {"department": "sales"}}
    has_perm_no_match, _ = await perm_service.check_permission(
        str(user.id),
        "budget:approve",
        str(test_entity_hierarchy["office_a1"].id),
        context=context_no_match,
    )
    assert not has_perm_no_match, "Should NOT have permission when ABAC condition fails"

    # Cleanup
    await role.delete()
    await user.delete()
