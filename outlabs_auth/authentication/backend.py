"""
AuthBackend combines Transport + Strategy for complete authentication.

Transport/Strategy separation pattern from FastAPI-Users (DD-038).
"""

from typing import Optional, Any
from outlabs_auth.authentication.transport import Transport
from outlabs_auth.authentication.strategy import Strategy


class AuthBackend:
    """
    Authentication backend that combines a Transport and a Strategy.

    The Transport defines HOW credentials are delivered (Bearer, API key header, cookie, etc.)
    The Strategy defines HOW credentials are validated (JWT decode, API key lookup, etc.)

    Example:
        ```python
        # JWT authentication via Bearer token
        jwt_backend = AuthBackend(
            name="jwt",
            transport=BearerTransport(),
            strategy=JWTStrategy(secret=SECRET)
        )

        # API key authentication via X-API-Key header
        api_key_backend = AuthBackend(
            name="api_key",
            transport=ApiKeyTransport(header_name="X-API-Key"),
            strategy=ApiKeyStrategy()
        )
        ```
    """

    def __init__(self, name: str, transport: Transport, strategy: Strategy):
        """
        Initialize authentication backend.

        Args:
            name: Unique name for this backend (used in OpenAPI schema)
            transport: Transport instance (how to get credentials)
            strategy: Strategy instance (how to validate credentials)
        """
        self.name = name
        self.transport = transport
        self.strategy = strategy

    def has_credentials(self, request: Any) -> bool:
        """
        Cheap hint: does this request look like it carries credentials for this backend?

        Lets the caller skip the full authentication pipeline for requests that
        obviously have no credentials. Defaults to ``True`` when the transport does
        not implement the hint, preserving previous behavior.
        """
        transport_hint = getattr(self.transport, "has_credentials", None)
        if transport_hint is None:
            return True
        try:
            return bool(transport_hint(request))
        except Exception:
            return True

    async def authenticate(self, request: Any, **kwargs: Any) -> Optional[dict]:
        """
        Attempt authentication using this backend.

        Args:
            request: FastAPI request object
            **kwargs: Additional context (services, etc.)

        Returns:
            Authentication result dict if successful, None otherwise

        The returned dict contains:
            - user: User object (if applicable)
            - user_id: User ID string
            - source: Authentication source ("jwt", "api_key", "service_token", etc.)
            - metadata: Additional auth metadata
        """
        # Step 1: Extract credentials using transport
        credentials = await self.transport.get_credentials(request)
        if not credentials:
            return None

        # Step 2: Validate credentials using strategy
        result = await self.strategy.authenticate(credentials, request=request, **kwargs)
        return result

    def __repr__(self) -> str:
        return f"AuthBackend(name={self.name!r}, transport={self.transport.__class__.__name__}, strategy={self.strategy.__class__.__name__})"
