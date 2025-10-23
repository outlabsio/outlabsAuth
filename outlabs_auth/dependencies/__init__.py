"""
FastAPI dependency injection helpers

Provides easy-to-use decorators and dependencies for protecting routes.
"""
# Import the NEW AuthDeps from dependencies.py (FastAPI-Users pattern)
# Note: We need absolute import to get ../dependencies.py not ./auth.py
import sys
from pathlib import Path

# Add parent directory to path to import dependencies.py
parent_dir = Path(__file__).parent.parent
spec_path = parent_dir / "dependencies.py"

import importlib.util
spec = importlib.util.spec_from_file_location("outlabs_auth_new_deps", spec_path)
deps_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deps_module)

# Export the NEW AuthDeps
AuthDeps = deps_module.AuthDeps

# Keep the old one available for backwards compat
from outlabs_auth.dependencies.auth import AuthDeps as OldAuthDeps

__all__ = ["AuthDeps", "OldAuthDeps"]
