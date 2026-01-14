"""
Integration tests for SimpleRBAC

Tests complete end-to-end workflows including user registration,
login, role assignment, and permission checking.
"""
import pytest
import asyncio
from outlabs_auth import SimpleRBAC
from outlabs_auth.models.user import UserModel
from outlabs_auth.models.role import RoleModel
from outlabs_auth.core.exceptions import (
    InvalidCredentialsError,
    AccountLockedError,
    PermissionDeniedError,
)


@pytest.mark.asyncio
@pytest.mark.integration
class TestCompleteAuthFlow:
    """Test complete authentication workflows."""

    async def test_user_registration_and_login_flow(self, auth: SimpleRBAC):
        """
        Test complete user registration and login flow.

        Steps:
        1. Create a user
        2. Login with credentials
        3. Verify JWT tokens returned
        4. Use access token to get current user
        """
        # Step 1: Register user
        user = await auth.user_service.create_user(
            email="newuser@example.com",
            password="SecurePass123!",
            first_name="New",
            last_name="User",
        )

        assert user.email == "newuser@example.com"

        # Step 2: Login
        logged_in_user, tokens = await auth.auth_service.login(
            email="newuser@example.com",
            password="SecurePass123!",
        )

        assert logged_in_user.id == user.id
        assert tokens.access_token is not None
        assert tokens.refresh_token is not None
        assert tokens.token_type == "bearer"

        # Step 3: Use access token to get current user
        current_user = await auth.get_current_user(tokens.access_token)

        assert current_user.id == user.id
        assert current_user.email == user.email

    async def test_login_with_invalid_credentials_fails(self, auth: SimpleRBAC, test_user: UserModel):
        """Test that login with wrong password fails."""
        # Act & Assert
        with pytest.raises(InvalidCredentialsError):
            await auth.auth_service.login(
                email=test_user.email,
                password="WrongPassword123!",
            )

    async def test_account_lockout_after_failed_attempts(self, auth: SimpleRBAC, test_user: UserModel):
        """
        Test that account is locked after max failed login attempts.

        Default is 5 failed attempts.
        """
        # Arrange
        max_attempts = auth.config.max_login_attempts

        # Act - Attempt login with wrong password multiple times
        for i in range(max_attempts):
            with pytest.raises(InvalidCredentialsError):
                await auth.auth_service.login(
                    email=test_user.email,
                    password="WrongPassword!",
                )

        # Assert - Account should now be locked
        with pytest.raises(AccountLockedError) as exc_info:
            await auth.auth_service.login(
                email=test_user.email,
                password="WrongPassword!",  # Even with wrong password
            )

        assert "locked" in exc_info.value.message.lower()

    async def test_token_refresh_flow(self, auth: SimpleRBAC, test_user: UserModel, test_password: str):
        """
        Test token refresh workflow.

        Steps:
        1. Login to get tokens
        2. Use refresh token to get new access token
        3. Verify new access token works
        """
        # Step 1: Login
        _, initial_tokens = await auth.auth_service.login(
            email=test_user.email,
            password=test_password,
        )

        # Wait 1 second to ensure different timestamp in new token
        await asyncio.sleep(1)

        # Step 2: Refresh access token
        new_tokens = await auth.auth_service.refresh_access_token(
            initial_tokens.refresh_token
        )

        assert new_tokens.access_token != initial_tokens.access_token
        assert new_tokens.refresh_token == initial_tokens.refresh_token

        # Step 3: Verify new token works
        current_user = await auth.get_current_user(new_tokens.access_token)
        assert current_user.id == test_user.id

    async def test_logout_revokes_refresh_token(
        self, auth: SimpleRBAC, test_user: UserModel, test_password: str
    ):
        """
        Test that logout revokes the refresh token.

        Steps:
        1. Login
        2. Logout
        3. Attempt to refresh with revoked token (should fail)
        """
        # Step 1: Login
        _, tokens = await auth.auth_service.login(
            email=test_user.email,
            password=test_password,
        )

        # Step 2: Logout
        success = await auth.auth_service.logout(tokens.refresh_token)
        assert success is True

        # Step 3: Attempt to use revoked token
        from outlabs_auth.core.exceptions import RefreshTokenInvalidError

        with pytest.raises(RefreshTokenInvalidError):
            await auth.auth_service.refresh_access_token(tokens.refresh_token)


