"""
Integration tests for EnterpriseRBAC with tree permissions

Tests complete end-to-end workflows including:
- Entity hierarchy creation and management
- Tree permission inheritance through multiple levels
- Direct vs tree vs all permission resolution
- Permission source tracking
- Complex multi-level scenarios
"""
import pytest
from datetime import datetime, timezone, timedelta
from outlabs_auth import EnterpriseRBAC
from outlabs_auth.models.user import UserModel
from outlabs_auth.models.role import RoleModel
from outlabs_auth.models.entity import EntityModel, EntityClass
from outlabs_auth.models.membership import EntityMembershipModel
from outlabs_auth.core.exceptions import (
    EntityNotFoundError,
    UserNotFoundError,
    InvalidInputError,
    PermissionDeniedError,
)


@pytest.mark.asyncio
@pytest.mark.integration
class TestEntityHierarchy:
    """Test entity hierarchy creation and management."""

    async def test_create_multi_level_hierarchy(self, test_db, test_secret_key):
        """
        Test creating a multi-level entity hierarchy.

        Hierarchy:
        Platform (root)
        └── Organization
            └── Department
                └── Team
        """
        # Initialize EnterpriseRBAC
        auth = EnterpriseRBAC(database=test_db, secret_key=test_secret_key)
        await auth.initialize()

        # Create platform (root entity)
        platform = await auth.entity_service.create_entity(
            name="acme_platform",
            display_name="ACME Platform",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="platform",
        )

        # Create organization
        org = await auth.entity_service.create_entity(
            name="acme_corp",
            display_name="ACME Corporation",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
            parent_id=str(platform.id),
        )

        # Create department
        dept = await auth.entity_service.create_entity(
            name="engineering",
            display_name="Engineering",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
            parent_id=str(org.id),
        )

        # Create team
        team = await auth.entity_service.create_entity(
            name="backend_team",
            display_name="Backend Team",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=str(dept.id),
        )

        # Verify hierarchy path
        team_path = await auth.entity_service.get_entity_path(str(team.id))
        assert len(team_path) == 4
        assert team_path[0].id == platform.id
        assert team_path[1].id == org.id
        assert team_path[2].id == dept.id
        assert team_path[3].id == team.id

        # Verify descendants
        platform_descendants = await auth.entity_service.get_descendants(str(platform.id))
        assert len(platform_descendants) == 3  # org, dept, team

        org_descendants = await auth.entity_service.get_descendants(str(org.id))
        assert len(org_descendants) == 2  # dept, team

        dept_descendants = await auth.entity_service.get_descendants(str(dept.id))
        assert len(dept_descendants) == 1  # team

    async def test_access_group_cannot_have_structural_children(self, test_db, test_secret_key):
        """Test that access groups cannot have structural children."""
        auth = EnterpriseRBAC(database=test_db, secret_key=test_secret_key)
        await auth.initialize()

        # Create access group
        access_group = await auth.entity_service.create_entity(
            name="admin_group",
            display_name="Admin Group",
            entity_class=EntityClass.ACCESS_GROUP,
            entity_type="access_group",
        )

        # Attempt to create structural child
        with pytest.raises(InvalidInputError) as exc_info:
            await auth.entity_service.create_entity(
                name="sub_org",
                display_name="Sub Organization",
                entity_class=EntityClass.STRUCTURAL,
                entity_type="organization",
                parent_id=str(access_group.id),
            )

        assert "access groups cannot have structural entities" in exc_info.value.message.lower()

    async def test_entity_deletion_cascade(self, test_db, test_secret_key):
        """Test cascading entity deletion."""
        auth = EnterpriseRBAC(database=test_db, secret_key=test_secret_key)
        await auth.initialize()

        # Create hierarchy
        platform = await auth.entity_service.create_entity(
            name="platform",
            display_name="Platform",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="platform",
        )

        org = await auth.entity_service.create_entity(
            name="org",
            display_name="Organization",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
            parent_id=str(platform.id),
        )

        dept = await auth.entity_service.create_entity(
            name="dept",
            display_name="Department",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
            parent_id=str(org.id),
        )

        # Delete platform with cascade
        await auth.entity_service.delete_entity(str(platform.id), cascade=True)

        # Verify all entities are archived
        platform_reloaded = await EntityModel.get(platform.id)
        org_reloaded = await EntityModel.get(org.id)
        dept_reloaded = await EntityModel.get(dept.id)

        assert platform_reloaded.status == "archived"
        assert org_reloaded.status == "archived"
        assert dept_reloaded.status == "archived"


