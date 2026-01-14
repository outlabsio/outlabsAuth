"""
Tests for context-aware roles (Phase 4.1)

Context-aware roles allow permissions to vary based on entity type.
For example, a "Regional Manager" role might have different permissions
in a region vs. in a specific office.
"""
import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from outlabs_auth.models.user import UserModel
from outlabs_auth.models.role import RoleModel
from outlabs_auth.models.entity import EntityModel, EntityClass
from outlabs_auth.models.membership import EntityMembershipModel
from outlabs_auth.models.closure import EntityClosureModel
from outlabs_auth.services.entity import EntityService
from outlabs_auth.services.membership import MembershipService
from outlabs_auth.services.permission import EnterprisePermissionService
from outlabs_auth.core.config import EnterpriseConfig


@pytest.fixture
async def database():
    """Create a test database connection"""
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["outlabs_auth_test_context_aware"]

    # Initialize Beanie
    await init_beanie(
        database=db,
        document_models=[
            UserModel,
            RoleModel,
            EntityModel,
            EntityMembershipModel,
            EntityClosureModel,
        ]
    )

    # Clean up before tests
    await UserModel.delete_all()
    await RoleModel.delete_all()
    await EntityModel.delete_all()
    await EntityMembershipModel.delete_all()
    await EntityClosureModel.delete_all()

    yield db

    # Clean up after tests
    await UserModel.delete_all()
    await RoleModel.delete_all()
    await EntityModel.delete_all()
    await EntityMembershipModel.delete_all()
    await EntityClosureModel.delete_all()


@pytest.fixture
def config():
    """Create test configuration"""
    return EnterpriseConfig(
        secret_key="test-secret-key-12345",
        redis_enabled=False,  # Disable Redis for these tests
    )


@pytest.fixture
async def test_user(database):
    """Create a test user"""
    user = UserModel(
        email="contexttest@example.com",
        username="contexttest",
        hashed_password="test_hash",
        is_superuser=False,
    )
    await user.save()
    return user


@pytest.fixture
async def entity_hierarchy(database, config):
    """Create a test entity hierarchy: Platform -> Region -> Office -> Team"""
    entity_service = EntityService(config=config, redis_client=None)

    # Create platform
    platform = await entity_service.create_entity(
        name="acme_corp",
        display_name="Acme Corp",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="platform",
    )

    # Create region
    region = await entity_service.create_entity(
        name="west_region",
        display_name="West Region",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="region",
        parent_id=str(platform.id),
    )

    # Create office
    office = await entity_service.create_entity(
        name="sf_office",
        display_name="San Francisco Office",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="office",
        parent_id=str(region.id),
    )

    # Create team
    team = await entity_service.create_entity(
        name="engineering",
        display_name="Engineering Team",
        entity_class=EntityClass.STRUCTURAL,
        entity_type="team",
        parent_id=str(office.id),
    )

    return {
        "platform": platform,
        "region": region,
        "office": office,
        "team": team,
    }


@pytest.mark.asyncio
async def test_context_aware_role_basic(database, config, test_user, entity_hierarchy):
    """Test basic context-aware role functionality"""
    # Create a context-aware role
    regional_manager_role = RoleModel(
        name="regional_manager",
        display_name="Regional Manager",
        permissions=["entity:read", "user:read"],  # Default permissions
        entity_type_permissions={
            "region": ["entity:update_tree", "user:update_tree"],  # Tree permissions in regions
            "office": ["entity:update", "user:update"],  # Limited management in offices
            "team": ["entity:read", "user:read"],  # Read-only in teams
        }
    )
    await regional_manager_role.save()

    # Add user as member of region with this role
    membership_service = MembershipService(config=config)
    await membership_service.add_member(
        entity_id=str(entity_hierarchy["region"].id),
        user_id=str(test_user.id),
        role_ids=[str(regional_manager_role.id)],
    )

    # Test permissions
    perm_service = EnterprisePermissionService(database, config, redis_client=None)

    # In region: should have update_tree permission
    has_perm, source = await perm_service.check_permission(
        str(test_user.id),
        "entity:update_tree",
        str(entity_hierarchy["region"].id)
    )
    assert has_perm is True
    assert source == "direct"

    # In office (child of region): should have update permission via tree
    has_perm, source = await perm_service.check_permission(
        str(test_user.id),
        "entity:update",
        str(entity_hierarchy["office"].id)
    )
    assert has_perm is True
    assert source == "tree"  # Via entity:update_tree permission from region

    # Clean up
    await regional_manager_role.delete()


