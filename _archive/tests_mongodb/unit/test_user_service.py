"""
Unit tests for UserService

Tests user CRUD operations, search, status management, and validation.
"""
import pytest
from outlabs_auth import SimpleRBAC
from outlabs_auth.models.user import UserModel, UserStatus
from outlabs_auth.core.exceptions import (
    UserAlreadyExistsError,
    UserNotFoundError,
    InvalidPasswordError,
)


@pytest.mark.asyncio
class TestUserCreation:
    """Test user creation functionality."""

    async def test_create_user_with_valid_data(self, auth: SimpleRBAC, test_password: str):
        """Test creating a user with valid data succeeds."""
        # Arrange
        user_data = {
            "email": "newuser@example.com",
            "password": test_password,
            "first_name": "John",
            "last_name": "Doe",
        }

        # Act
        user = await auth.user_service.create_user(**user_data)

        # Assert
        assert user.email == "newuser@example.com"
        assert user.first_name == "John"
        assert user.last_name == "Doe"
        assert user.status == UserStatus.ACTIVE
        assert user.is_superuser is False
        assert user.email_verified is False
        assert user.hashed_password is not None
        assert user.hashed_password != test_password  # Should be hashed

    async def test_create_user_with_duplicate_email_fails(
        self, auth: SimpleRBAC, test_user: UserModel, test_password: str
    ):
        """Test that creating user with duplicate email raises error."""
        # Arrange - test_user already exists with test@example.com

        # Act & Assert
        with pytest.raises(UserAlreadyExistsError) as exc_info:
            await auth.user_service.create_user(
                email=test_user.email,  # Duplicate
                password=test_password,
                first_name="Jane",
                last_name="Doe",
            )

        assert "already exists" in exc_info.value.message.lower()
        assert exc_info.value.details["email"] == test_user.email

    async def test_create_user_with_weak_password_fails(self, auth: SimpleRBAC):
        """Test that weak password raises InvalidPasswordError."""
        # Act & Assert
        with pytest.raises(InvalidPasswordError) as exc_info:
            await auth.user_service.create_user(
                email="newuser@example.com",
                password="weak",  # Too short, no uppercase, no special char
                first_name="John",
                last_name="Doe",
            )

        assert "at least 8 characters" in exc_info.value.message.lower()

    async def test_create_user_normalizes_email_to_lowercase(
        self, auth: SimpleRBAC, test_password: str
    ):
        """Test that email is normalized to lowercase."""
        # Act
        user = await auth.user_service.create_user(
            email="MixedCase@EXAMPLE.COM",
            password=test_password,
            first_name="John",
            last_name="Doe",
        )

        # Assert
        assert user.email == "mixedcase@example.com"

    async def test_create_superuser(self, auth: SimpleRBAC, test_password: str):
        """Test creating a superuser."""
        # Act
        user = await auth.user_service.create_user(
            email="superuser@example.com",
            password=test_password,
            first_name="Super",
            last_name="User",
            is_superuser=True,
        )

        # Assert
        assert user.is_superuser is True


@pytest.mark.asyncio
class TestUserRetrieval:
    """Test user retrieval operations."""

    async def test_get_user_by_id(self, auth: SimpleRBAC, test_user: UserModel):
        """Test retrieving user by ID."""
        # Act
        user = await auth.user_service.get_user_by_id(str(test_user.id))

        # Assert
        assert user is not None
        assert user.id == test_user.id
        assert user.email == test_user.email

    async def test_get_user_by_id_not_found(self, auth: SimpleRBAC):
        """Test that getting non-existent user returns None."""
        # Act
        user = await auth.user_service.get_user_by_id("507f1f77bcf86cd799439011")

        # Assert
        assert user is None

    async def test_get_user_by_email(self, auth: SimpleRBAC, test_user: UserModel):
        """Test retrieving user by email."""
        # Act
        user = await auth.user_service.get_user_by_email(test_user.email)

        # Assert
        assert user is not None
        assert user.id == test_user.id
        assert user.email == test_user.email

    async def test_get_user_by_email_case_insensitive(
        self, auth: SimpleRBAC, test_user: UserModel
    ):
        """Test that email lookup is case-insensitive."""
        # Act
        user = await auth.user_service.get_user_by_email("TEST@EXAMPLE.COM")

        # Assert
        assert user is not None
        assert user.email == "test@example.com"


