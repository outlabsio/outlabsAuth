"""
Transport classes define HOW authentication credentials are delivered.

Transport/Strategy separation pattern from FastAPI-Users (DD-038).
"""

from typing import Optional
from fastapi import Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials


class Transport:
    """
    Base class for authentication transports.

    A transport defines how to extract authentication credentials from an HTTP request.
    Examples: Bearer token in Authorization header, API key in custom header, cookies, etc.
    """

    async def get_credentials(self, request: Request) -> Optional[str]:
        """
        Extract authentication credentials from the request.

        Args:
            request: FastAPI request object

        Returns:
            Credentials string if found, None otherwise
        """
        raise NotImplementedError()  # pragma: no cover

    def has_credentials(self, request: Request) -> bool:
        """
        Cheap hint: does the request appear to carry credentials this transport can read?

        Used by the backend loop to skip credential validation entirely when no backend
        could possibly match (e.g. an anonymous request with no auth headers). The default
        is conservative (``True``) so unknown transports still run their full extraction.
        """
        return True


class BearerTransport(Transport):
    """
    Extract credentials from Authorization: Bearer {token} header.

    Used for JWT tokens and service tokens.
    """

    def __init__(self):
        self.scheme = HTTPBearer(auto_error=False)

    async def get_credentials(self, request: Request) -> Optional[str]:
        """Extract Bearer token from Authorization header."""
        authorization: Optional[HTTPAuthorizationCredentials] = await self.scheme(request)
        if authorization:
            return authorization.credentials
        return None

    def has_credentials(self, request: Request) -> bool:
        return "authorization" in request.headers


class ApiKeyTransport(Transport):
    """
    Extract API key from custom header.

    Default: X-API-Key header
    Can be configured to use different header names.
    """

    def __init__(self, header_name: str = "X-API-Key"):
        """
        Initialize API key transport.

        Args:
            header_name: Name of the header containing the API key
        """
        self.header_name = header_name

    async def get_credentials(self, request: Request) -> Optional[str]:
        """Extract API key from custom header."""
        return request.headers.get(self.header_name)

    def has_credentials(self, request: Request) -> bool:
        return self.header_name.lower() in request.headers


class HeaderTransport(Transport):
    """
    Extract credentials from any custom header.

    Generic transport for custom authentication schemes.
    """

    def __init__(self, header_name: str, prefix: Optional[str] = None):
        """
        Initialize header transport.

        Args:
            header_name: Name of the header containing credentials
            prefix: Optional prefix to strip from the header value (e.g., "Bearer ")
        """
        self.header_name = header_name
        self.prefix = prefix

    async def get_credentials(self, request: Request) -> Optional[str]:
        """Extract credentials from custom header."""
        value = request.headers.get(self.header_name)
        if value and self.prefix:
            if value.startswith(self.prefix):
                return value[len(self.prefix):]
            return None
        return value

    def has_credentials(self, request: Request) -> bool:
        return self.header_name.lower() in request.headers


class CookieTransport(Transport):
    """
    Extract credentials from cookie.

    Used for session-based authentication.
    """

    def __init__(self, cookie_name: str = "access_token"):
        """
        Initialize cookie transport.

        Args:
            cookie_name: Name of the cookie containing credentials
        """
        self.cookie_name = cookie_name

    async def get_credentials(self, request: Request) -> Optional[str]:
        """Extract credentials from cookie."""
        return request.cookies.get(self.cookie_name)

    def has_credentials(self, request: Request) -> bool:
        return self.cookie_name in request.cookies


class QueryParamTransport(Transport):
    """
    Extract credentials from query parameter.

    WARNING: Not recommended for production (credentials appear in logs).
    Useful for development/testing only.
    """

    def __init__(self, param_name: str = "token"):
        """
        Initialize query parameter transport.

        Args:
            param_name: Name of the query parameter containing credentials
        """
        self.param_name = param_name

    async def get_credentials(self, request: Request) -> Optional[str]:
        """Extract credentials from query parameter."""
        return request.query_params.get(self.param_name)

    def has_credentials(self, request: Request) -> bool:
        return self.param_name in request.query_params