@pytest.mark.asyncio
@pytest.mark.integration
class TestRoleAndPermissionFlow:
    """Test role creation and permission assignment flow."""

    async def test_create_role_and_assign_permissions(self, auth: SimpleRBAC):
        """
        Test creating a role and assigning permissions.

        Steps:
        1. Create permissions
        2. Create role with permissions
        3. Verify role has permissions
        """
        # Step 1: Create permissions
        perm1 = await auth.permission_service.create_permission(
            name="article:create",
            display_name="Create Articles",
            description="Can create new articles",
        )

        perm2 = await auth.permission_service.create_permission(
            name="article:publish",
            display_name="Publish Articles",
            description="Can publish articles",
        )

        # Step 2: Create role with permissions
        role = await auth.role_service.create_role(
            name="editor",
            display_name="Editor",
            permissions=[perm1.name, perm2.name],
        )

        # Step 3: Verify
        assert "article:create" in role.permissions
        assert "article:publish" in role.permissions

    async def test_user_with_role_has_permissions(
        self, auth: SimpleRBAC, test_user: UserModel, test_role: RoleModel
    ):
        """
        Test that user with assigned role has role's permissions.

        Steps:
        1. Assign role to user
        2. Check user permissions
        """
        # Step 1: Assign role (via metadata in SimpleRBAC)
        test_user.metadata["role_ids"] = [str(test_role.id)]
        await test_user.save()

        # Step 2: Check permissions
        has_read = await auth.permission_service.check_permission(
            str(test_user.id),
            "user:read",  # test_role has this permission
        )

        has_create = await auth.permission_service.check_permission(
            str(test_user.id),
            "user:create",  # test_role has this permission
        )

        has_delete = await auth.permission_service.check_permission(
            str(test_user.id),
            "user:delete",  # test_role does NOT have this
        )

        assert has_read is True
        assert has_create is True
        assert has_delete is False

    async def test_superuser_has_all_permissions(self, auth: SimpleRBAC, test_admin: UserModel):
        """Test that superuser has all permissions."""
        # Superuser should have any permission
        has_perm = await auth.permission_service.check_permission(
            str(test_admin.id),
            "anything:anything",  # Any permission
        )

        assert has_perm is True


@pytest.mark.asyncio
@pytest.mark.integration
class TestWildcardPermissions:
    """Test wildcard permission support."""

    async def test_resource_wildcard_grants_all_actions(self, auth: SimpleRBAC, test_password: str):
        """
        Test that wildcard permission 'user:*' grants all user actions.

        Steps:
        1. Create role with wildcard permission
        2. Assign to user
        3. Check various permissions
        """
        # Step 1: Create role with wildcard
        role = await auth.role_service.create_role(
            name="user_admin",
            display_name="User Administrator",
            permissions=["user:*"],  # Wildcard for all user actions
        )

        # Step 2: Create and assign to user
        user = await auth.user_service.create_user(
            email="wildcard@example.com",
            password=test_password,
            first_name="Wildcard",
            last_name="User",
        )

        user.metadata["role_ids"] = [str(role.id)]
        await user.save()

        # Step 3: Check various permissions
        for action in ["create", "read", "update", "delete"]:
            has_perm = await auth.permission_service.check_permission(
                str(user.id),
                f"user:{action}",
            )
            assert has_perm is True, f"Should have user:{action}"

    async def test_full_wildcard_grants_everything(self, auth: SimpleRBAC, test_password: str):
        """Test that '*:*' wildcard grants all permissions."""
        # Arrange - Create role with full wildcard
        role = await auth.role_service.create_role(
            name="god_mode",
            display_name="God Mode",
            permissions=["*:*"],  # Full wildcard
        )

        user = await auth.user_service.create_user(
            email="godmode@example.com",
            password=test_password,
            first_name="God",
            last_name="Mode",
        )

        user.metadata["role_ids"] = [str(role.id)]
        await user.save()

        # Act & Assert - Should have any permission
        for perm in ["user:create", "article:delete", "payment:process"]:
            has_perm = await auth.permission_service.check_permission(
                str(user.id),
                perm,
            )
            assert has_perm is True


