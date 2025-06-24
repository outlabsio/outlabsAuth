from enum import Enum

class RBACScope(str, Enum):
    """
    Unified scope enumeration for all RBAC components (roles, permissions, groups).
    Three-tier architecture: system -> platform -> client
    """
    SYSTEM = "system"      # Global/system level (super admins, core auth)
    PLATFORM = "platform"  # Platform level (corporate clients, platform teams)
    CLIENT = "client"      # Client level (individual locations, end users)

# For backward compatibility and semantic clarity, create aliases
RoleScope = RBACScope
PermissionScope = RBACScope  
GroupScope = RBACScope 