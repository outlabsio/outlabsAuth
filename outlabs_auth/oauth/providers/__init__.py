"""Pre-configured OAuth providers for popular services."""

from ..provider_factories import (
    get_discord_client,
    get_facebook_client,
    get_github_client,
    get_google_client,
    get_microsoft_client,
)
from .google import GoogleProvider
from .facebook import FacebookProvider
from .apple import AppleProvider
from .github import GitHubProvider

__all__ = [
    "GoogleProvider",
    "FacebookProvider",
    "AppleProvider",
    "GitHubProvider",
    "get_google_client",
    "get_facebook_client",
    "get_github_client",
    "get_microsoft_client",
    "get_discord_client",
]
