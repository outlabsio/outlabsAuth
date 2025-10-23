"""Facebook Login provider implementation."""

from typing import Optional
from outlabs_auth.oauth.provider import OAuthProvider
from outlabs_auth.oauth.models import OAuthTokenResponse, OAuthUserInfo
from outlabs_auth.oauth.exceptions import InvalidCodeError, ProviderError


class FacebookProvider(OAuthProvider):
    """
    Facebook Login (OAuth 2.0) provider.
    
    Pre-configured with Facebook's OAuth endpoints and recommended scopes.
    Users only need to provide app_id and app_secret.
    
    Setup:
        1. Go to https://developers.facebook.com/apps
        2. Create a new app
        3. Add Facebook Login product
        4. Add OAuth redirect URIs in Facebook Login settings
        5. Copy App ID and App Secret
    
    Example:
        provider = FacebookProvider(
            client_id="your-facebook-app-id",
            client_secret="your-facebook-app-secret"
        )
    
    Scopes:
        - email: User's email address
        - public_profile: User's public profile info (name, picture)
    
    Note:
        Facebook uses "App ID" instead of "Client ID" but we map it to client_id
        for consistency with other providers.
    """
    
    # Provider metadata
    name = "facebook"
    display_name = "Facebook"
    
    # Pre-configured OAuth endpoints
    authorization_url = "https://www.facebook.com/v18.0/dialog/oauth"
    token_url = "https://graph.facebook.com/v18.0/oauth/access_token"
    user_info_url = "https://graph.facebook.com/me"
    
    # Pre-configured scopes
    default_scopes = ["email", "public_profile"]
    
    # OAuth capabilities
    supports_pkce = False  # Facebook doesn't support PKCE yet
    supports_refresh = True  # Can exchange for long-lived token
    supports_revocation = False  # No standard revocation endpoint
    
    # Not OpenID Connect
    is_oidc = False
    
    def __init__(
        self,
        client_id: str,  # Facebook App ID
        client_secret: str,  # Facebook App Secret
        scopes: Optional[list[str]] = None,
        api_version: str = "v18.0"
    ):
        """
        Initialize Facebook OAuth provider.
        
        Args:
            client_id: Facebook App ID
            client_secret: Facebook App Secret
            scopes: List of scopes (uses default if not provided)
            api_version: Facebook Graph API version (default: v18.0)
        """
        super().__init__(client_id, client_secret, scopes)
        self.api_version = api_version
        
        # Update URLs with API version
        self.authorization_url = f"https://www.facebook.com/{api_version}/dialog/oauth"
        self.token_url = f"https://graph.facebook.com/{api_version}/oauth/access_token"
    
    async def exchange_code(
        self,
        code: str,
        redirect_uri: str,
        code_verifier: Optional[str] = None
    ) -> OAuthTokenResponse:
        """
        Exchange authorization code for Facebook access token.
        
        Args:
            code: Authorization code from callback
            redirect_uri: Same redirect_uri used in authorization
            code_verifier: Not used (Facebook doesn't support PKCE)
        
        Returns:
            OAuth token response with access_token
        
        Raises:
            InvalidCodeError: If code is invalid or expired
            ProviderError: If Facebook returns an error
        """
        client = await self.get_http_client()
        
        # Build token request
        params = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        }
        
        # Exchange code for tokens
        try:
            response = await client.get(
                self.token_url,
                params=params
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
            error_code = error_data.get("error", {}).get("code", "unknown_error")
            error_msg = error_data.get("error", {}).get("message", response.text)
            
            if "code" in error_msg.lower() or "invalid" in error_msg.lower():
                raise InvalidCodeError("Authorization code invalid or expired")
            
            raise ProviderError(
                provider=self.name,
                error=str(error_code),
                error_description=error_msg
            )
        
        # Parse token response
        token_data = response.json()
        return OAuthTokenResponse(
            access_token=token_data["access_token"],
            token_type=token_data.get("token_type", "Bearer"),
            expires_in=token_data.get("expires_in"),
            extras=token_data
        )
    
    async def get_user_info(
        self,
        access_token: str
    ) -> OAuthUserInfo:
        """
        Fetch user info from Facebook using access token.
        
        Args:
            access_token: Facebook OAuth access token
        
        Returns:
            Standardized user info
        
        Raises:
            ProviderError: If Facebook returns an error
        """
        client = await self.get_http_client()
        
        # Fetch user info with specific fields
        params = {
            "fields": "id,name,email,first_name,last_name,picture,verified",
            "access_token": access_token
        }
        
        try:
            response = await client.get(
                self.user_info_url,
                params=params
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
        
        # Get picture URL
        picture_url = None
        if "picture" in data:
            picture_url = data["picture"].get("data", {}).get("url")
        
        return OAuthUserInfo(
            provider_user_id=data["id"],
            email=data.get("email", ""),
            email_verified=data.get("verified", False),  # Facebook verified field
            name=data.get("name"),
            given_name=data.get("first_name"),
            family_name=data.get("last_name"),
            picture=picture_url,
            provider_data=data
        )
    
    async def refresh_token(
        self,
        refresh_token: str
    ) -> OAuthTokenResponse:
        """
        Facebook doesn't use refresh tokens.
        
        Instead, you can exchange short-lived token for long-lived token.
        Call exchange_short_lived_token() instead.
        """
        raise NotImplementedError(
            "Facebook doesn't use refresh tokens. "
            "Use exchange_short_lived_token() to get long-lived token."
        )
    
    async def exchange_short_lived_token(
        self,
        short_lived_token: str
    ) -> OAuthTokenResponse:
        """
        Exchange short-lived token for long-lived token (60 days).
        
        Args:
            short_lived_token: Short-lived access token
        
        Returns:
            Long-lived access token (valid for 60 days)
        
        Raises:
            ProviderError: If Facebook returns an error
        """
        client = await self.get_http_client()
        
        params = {
            "grant_type": "fb_exchange_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "fb_exchange_token": short_lived_token,
        }
        
        try:
            response = await client.get(
                self.token_url,
                params=params
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
                error="token_exchange_failed",
                error_description=response.text
            )
        
        token_data = response.json()
        return OAuthTokenResponse(
            access_token=token_data["access_token"],
            token_type=token_data.get("token_type", "Bearer"),
            expires_in=token_data.get("expires_in", 5184000),  # 60 days default
            extras=token_data
        )
