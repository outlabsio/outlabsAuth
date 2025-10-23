"""OAuth-specific exceptions."""


class OAuthError(Exception):
    """Base exception for OAuth-related errors."""
    
    def __init__(self, message: str = "OAuth error occurred"):
        self.message = message
        super().__init__(self.message)


class InvalidStateError(OAuthError):
    """State parameter is invalid, expired, or missing."""
    
    def __init__(self, message: str = "OAuth state invalid or expired"):
        super().__init__(message)


class InvalidCodeError(OAuthError):
    """Authorization code is invalid or expired."""
    
    def __init__(self, message: str = "Authorization code invalid or expired"):
        super().__init__(message)


class ProviderError(OAuthError):
    """Error returned by OAuth provider."""
    
    def __init__(
        self,
        provider: str,
        error: str,
        error_description: str = "",
        error_uri: str = ""
    ):
        self.provider = provider
        self.error = error
        self.error_description = error_description
        self.error_uri = error_uri
        
        message = f"OAuth provider '{provider}' returned error: {error}"
        if error_description:
            message += f" - {error_description}"
        
        super().__init__(message)


class AccountLinkError(OAuthError):
    """Cannot link OAuth account to user."""
    
    def __init__(self, message: str):
        super().__init__(message)


class ProviderNotConfiguredError(OAuthError):
    """OAuth provider not configured."""
    
    def __init__(self, provider: str):
        super().__init__(f"OAuth provider '{provider}' not configured")


class EmailNotVerifiedError(OAuthError):
    """Provider did not verify email address."""
    
    def __init__(self, email: str):
        super().__init__(
            f"Email '{email}' not verified by provider. "
            "Cannot auto-link for security reasons."
        )


class AccountAlreadyLinkedError(AccountLinkError):
    """This provider account is already linked to another user."""
    
    def __init__(self, provider: str, email: str):
        super().__init__(
            f"{provider} account ({email}) is already linked to another user"
        )


class ProviderAlreadyLinkedError(AccountLinkError):
    """User already has this provider linked."""
    
    def __init__(self, provider: str):
        super().__init__(
            f"User already has a {provider} account linked"
        )


class CannotUnlinkLastMethodError(AccountLinkError):
    """Cannot unlink last authentication method."""
    
    def __init__(self):
        super().__init__(
            "Cannot unlink last authentication method. "
            "User must have at least one way to log in (password or social account)."
        )


class TokenRefreshError(OAuthError):
    """Failed to refresh OAuth token."""
    
    def __init__(self, provider: str, reason: str = ""):
        message = f"Failed to refresh {provider} token"
        if reason:
            message += f": {reason}"
        super().__init__(message)


class InvalidNonceError(OAuthError):
    """Nonce validation failed (OpenID Connect)."""
    
    def __init__(self):
        super().__init__(
            "ID token nonce validation failed. Possible replay attack."
        )


class PKCEValidationError(OAuthError):
    """PKCE validation failed."""
    
    def __init__(self):
        super().__init__(
            "PKCE validation failed. Code verifier does not match challenge."
        )