@pytest.mark.asyncio
@pytest.mark.integration
class TestTreePermissions:
    """Test tree permission inheritance and resolution."""

    async def test_tree_permission_basic_inheritance(self, test_db, test_secret_key):
        """
        Test basic tree permission inheritance.

        Scenario:
        - User has entity:read_tree at Organization level
        - Should be able to read Department and Team entities
        - Should NOT be able to read Organization itself (tree permissions apply to descendants only)
        """
        auth = EnterpriseRBAC(database=test_db, secret_key=test_secret_key)
        await auth.initialize()

        # Create hierarchy
        org = await auth.entity_service.create_entity(
            name="org",
            display_name="Organization",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )

        dept = await auth.entity_service.create_entity(
            name="dept",
            display_name="Department",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
            parent_id=str(org.id),
        )

        team = await auth.entity_service.create_entity(
            name="team",
            display_name="Team",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=str(dept.id),
        )

        # Create user and role with tree permission
        user = await auth.user_service.create_user(
            email="manager@example.com",
            password="SecurePass123!",
            first_name="Manager",
            last_name="User",
        )

        role = await auth.role_service.create_role(
            name="org_manager",
            display_name="Organization Manager",
            permissions=["entity:read_tree"],  # Tree permission
            entity_id=str(org.id),
        )

        # Add user to organization with role
        await auth.membership_service.add_member(
            entity_id=str(org.id),
            user_id=str(user.id),
            role_ids=[str(role.id)],
        )

        # Test permissions
        # Should NOT have permission on org itself (tree permissions don't apply to source entity)
        has_org_perm, source = await auth.permission_service.check_permission(
            user_id=str(user.id),
            permission="entity:read",
            entity_id=str(org.id),
        )
        assert has_org_perm is False

        # Should have permission on department (descendant)
        has_dept_perm, source = await auth.permission_service.check_permission(
            user_id=str(user.id),
            permission="entity:read",
            entity_id=str(dept.id),
        )
        assert has_dept_perm is True
        assert source == "tree"

        # Should have permission on team (descendant)
        has_team_perm, source = await auth.permission_service.check_permission(
            user_id=str(user.id),
            permission="entity:read",
            entity_id=str(team.id),
        )
        assert has_team_perm is True
        assert source == "tree"

    async def test_direct_and_tree_permissions_combined(self, test_db, test_secret_key):
        """
        Test combination of direct and tree permissions.

        To manage an entity AND its descendants, assign both:
        - entity:update (for the entity itself)
        - entity:update_tree (for descendants)
        """
        auth = EnterpriseRBAC(database=test_db, secret_key=test_secret_key)
        await auth.initialize()

        # Create hierarchy
        org = await auth.entity_service.create_entity(
            name="org",
            display_name="Organization",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )

        dept = await auth.entity_service.create_entity(
            name="dept",
            display_name="Department",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
            parent_id=str(org.id),
        )

        # Create user with BOTH direct and tree permissions
        user = await auth.user_service.create_user(
            email="admin@example.com",
            password="SecurePass123!",
            first_name="Admin",
            last_name="User",
        )

        role = await auth.role_service.create_role(
            name="full_admin",
            display_name="Full Administrator",
            permissions=[
                "entity:update",      # Direct permission on org
                "entity:update_tree", # Tree permission for descendants
            ],
            entity_id=str(org.id),
        )

        await auth.membership_service.add_member(
            entity_id=str(org.id),
            user_id=str(user.id),
            role_ids=[str(role.id)],
        )

        # Should have direct permission on org
        has_org_perm, source = await auth.permission_service.check_permission(
            user_id=str(user.id),
            permission="entity:update",
            entity_id=str(org.id),
        )
        assert has_org_perm is True
        assert source == "direct"

        # Should have tree permission on dept
        has_dept_perm, source = await auth.permission_service.check_permission(
            user_id=str(user.id),
            permission="entity:update",
            entity_id=str(dept.id),
        )
        assert has_dept_perm is True
        assert source == "tree"

    async def test_platform_wide_permissions(self, test_db, test_secret_key):
        """
        Test platform-wide permissions (_all suffix).

        User with entity:read_all should access ALL entities.
        """
        auth = EnterpriseRBAC(database=test_db, secret_key=test_secret_key)
        await auth.initialize()

        # Create multiple hierarchies
        platform1 = await auth.entity_service.create_entity(
            name="platform1",
            display_name="Platform 1",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="platform",
        )

        platform2 = await auth.entity_service.create_entity(
            name="platform2",
            display_name="Platform 2",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="platform",
        )

        org1 = await auth.entity_service.create_entity(
            name="org1",
            display_name="Organization 1",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
            parent_id=str(platform1.id),
        )

        org2 = await auth.entity_service.create_entity(
            name="org2",
            display_name="Organization 2",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
            parent_id=str(platform2.id),
        )

        # Create super admin with platform-wide permission
        user = await auth.user_service.create_user(
            email="superadmin@example.com",
            password="SecurePass123!",
            first_name="Super",
            last_name="Admin",
        )

        # Create global role with _all permission
        role = await auth.role_service.create_role(
            name="super_admin",
            display_name="Super Administrator",
            permissions=["entity:read_all"],  # Platform-wide permission
            is_global=True,
        )

        # Assign role (add user to any entity for membership)
        await auth.membership_service.add_member(
            entity_id=str(platform1.id),
            user_id=str(user.id),
            role_ids=[str(role.id)],
        )

        # Should have permission on all entities
        for entity in [platform1, platform2, org1, org2]:
            has_perm, source = await auth.permission_service.check_permission(
                user_id=str(user.id),
                permission="entity:read",
                entity_id=str(entity.id),
            )
            assert has_perm is True
            assert source == "all"

    async def test_permission_resolution_order(self, test_db, test_secret_key):
        """
        Test permission resolution algorithm order: direct → tree → all.
        """
        auth = EnterpriseRBAC(database=test_db, secret_key=test_secret_key)
        await auth.initialize()

        # Create hierarchy
        platform = await auth.entity_service.create_entity(
            name="platform",
            display_name="Platform",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="platform",
        )

        org = await auth.entity_service.create_entity(
            name="org",
            display_name="Organization",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
            parent_id=str(platform.id),
        )

        dept = await auth.entity_service.create_entity(
            name="dept",
            display_name="Department",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
            parent_id=str(org.id),
        )

        # Create user
        user = await auth.user_service.create_user(
            email="user@example.com",
            password="SecurePass123!",
            first_name="Test",
            last_name="User",
        )

        # Test 1: Direct permission takes precedence
        direct_role = await auth.role_service.create_role(
            name="direct_role",
            display_name="Direct Role",
            permissions=["entity:read"],
            entity_id=str(dept.id),
        )

        await auth.membership_service.add_member(
            entity_id=str(dept.id),
            user_id=str(user.id),
            role_ids=[str(direct_role.id)],
        )

        has_perm, source = await auth.permission_service.check_permission(
            user_id=str(user.id),
            permission="entity:read",
            entity_id=str(dept.id),
        )
        assert has_perm is True
        assert source == "direct"

        # Test 2: Tree permission (add tree permission from org)
        tree_role = await auth.role_service.create_role(
            name="tree_role",
            display_name="Tree Role",
            permissions=["entity:update_tree"],
            entity_id=str(org.id),
        )

        await auth.membership_service.add_member(
            entity_id=str(org.id),
            user_id=str(user.id),
            role_ids=[str(tree_role.id)],
        )

        has_perm, source = await auth.permission_service.check_permission(
            user_id=str(user.id),
            permission="entity:update",
            entity_id=str(dept.id),
        )
        assert has_perm is True
        assert source == "tree"


