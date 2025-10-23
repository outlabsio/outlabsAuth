"""Pre-configured OAuth providers for popular services."""

from .google import GoogleProvider
from .facebook import FacebookProvider
from .apple import AppleProvider
from .github import GitHubProvider

__all__ = [
    "GoogleProvider",
    "FacebookProvider",
    "AppleProvider",
    "GitHubProvider",
]
