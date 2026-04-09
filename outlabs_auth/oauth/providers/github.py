"""GitHub OAuth provider implementation."""

from typing import Any, Optional, cast
from outlabs_auth.oauth.provider import OAuthProvider
from outlabs_auth.oauth.models import OAuthTokenResponse, OAuthUserInfo
from outlabs_auth.oauth.exceptions import InvalidCodeError, ProviderError


class GitHubProvider(OAuthProvider):
    """
    GitHub OAuth 2.0 provider.
    
    Pre-configured with GitHub's OAuth endpoints and recommended scopes.
    Users only need to provide client_id and client_secret.
    
    Setup:
        1. Go to https://github.com/settings/developers
        2. Click "New OAuth App"
        3. Set Authorization callback URL (e.g., http://localhost:3000/auth/github/callback)
        4. Copy Client ID and Client Secret
    
    Example:
        provider = GitHubProvider(
            client_id="your-github-client-id",
            client_secret="your-github-client-secret"
        )
    
    Scopes:
        - user:email: User's email addresses (required for email access)
        - read:user: User's profile info
    
    Note:
        GitHub requires user:email scope to get email addresses.
        Primary email is automatically included in user info.
    """
    
    # Provider metadata
    name = "github"
    display_name = "GitHub"
    
    # Pre-configured OAuth endpoints
    authorization_url = "https://github.com/login/oauth/authorize"
    token_url = "https://github.com/login/oauth/access_token"
    user_info_url = "https://api.github.com/user"
    user_emails_url = "https://api.github.com/user/emails"
    
    # Pre-configured scopes
    default_scopes = ["user:email", "read:user"]
    
    # OAuth capabilities
    supports_pkce = True
    supports_refresh = True  # GitHub added refresh tokens in 2021
    supports_revocation = True
    
    # Not OpenID Connect
    is_oidc = False
    
    # Revocation endpoint
    revocation_url = "https://api.github.com/applications/{client_id}/token"
    
    async def exchange_code(
        self,
        code: str,
        redirect_uri: str,
        code_verifier: Optional[str] = None
    ) -> OAuthTokenResponse:
        """
        Exchange authorization code for GitHub access token.
        
        Args:
            code: Authorization code from callback
            redirect_uri: Same redirect_uri used in authorization
            code_verifier: PKCE code verifier (optional)
        
        Returns:
            OAuth token response with access_token
        
        Raises:
            InvalidCodeError: If code is invalid or expired
            ProviderError: If GitHub returns an error
        """
        client = await self.get_http_client()
        
        # Build token request
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        }
        
        # Add PKCE verifier if provided
        if code_verifier:
            data["code_verifier"] = code_verifier
        
        # Exchange code for tokens
        try:
            response = await client.post(
                self.token_url,
                data=data,
                headers={"Accept": "application/json"}  # GitHub returns form data by default
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
            
            if error_code == "bad_verification_code":
                raise InvalidCodeError("Authorization code invalid or expired")
            
            raise ProviderError(
                provider=self.name,
                error=error_code,
                error_description=error_desc
            )
        
        # Parse token response
        token_data = response.json()
        
        # Check for error in response body
        if "error" in token_data:
            raise ProviderError(
                provider=self.name,
                error=token_data["error"],
                error_description=token_data.get("error_description", "")
            )
        
        return OAuthTokenResponse(
            access_token=token_data["access_token"],
            token_type=token_data.get("token_type", "Bearer"),
            scope=token_data.get("scope"),
            refresh_token=token_data.get("refresh_token"),
            expires_in=token_data.get("expires_in"),
            extras=token_data
        )
    
    async def get_user_info(
        self,
        access_token: str
    ) -> OAuthUserInfo:
        """
        Fetch user info from GitHub using access token.
        
        Args:
            access_token: GitHub OAuth access token
        
        Returns:
            Standardized user info
        
        Raises:
            ProviderError: If GitHub returns an error
        """
        client = await self.get_http_client()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json"
        }
        
        # Fetch user profile
        try:
            response = await client.get(
                self.user_info_url,
                headers=headers
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
        
        user_data = response.json()
        
        # Fetch user emails (need user:email scope)
        email = user_data.get("email", "")
        email_verified = False
        
        try:
            email_response = await client.get(
                self.user_emails_url,
                headers=headers
            )
            
            if email_response.status_code == 200:
                emails = email_response.json()
                # Find primary verified email
                for email_data in emails:
                    if email_data.get("primary") and email_data.get("verified"):
                        email = email_data["email"]
                        email_verified = True
                        break
                
                # Fallback to any verified email
                if not email:
                    for email_data in emails:
                        if email_data.get("verified"):
                            email = email_data["email"]
                            email_verified = True
                            break
        except Exception:
            # Email fetch failed, use email from profile if available
            pass
        
        return OAuthUserInfo(
            provider_user_id=str(user_data["id"]),
            email=email,
            email_verified=email_verified,
            name=user_data.get("name") or user_data.get("login"),
            picture=user_data.get("avatar_url"),
            provider_data=user_data
        )
    
    async def refresh_token(
        self,
        refresh_token: str
    ) -> OAuthTokenResponse:
        """
        Refresh GitHub access token.
        
        Args:
            refresh_token: GitHub refresh token
        
        Returns:
            New token response
        
        Raises:
            ProviderError: If GitHub returns an error
        """
        client = await self.get_http_client()
        
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        
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
        
        if response.status_code != 200:
            raise ProviderError(
                provider=self.name,
                error="token_refresh_failed",
                error_description=response.text
            )
        
        token_data = response.json()
        return OAuthTokenResponse(
            access_token=token_data["access_token"],
            token_type=token_data.get("token_type", "Bearer"),
            refresh_token=token_data.get("refresh_token", refresh_token),
            expires_in=token_data.get("expires_in"),
            scope=token_data.get("scope"),
            extras=token_data
        )
    
    async def revoke_token(
        self,
        token: str,
        token_type_hint: str = "access_token"
    ) -> bool:
        """
        Revoke a GitHub OAuth token.
        
        Requires basic auth with client credentials.
        
        Args:
            token: Token to revoke
            token_type_hint: Not used by GitHub
        
        Returns:
            True if revoked successfully
        
        Raises:
            ProviderError: If GitHub returns an error
        """
        client = await self.get_http_client()
        
        url = self.revocation_url.format(client_id=self.client_id)
        
        try:
            response = await cast(Any, client).delete(
                url,
                json={"access_token": token},
                auth=(self.client_id, self.client_secret),
                headers={"Accept": "application/vnd.github+json"}
            )
        except Exception as e:
            raise ProviderError(
                provider=self.name,
                error="network_error",
                error_description=str(e)
            )
        
        # GitHub returns 204 on success
        return bool(response.status_code == 204)