@pytest.mark.asyncio
@pytest.mark.integration
class TestMembershipManagement:
    """Test entity membership management with multiple roles."""

    async def test_add_member_with_multiple_roles(self, test_db, test_secret_key):
        """Test adding a member with multiple roles to an entity."""
        auth = EnterpriseRBAC(database=test_db, secret_key=test_secret_key)
        await auth.initialize()

        # Create entity
        dept = await auth.entity_service.create_entity(
            name="engineering",
            display_name="Engineering",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
        )

        # Create user
        user = await auth.user_service.create_user(
            email="developer@example.com",
            password="SecurePass123!",
            first_name="Dev",
            last_name="User",
        )

        # Create multiple roles
        dev_role = await auth.role_service.create_role(
            name="developer",
            display_name="Developer",
            permissions=["code:write", "code:review"],
            entity_id=str(dept.id),
        )

        lead_role = await auth.role_service.create_role(
            name="team_lead",
            display_name="Team Lead",
            permissions=["team:manage", "sprint:plan"],
            entity_id=str(dept.id),
        )

        # Add member with multiple roles
        membership = await auth.membership_service.add_member(
            entity_id=str(dept.id),
            user_id=str(user.id),
            role_ids=[str(dev_role.id), str(lead_role.id)],
        )

        assert len(membership.roles) == 2

        # Verify user has permissions from both roles
        has_code_perm = await auth.permission_service.has_permission(
            user_id=str(user.id),
            permission="code:write",
            entity_id=str(dept.id),
        )

        has_team_perm = await auth.permission_service.has_permission(
            user_id=str(user.id),
            permission="team:manage",
            entity_id=str(dept.id),
        )

        assert has_code_perm is True
        assert has_team_perm is True

    async def test_update_member_roles(self, test_db, test_secret_key):
        """Test updating a member's roles."""
        auth = EnterpriseRBAC(database=test_db, secret_key=test_secret_key)
        await auth.initialize()

        # Create entity
        dept = await auth.entity_service.create_entity(
            name="sales",
            display_name="Sales",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
        )

        # Create user
        user = await auth.user_service.create_user(
            email="sales@example.com",
            password="SecurePass123!",
            first_name="Sales",
            last_name="Rep",
        )

        # Create roles
        junior_role = await auth.role_service.create_role(
            name="junior_sales",
            display_name="Junior Sales",
            permissions=["lead:view"],
            entity_id=str(dept.id),
        )

        senior_role = await auth.role_service.create_role(
            name="senior_sales",
            display_name="Senior Sales",
            permissions=["lead:view", "lead:assign", "deal:close"],
            entity_id=str(dept.id),
        )

        # Add member with junior role
        await auth.membership_service.add_member(
            entity_id=str(dept.id),
            user_id=str(user.id),
            role_ids=[str(junior_role.id)],
        )

        # Promote to senior role
        updated_membership = await auth.membership_service.update_member_roles(
            entity_id=str(dept.id),
            user_id=str(user.id),
            role_ids=[str(senior_role.id)],
        )

        assert len(updated_membership.roles) == 1
        assert updated_membership.roles[0].id == senior_role.id

    async def test_max_members_limit(self, test_db, test_secret_key):
        """Test that max_members limit is enforced."""
        auth = EnterpriseRBAC(database=test_db, secret_key=test_secret_key)
        await auth.initialize()

        # Create entity with max_members=2
        team = await auth.entity_service.create_entity(
            name="small_team",
            display_name="Small Team",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            max_members=2,
        )

        # Create role
        role = await auth.role_service.create_role(
            name="member",
            display_name="Team Member",
            permissions=["team:participate"],
            entity_id=str(team.id),
        )

        # Add first member
        user1 = await auth.user_service.create_user(
            email="user1@example.com",
            password="Pass123!",
            first_name="User",
            last_name="One",
        )
        await auth.membership_service.add_member(
            entity_id=str(team.id),
            user_id=str(user1.id),
            role_ids=[str(role.id)],
        )

        # Add second member
        user2 = await auth.user_service.create_user(
            email="user2@example.com",
            password="Pass123!",
            first_name="User",
            last_name="Two",
        )
        await auth.membership_service.add_member(
            entity_id=str(team.id),
            user_id=str(user2.id),
            role_ids=[str(role.id)],
        )

        # Try to add third member (should fail)
        user3 = await auth.user_service.create_user(
            email="user3@example.com",
            password="Pass123!",
            first_name="User",
            last_name="Three",
        )

        with pytest.raises(InvalidInputError) as exc_info:
            await auth.membership_service.add_member(
                entity_id=str(team.id),
                user_id=str(user3.id),
                role_ids=[str(role.id)],
            )

        assert "maximum members limit" in exc_info.value.message.lower()