@pytest.mark.asyncio
@pytest.mark.integration
class TestMultiDeviceSessions:
    """Test multi-device session support."""

    async def test_login_from_multiple_devices(
        self, auth: SimpleRBAC, test_user: UserModel, test_password: str
    ):
        """
        Test that user can login from multiple devices simultaneously.

        Each device gets its own refresh token.
        """
        # Login from device 1
        _, tokens1 = await auth.auth_service.login(
            email=test_user.email,
            password=test_password,
            device_name="iPhone 12",
        )

        # Wait 1 second to ensure different timestamp in second login
        await asyncio.sleep(1)

        # Login from device 2
        _, tokens2 = await auth.auth_service.login(
            email=test_user.email,
            password=test_password,
            device_name="MacBook Pro",
        )

        # Both tokens should be different
        assert tokens1.refresh_token != tokens2.refresh_token

        # Both should work for token refresh
        new_tokens1 = await auth.auth_service.refresh_access_token(tokens1.refresh_token)
        new_tokens2 = await auth.auth_service.refresh_access_token(tokens2.refresh_token)

        assert new_tokens1.access_token is not None
        assert new_tokens2.access_token is not None

    async def test_logout_from_one_device_keeps_others_active(
        self, auth: SimpleRBAC, test_user: UserModel, test_password: str
    ):
        """Test that logging out from one device doesn't affect others."""
        # Login from two devices
        _, tokens1 = await auth.auth_service.login(
            email=test_user.email,
            password=test_password,
            device_name="Device 1",
        )

        # Wait 1 second to ensure different timestamps
        await asyncio.sleep(1)

        _, tokens2 = await auth.auth_service.login(
            email=test_user.email,
            password=test_password,
            device_name="Device 2",
        )

        # Logout from device 1
        await auth.auth_service.logout(tokens1.refresh_token)

        # Device 1 token should not work
        from outlabs_auth.core.exceptions import RefreshTokenInvalidError

        with pytest.raises(RefreshTokenInvalidError):
            await auth.auth_service.refresh_access_token(tokens1.refresh_token)

        # Device 2 token should still work
        new_tokens2 = await auth.auth_service.refresh_access_token(tokens2.refresh_token)
        assert new_tokens2.access_token is not None


@pytest.mark.asyncio
@pytest.mark.integration
class TestSimpleRBACInitialization:
    """Test SimpleRBAC initialization and configuration."""

    async def test_simple_rbac_forces_flat_structure(self, test_db, test_secret_key):
        """Test that SimpleRBAC forces entity hierarchy off."""
        # Arrange & Act
        auth = SimpleRBAC(
            database=test_db,
            secret_key=test_secret_key,
        )

        await auth.initialize()

        # Assert
        assert auth.config.enable_entity_hierarchy is False
        assert auth.config.enable_context_aware_roles is False
        assert auth.config.enable_abac is False
        assert auth.entity_service is None
        assert auth.membership_service is None

    async def test_simple_rbac_repr(self, auth: SimpleRBAC):
        """Test SimpleRBAC string representation."""
        # Act
        repr_str = repr(auth)

        # Assert
        assert "SimpleRBAC" in repr_str
        assert "EnterpriseRBAC" not in repr_str
