"""
Strategy classes define HOW authentication credentials are validated.

Transport/Strategy separation pattern from FastAPI-Users (DD-038).
"""

from typing import Optional, Protocol, Any
import jwt
from datetime import datetime, timedelta


class Strategy(Protocol):
    """
    Base protocol for authentication strategies.

    A strategy defines how to validate credentials and return user information.
    Examples: JWT validation, API key lookup, database session, etc.
    """

    async def authenticate(
        self,
        credentials: str,
        **kwargs: Any
    ) -> Optional[dict]:
        """
        Authenticate credentials and return user data.

        Args:
            credentials: The credentials to validate (token, API key, etc.)
            **kwargs: Additional context (user_service, api_key_service, etc.)

        Returns:
            User data dict if valid, None otherwise
        """
        ...  # pragma: no cover


class JWTStrategy:
    """
    Validate JWT tokens and return user information.

    Used for standard user authentication with access tokens.
    """

    def __init__(
        self,
        secret: str,
        algorithm: str = "HS256",
        audience: list[str] = None,
        verify_exp: bool = True
    ):
        """
        Initialize JWT strategy.

        Args:
            secret: Secret key for JWT validation
            algorithm: JWT algorithm (default: HS256)
            audience: Expected JWT audience (default: ["outlabs-auth:access"])
            verify_exp: Whether to verify token expiration (default: True)
        """
        self.secret = secret
        self.algorithm = algorithm
        self.audience = audience or ["outlabs-auth:access"]
        self.verify_exp = verify_exp

    async def authenticate(
        self,
        credentials: str,
        user_service: Any = None,
        **kwargs: Any
    ) -> Optional[dict]:
        """
        Validate JWT token and return user data.

        Args:
            credentials: JWT token
            user_service: UserService instance to fetch user
            **kwargs: Additional context

        Returns:
            User data dict if valid, None otherwise
        """
        try:
            # Decode and validate JWT
            payload = jwt.decode(
                credentials,
                self.secret,
                algorithms=[self.algorithm],
                audience=self.audience,
                options={"verify_exp": self.verify_exp}
            )

            # Extract user ID from payload
            user_id = payload.get("sub")
            if not user_id:
                return None

            # Fetch user from database
            if user_service:
                user = await user_service.get_user(user_id)
                if user and user.is_active:
                    return {
                        "user": user,
                        "user_id": str(user.id),
                        "source": "jwt",
                        "metadata": payload
                    }

            return None

        except jwt.ExpiredSignatureError:
            # Token expired
            return None
        except jwt.InvalidTokenError:
            # Invalid token
            return None
        except Exception:
            # Any other error
            return None


class ApiKeyStrategy:
    """
    Validate API keys and return user information.

    Uses argon2id hashing for security (DD-028).
    Checks temporary locks and tracks failures (DD-028).
    """

    async def authenticate(
        self,
        credentials: str,
        api_key_service: Any = None,
        **kwargs: Any
    ) -> Optional[dict]:
        """
        Validate API key and return user data.

        Args:
            credentials: API key (full key with prefix)
            api_key_service: ApiKeyService instance
            **kwargs: Additional context

        Returns:
            User data dict if valid, None otherwise
        """
        if not api_key_service:
            return None

        try:
            # Verify API key (checks hash, locks, permissions, IP, etc.)
            api_key_result = await api_key_service.verify_api_key(credentials)

            if api_key_result:
                return {
                    "user": api_key_result["user"],
                    "user_id": str(api_key_result["user"].id),
                    "source": "api_key",
                    "api_key": api_key_result["api_key"],
                    "metadata": {
                        "key_id": str(api_key_result["api_key"].id),
                        "key_prefix": api_key_result["api_key"].key_prefix,
                        "permissions": api_key_result["api_key"].permissions,
                        "environment": api_key_result["api_key"].environment
                    }
                }

            return None

        except Exception:
            return None


class ServiceTokenStrategy:
    """
    Validate JWT service tokens for microservice authentication.

    Zero-DB authentication for internal services (DD-034).
    Service tokens are stateless JWTs with special audience.
    """

    def __init__(
        self,
        secret: str,
        algorithm: str = "HS256",
        audience: str = "outlabs-auth:service"
    ):
        """
        Initialize service token strategy.

        Args:
            secret: Secret key for service tokens (different from user JWT secret)
            algorithm: JWT algorithm (default: HS256)
            audience: Expected JWT audience (default: "outlabs-auth:service")
        """
        self.secret = secret
        self.algorithm = algorithm
        self.audience = audience

    async def authenticate(
        self,
        credentials: str,
        **kwargs: Any
    ) -> Optional[dict]:
        """
        Validate service token.

        Service tokens don't require database lookup - they are self-contained.

        Args:
            credentials: Service JWT token
            **kwargs: Additional context (not used)

        Returns:
            Service auth data if valid, None otherwise
        """
        try:
            # Decode and validate service token
            payload = jwt.decode(
                credentials,
                self.secret,
                algorithms=[self.algorithm],
                audience=[self.audience],
                options={"verify_exp": True}
            )

            # Service tokens must have service_name
            service_name = payload.get("service_name")
            if not service_name:
                return None

            # Return service authentication context
            return {
                "user": None,  # Services don't have user accounts
                "user_id": None,
                "source": "service_token",
                "service_name": service_name,
                "metadata": {
                    "service_name": service_name,
                    "permissions": payload.get("permissions", []),
                    "iat": payload.get("iat"),
                    "exp": payload.get("exp")
                }
            }

        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
        except Exception:
            return None


class SuperuserStrategy:
    """
    Validate superuser token (emergency access).

    Simple token comparison for superuser access.
    Should be used sparingly and with strong tokens.
    """

    def __init__(self, superuser_token: str):
        """
        Initialize superuser strategy.

        Args:
            superuser_token: The static superuser token (should be strong and secret)
        """
        self.superuser_token = superuser_token

    async def authenticate(
        self,
        credentials: str,
        user_service: Any = None,
        **kwargs: Any
    ) -> Optional[dict]:
        """
        Validate superuser token.

        Args:
            credentials: Superuser token
            user_service: UserService instance (optional, to fetch superuser account)
            **kwargs: Additional context

        Returns:
            Superuser auth data if valid, None otherwise
        """
        # Simple token comparison
        if credentials == self.superuser_token:
            # Optionally fetch first superuser account from DB
            superuser = None
            if user_service:
                try:
                    # Get first superuser from database
                    superuser = await user_service.get_first_superuser()
                except Exception:
                    pass

            return {
                "user": superuser,
                "user_id": str(superuser.id) if superuser else None,
                "source": "superuser",
                "metadata": {"superuser": True}
            }

        return None


class AnonymousStrategy:
    """
    Allow anonymous access (no authentication).

    Used when authentication is optional.
    """

    async def authenticate(
        self,
        credentials: str,
        **kwargs: Any
    ) -> Optional[dict]:
        """
        Always return anonymous user data.

        Args:
            credentials: Not used (anonymous has no credentials)
            **kwargs: Additional context

        Returns:
            Anonymous user data
        """
        return {
            "user": None,
            "user_id": None,
            "source": "anonymous",
            "metadata": {"anonymous": True}
        }