@pytest.mark.asyncio
class TestUserUpdate:
    """Test user update operations."""

    async def test_update_user_profile(self, auth: SimpleRBAC, test_user: UserModel):
        """Test updating user profile information."""
        # Act
        updated_user = await auth.user_service.update_user(
            user_id=str(test_user.id),
            first_name="Updated",
            last_name="Name",
        )

        # Assert
        assert updated_user.first_name == "Updated"
        assert updated_user.last_name == "Name"

    async def test_update_user_metadata(self, auth: SimpleRBAC, test_user: UserModel):
        """Test updating user metadata."""
        # Act
        updated_user = await auth.user_service.update_user(
            user_id=str(test_user.id),
            metadata={"theme": "dark"},
        )

        # Assert
        assert "theme" in updated_user.metadata
        assert updated_user.metadata["theme"] == "dark"

    async def test_update_nonexistent_user_raises_error(self, auth: SimpleRBAC):
        """Test that updating non-existent user raises error."""
        # Act & Assert
        with pytest.raises(UserNotFoundError):
            await auth.user_service.update_user(
                user_id="507f1f77bcf86cd799439011",
                first_name="Test",
            )

    async def test_change_password(self, auth: SimpleRBAC, test_user: UserModel, test_password: str):
        """Test changing user password."""
        # Arrange
        new_password = "NewSecurePass123!"

        # Act
        updated_user = await auth.user_service.change_password(
            user_id=str(test_user.id),
            new_password=new_password,
        )

        # Assert
        from outlabs_auth.utils.password import verify_password
        assert verify_password(new_password, updated_user.hashed_password)
        assert not verify_password(test_password, updated_user.hashed_password)

    async def test_change_password_resets_failed_attempts(self, auth: SimpleRBAC, test_user: UserModel):
        """Test that changing password resets failed login attempts."""
        # Arrange - Simulate failed login attempts
        test_user.failed_login_attempts = 3
        await test_user.save()

        # Act
        updated_user = await auth.user_service.change_password(
            user_id=str(test_user.id),
            new_password="NewSecurePass123!",
        )

        # Assert
        assert updated_user.failed_login_attempts == 0


@pytest.mark.asyncio
class TestUserStatusManagement:
    """Test user status management."""

    async def test_update_user_status(self, auth: SimpleRBAC, test_user: UserModel):
        """Test updating user status."""
        # Act
        updated_user = await auth.user_service.update_user_status(
            user_id=str(test_user.id),
            status=UserStatus.SUSPENDED,
        )

        # Assert
        assert updated_user.status == UserStatus.SUSPENDED

    async def test_verify_email(self, auth: SimpleRBAC, test_user: UserModel):
        """Test marking email as verified."""
        # Arrange
        assert test_user.email_verified is False

        # Act
        updated_user = await auth.user_service.verify_email(str(test_user.id))

        # Assert
        assert updated_user.email_verified is True


@pytest.mark.asyncio
class TestUserDeletion:
    """Test user deletion."""

    async def test_delete_user(self, auth: SimpleRBAC, test_user: UserModel):
        """Test deleting a user."""
        # Act
        result = await auth.user_service.delete_user(str(test_user.id))

        # Assert
        assert result is True

        # Verify user is gone
        user = await auth.user_service.get_user_by_id(str(test_user.id))
        assert user is None

    async def test_delete_nonexistent_user(self, auth: SimpleRBAC):
        """Test that deleting non-existent user returns False."""
        # Act
        result = await auth.user_service.delete_user("507f1f77bcf86cd799439011")

        # Assert
        assert result is False


@pytest.mark.asyncio
class TestUserListing:
    """Test user listing and pagination."""

    async def test_list_users(self, auth: SimpleRBAC, test_user: UserModel):
        """Test listing users with pagination."""
        # Act
        users, total = await auth.user_service.list_users(page=1, limit=10)

        # Assert
        assert len(users) >= 1
        assert total >= 1
        assert any(u.id == test_user.id for u in users)

    async def test_list_users_pagination(self, auth: SimpleRBAC, test_password: str):
        """Test user listing pagination."""
        # Arrange - Create multiple users
        for i in range(5):
            await auth.user_service.create_user(
                email=f"user{i}@example.com",
                password=test_password,
                first_name=f"User{i}",
                last_name="Test",
            )

        # Act - Get first page
        users_page1, total = await auth.user_service.list_users(page=1, limit=3)

        # Assert
        assert len(users_page1) == 3
        assert total >= 5

    async def test_list_users_by_status(self, auth: SimpleRBAC, test_user: UserModel):
        """Test filtering users by status."""
        # Act
        users, total = await auth.user_service.list_users(
            status=UserStatus.ACTIVE
        )

        # Assert
        assert all(u.status == UserStatus.ACTIVE for u in users)


@pytest.mark.asyncio
class TestUserSearch:
    """Test user search functionality."""

    async def test_search_users_by_email(self, auth: SimpleRBAC, test_user: UserModel):
        """Test searching users by email."""
        # Act
        users = await auth.user_service.search_users("test@")

        # Assert
        assert len(users) >= 1
        assert any(u.id == test_user.id for u in users)

    async def test_search_users_by_name(self, auth: SimpleRBAC, test_password: str):
        """Test searching users by name."""
        # Arrange
        user = await auth.user_service.create_user(
            email="uniquename@example.com",
            password=test_password,
            first_name="UniqueFirst",
            last_name="UniqueLast",
        )

        # Act
        users = await auth.user_service.search_users("UniqueFirst")

        # Assert
        assert len(users) >= 1
        assert any(u.id == user.id for u in users)

    async def test_search_users_case_insensitive(self, auth: SimpleRBAC, test_user: UserModel):
        """Test that search is case-insensitive."""
        # Act
        users = await auth.user_service.search_users("TEST")

        # Assert
        assert len(users) >= 1
