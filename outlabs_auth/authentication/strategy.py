"""
Strategy classes define HOW authentication credentials are validated.

Transport/Strategy separation pattern from FastAPI-Users (DD-038).
"""

import logging
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Protocol

from jose import JWTError, jwt

from outlabs_auth.core.exceptions import TokenInvalidError

logger = logging.getLogger(__name__)


class Strategy(Protocol):
    """
    Base protocol for authentication strategies.

    A strategy defines how to validate credentials and return user information.
    Examples: JWT validation, API key lookup, database session, etc.
    """

    async def authenticate(self, credentials: str, **kwargs: Any) -> Optional[dict]:
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
        audience: Optional[str] = None,
        verify_exp: bool = True,
        redis_client: Optional[Any] = None,
    ):
        """
        Initialize JWT strategy.

        Args:
            secret: Secret key for JWT validation
            algorithm: JWT algorithm (default: HS256)
            audience: Expected JWT audience (default: "outlabs-auth")
            verify_exp: Whether to verify token expiration (default: True)
            redis_client: Optional Redis client for blacklist checking
        """
        self.secret = secret
        self.algorithm = algorithm
        self.audience = audience or "outlabs-auth"
        self.verify_exp = verify_exp
        self.redis_client = redis_client

    async def authenticate(
        self,
        credentials: str,
        user_service: Any = None,
        session: Any = None,
        **kwargs: Any,
    ) -> Optional[dict]:
        """
        Validate JWT token and return user data.

        Args:
            credentials: JWT token
            user_service: UserService instance to fetch user
            session: Database session for PostgreSQL queries
            **kwargs: Additional context

        Returns:
            User data dict if valid, None otherwise
        """
        try:
            # Decode and validate JWT
            logger.debug("jwt_decode_start", extra={"audience": self.audience})
            payload = jwt.decode(
                credentials,
                self.secret,
                algorithms=[self.algorithm],
                audience=self.audience,
                options={"verify_exp": self.verify_exp},
            )
            logger.debug("jwt_decode_success", extra={"user_id": payload.get("sub")})

            # Check Redis blacklist if available (for immediate logout)
            jti = payload.get("jti")
            if jti and self.redis_client:
                if hasattr(self.redis_client, "is_available") and self.redis_client.is_available:
                    is_blacklisted = await self.redis_client.exists(f"blacklist:jwt:{jti}")
                    if is_blacklisted:
                        logger.info("jwt_blacklisted", extra={"jti": jti})
                        return None

            # Extract user ID from payload
            user_id = payload.get("sub")
            if not user_id:
                logger.warning("jwt_missing_sub")
                return None

            # Fetch user from database (requires session for PostgreSQL)
            if user_service and session:
                logger.debug("jwt_fetch_user_start", extra={"user_id": user_id})
                user = await user_service.get_user_by_id(session, user_id)
                logger.debug(
                    "jwt_fetch_user_done",
                    extra={
                        "user_found": user is not None,
                        "can_authenticate": user.can_authenticate() if user else None,
                    },
                )
                if user and self._token_is_stale(payload, getattr(user, "last_password_change", None)):
                    logger.info("jwt_stale_password_change", extra={"user_id": user_id})
                    return None
                if user and user.can_authenticate():
                    return {
                        "user": user,
                        "user_id": str(user.id),
                        "source": "jwt",
                        "metadata": payload,
                        "jti": jti,  # Include JTI for logout
                    }
            elif user_service:
                logger.warning("jwt_missing_db_session")
            else:
                logger.warning("jwt_missing_user_service")

            return None

        except jwt.ExpiredSignatureError:
            logger.info("jwt_expired")
            return None
        except JWTError as e:
            logger.info("jwt_invalid", extra={"error": str(e)})
            return None
        except Exception as e:
            logger.exception("jwt_auth_error", extra={"error": str(e)})
            return None

    @staticmethod
    def _normalize_token_timestamp(value: Any) -> Optional[datetime]:
        if isinstance(value, Mapping):
            precise_issued_at = value.get("iat_ms")
            if precise_issued_at is not None:
                try:
                    return datetime.fromtimestamp(
                        float(precise_issued_at) / 1000,
                        tz=timezone.utc,
                    )
                except (TypeError, ValueError, OSError):
                    return None
            value = value.get("iat")
        if value is None:
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            return None

    @classmethod
    def _token_is_stale(
        cls,
        issued_at: Any,
        last_password_change: Optional[datetime],
    ) -> bool:
        if last_password_change is None:
            return False

        issued_at_dt = cls._normalize_token_timestamp(issued_at)
        if issued_at_dt is None:
            return True

        password_change_dt = (
            last_password_change
            if last_password_change.tzinfo is not None
            else last_password_change.replace(tzinfo=timezone.utc)
        )
        return issued_at_dt < password_change_dt