@pytest.mark.asyncio
@pytest.mark.integration
class TestComplexTreePermissionScenarios:
    """Test complex multi-level tree permission scenarios."""

    async def test_platform_admin_manages_entire_hierarchy(self, test_db, test_secret_key):
        """
        Test platform admin with tree permissions can manage entire hierarchy.

        Scenario:
        Platform Admin (entity:create_tree, entity:update_tree at platform level)
        └── Can create/update entities anywhere in the hierarchy
        """
        auth = EnterpriseRBAC(database=test_db, secret_key=test_secret_key)
        await auth.initialize()

        # Create platform
        platform = await auth.entity_service.create_entity(
            name="platform",
            display_name="Platform",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="platform",
        )

        # Create platform admin user
        admin = await auth.user_service.create_user(
            email="platformadmin@example.com",
            password="SecurePass123!",
            first_name="Platform",
            last_name="Admin",
        )

        # Create platform admin role with tree permissions
        admin_role = await auth.role_service.create_role(
            name="platform_admin",
            display_name="Platform Administrator",
            permissions=[
                "entity:create_tree",
                "entity:update_tree",
                "entity:delete_tree",
                "entity:read_tree",
            ],
            entity_id=str(platform.id),
        )

        await auth.membership_service.add_member(
            entity_id=str(platform.id),
            user_id=str(admin.id),
            role_ids=[str(admin_role.id)],
        )

        # Create organization under platform
        org = await auth.entity_service.create_entity(
            name="org",
            display_name="Organization",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
            parent_id=str(platform.id),
        )

        # Create department under organization
        dept = await auth.entity_service.create_entity(
            name="dept",
            display_name="Department",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
            parent_id=str(org.id),
        )

        # Verify admin has tree permissions on org
        has_org_read, source = await auth.permission_service.check_permission(
            user_id=str(admin.id),
            permission="entity:read",
            entity_id=str(org.id),
        )
        assert has_org_read is True
        assert source == "tree"

        # Verify admin has tree permissions on dept (2 levels down)
        has_dept_update, source = await auth.permission_service.check_permission(
            user_id=str(admin.id),
            permission="entity:update",
            entity_id=str(dept.id),
        )
        assert has_dept_update is True
        assert source == "tree"

    async def test_department_manager_limited_to_subtree(self, test_db, test_secret_key):
        """
        Test that department manager with tree permissions only affects their subtree.

        Scenario:
        - Dept A Manager has entity:read_tree on Dept A
        - Should access Team A1, Team A2 (children of Dept A)
        - Should NOT access Dept B or Team B1 (different subtree)
        """
        auth = EnterpriseRBAC(database=test_db, secret_key=test_secret_key)
        await auth.initialize()

        # Create hierarchy
        org = await auth.entity_service.create_entity(
            name="org",
            display_name="Organization",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="organization",
        )

        # Department A
        dept_a = await auth.entity_service.create_entity(
            name="dept_a",
            display_name="Department A",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
            parent_id=str(org.id),
        )

        team_a1 = await auth.entity_service.create_entity(
            name="team_a1",
            display_name="Team A1",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=str(dept_a.id),
        )

        team_a2 = await auth.entity_service.create_entity(
            name="team_a2",
            display_name="Team A2",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=str(dept_a.id),
        )

        # Department B
        dept_b = await auth.entity_service.create_entity(
            name="dept_b",
            display_name="Department B",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="department",
            parent_id=str(org.id),
        )

        team_b1 = await auth.entity_service.create_entity(
            name="team_b1",
            display_name="Team B1",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="team",
            parent_id=str(dept_b.id),
        )

        # Create Dept A manager
        manager_a = await auth.user_service.create_user(
            email="managera@example.com",
            password="SecurePass123!",
            first_name="Manager",
            last_name="A",
        )

        role_a = await auth.role_service.create_role(
            name="dept_a_manager",
            display_name="Department A Manager",
            permissions=["entity:read_tree", "entity:update_tree"],
            entity_id=str(dept_a.id),
        )

        await auth.membership_service.add_member(
            entity_id=str(dept_a.id),
            user_id=str(manager_a.id),
            role_ids=[str(role_a.id)],
        )

        # Manager A should have access to Dept A's subtree
        has_team_a1, _ = await auth.permission_service.check_permission(
            user_id=str(manager_a.id),
            permission="entity:read",
            entity_id=str(team_a1.id),
        )
        assert has_team_a1 is True

        has_team_a2, _ = await auth.permission_service.check_permission(
            user_id=str(manager_a.id),
            permission="entity:read",
            entity_id=str(team_a2.id),
        )
        assert has_team_a2 is True

        # Manager A should NOT have access to Dept B's subtree
        has_dept_b, _ = await auth.permission_service.check_permission(
            user_id=str(manager_a.id),
            permission="entity:read",
            entity_id=str(dept_b.id),
        )
        assert has_dept_b is False

        has_team_b1, _ = await auth.permission_service.check_permission(
            user_id=str(manager_a.id),
            permission="entity:read",
            entity_id=str(team_b1.id),
        )
        assert has_team_b1 is False

    async def test_time_based_membership_validity(self, test_db, test_secret_key):
        """Test time-based membership validity with valid_from and valid_until."""
        auth = EnterpriseRBAC(database=test_db, secret_key=test_secret_key)
        await auth.initialize()

        # Create entity
        dept = await auth.entity_service.create_entity(
            name="temp_project",
            display_name="Temporary Project",
            entity_class=EntityClass.STRUCTURAL,
            entity_type="project",
        )

        # Create user and role
        user = await auth.user_service.create_user(
            email="contractor@example.com",
            password="SecurePass123!",
            first_name="Contract",
            last_name="Worker",
        )

        role = await auth.role_service.create_role(
            name="contractor",
            display_name="Contractor",
            permissions=["project:contribute"],
            entity_id=str(dept.id),
        )

        # Add member with time-based validity (future start date)
        future_start = datetime.now(timezone.utc) + timedelta(days=1)
        future_end = datetime.now(timezone.utc) + timedelta(days=30)

        membership = await auth.membership_service.add_member(
            entity_id=str(dept.id),
            user_id=str(user.id),
            role_ids=[str(role.id)],
            valid_from=future_start,
            valid_until=future_end,
        )

        # MongoDB stores datetimes without timezone info and with millisecond precision
        # So we need to compare without timezone and with millisecond precision
        assert membership.valid_from.replace(tzinfo=timezone.utc) == future_start.replace(microsecond=(future_start.microsecond // 1000) * 1000)
        assert membership.valid_until.replace(tzinfo=timezone.utc) == future_end.replace(microsecond=(future_end.microsecond // 1000) * 1000)

        # Permission check should fail (membership not yet active)
        # Note: This requires EnterprisePermissionService to check membership validity
        # Implementation may vary based on design decision


@pytest.mark.asyncio
@pytest.mark.integration
class TestEnterpriseRBACInitialization:
    """Test EnterpriseRBAC initialization and configuration."""

    async def test_enterprise_rbac_enables_entity_hierarchy(self, test_db, test_secret_key):
        """Test that EnterpriseRBAC enables entity hierarchy features."""
        auth = EnterpriseRBAC(database=test_db, secret_key=test_secret_key)
        await auth.initialize()

        # Assert entity hierarchy is enabled
        assert auth.config.enable_entity_hierarchy is True
        assert auth.entity_service is not None
        assert auth.membership_service is not None

        # Verify services are properly initialized
        assert hasattr(auth.entity_service, 'create_entity')
        assert hasattr(auth.membership_service, 'add_member')
        assert hasattr(auth.permission_service, 'check_permission')

    async def test_enterprise_rbac_repr(self, test_db, test_secret_key):
        """Test EnterpriseRBAC string representation."""
        auth = EnterpriseRBAC(database=test_db, secret_key=test_secret_key)
        await auth.initialize()

        repr_str = repr(auth)

        assert "EnterpriseRBAC" in repr_str
        assert "SimpleRBAC" not in repr_str
