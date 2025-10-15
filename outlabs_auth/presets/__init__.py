"""
Preset classes for OutlabsAuth.

SimpleRBAC: Flat RBAC without entity hierarchy
EnterpriseRBAC: Hierarchical RBAC with tree permissions
"""
from outlabs_auth.presets.simple import SimpleRBAC
from outlabs_auth.presets.enterprise import EnterpriseRBAC

__all__ = ["SimpleRBAC", "EnterpriseRBAC"]