class ApiKeyStrategy:
    """
    Verify API keys and return user information.

    Uses SHA-256 hashing for fast verification of high-entropy secrets (DD-028 corrected).
    Checks temporary locks and tracks failures (DD-028).

    Note: Activity tracking (DD-049) happens in AuthDeps middleware
    after successful authentication, not here. This keeps tracking
    consistent across all authentication backends (JWT, API Key, Service Token).
    """

    async def authenticate(
        self,
        credentials: str,
        api_key_service: Any = None,
        session: Any = None,
        user_service: Any = None,
        request: Any = None,
        **kwargs: Any,
    ) -> Optional[dict]:
        """
        Verify API key and return user data.

        Activity tracking happens automatically in AuthDeps after this
        method returns a valid user.

        Args:
            credentials: API key (full key with prefix)
            api_key_service: ApiKeyService instance
            **kwargs: Additional context

        Returns:
            User data dict if valid, None otherwise
        """
        if not api_key_service or session is None:
            return None

        try:
            client_ip = None
            if request is not None and getattr(request, "client", None):
                client_ip = getattr(request.client, "host", None)

            # Verify API key (checks hash, locks, scopes, IP, etc.)
            # Returns tuple: (api_key_model, usage_count)
            api_key, usage_count = await api_key_service.verify_api_key(
                session,
                credentials,
                ip_address=client_ip,
            )

            if api_key:
                resolved_owner = None
                if hasattr(api_key_service, "resolve_api_key_owner"):
                    resolved_owner = await api_key_service.resolve_api_key_owner(session, api_key)
                elif getattr(api_key, "owner_id", None) is not None:
                    if user_service is not None:
                        user = await user_service.get_user_by_id(session, api_key.owner_id)
                    else:
                        from outlabs_auth.models.sql.user import User

                        user = await session.get(User, api_key.owner_id)
                    if user is not None:
                        resolved_owner = {
                            "user": user,
                            "integration_principal": None,
                            "owner_id": getattr(user, "id", api_key.owner_id),
                        }
                if resolved_owner is None:
                    return None

                key_scopes = await api_key_service.get_api_key_scopes(session, api_key.id)
                metadata = {
                    "key_id": str(api_key.id),
                    "key_prefix": api_key.prefix,
                    "scopes": key_scopes,
                    "usage_count": usage_count,
                }
                key_kind = getattr(api_key, "key_kind", None)
                if key_kind is not None:
                    metadata["key_kind"] = key_kind.value if hasattr(key_kind, "value") else str(key_kind)
                owner_type = getattr(api_key, "owner_type", None)
                if owner_type is not None:
                    metadata["owner_type"] = owner_type
                resolved_owner_id = getattr(api_key, "resolved_owner_id", None)
                if resolved_owner_id is not None:
                    metadata["owner_id"] = str(resolved_owner_id)
                entity_id = getattr(api_key, "entity_id", None)
                if entity_id is not None:
                    metadata["entity_id"] = str(entity_id)
                principal = (
                    resolved_owner.integration_principal
                    if hasattr(resolved_owner, "integration_principal")
                    else resolved_owner.get("integration_principal")
                )
                user = resolved_owner.user if hasattr(resolved_owner, "user") else resolved_owner.get("user")
                owner_id = resolved_owner.owner_id if hasattr(resolved_owner, "owner_id") else resolved_owner.get("owner_id")
                if principal is not None:
                    metadata["principal_allowed_scopes"] = list(principal.allowed_scopes)

                if user is not None:
                    return {
                        "user": user,
                        "user_id": str(user.id),
                        "source": "api_key",
                        "api_key": api_key,
                        "metadata": metadata,
                    }

                return {
                    "user": None,
                    "user_id": None,
                    "integration_principal": principal,
                    "integration_principal_id": str(owner_id),
                    "source": "api_key",
                    "api_key": api_key,
                    "metadata": metadata,
                }

            return None

        except Exception:
            logger.exception("api_key_auth_error")
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
        audience: str = "outlabs-auth:service",
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

    async def authenticate(self, credentials: str, **kwargs: Any) -> Optional[dict]:
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
            service_token_service = kwargs.get("service_token_service")
            if service_token_service is not None:
                payload = service_token_service.validate_service_token(credentials)
            else:
                payload = jwt.decode(
                    credentials,
                    self.secret,
                    algorithms=[self.algorithm],
                    audience=self.audience,
                    options={"verify_exp": True},
                )

                if payload.get("type") != "service":
                    return None

            service_id = payload.get("sub")
            service_name = payload.get("service_name")
            permissions = payload.get("permissions")
            if not service_id or not service_name or not isinstance(permissions, list):
                return None

            # Return service authentication context
            return {
                "user": None,  # Services don't have user accounts
                "user_id": None,
                "source": "service_token",
                "service_id": service_id,
                "service_name": service_name,
                "metadata": payload,
            }

        except jwt.ExpiredSignatureError:
            return None
        except TokenInvalidError:
            return None
        except JWTError:
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

    async def authenticate(self, credentials: str, user_service: Any = None, **kwargs: Any) -> Optional[dict]:
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
                "metadata": {"superuser": True},
            }

        return None


class AnonymousStrategy:
    """
    Allow anonymous access (no authentication).

    Used when authentication is optional.
    """

    async def authenticate(self, credentials: str, **kwargs: Any) -> Optional[dict]:
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
            "metadata": {"anonymous": True},
        }
