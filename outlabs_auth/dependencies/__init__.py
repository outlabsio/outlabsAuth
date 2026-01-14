"""
FastAPI dependency injection helpers

Provides easy-to-use decorators and dependencies for protecting routes.
"""
# Import AuthDeps from dependencies.py (FastAPI-Users pattern)
from outlabs_auth.dependencies_impl import AuthDeps, create_auth_deps

__all__ = ["AuthDeps", "create_auth_deps"]
