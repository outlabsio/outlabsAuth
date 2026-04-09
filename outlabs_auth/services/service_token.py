"""
Service Token Service

Provides long-lived JWT tokens for service-to-service authentication.
Tokens have embedded permissions for ~0.5ms validation with zero DB hits (DD-034).

Key differences from user tokens:
- Long-lived (365 days vs 15 minutes)
- Permissions embedded in token (no DB lookup)
- For service accounts, not users
- No refresh mechanism (recreate when expired)
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, cast

from jose import jwt, JWTError
from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import TokenInvalidError

logger = logging.getLogger(__name__)


class ServiceTokenService:
    """
    Service for creating and validating service tokens.

    Service tokens are long-lived JWT tokens used for service-to-service
    authentication. They embed permissions directly in the token payload,
    enabling ~0.5ms validation with zero database hits.

    Features:
    - Long-lived tokens (default: 365 days)
    - Embedded permissions for fast validation
    - No database lookups required
    - Support for service metadata

    Example:
        >>> service = ServiceTokenService(config)
        >>> token = service.create_service_token(
        ...     service_id="reporting-service",
        ...     service_name="Reporting Service",
        ...     permissions=["report:generate", "data:read"],
        ...     metadata={"environment": "production"}
        ... )
        >>> # Later, validate token...
        >>> payload = service.validate_service_token(token)
        >>> payload["permissions"]  # ['report:generate', 'data:read']
    """

    SERVICE_AUDIENCE = "outlabs-auth:service"

    def __init__(self, config: AuthConfig):
        """
        Initialize ServiceTokenService.

        Args:
            config: Authentication configuration
        """
        self.config = config

    def create_service_token(
        self,
        service_id: str,
        service_name: str,
        permissions: List[str],
        expires_days: int = 365,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Create a service token with embedded permissions.

        Args:
            service_id: Unique service identifier
            service_name: Human-readable service name
            permissions: List of permissions to embed
            expires_days: Token expiration in days (default: 365)
            metadata: Optional metadata to include

        Returns:
            str: JWT service token

        Example:
            >>> token = service.create_service_token(
            ...     service_id="analytics-api",
            ...     service_name="Analytics API",
            ...     permissions=["analytics:read", "data:export"],
            ...     metadata={"version": "2.0", "environment": "prod"}
            ... )
        """
        # Calculate expiration
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)

        # Build token payload
        payload = {
            "sub": service_id,  # Subject (service ID)
            "type": "service",  # Token type
            "aud": self.SERVICE_AUDIENCE,
            "service_name": service_name,
            "permissions": permissions,  # Embedded permissions
            "iat": datetime.now(timezone.utc),  # Issued at
            "exp": expires_at,  # Expiration
        }

        # Add metadata if provided
        if metadata:
            payload["metadata"] = metadata

        # Create JWT token using jose
        token = jwt.encode(
            payload,
            self.config.secret_key,
            algorithm=self.config.algorithm,
        )

        logger.info(
            f"Created service token for {service_id} "
            f"with {len(permissions)} permissions "
            f"(expires: {expires_at.strftime('%Y-%m-%d')})"
        )

        return cast(str, token)

    def validate_service_token(self, token: str) -> Dict[str, Any]:
        """
        Validate service token and return payload.

        This is a fast operation (~0.5ms) with zero database hits.
        Permissions are read directly from the token payload.

        Args:
            token: JWT service token

        Returns:
            Dict[str, Any]: Token payload with embedded permissions

        Raises:
            TokenInvalidError: If token is invalid or expired

        Example:
            >>> payload = service.validate_service_token(token)
            >>> service_id = payload["sub"]
            >>> permissions = payload["permissions"]
            >>> if "report:generate" in permissions:
            ...     # Service has permission
        """
        try:
            # Verify token (includes expiration check)
            payload = jwt.decode(
                token,
                self.config.secret_key,
                algorithms=[self.config.algorithm],
                audience=self.SERVICE_AUDIENCE,
            )

            # Verify it's a service token
            if payload.get("type") != "service":
                raise TokenInvalidError(
                    message="Token is not a service token",
                    details={"token_type": payload.get("type")}
                )

            return cast(Dict[str, Any], payload)

        except jwt.ExpiredSignatureError:
            raise TokenInvalidError(
                message="Service token has expired",
                details={"expired": True}
            )
        except JWTError as e:
            raise TokenInvalidError(
                message=f"Invalid service token: {str(e)}",
                details={"error": str(e)}
            )

    def check_service_permission(
        self,
        token_payload: Dict[str, Any],
        required_permission: str
    ) -> bool:
        """
        Check if service has a specific permission.

        Args:
            token_payload: Validated token payload
            required_permission: Permission to check

        Returns:
            bool: True if service has permission

        Example:
            >>> payload = service.validate_service_token(token)
            >>> if service.check_service_permission(payload, "data:export"):
            ...     # Service has permission to export data
        """
        permissions = token_payload.get("permissions", [])
        normalized = {
            ("*:*" if permission == "*" else permission)
            for permission in permissions
            if permission
        }

        from outlabs_auth.services.permission import PermissionService

        return PermissionService._permission_set_allows(required_permission, normalized)

    def get_service_permissions(self, token_payload: Dict[str, Any]) -> List[str]:
        """
        Get all permissions from service token.

        Args:
            token_payload: Validated token payload

        Returns:
            List[str]: List of permissions

        Example:
            >>> payload = service.validate_service_token(token)
            >>> permissions = service.get_service_permissions(payload)
            >>> print(permissions)
            ['report:generate', 'data:read', 'data:export']
        """
        return cast(List[str], token_payload.get("permissions", []))

    def get_service_metadata(self, token_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get metadata from service token.

        Args:
            token_payload: Validated token payload

        Returns:
            Dict[str, Any]: Service metadata

        Example:
            >>> payload = service.validate_service_token(token)
            >>> metadata = service.get_service_metadata(payload)
            >>> environment = metadata.get("environment")
        """
        return cast(Dict[str, Any], token_payload.get("metadata", {}))

    def get_service_info(self, token_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get service information from token.

        Args:
            token_payload: Validated token payload

        Returns:
            Dict[str, Any]: Service information

        Example:
            >>> payload = service.validate_service_token(token)
            >>> info = service.get_service_info(payload)
            >>> print(f"Service: {info['service_name']}")
            >>> print(f"ID: {info['service_id']}")
            >>> print(f"Expires: {info['expires_at']}")
        """
        return {
            "service_id": token_payload.get("sub"),
            "service_name": token_payload.get("service_name"),
            "token_type": token_payload.get("type"),
            "issued_at": token_payload.get("iat"),
            "expires_at": token_payload.get("exp"),
            "permissions": token_payload.get("permissions", []),
            "metadata": token_payload.get("metadata", {}),
        }

    def create_api_service_token(
        self,
        api_name: str,
        permissions: List[str],
        expires_days: int = 365,
    ) -> str:
        """
        Convenience method for creating API service tokens.

        Args:
            api_name: API name (e.g., "analytics-api")
            permissions: List of permissions
            expires_days: Token expiration in days

        Returns:
            str: JWT service token

        Example:
            >>> token = service.create_api_service_token(
            ...     api_name="reporting-api",
            ...     permissions=["report:*", "data:read"]
            ... )
        """
        return self.create_service_token(
            service_id=f"api-{api_name}",
            service_name=f"{api_name.title()} API",
            permissions=permissions,
            expires_days=expires_days,
            metadata={"service_type": "api"}
        )

    def create_worker_service_token(
        self,
        worker_name: str,
        permissions: List[str],
        expires_days: int = 365,
    ) -> str:
        """
        Convenience method for creating background worker service tokens.

        Args:
            worker_name: Worker name (e.g., "email-sender")
            permissions: List of permissions
            expires_days: Token expiration in days

        Returns:
            str: JWT service token

        Example:
            >>> token = service.create_worker_service_token(
            ...     worker_name="notification-sender",
            ...     permissions=["notification:send", "user:read"]
            ... )
        """
        return self.create_service_token(
            service_id=f"worker-{worker_name}",
            service_name=f"{worker_name.title()} Worker",
            permissions=permissions,
            expires_days=expires_days,
            metadata={"service_type": "worker"}
        )

    def create_token(self, *args: Any, **kwargs: Any) -> str:
        """Backward-compatible alias for service token creation."""
        return self.create_service_token(*args, **kwargs)

    def validate_jwt(self, token: str) -> Dict[str, Any]:
        """Backward-compatible alias for service token validation."""
        return self.validate_service_token(token)
