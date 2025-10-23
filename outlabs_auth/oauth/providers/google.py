"""Google OAuth 2.0 provider implementation."""

from typing import Optional
from outlabs_auth.oauth.provider import OAuthProvider
from outlabs_auth.oauth.models import OAuthTokenResponse, OAuthUserInfo
from outlabs_auth.oauth.exceptions import InvalidCodeError, ProviderError


class GoogleProvider(OAuthProvider):
    """
    Google OAuth 2.0 provider (OpenID Connect).
    
    Pre-configured with Google's OAuth endpoints and recommended scopes.
    Users only need to provide client_id and client_secret.
    
    Setup:
        1. Go to https://console.cloud.google.com/apis/credentials
        2. Create OAuth 2.0 Client ID
        3. Add authorized redirect URIs (e.g., http://localhost:3000/auth/google/callback)
        4. Copy Client ID and Client Secret
    
    Example:
        provider = GoogleProvider(
            client_id="your-client-id.apps.googleusercontent.com",
            client_secret="your-client-secret"
        )
    
    Scopes:
        - openid: OpenID Connect
        - email: User's email address
        - profile: User's profile info (name, picture)
    """
    
    # Provider metadata
    name = "google"
    display_name = "Google"
    
    # Pre-configured OAuth endpoints (Google uses OpenID Connect)
    authorization_url = "https://accounts.google.com/o/oauth2/v2/auth"
    token_url = "https://oauth2.googleapis.com/token"
    user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
    
    # OpenID Connect configuration
    is_oidc = True
    jwks_uri = "https://www.googleapis.com/oauth2/v3/certs"
    
    # Pre-configured scopes (minimum needed for authentication)
    default_scopes = ["openid", "email", "profile"]
    
    # OAuth capabilities
    supports_pkce = True
    supports_refresh = True
    supports_revocation = True
    
    # Revocation endpoint
    revocation_url = "https://oauth2.googleapis.com/revoke"
    
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        scopes: Optional[list[str]] = None,
        hosted_domain: Optional[str] = None
    ):
        """
        Initialize Google OAuth provider.
        
        Args:
            client_id: Google OAuth client ID
            client_secret: Google OAuth client secret
            scopes: List of scopes (uses default if not provided)
            hosted_domain: Restrict to specific Google Workspace domain (optional)
        """
        super().__init__(client_id, client_secret, scopes)
        self.hosted_domain = hosted_domain
    
    def get_authorization_url(
        self,
        redirect_uri: str,
        state: Optional[str] = None,
        use_pkce: bool = True,
        use_nonce: bool = None,
        **extra_params
    ):
        """
        Generate Google authorization URL.
        
        Adds hosted_domain parameter if configured.
        """
        # Add hosted domain if configured (Google Workspace)
        if self.hosted_domain:
            extra_params["hd"] = self.hosted_domain
        
        # Add prompt=consent to always show consent screen (optional)
        # This ensures we always get a refresh token
        if "prompt" not in extra_params:
            extra_params["access_type"] = "offline"  # Request refresh token
        
        return super().get_authorization_url(
            redirect_uri=redirect_uri,
            state=state,
            use_pkce=use_pkce,
            use_nonce=use_nonce,
            **extra_params
        )
    
    async def exchange_code(
        self,
        code: str,
        redirect_uri: str,
        code_verifier: Optional[str] = None
    ) -> OAuthTokenResponse:
        """
        Exchange authorization code for Google access token.
        
        Args:
            code: Authorization code from callback
            redirect_uri: Same redirect_uri used in authorization
            code_verifier: PKCE code verifier (if PKCE was used)
        
        Returns:
            OAuth token response with access_token, refresh_token, id_token
        
        Raises:
            InvalidCodeError: If code is invalid or expired
            ProviderError: If Google returns an error
        """
        client = await self.get_http_client()
        
        # Build token request
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        
        # Add PKCE verifier if provided
        if code_verifier:
            data["code_verifier"] = code_verifier
        
        # Exchange code for tokens
        try:
            response = await client.post(
                self.token_url,
                data=data,
                headers={"Accept": "application/json"}
            )
        except Exception as e:
            raise ProviderError(
                provider=self.name,
                error="network_error",
                error_description=str(e)
            )
        
        # Handle error responses
        if response.status_code != 200:
            error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            error_code = error_data.get("error", "unknown_error")
            error_desc = error_data.get("error_description", response.text)
            
            if error_code == "invalid_grant":
                raise InvalidCodeError("Authorization code invalid or expired")
            
            raise ProviderError(
                provider=self.name,
                error=error_code,
                error_description=error_desc
            )
        
        # Parse token response
        token_data = response.json()
        return OAuthTokenResponse(
            access_token=token_data["access_token"],
            token_type=token_data.get("token_type", "Bearer"),
            expires_in=token_data.get("expires_in"),
            refresh_token=token_data.get("refresh_token"),
            scope=token_data.get("scope"),
            id_token=token_data.get("id_token"),  # OpenID Connect
            extras=token_data
        )
    
    async def get_user_info(
        self,
        access_token: str
    ) -> OAuthUserInfo:
        """
        Fetch user info from Google using access token.
        
        Args:
            access_token: Google OAuth access token
        
        Returns:
            Standardized user info
        
        Raises:
            ProviderError: If Google returns an error
        """
        client = await self.get_http_client()
        
        # Fetch user info
        try:
            response = await client.get(
                self.user_info_url,
                headers={"Authorization": f"Bearer {access_token}"}
            )
        except Exception as e:
            raise ProviderError(
                provider=self.name,
                error="network_error",
                error_description=str(e)
            )
        
        if response.status_code != 200:
            raise ProviderError(
                provider=self.name,
                error="user_info_failed",
                error_description=response.text
            )
        
        # Parse user info
        data = response.json()
        
        return OAuthUserInfo(
            provider_user_id=data["id"],
            email=data.get("email", ""),
            email_verified=data.get("verified_email", False),
            name=data.get("name"),
            given_name=data.get("given_name"),
            family_name=data.get("family_name"),
            picture=data.get("picture"),
            locale=data.get("locale"),
            provider_data=data
        )
    
    async def revoke_token(
        self,
        token: str,
        token_type_hint: str = "access_token"
    ) -> bool:
        """
        Revoke a Google OAuth token.
        
        Args:
            token: Token to revoke (access or refresh token)
            token_type_hint: Not used by Google
        
        Returns:
            True if revoked successfully
        
        Raises:
            ProviderError: If Google returns an error
        """
        client = await self.get_http_client()
        
        try:
            response = await client.post(
                self.revocation_url,
                data={"token": token}
            )
        except Exception as e:
            raise ProviderError(
                provider=self.name,
                error="network_error",
                error_description=str(e)
            )
        
        # Google returns 200 on success
        return response.status_code == 200
