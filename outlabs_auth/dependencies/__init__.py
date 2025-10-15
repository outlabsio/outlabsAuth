"""
FastAPI dependency injection helpers

Provides easy-to-use decorators and dependencies for protecting routes.
"""
from outlabs_auth.dependencies.auth import AuthDeps

__all__ = ["AuthDeps"]
