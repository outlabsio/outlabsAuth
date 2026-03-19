"""Apple Sign In provider implementation."""

from pathlib import Path
import time

import jwt

from typing import Any, Optional

from outlabs_auth.oauth.provider import OAuthProvider
from outlabs_auth.oauth.exceptions import InvalidCodeError, ProviderError
from outlabs_auth.oauth.models import OAuthTokenResponse, OAuthUserInfo


class AppleProvider(OAuthProvider):
    """
    Apple Sign In (OAuth 2.0 with OpenID Connect) provider.
    
    Pre-configured with Apple's OAuth endpoints and scopes.
    Requires Service ID, Team ID, Key ID, and Private Key (P8 file).
    
    Setup:
        1. Go to https://developer.apple.com/account/resources/identifiers/list/serviceId
        2. Create a Service ID (this is your client_id)
        3. Create a Sign in with Apple Key (download P8 file)
        4. Note your Team ID, Key ID
        5. Configure redirect URIs in Service ID settings
    
    Example:
        provider = AppleProvider(
            client_id="com.yourcompany.service",  # Service ID
            team_id="ABCD123456",
            key_id="ABCD123456",
            private_key_path="/path/to/AuthKey_ABCD123456.p8"
        )
    
    Scopes:
        - email: User's email address
        - name: User's name (only provided on first authorization)
    
    Special Notes:
        - Apple uses JWT for client authentication (not client_secret)
        - Name and email only provided on first authorization
        - Subsequent logins only return user ID
        - Email may be privaterelay address (@privaterelay.appleid.com)
    """
    
    # Provider metadata
    name = "apple"
    display_name = "Apple"
    
    # Pre-configured OAuth endpoints
    authorization_url = "https://appleid.apple.com/auth/authorize"
    token_url = "https://appleid.apple.com/auth/token"
    
    # OpenID Connect configuration
    is_oidc = True
    jwks_uri = "https://appleid.apple.com/auth/keys"
    
    # Pre-configured scopes
    default_scopes = ["email", "name"]
    
    # OAuth capabilities
    supports_pkce = True
    supports_refresh = True
    supports_revocation = True
    
    # Revocation endpoint
    revocation_url = "https://appleid.apple.com/auth/revoke"
    
    def __init__(
        self,
        client_id: str,  # Service ID
        team_id: str,
        key_id: str,
        private_key: Optional[str] = None,
        private_key_path: Optional[str] = None,
        scopes: Optional[list[str]] = None
    ):
        """
        Initialize Apple OAuth provider.
        
        Args:
            client_id: Apple Service ID
            team_id: Apple Developer Team ID
            key_id: Apple Sign in with Apple Key ID
            private_key: Private key content (P8 format)
            private_key_path: Path to private key file (P8)
            scopes: List of scopes (uses default if not provided)
        
        Raises:
            ValueError: If neither private_key nor private_key_path provided
        """
        # Apple doesn't use client_secret - we generate JWT instead
        super().__init__(client_id, "", scopes)
        
        self.team_id = team_id
        self.key_id = key_id
        
        # Load private key
        if private_key:
            self.private_key = private_key
        elif private_key_path:
            self.private_key = Path(private_key_path).read_text()
        else:
            raise ValueError(
                "Either private_key or private_key_path must be provided"
            )
        self._jwk_client: Optional[jwt.PyJWKClient] = None

    def _get_jwk_client(self) -> jwt.PyJWKClient:
        """Create or reuse the Apple JWKS client."""
        if self._jwk_client is None:
            self._jwk_client = jwt.PyJWKClient(self.jwks_uri)
        return self._jwk_client

    @staticmethod
    def _coerce_email_verified(value: Any) -> bool:
        """Normalize Apple email_verified into a bool."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() == "true"
        return bool(value)
    
    def _generate_client_secret(self) -> str:
        """
        Generate JWT client secret for Apple.
        
        Apple requires a JWT signed with your private key for authentication.
        The JWT must include specific claims and is valid for up to 6 months.
        
        Returns:
            JWT client secret
        """
        now = int(time.time())
        
        # JWT claims required by Apple
        claims = {
            "iss": self.team_id,  # Issuer (Team ID)
            "iat": now,  # Issued at
            "exp": now + 3600,  # Expires in 1 hour
            "aud": "https://appleid.apple.com",  # Audience
            "sub": self.client_id,  # Subject (Service ID)
        }
        
        # Sign JWT with ES256 algorithm
        headers = {
            "kid": self.key_id,  # Key ID
            "alg": "ES256"
        }
        
        return jwt.encode(
            claims,
            self.private_key,
            algorithm="ES256",
            headers=headers
        )
    
    async def exchange_code(
        self,
        code: str,
        redirect_uri: str,
        code_verifier: Optional[str] = None
    ) -> OAuthTokenResponse:
        """
        Exchange authorization code for Apple access token.
        
        Args:
            code: Authorization code from callback
            redirect_uri: Same redirect_uri used in authorization
            code_verifier: PKCE code verifier (optional)
        
        Returns:
            OAuth token response with access_token and id_token
        
        Raises:
            InvalidCodeError: If code is invalid or expired
            ProviderError: If Apple returns an error
        """
        client = await self.get_http_client()
        
        # Generate client secret (JWT)
        client_secret = self._generate_client_secret()
        
        # Build token request
        data = {
            "client_id": self.client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
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
                headers={"Content-Type": "application/x-www-form-urlencoded"}
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
            
            if error_code == "invalid_grant":
                raise InvalidCodeError("Authorization code invalid or expired")
            
            raise ProviderError(
                provider=self.name,
                error=error_code,
                error_description=error_data.get("error_description", response.text)
            )
        
        # Parse token response
        token_data = response.json()
        return OAuthTokenResponse(
            access_token=token_data["access_token"],
            token_type=token_data.get("token_type", "Bearer"),
            expires_in=token_data.get("expires_in"),
            refresh_token=token_data.get("refresh_token"),
            id_token=token_data.get("id_token"),  # OpenID Connect
            extras=token_data
        )
    
    async def get_user_info(
        self,
        access_token: str
    ) -> OAuthUserInfo:
        """
        Extract user info from Apple ID token.
        
        Apple doesn't have a userinfo endpoint. Instead, user info is embedded
        in the ID token (JWT). Name and email are only provided on first auth.
        
        Args:
            access_token: Not used - Apple uses ID token
        
        Returns:
            Standardized user info
        
        Note:
            Apple does not expose a userinfo endpoint. Callers should use the
            ID token path via `parse_id_token()`.
        """
        # Apple doesn't have a user info endpoint
        # User info comes from the ID token
        # For now, we'll extract minimal info
        # In production, you should verify the ID token signature
        
        # This is a simplified version - in practice, you'd need the id_token
        # which should be passed through the provider's token response
        raise NotImplementedError(
            "Apple user info requires ID token parsing. "
            "Override this method or pass id_token to extract user info."
        )
    
    def parse_id_token(self, id_token: str, verify: bool = False) -> OAuthUserInfo:
        """
        Parse Apple ID token to extract user info.
        
        Args:
            id_token: Apple ID token (JWT)
            verify: Whether to verify JWT signature (requires JWKS)
        
        Returns:
            Standardized user info
        
        Note:
            If verify=True, signature, issuer, and audience are validated against
            Apple's JWKS metadata.
        """
        try:
            if verify:
                signing_key = self._get_jwk_client().get_signing_key_from_jwt(id_token)
                payload = jwt.decode(
                    id_token,
                    signing_key.key,
                    algorithms=["RS256"],
                    audience=self.client_id,
                    issuer="https://appleid.apple.com",
                )
            else:
                payload = jwt.decode(id_token, options={"verify_signature": False})
        except Exception as exc:
            raise ProviderError(
                provider=self.name,
                error="invalid_id_token",
                error_description=str(exc),
            ) from exc

        return OAuthUserInfo(
            provider_user_id=payload["sub"],
            email=payload.get("email", ""),
            email_verified=self._coerce_email_verified(payload.get("email_verified", False)),
            name=None,  # Name not in ID token (only in initial auth response)
            provider_data=payload
        )
    
    async def refresh_token(
        self,
        refresh_token: str
    ) -> OAuthTokenResponse:
        """
        Refresh Apple access token.
        
        Args:
            refresh_token: Apple refresh token
        
        Returns:
            New token response
        
        Raises:
            ProviderError: If Apple returns an error
        """
        client = await self.get_http_client()
        
        # Generate client secret (JWT)
        client_secret = self._generate_client_secret()
        
        data = {
            "client_id": self.client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        
        try:
            response = await client.post(
                self.token_url,
                data=data
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
            id_token=token_data.get("id_token"),
            extras=token_data
        )
    
    async def revoke_token(
        self,
        token: str,
        token_type_hint: str = "access_token"
    ) -> bool:
        """
        Revoke an Apple OAuth token.
        
        Args:
            token: Token to revoke
            token_type_hint: "access_token" or "refresh_token"
        
        Returns:
            True if revoked successfully
        
        Raises:
            ProviderError: If Apple returns an error
        """
        client = await self.get_http_client()
        
        # Generate client secret (JWT)
        client_secret = self._generate_client_secret()
        
        data = {
            "client_id": self.client_id,
            "client_secret": client_secret,
            "token": token,
            "token_type_hint": token_type_hint,
        }
        
        try:
            response = await client.post(
                self.revocation_url,
                data=data
            )
        except Exception as e:
            raise ProviderError(
                provider=self.name,
                error="network_error",
                error_description=str(e)
            )
        
        # Apple returns 200 on success
        return response.status_code == 200
