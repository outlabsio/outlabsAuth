"""OAuth service for social login and account linking."""

from datetime import datetime, timedelta
from typing import Dict, Optional, List
from bson import ObjectId

from outlabs_auth.models.sql.user import User
from outlabs_auth.models.sql.enums import UserStatus
from outlabs_auth.models.sql.social_account import SocialAccount
from outlabs_auth.models.sql.oauth_state import OAuthState
from outlabs_auth.oauth.provider import OAuthProvider
from outlabs_auth.oauth.models import OAuthCallbackResult
from outlabs_auth.oauth.exceptions import (
    InvalidStateError,
    ProviderNotConfiguredError,
    EmailNotVerifiedError,
    AccountAlreadyLinkedError,
    ProviderAlreadyLinkedError,
    CannotUnlinkLastMethodError,
)
from outlabs_auth.utils.jwt import generate_tokens


class OAuthService:
    """
    High-level OAuth service for social login and account linking.
    
    Handles:
    - Authorization URL generation with security (state, PKCE, nonce)
    - OAuth callback processing
    - Account linking by verified email
    - User creation for new OAuth users
    - Account unlinking with safety checks
    
    Example:
        oauth_service = OAuthService(
            providers={"google": google_provider},
            user_service=user_service,
            secret_key="your-jwt-secret"
        )
        
        # Start OAuth flow
        auth_url = await oauth_service.get_authorization_url(
            provider="google",
            redirect_uri="http://localhost:3000/auth/google/callback"
        )
        
        # Handle callback
        result = await oauth_service.handle_callback(
            provider="google",
            code=request.query_params["code"],
            state=request.query_params["state"],
            redirect_uri="http://localhost:3000/auth/google/callback"
        )
    """
    
    def __init__(
        self,
        providers: Dict[str, OAuthProvider],
        user_service,  # UserService
        secret_key: str,
        access_token_expire_minutes: int = 15,
        refresh_token_expire_days: int = 30,
    ):
        """
        Initialize OAuth service.
        
        Args:
            providers: Dictionary of provider name -> OAuthProvider instance
            user_service: UserService instance for user management
            secret_key: JWT secret key for token generation
            access_token_expire_minutes: Access token lifetime
            refresh_token_expire_days: Refresh token lifetime
        """
        self.providers = providers
        self.user_service = user_service
        self.secret_key = secret_key
        self.access_token_expire_minutes = access_token_expire_minutes
        self.refresh_token_expire_days = refresh_token_expire_days
    
    def _get_provider(self, provider_name: str) -> OAuthProvider:
        """Get provider by name or raise error."""
        provider = self.providers.get(provider_name)
        if not provider:
            raise ProviderNotConfiguredError(provider_name)
        return provider
    
    async def get_authorization_url(
        self,
        provider: str,
        redirect_uri: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> str:
        """
        Generate OAuth authorization URL and store state.
        
        Args:
            provider: Provider name (google, facebook, etc.)
            redirect_uri: Where to redirect after authorization
            user_id: User ID if linking to existing user (optional)
            ip_address: IP address for security audit (optional)
            user_agent: User agent for security audit (optional)
        
        Returns:
            Authorization URL to redirect user to
        
        Raises:
            ProviderNotConfiguredError: If provider not configured
        """
        oauth_provider = self._get_provider(provider)
        
        # Generate authorization URL with security parameters
        auth_url_data = oauth_provider.get_authorization_url(
            redirect_uri=redirect_uri,
            use_pkce=True,
            use_nonce=oauth_provider.is_oidc,
        )
        
        # Store state in database for validation
        await OAuthState(
            state=auth_url_data.state,
            provider=provider,
            code_verifier=auth_url_data.code_verifier,
            code_challenge=auth_url_data.code_challenge,
            nonce=auth_url_data.nonce,
            redirect_uri=redirect_uri,
            user_id=ObjectId(user_id) if user_id else None,
            ip_address=ip_address,
            user_agent=user_agent,
        ).insert()
        
        return auth_url_data.url
    
    async def handle_callback(
        self,
        provider: str,
        code: str,
        state: str,
        redirect_uri: str,
    ) -> OAuthCallbackResult:
        """
        Handle OAuth callback and create/link user account.
        
        This is the main OAuth flow handler that:
        1. Validates state parameter (CSRF protection)
        2. Exchanges code for tokens
        3. Fetches user info from provider
        4. Creates new user OR links to existing user
        5. Generates JWT tokens for our system
        
        Args:
            provider: Provider name
            code: Authorization code from callback
            state: State parameter from callback
            redirect_uri: Same redirect_uri used in authorization
        
        Returns:
            OAuthCallbackResult with user, tokens, and metadata
        
        Raises:
            InvalidStateError: If state is invalid or expired
            ProviderNotConfiguredError: If provider not configured
            Various provider errors
        """
        oauth_provider = self._get_provider(provider)
        
        # 1. Validate state (CSRF protection)
        stored_state = await OAuthState.find_one(
            OAuthState.state == state,
            OAuthState.provider == provider,
            OAuthState.expires_at > datetime.utcnow(),
        )
        
        if not stored_state:
            raise InvalidStateError("State invalid, expired, or already used")
        
        # 2. Exchange code for tokens
        token_response = await oauth_provider.exchange_code(
            code=code,
            redirect_uri=redirect_uri,
            code_verifier=stored_state.code_verifier,
        )
        
        # 3. Fetch user info
        user_info = await oauth_provider.get_user_info(
            access_token=token_response.access_token
        )
        
        # 4. Create or link account
        if stored_state.user_id:
            # Manual linking to existing user
            user, social_account, is_new = await self._link_to_existing_user(
                user_id=stored_state.user_id,
                provider=provider,
                user_info=user_info,
                token_response=token_response,
            )
            linked = True
        else:
            # Auto-link or create new user
            user, social_account, is_new = await self._create_or_link_user(
                provider=provider,
                user_info=user_info,
                token_response=token_response,
            )
            linked = not is_new
        
        # 5. Delete used state (one-time use)
        await stored_state.delete()
        
        # 6. Generate JWT tokens for our system
        access_token, refresh_token = generate_tokens(
            user_id=str(user.id),
            secret_key=self.secret_key,
            access_expire_minutes=self.access_token_expire_minutes,
            refresh_expire_days=self.refresh_token_expire_days,
        )
        
        return OAuthCallbackResult(
            user_id=str(user.id),
            is_new_user=is_new,
            social_account_id=str(social_account.id),
            access_token=access_token,
            refresh_token=refresh_token,
            linked_account=linked,
        )
    
    async def _create_or_link_user(
        self,
        provider: str,
        user_info,
        token_response,
    ) -> tuple:
        """
        Create new user or auto-link to existing user by verified email.
        
        Security rules:
        - Only auto-link if email is verified by provider
        - If email not verified, create separate account
        - If email exists but not verified, create new account
        
        Returns:
            Tuple of (user, social_account, is_new_user)
        """
        # Check if provider account already linked
        existing_social = await SocialAccount.find_one(
            SocialAccount.provider == provider,
            SocialAccount.provider_user_id == user_info.provider_user_id,
        )
        
        if existing_social:
            # Already linked - return existing user
            user = await User.get(existing_social.user_id)
            await existing_social.set({SocialAccount.last_used_at: datetime.utcnow()})
            return user, existing_social, False
        
        # Try to find user by email (for auto-linking)
        user = None
        if user_info.email_verified:
            user = await User.find_one(User.email == user_info.email)
        
        if user:
            # Auto-link to existing user (email verified by provider)
            # Check if user already has this provider
            existing_provider = await SocialAccount.find_one(
                SocialAccount.user_id == user.id,
                SocialAccount.provider == provider,
            )
            if existing_provider:
                raise ProviderAlreadyLinkedError(provider)
            
            # Create social account link
            social_account = await self._create_social_account(
                user_id=user.id,
                provider=provider,
                user_info=user_info,
                token_response=token_response,
            )
            
            # Update user's auth methods
            if provider.upper() not in user.auth_methods:
                user.auth_methods.append(provider.upper())
                await user.save()
            
            return user, social_account, False
        
        else:
            # Create new user
            user = await self.user_service.create_user(
                email=user_info.email,
                password=None,  # Passwordless OAuth user
                full_name=user_info.name or user_info.email,
                email_verified=user_info.email_verified,
                status=UserStatus.ACTIVE,
            )
            
            # Set auth methods
            user.auth_methods = [provider.upper()]
            await user.save()
            
            # Create social account
            social_account = await self._create_social_account(
                user_id=user.id,
                provider=provider,
                user_info=user_info,
                token_response=token_response,
            )
            
            return user, social_account, True
    
    async def _link_to_existing_user(
        self,
        user_id: ObjectId,
        provider: str,
        user_info,
        token_response,
    ) -> tuple:
        """
        Link OAuth provider to existing authenticated user.
        
        Security checks:
        - User must exist and be active
        - Provider account not already linked to another user
        - User doesn't already have this provider linked
        
        Returns:
            Tuple of (user, social_account, is_new_user=False)
        """
        # Get user
        user = await User.get(user_id)
        if not user or user.status != UserStatus.ACTIVE:
            raise ValueError("User not found or not active")
        
        # Check if this provider account already linked to another user
        existing_social = await SocialAccount.find_one(
            SocialAccount.provider == provider,
            SocialAccount.provider_user_id == user_info.provider_user_id,
        )
        
        if existing_social and existing_social.user_id != user_id:
            raise AccountAlreadyLinkedError(provider, user_info.email)
        
        if existing_social:
            # Already linked to this user
            return user, existing_social, False
        
        # Check if user already has this provider
        user_provider = await SocialAccount.find_one(
            SocialAccount.user_id == user_id,
            SocialAccount.provider == provider,
        )
        
        if user_provider:
            raise ProviderAlreadyLinkedError(provider)
        
        # Create social account link
        social_account = await self._create_social_account(
            user_id=user_id,
            provider=provider,
            user_info=user_info,
            token_response=token_response,
        )
        
        # Update user's auth methods
        if provider.upper() not in user.auth_methods:
            user.auth_methods.append(provider.upper())
            await user.save()
        
        return user, social_account, False
    
    async def _create_social_account(
        self,
        user_id: ObjectId,
        provider: str,
        user_info,
        token_response,
    ) -> SocialAccount:
        """Create and save SocialAccount record."""
        social_account = SocialAccount(
            user_id=user_id,
            provider=provider,
            provider_user_id=user_info.provider_user_id,
            email=user_info.email,
            email_verified=user_info.email_verified,
            display_name=user_info.name,
            avatar_url=user_info.picture,
            access_token=token_response.access_token,  # TODO: Encrypt
            refresh_token=token_response.refresh_token,  # TODO: Encrypt
            token_expires_at=(
                datetime.utcnow() + timedelta(seconds=token_response.expires_in)
                if token_response.expires_in
                else None
            ),
            provider_data=user_info.provider_data,
            linked_at=datetime.utcnow(),
            last_used_at=datetime.utcnow(),
        )
        await social_account.insert()
        return social_account
    
    async def unlink_provider(
        self,
        user_id: str,
        provider: str,
    ) -> bool:
        """
        Unlink OAuth provider from user.
        
        Safety checks:
        - Cannot unlink if it's the only authentication method
        - User must have password OR another social account
        
        Args:
            user_id: User ID
            provider: Provider name to unlink
        
        Returns:
            True if unlinked successfully
        
        Raises:
            CannotUnlinkLastMethodError: If this is the last auth method
        """
        user = await User.get(ObjectId(user_id))
        if not user:
            raise ValueError("User not found")
        
        # Find social account
        social_account = await SocialAccount.find_one(
            SocialAccount.user_id == ObjectId(user_id),
            SocialAccount.provider == provider,
        )
        
        if not social_account:
            return False  # Already unlinked
        
        # Check if user has other auth methods
        has_password = user.hashed_password is not None
        other_socials = await SocialAccount.find(
            SocialAccount.user_id == ObjectId(user_id),
            SocialAccount.provider != provider,
        ).count()
        
        if not has_password and other_socials == 0:
            raise CannotUnlinkLastMethodError()
        
        # Delete social account
        await social_account.delete()
        
        # Update user's auth methods
        if provider.upper() in user.auth_methods:
            user.auth_methods.remove(provider.upper())
            await user.save()
        
        return True
    
    async def list_linked_providers(
        self,
        user_id: str,
    ) -> List[SocialAccount]:
        """
        List all OAuth providers linked to user.
        
        Args:
            user_id: User ID
        
        Returns:
            List of SocialAccount records
        """
        accounts = await SocialAccount.find(
            SocialAccount.user_id == ObjectId(user_id)
        ).to_list()
        return accounts
    
    async def cleanup_expired_states(self):
        """
        Cleanup expired OAuth states.
        
        Should be run periodically (e.g., every hour).
        """
        result = await OAuthState.find(
            OAuthState.expires_at < datetime.utcnow()
        ).delete()
        return result.deleted_count