@pytest.mark.asyncio
async def test_context_aware_permissions_in_different_types(database, config, test_user, entity_hierarchy):
    """Test that permissions vary correctly based on entity type"""
    # Create context-aware role
    flexible_role = RoleModel(
        name="flexible_manager",
        display_name="Flexible Manager",
        permissions=["entity:read"],  # Default: read-only
        entity_type_permissions={
            "office": ["entity:update", "entity:delete", "user:manage"],
            "team": ["entity:read", "user:read"],
        }
    )
    await flexible_role.save()

    # Add user to both office and team
    membership_service = MembershipService(config=config)

    await membership_service.add_member(
        entity_id=str(entity_hierarchy["office"].id),
        user_id=str(test_user.id),
        role_ids=[str(flexible_role.id)],
    )

    await membership_service.add_member(
        entity_id=str(entity_hierarchy["team"].id),
        user_id=str(test_user.id),
        role_ids=[str(flexible_role.id)],
    )

    perm_service = EnterprisePermissionService(database, config, redis_client=None)

    # In office: should have update permission
    has_perm, _ = await perm_service.check_permission(
        str(test_user.id),
        "entity:update",
        str(entity_hierarchy["office"].id)
    )
    assert has_perm is True

    # In team: should NOT have update permission (only read)
    has_perm, _ = await perm_service.check_permission(
        str(test_user.id),
        "entity:update",
        str(entity_hierarchy["team"].id)
    )
    assert has_perm is False

    # In team: should have read permission
    has_perm, _ = await perm_service.check_permission(
        str(test_user.id),
        "entity:read",
        str(entity_hierarchy["team"].id)
    )
    assert has_perm is True

    # Clean up
    await flexible_role.delete()


@pytest.mark.asyncio
async def test_get_permissions_for_entity_type_method(database):
    """Test the get_permissions_for_entity_type method on RoleModel"""
    role = RoleModel(
        name="test_role",
        display_name="Test Role",
        permissions=["default:permission"],
        entity_type_permissions={
            "department": ["department:specific"],
            "team": ["team:specific", "team:other"],
        }
    )

    # Get default permissions
    default_perms = role.get_permissions_for_entity_type(None)
    assert default_perms == ["default:permission"]

    # Get department-specific permissions
    dept_perms = role.get_permissions_for_entity_type("department")
    assert dept_perms == ["department:specific"]

    # Get team-specific permissions
    team_perms = role.get_permissions_for_entity_type("team")
    assert set(team_perms) == {"team:specific", "team:other"}

    # Get permissions for unspecified type (should return default)
    unknown_perms = role.get_permissions_for_entity_type("unknown_type")
    assert unknown_perms == ["default:permission"]


@pytest.mark.asyncio
async def test_context_aware_with_tree_permissions(database, config, test_user, entity_hierarchy):
    """Test context-aware roles with tree permissions"""
    # Create role with context-aware tree permissions
    manager_role = RoleModel(
        name="manager",
        display_name="Manager",
        permissions=["entity:read"],
        entity_type_permissions={
            "region": ["entity:update_tree", "user:update_tree"],
            "office": ["entity:read", "user:read"],
        }
    )
    await manager_role.save()

    # Add user to region
    membership_service = MembershipService(config=config)
    await membership_service.add_member(
        entity_id=str(entity_hierarchy["region"].id),
        user_id=str(test_user.id),
        role_ids=[str(manager_role.id)],
    )

    perm_service = EnterprisePermissionService(database, config, redis_client=None)

    # User should have update_tree in region
    has_perm, source = await perm_service.check_permission(
        str(test_user.id),
        "entity:update_tree",
        str(entity_hierarchy["region"].id)
    )
    assert has_perm is True
    assert source == "direct"

    # User should have update permission in office (tree permission from region)
    has_perm, source = await perm_service.check_permission(
        str(test_user.id),
        "entity:update",
        str(entity_hierarchy["office"].id)
    )
    assert has_perm is True
    assert source == "tree"

    # User should have update permission in team (tree permission from region)
    has_perm, source = await perm_service.check_permission(
        str(test_user.id),
        "entity:update",
        str(entity_hierarchy["team"].id)
    )
    assert has_perm is True
    assert source == "tree"

    # Clean up
    await manager_role.delete()


@pytest.mark.asyncio
async def test_get_user_permissions_in_entity_with_context(database, config, test_user, entity_hierarchy):
    """Test get_user_permissions_in_entity with context-aware roles"""
    # Create context-aware role
    role = RoleModel(
        name="context_role",
        display_name="Context Role",
        permissions=["default:perm"],
        entity_type_permissions={
            "office": ["office:perm1", "office:perm2"],
            "team": ["team:perm"],
        }
    )
    await role.save()

    # Add user to office
    membership_service = MembershipService(config=config)
    await membership_service.add_member(
        entity_id=str(entity_hierarchy["office"].id),
        user_id=str(test_user.id),
        role_ids=[str(role.id)],
    )

    # Add user to team
    await membership_service.add_member(
        entity_id=str(entity_hierarchy["team"].id),
        user_id=str(test_user.id),
        role_ids=[str(role.id)],
    )

    perm_service = EnterprisePermissionService(database, config, redis_client=None)

    # Get permissions in office (should be office-specific)
    office_perms = await perm_service.get_user_permissions_in_entity(
        str(test_user.id),
        str(entity_hierarchy["office"].id)
    )
    assert set(office_perms) == {"office:perm1", "office:perm2"}

    # Get permissions in team (should be team-specific)
    team_perms = await perm_service.get_user_permissions_in_entity(
        str(test_user.id),
        str(entity_hierarchy["team"].id)
    )
    assert set(team_perms) == {"team:perm"}

    # Clean up
    await role.delete()


