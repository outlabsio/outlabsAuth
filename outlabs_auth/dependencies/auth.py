"""
FastAPI Authentication Dependencies

Provides easy-to-use dependency helpers for protecting routes.
"""
from typing import Optional, List
from fastapi import Depends, Header, HTTPException

from outlabs_auth.models.sql.user import User
from outlabs_auth.core.auth import OutlabsAuth
from outlabs_auth.core.exceptions import (
    TokenInvalidError,
    TokenExpiredError,
    UserNotFoundError,
    PermissionDeniedError,
)


class AuthDeps:
    """
    FastAPI dependency factory for authentication and authorization.

    Example:
        >>> from fastapi import FastAPI, Depends
        >>> from outlabs_auth import SimpleRBAC
        >>> from outlabs_auth.dependencies import AuthDeps
        >>>
        >>> app = FastAPI()
        >>> auth = SimpleRBAC(database=db, secret_key="secret")
        >>> deps = AuthDeps(auth)
        >>>
        >>> @app.get("/protected")
        >>> async def protected_route(user: User = Depends(deps.authenticated())):
        ...     return {"user_id": str(user.id), "email": user.email}
        >>>
        >>> @app.delete("/users/{user_id}")
        >>> async def delete_user(
        ...     user_id: str,
        ...     user: User = Depends(deps.requires("user:delete"))
        ... ):
        ...     return await auth.user_service.delete_user(user_id)
    """

    def __init__(self, auth: OutlabsAuth):
        """
        Initialize dependency factory.

        Args:
            auth: Initialized OutlabsAuth instance
        """
        self.auth = auth

    def authenticated(self):
        """
        Dependency to require authenticated user.

        Returns:
            Dependency that extracts and validates JWT token

        Example:
            >>> @app.get("/me")
            >>> async def get_me(user: User = Depends(deps.authenticated())):
            ...     return user

        """
        async def get_current_user(
            authorization: Optional[str] = Header(None)
        ) -> User:
            if not authorization:
                raise HTTPException(
                    status_code=401,
                    detail="Not authenticated",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Extract token from "Bearer <token>"
            if not authorization.startswith("Bearer "):
                raise HTTPException(
                    status_code=401,
                    detail="Invalid authentication scheme. Expected: Bearer",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            token = authorization.replace("Bearer ", "")

            try:
                user = await self.auth.get_current_user(token)
                return user
            except TokenExpiredError:
                raise HTTPException(
                    status_code=401,
                    detail="Token has expired",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            except TokenInvalidError as e:
                raise HTTPException(
                    status_code=401,
                    detail=f"Invalid token: {e.message}",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            except UserNotFoundError:
                raise HTTPException(
                    status_code=401,
                    detail="User not found",
                    headers={"WWW-Authenticate": "Bearer"},
                )

        return Depends(get_current_user)

    def requires(self, *permissions: str):
        """
        Dependency to require specific permission(s).

        Args:
            *permissions: Permission names (user must have ALL)

        Returns:
            Dependency that checks permissions

        Example:
            >>> @app.post("/users")
            >>> async def create_user(
            ...     data: UserCreate,
            ...     user: User = Depends(deps.requires("user:create"))
            ... ):
            ...     return await auth.user_service.create_user(**data.dict())

        """
        async def check_permissions(
            user: User = Depends(self.authenticated())
        ) -> User:
            # Superusers always pass
            if user.is_superuser:
                return user

            # Check each permission
            for perm in permissions:
                try:
                    has_perm = await self.auth.permission_service.check_permission(
                        str(user.id), perm
                    )
                    if not has_perm:
                        raise PermissionDeniedError(
                            message=f"Missing permission: {perm}",
                            details={"required_permission": perm}
                        )
                except PermissionDeniedError:
                    raise HTTPException(
                        status_code=403,
                        detail=f"Permission denied: {perm}",
                    )

            return user

        return Depends(check_permissions)

    def requires_any(self, *permissions: str):
        """
        Dependency to require ANY of the permissions.

        Args:
            *permissions: Permission names (user must have AT LEAST ONE)

        Returns:
            Dependency that checks permissions

        Example:
            >>> @app.put("/users/{user_id}")
            >>> async def update_user(
            ...     user_id: str,
            ...     data: UserUpdate,
            ...     user: User = Depends(
            ...         deps.requires_any("user:update", "admin:all")
            ...     )
            ... ):
            ...     return await auth.user_service.update_user(user_id, **data.dict())
        """
        async def check_any_permission(
            user: User = Depends(self.authenticated())
        ) -> User:
            # Superusers always pass
            if user.is_superuser:
                return user

            # Check if user has any of the permissions
            for perm in permissions:
                has_perm = await self.auth.permission_service.check_permission(
                    str(user.id), perm
                )
                if has_perm:
                    return user  # User has at least one permission

            # User has none of the required permissions
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: requires one of {list(permissions)}",
            )

        return Depends(check_any_permission)

    def optional_auth(self):
        """
        Dependency for optional authentication.

        Returns None if no token provided, otherwise returns user.

        Example:
            >>> @app.get("/public-or-private")
            >>> async def flexible_route(
            ...     user: Optional[User] = Depends(deps.optional_auth())
            ... ):
            ...     if user:
            ...         return {"message": f"Hello {user.email}"}
            ...     return {"message": "Hello guest"}
        """
        async def get_optional_user(
            authorization: Optional[str] = Header(None)
        ) -> Optional[User]:
            if not authorization:
                return None

            if not authorization.startswith("Bearer "):
                return None

            token = authorization.replace("Bearer ", "")

            try:
                user = await self.auth.get_current_user(token)
                return user
            except (TokenExpiredError, TokenInvalidError, UserNotFoundError):
                return None

        return Depends(get_optional_user)

    @property
    def user(self):
        """Shortcut for authenticated user dependency"""
        return self.authenticated()

    def superuser(self):
        """
        Dependency to require superuser.

        Example:
            >>> @app.post("/admin/reset-database")
            >>> async def reset_db(user: User = Depends(deps.superuser())):
            ...     # Only superusers can access
            ...     pass
        """
        async def check_superuser(
            user: User = Depends(self.authenticated())
        ) -> User:
            if not user.is_superuser:
                raise HTTPException(
                    status_code=403,
                    detail="Superuser access required",
                )
            return user

        return Depends(check_superuser)
