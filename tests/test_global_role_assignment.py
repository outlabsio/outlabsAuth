"""
Test global role assignment functionality
"""
import pytest
from api.models import UserModel, EntityModel, RoleModel, EntityMembershipModel
from api.models.user_model import UserProfile
from api.services.user_service import UserService
from api.services.auth_service import AuthService


@pytest.mark.asyncio
async def test_global_role_assignment(
    system_auth_headers,
    system_user,
    test_platform,
    test_organization
):
    """Test that global roles can be assigned to users in any entity"""
    # Create a global role at platform level
    global_role = RoleModel(
        name="global_member",
        display_name="Global Member",
        description="A globally assignable role",
        permissions=["resource:read"],
        entity=test_platform,
        is_global=True,  # This makes it assignable anywhere
        is_system_role=False
    )
    await global_role.save()
    
    # Create a test user
    auth_service = AuthService()
    test_user = UserModel(
        email="test.global.role@example.com",
        profile=UserProfile(first_name="Test", last_name="Global"),
        is_active=True,
        hashed_password=auth_service.hash_password("TestPassword123!")
    )
    await test_user.save()
    
    # Assign the global role to the user in a child entity
    entity_assignments = [{
        "entity_id": str(test_organization.id),
        "role_ids": [str(global_role.id)],
        "status": "active"
    }]
    
    # Update user entities
    updated_user = await UserService.update_user_entities(
        user_id=str(test_user.id),
        entity_assignments=entity_assignments,
        current_user=system_user
    )
    
    # Verify the membership was created
    membership = await EntityMembershipModel.find_one(
        EntityMembershipModel.user.id == test_user.id,
        EntityMembershipModel.entity.id == test_organization.id
    )
    
    assert membership is not None
    assert membership.status == "active"
    assert len(membership.roles) == 1
    
    # Fetch role to verify
    await membership.fetch_all_links()
    assert membership.roles[0].name == "global_member"
    assert membership.roles[0].is_global is True
    
    # Clean up
    await membership.delete()
    await test_user.delete()
    await global_role.delete()


@pytest.mark.asyncio
async def test_non_global_role_assignment_restriction(
    system_auth_headers,
    system_user,
    test_platform,
    test_organization
):
    """Test that non-global roles cannot be assigned outside their entity"""
    # Create a non-global role specific to platform
    platform_role = RoleModel(
        name="platform_only_role",
        display_name="Platform Only Role",
        description="Role only for platform entity",
        permissions=["platform:manage"],
        entity=test_platform,
        is_global=False,  # NOT globally assignable
        is_system_role=False
    )
    await platform_role.save()
    
    # Create a test user
    auth_service = AuthService()
    test_user = UserModel(
        email="test.restricted.role@example.com",
        profile=UserProfile(first_name="Test", last_name="Restricted"),
        is_active=True,
        hashed_password=auth_service.hash_password("TestPassword123!")
    )
    await test_user.save()
    
    # Try to assign the platform-only role to the user in a child entity
    entity_assignments = [{
        "entity_id": str(test_organization.id),
        "role_ids": [str(platform_role.id)],
        "status": "active"
    }]
    
    # Update user entities
    updated_user = await UserService.update_user_entities(
        user_id=str(test_user.id),
        entity_assignments=entity_assignments,
        current_user=system_user
    )
    
    # Verify the membership was created but role was NOT assigned
    membership = await EntityMembershipModel.find_one(
        EntityMembershipModel.user.id == test_user.id,
        EntityMembershipModel.entity.id == test_organization.id
    )
    
    assert membership is not None
    assert membership.status == "active"
    assert len(membership.roles) == 0  # Role should NOT be assigned
    
    # Clean up
    await membership.delete()
    await test_user.delete()
    await platform_role.delete()


@pytest.mark.asyncio
async def test_assignable_at_types_role(
    system_auth_headers,
    system_user,
    test_platform,
    test_organization
):
    """Test roles with assignable_at_types work correctly"""
    # Create another organization to test
    other_org = EntityModel(
        name="other_organization",
        display_name="Other Organization",
        entity_type="organization",
        entity_class="STRUCTURAL",
        parent_entity=test_platform
    )
    await other_org.save()
    
    # Create a role assignable at organization level
    org_role = RoleModel(
        name="organization_admin",
        display_name="Organization Administrator",
        description="Admin role for organizations",
        permissions=["organization:manage"],
        entity=test_platform,  # Owned by platform
        assignable_at_types=["organization"],  # But assignable at org level
        is_global=False,
        is_system_role=False
    )
    await org_role.save()
    
    # Create a test user
    auth_service = AuthService()
    test_user = UserModel(
        email="test.org.admin@example.com",
        profile=UserProfile(first_name="Test", last_name="OrgAdmin"),
        is_active=True,
        hashed_password=auth_service.hash_password("TestPassword123!")
    )
    await test_user.save()
    
    # Assign the role to user in an organization
    entity_assignments = [{
        "entity_id": str(test_organization.id),
        "role_ids": [str(org_role.id)],
        "status": "active"
    }]
    
    # Update user entities
    updated_user = await UserService.update_user_entities(
        user_id=str(test_user.id),
        entity_assignments=entity_assignments,
        current_user=system_user
    )
    
    # Verify the membership and role were assigned
    membership = await EntityMembershipModel.find_one(
        EntityMembershipModel.user.id == test_user.id,
        EntityMembershipModel.entity.id == test_organization.id
    )
    
    assert membership is not None
    assert len(membership.roles) == 1
    
    await membership.fetch_all_links()
    assert membership.roles[0].name == "organization_admin"
    
    # Clean up
    await membership.delete()
    await test_user.delete()
    await org_role.delete()
    await other_org.delete()