@pytest.mark.asyncio
async def test_fallback_to_default_permissions(database, config, test_user, entity_hierarchy):
    """Test that roles fall back to default permissions when no context-specific ones exist"""
    # Create role with partial context-aware permissions
    role = RoleModel(
        name="partial_context_role",
        display_name="Partial Context Role",
        permissions=["default:read", "default:update"],
        entity_type_permissions={
            "office": ["office:special"],
            # No permissions defined for "team" - should use defaults
        }
    )
    await role.save()

    # Add user to office
    membership_service = MembershipService(config=config)
    await membership_service.add_member(
        entity_id=str(entity_hierarchy["office"].id),
        user_id=str(test_user.id),
        role_ids=[str(role.id)],
    )

    # Add user to team
    await membership_service.add_member(
        entity_id=str(entity_hierarchy["team"].id),
        user_id=str(test_user.id),
        role_ids=[str(role.id)],
    )

    perm_service = EnterprisePermissionService(database, config, redis_client=None)

    # In office: should have office-specific permission
    has_perm, _ = await perm_service.check_permission(
        str(test_user.id),
        "office:special",
        str(entity_hierarchy["office"].id)
    )
    assert has_perm is True

    # In office: should NOT have default permissions
    has_perm, _ = await perm_service.check_permission(
        str(test_user.id),
        "default:read",
        str(entity_hierarchy["office"].id)
    )
    assert has_perm is False

    # In team: should have default permissions (fallback)
    has_perm, _ = await perm_service.check_permission(
        str(test_user.id),
        "default:read",
        str(entity_hierarchy["team"].id)
    )
    assert has_perm is True

    # In team: should have default update permission
    has_perm, _ = await perm_service.check_permission(
        str(test_user.id),
        "default:update",
        str(entity_hierarchy["team"].id)
    )
    assert has_perm is True

    # Clean up
    await role.delete()


@pytest.mark.asyncio
async def test_context_aware_role_with_wildcard_permissions(database, config, test_user, entity_hierarchy):
    """Test context-aware roles with wildcard permissions"""
    role = RoleModel(
        name="wildcard_role",
        display_name="Wildcard Role",
        permissions=["default:*"],
        entity_type_permissions={
            "region": ["entity:*", "user:*"],
            "office": ["entity:read", "user:*"],
        }
    )
    await role.save()

    # Add user to region
    membership_service = MembershipService(config=config)
    await membership_service.add_member(
        entity_id=str(entity_hierarchy["region"].id),
        user_id=str(test_user.id),
        role_ids=[str(role.id)],
    )

    perm_service = EnterprisePermissionService(database, config, redis_client=None)

    # In region: wildcard should match any entity action
    has_perm, _ = await perm_service.check_permission(
        str(test_user.id),
        "entity:create",
        str(entity_hierarchy["region"].id)
    )
    assert has_perm is True

    has_perm, _ = await perm_service.check_permission(
        str(test_user.id),
        "entity:delete",
        str(entity_hierarchy["region"].id)
    )
    assert has_perm is True

    # Clean up
    await role.delete()


@pytest.mark.asyncio
async def test_multiple_roles_with_context_awareness(database, config, test_user, entity_hierarchy):
    """Test user with multiple context-aware roles"""
    # Create two roles
    role1 = RoleModel(
        name="role1",
        display_name="Role 1",
        permissions=["default:perm1"],
        entity_type_permissions={
            "office": ["office:perm1"],
        }
    )
    await role1.save()

    role2 = RoleModel(
        name="role2",
        display_name="Role 2",
        permissions=["default:perm2"],
        entity_type_permissions={
            "office": ["office:perm2"],
        }
    )
    await role2.save()

    # Add user to office with both roles
    membership_service = MembershipService(config=config)
    await membership_service.add_member(
        entity_id=str(entity_hierarchy["office"].id),
        user_id=str(test_user.id),
        role_ids=[str(role1.id), str(role2.id)],
    )

    perm_service = EnterprisePermissionService(database, config, redis_client=None)

    # Should have permissions from both roles
    has_perm, _ = await perm_service.check_permission(
        str(test_user.id),
        "office:perm1",
        str(entity_hierarchy["office"].id)
    )
    assert has_perm is True

    has_perm, _ = await perm_service.check_permission(
        str(test_user.id),
        "office:perm2",
        str(entity_hierarchy["office"].id)
    )
    assert has_perm is True

    # Clean up
    await role1.delete()
    await role2.delete()
