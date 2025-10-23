"""Abstract OAuth provider base class."""

from abc import ABC, abstractmethod
from typing import Optional
import httpx

from .models import OAuthTokenResponse, OAuthUserInfo, OAuthAuthorizationURL
from .security import generate_state, generate_nonce, generate_pkce_pair, build_authorization_url
from .exceptions import ProviderError


class OAuthProvider(ABC):
    """
    Abstract base class for OAuth 2.0 providers.
    
    Implement this class to add support for a new OAuth provider.
    Pre-configured providers (Google, Facebook, Apple, GitHub) are available.
    
    Example:
        class CustomProvider(OAuthProvider):
            name = "custom"
            display_name = "Custom OAuth"
            
            def __init__(self, client_id: str, client_secret: str):
                self.client_id = client_id
                self.client_secret = client_secret
                # Configure endpoints and scopes
            
            async def exchange_code(...):
                # Implement token exchange
                pass
            
            async def get_user_info(...):
                # Implement user info fetch
                pass
    """
    
    # Provider metadata (override in subclass)
    name: str = "abstract"  # Unique provider name (lowercase, e.g., "google")
    display_name: str = "Abstract Provider"  # Human-readable name
    
    # OAuth endpoints (override in subclass)
    authorization_url: str = ""
    token_url: str = ""
    user_info_url: str = ""
    
    # Default scopes (override in subclass)
    default_scopes: list[str] = []
    
    # OAuth configuration
    supports_pkce: bool = True  # Most modern providers support PKCE
    supports_refresh: bool = True  # Most providers support token refresh
    supports_revocation: bool = False  # Not all providers support revocation
    
    # OpenID Connect
    is_oidc: bool = False  # True if provider supports OpenID Connect
    jwks_uri: Optional[str] = None  # For OIDC ID token validation
    
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        scopes: Optional[list[str]] = None
    ):
        """
        Initialize OAuth provider.
        
        Args:
            client_id: OAuth client ID from provider
            client_secret: OAuth client secret from provider
            scopes: List of scopes to request (uses default_scopes if not provided)
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.scopes = scopes or self.default_scopes
        
        # HTTP client for API requests
        self._http_client: Optional[httpx.AsyncClient] = None
    
    async def get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client
    
    async def close(self):
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
    
    def get_authorization_url(
        self,
        redirect_uri: str,
        state: Optional[str] = None,
        use_pkce: bool = True,
        use_nonce: bool = None,
        **extra_params
    ) -> OAuthAuthorizationURL:
        """
        Generate OAuth authorization URL.
        
        Args:
            redirect_uri: Where to redirect after authorization
            state: State parameter (generated if not provided)
            use_pkce: Use PKCE flow (recommended)
            use_nonce: Use nonce for OIDC (auto-detected if None)
            **extra_params: Additional provider-specific parameters
        
        Returns:
            OAuthAuthorizationURL with URL and security parameters
        """
        # Generate security parameters
        state = state or generate_state()
        
        code_verifier = None
        code_challenge = None
        if use_pkce and self.supports_pkce:
            code_verifier, code_challenge = generate_pkce_pair()
        
        nonce = None
        if use_nonce is None:
            use_nonce = self.is_oidc
        if use_nonce:
            nonce = generate_nonce()
        
        # Build authorization URL
        scope_str = " ".join(self.scopes)
        url = build_authorization_url(
            base_url=self.authorization_url,
            client_id=self.client_id,
            redirect_uri=redirect_uri,
            scope=scope_str,
            state=state,
            code_challenge=code_challenge,
            nonce=nonce,
            **extra_params
        )
        
        return OAuthAuthorizationURL(
            url=url,
            state=state,
            code_verifier=code_verifier,
            code_challenge=code_challenge,
            nonce=nonce
        )
    
    @abstractmethod
    async def exchange_code(
        self,
        code: str,
        redirect_uri: str,
        code_verifier: Optional[str] = None
    ) -> OAuthTokenResponse:
        """
        Exchange authorization code for access token.
        
        Args:
            code: Authorization code from callback
            redirect_uri: Same redirect_uri used in authorization
            code_verifier: PKCE code verifier (if PKCE was used)
        
        Returns:
            OAuth token response
        
        Raises:
            InvalidCodeError: If code is invalid or expired
            ProviderError: If provider returns an error
        """
        pass
    
    @abstractmethod
    async def get_user_info(
        self,
        access_token: str
    ) -> OAuthUserInfo:
        """
        Fetch user info from provider using access token.
        
        Args:
            access_token: OAuth access token
        
        Returns:
            Standardized user info
        
        Raises:
            ProviderError: If provider returns an error
        """
        pass
    
    async def refresh_token(
        self,
        refresh_token: str
    ) -> OAuthTokenResponse:
        """
        Refresh access token using refresh token.
        
        Optional - not all providers support token refresh.
        
        Args:
            refresh_token: OAuth refresh token
        
        Returns:
            New token response
        
        Raises:
            NotImplementedError: If provider doesn't support refresh
            ProviderError: If provider returns an error
        """
        if not self.supports_refresh:
            raise NotImplementedError(
                f"{self.display_name} does not support token refresh"
            )
        
        # Default implementation - override if provider uses different format
        client = await self.get_http_client()
        response = await client.post(
            self.token_url,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }
        )
        
        if response.status_code != 200:
            raise ProviderError(
                provider=self.name,
                error="token_refresh_failed",
                error_description=response.text
            )
        
        data = response.json()
        return OAuthTokenResponse(**data)
    
    async def revoke_token(
        self,
        token: str,
        token_type_hint: str = "access_token"
    ) -> bool:
        """
        Revoke an access or refresh token.
        
        Optional - not all providers support revocation.
        
        Args:
            token: Token to revoke
            token_type_hint: "access_token" or "refresh_token"
        
        Returns:
            True if revoked successfully
        
        Raises:
            NotImplementedError: If provider doesn't support revocation
        """
        raise NotImplementedError(
            f"{self.display_name} does not support token revocation"
        )
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name})"
