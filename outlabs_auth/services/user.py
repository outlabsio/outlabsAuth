"""
User Service

Handles user management operations:
- Create users
- Update users
- Delete users
- List users with pagination
- Search users
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase

from outlabs_auth.models.user import UserModel, UserStatus, UserProfile
from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import (
    UserAlreadyExistsError,
    UserNotFoundError,
    InvalidPasswordError,
)
from outlabs_auth.utils.password import generate_password_hash, hash_password
from outlabs_auth.utils.validation import validate_email, validate_name


class UserService:
    """
    User management service.

    Handles:
    - User creation with password validation
    - User profile updates
    - User status management
    - User listing and search
    - User deletion
    """

    def __init__(
        self,
        database: AsyncIOMotorDatabase,
        config: AuthConfig,
        notification_service: Optional[Any] = None,
    ):
        """
        Initialize UserService.

        Args:
            database: MongoDB database instance
            config: Authentication configuration
            notification_service: Optional notification service for events
        """
        self.database = database
        self.config = config
        self.notifications = notification_service

    async def create_user(
        self,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        phone_number: Optional[str] = None,
        avatar_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        is_superuser: bool = False,
        tenant_id: Optional[str] = None,
    ) -> UserModel:
        """
        Create a new user.

        Args:
            email: User email (will be normalized to lowercase)
            password: Plain text password (will be hashed)
            first_name: User's first name
            last_name: User's last name
            phone_number: Optional phone number
            avatar_url: Optional avatar image URL
            metadata: Optional additional user data
            is_superuser: Whether user has superuser privileges
            tenant_id: Optional tenant ID for multi-tenant mode

        Returns:
            UserModel: Created user

        Raises:
            UserAlreadyExistsError: If email already exists
            InvalidPasswordError: If password doesn't meet requirements

        Example:
            >>> user = await user_service.create_user(
            ...     email="john@example.com",
            ...     password="SecurePass123!",
            ...     first_name="John",
            ...     last_name="Doe"
            ... )
            >>> user.email
            'john@example.com'
        """
        # Validate and normalize email
        email = validate_email(email)

        # Check if user already exists
        existing_user = await UserModel.find_one(UserModel.email == email)
        if existing_user:
            raise UserAlreadyExistsError(
                message=f"User with email {email} already exists",
                details={"email": email}
            )

        # Validate names
        first_name = validate_name(first_name, "first_name")
        last_name = validate_name(last_name, "last_name")

        # Hash password (with validation)
        hashed_password = generate_password_hash(password, self.config)

        # Create user profile
        profile = UserProfile(
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
            avatar_url=avatar_url,
            metadata=metadata or {},
        )

        # Create user
        user = UserModel(
            email=email,
            hashed_password=hashed_password,
            profile=profile,
            status=UserStatus.ACTIVE,
            is_superuser=is_superuser,
            tenant_id=tenant_id,
        )

        await user.save()
        
        # Emit notification (fire-and-forget)
        if self.notifications:
            await self.notifications.emit(
                "user.created",
                data={
                    "user_id": str(user.id),
                    "email": user.email,
                    "first_name": first_name,
                    "last_name": last_name,
                    "created_at": user.created_at.isoformat() if user.created_at else None
                }
            )
        
        return user

    async def get_user_by_id(self, user_id: str) -> Optional[UserModel]:
        """
        Get user by ID.

        Args:
            user_id: User ID

        Returns:
            Optional[UserModel]: User if found, None otherwise

        Example:
            >>> user = await user_service.get_user_by_id("507f1f77bcf86cd799439011")
            >>> user.email if user else None
            'john@example.com'
        """
        return await UserModel.get(user_id)

    async def get_user_by_email(self, email: str) -> Optional[UserModel]:
        """
        Get user by email.

        Args:
            email: User email

        Returns:
            Optional[UserModel]: User if found, None otherwise

        Example:
            >>> user = await user_service.get_user_by_email("john@example.com")
            >>> str(user.id) if user else None
            '507f1f77bcf86cd799439011'
        """
        email = validate_email(email)
        return await UserModel.find_one(UserModel.email == email)

    async def update_user(
        self,
        user_id: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        phone_number: Optional[str] = None,
        avatar_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> UserModel:
        """
        Update user profile.

        Args:
            user_id: User ID
            first_name: Updated first name
            last_name: Updated last name
            phone_number: Updated phone number
            avatar_url: Updated avatar URL
            metadata: Updated metadata (merged with existing)

        Returns:
            UserModel: Updated user

        Raises:
            UserNotFoundError: If user doesn't exist

        Example:
            >>> user = await user_service.update_user(
            ...     user_id="507f1f77bcf86cd799439011",
            ...     first_name="Jane"
            ... )
            >>> user.profile.first_name
            'Jane'
        """
        user = await UserModel.get(user_id)
        if not user:
            raise UserNotFoundError(
                message="User not found",
                details={"user_id": user_id}
            )

        # Update profile fields
        if first_name is not None:
            user.profile.first_name = validate_name(first_name, "first_name")

        if last_name is not None:
            user.profile.last_name = validate_name(last_name, "last_name")

        if phone_number is not None:
            user.profile.phone = phone_number  # UserProfile has 'phone' field

        if avatar_url is not None:
            user.profile.avatar_url = avatar_url

        if metadata is not None:
            # Merge metadata into preferences (UserProfile has 'preferences' field)
            user.profile.preferences = {**user.profile.preferences, **metadata}

        await user.save()
        return user

    async def change_password(
        self,
        user_id: str,
        new_password: str,
    ) -> UserModel:
        """
        Change user password.

        Args:
            user_id: User ID
            new_password: New plain text password (will be hashed)

        Returns:
            UserModel: Updated user

        Raises:
            UserNotFoundError: If user doesn't exist
            InvalidPasswordError: If password doesn't meet requirements

        Example:
            >>> user = await user_service.change_password(
            ...     user_id="507f1f77bcf86cd799439011",
            ...     new_password="NewSecurePass123!"
            ... )
        """
        user = await UserModel.get(user_id)
        if not user:
            raise UserNotFoundError(
                message="User not found",
                details={"user_id": user_id}
            )

        # Hash new password (with validation)
        hashed_password = generate_password_hash(new_password, self.config)
        user.hashed_password = hashed_password

        # Reset failed login attempts
        user.failed_login_attempts = 0
        user.locked_until = None

        await user.save()
        
        # Emit notification
        if self.notifications:
            await self.notifications.emit(
                "user.password_changed",
                data={
                    "user_id": str(user.id),
                    "email": user.email,
                    "changed_at": datetime.now(timezone.utc).isoformat()
                }
            )
        
        return user

    async def update_user_status(
        self,
        user_id: str,
        status: UserStatus,
    ) -> UserModel:
        """
        Update user status.

        Args:
            user_id: User ID
            status: New user status

        Returns:
            UserModel: Updated user

        Raises:
            UserNotFoundError: If user doesn't exist

        Example:
            >>> user = await user_service.update_user_status(
            ...     user_id="507f1f77bcf86cd799439011",
            ...     status=UserStatus.SUSPENDED
            ... )
            >>> user.status
            <UserStatus.SUSPENDED: 'suspended'>
        """
        user = await UserModel.get(user_id)
        if not user:
            raise UserNotFoundError(
                message="User not found",
                details={"user_id": user_id}
            )

        old_status = user.status
        user.status = status
        await user.save()
        
        # Emit notification
        if self.notifications:
            await self.notifications.emit(
                "user.status_changed",
                data={
                    "user_id": str(user.id),
                    "email": user.email,
                    "old_status": old_status.value,
                    "new_status": status.value,
                    "changed_at": datetime.now(timezone.utc).isoformat()
                }
            )
        
        return user

    async def delete_user(self, user_id: str) -> bool:
        """
        Delete user.

        Note: This is a hard delete. Consider using update_user_status
        with TERMINATED status for soft deletes.

        Args:
            user_id: User ID

        Returns:
            bool: True if deleted, False if not found

        Example:
            >>> deleted = await user_service.delete_user("507f1f77bcf86cd799439011")
            >>> deleted
            True
        """
        user = await UserModel.get(user_id)
        if not user:
            return False
        
        # Store user data before deletion for notification
        user_email = user.email
        user_id_str = str(user.id)

        await user.delete()
        
        # Emit notification
        if self.notifications:
            await self.notifications.emit(
                "user.deleted",
                data={
                    "user_id": user_id_str,
                    "email": user_email,
                    "deleted_at": datetime.now(timezone.utc).isoformat()
                }
            )
        
        return True

    async def list_users(
        self,
        page: int = 1,
        limit: int = 20,
        status: Optional[UserStatus] = None,
        tenant_id: Optional[str] = None,
    ) -> tuple[List[UserModel], int]:
        """
        List users with pagination.

        Args:
            page: Page number (1-indexed)
            limit: Results per page
            status: Filter by status
            tenant_id: Filter by tenant (multi-tenant mode)

        Returns:
            tuple[List[UserModel], int]: (users, total_count)

        Example:
            >>> users, total = await user_service.list_users(page=1, limit=10)
            >>> len(users)
            10
            >>> total
            42
        """
        # Build query
        query = {}
        if status:
            query["status"] = status
        if tenant_id:
            query["tenant_id"] = tenant_id

        # Get total count
        total_count = await UserModel.find(query).count()

        # Get paginated results
        skip = (page - 1) * limit
        users = await UserModel.find(query).skip(skip).limit(limit).to_list()

        return users, total_count

    async def search_users(
        self,
        search_term: str,
        limit: int = 20,
    ) -> List[UserModel]:
        """
        Search users by email or name.

        Args:
            search_term: Search term (searches email, first name, last name)
            limit: Maximum results to return

        Returns:
            List[UserModel]: Matching users

        Example:
            >>> users = await user_service.search_users("john")
            >>> [u.email for u in users]
            ['john@example.com', 'johnny@example.com']
        """
        # Case-insensitive regex search
        search_regex = {"$regex": search_term, "$options": "i"}

        users = await UserModel.find({
            "$or": [
                {"email": search_regex},
                {"profile.first_name": search_regex},
                {"profile.last_name": search_regex},
            ]
        }).limit(limit).to_list()

        return users

    async def verify_email(self, user_id: str) -> UserModel:
        """
        Mark user email as verified.

        Args:
            user_id: User ID

        Returns:
            UserModel: Updated user

        Raises:
            UserNotFoundError: If user doesn't exist

        Example:
            >>> user = await user_service.verify_email("507f1f77bcf86cd799439011")
            >>> user.email_verified
            True
        """
        user = await UserModel.get(user_id)
        if not user:
            raise UserNotFoundError(
                message="User not found",
                details={"user_id": user_id}
            )

        user.email_verified = True
        await user.save()
        return user
