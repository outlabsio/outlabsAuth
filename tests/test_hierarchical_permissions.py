import pytest
import pytest_asyncio
from httpx import AsyncClient
from api.services.permission_service import check_hierarchical_permission

class TestHierarchicalPermissions:
    """
    Comprehensive test suite for hierarchical permission cascading logic.
    
    Tests all permission hierarchies to ensure:
    1. Manage permissions include read permissions
    2. Broader scopes include narrower scopes
    3. All cascading scenarios work correctly
    4. No permission gaps or overlaps exist
    """

    def test_user_permission_hierarchy_direct(self):
        """Test direct user permission matches."""
        user_permissions = {"user:read_self"}
        assert check_hierarchical_permission(user_permissions, "user:read_self")
        assert not check_hierarchical_permission(user_permissions, "user:read_client")

    def test_user_read_permission_cascading(self):
        """Test user read permission cascading from broader to narrower scopes."""
        # user:read_client includes user:read_self
        user_permissions = {"user:read_client"}
        assert check_hierarchical_permission(user_permissions, "user:read_self")
        assert check_hierarchical_permission(user_permissions, "user:read_client")
        assert not check_hierarchical_permission(user_permissions, "user:read_platform")

        # user:read_platform includes user:read_client and user:read_self
        user_permissions = {"user:read_platform"}
        assert check_hierarchical_permission(user_permissions, "user:read_self")
        assert check_hierarchical_permission(user_permissions, "user:read_client")
        assert check_hierarchical_permission(user_permissions, "user:read_platform")
        assert not check_hierarchical_permission(user_permissions, "user:read_all")

        # user:read_all includes all user read permissions
        user_permissions = {"user:read_all"}
        assert check_hierarchical_permission(user_permissions, "user:read_self")
        assert check_hierarchical_permission(user_permissions, "user:read_client")
        assert check_hierarchical_permission(user_permissions, "user:read_platform")
        assert check_hierarchical_permission(user_permissions, "user:read_all")

    def test_user_manage_permission_cascading(self):
        """Test user manage permission cascading includes both manage and read permissions."""
        # user:manage_client includes user:read_client and user:read_self
        user_permissions = {"user:manage_client"}
        assert check_hierarchical_permission(user_permissions, "user:read_self")
        assert check_hierarchical_permission(user_permissions, "user:read_client")
        assert check_hierarchical_permission(user_permissions, "user:manage_client")
        assert not check_hierarchical_permission(user_permissions, "user:read_platform")
        assert not check_hierarchical_permission(user_permissions, "user:manage_platform")

        # user:manage_platform includes user:manage_client + all platform/client/self read permissions
        user_permissions = {"user:manage_platform"}
        assert check_hierarchical_permission(user_permissions, "user:read_self")
        assert check_hierarchical_permission(user_permissions, "user:read_client")
        assert check_hierarchical_permission(user_permissions, "user:read_platform")
        assert check_hierarchical_permission(user_permissions, "user:manage_client")
        assert check_hierarchical_permission(user_permissions, "user:manage_platform")
        assert not check_hierarchical_permission(user_permissions, "user:read_all")
        assert not check_hierarchical_permission(user_permissions, "user:manage_all")

        # user:manage_all includes ALL user permissions
        user_permissions = {"user:manage_all"}
        assert check_hierarchical_permission(user_permissions, "user:read_self")
        assert check_hierarchical_permission(user_permissions, "user:read_client")
        assert check_hierarchical_permission(user_permissions, "user:read_platform")
        assert check_hierarchical_permission(user_permissions, "user:read_all")
        assert check_hierarchical_permission(user_permissions, "user:manage_client")
        assert check_hierarchical_permission(user_permissions, "user:manage_platform")
        assert check_hierarchical_permission(user_permissions, "user:manage_all")

    def test_role_permission_hierarchy(self):
        """Test role permission cascading logic."""
        # role:read_platform includes role:read_client
        user_permissions = {"role:read_platform"}
        assert check_hierarchical_permission(user_permissions, "role:read_client")
        assert check_hierarchical_permission(user_permissions, "role:read_platform")
        assert not check_hierarchical_permission(user_permissions, "role:read_all")

        # role:manage_platform includes role:manage_client + all platform/client read permissions
        user_permissions = {"role:manage_platform"}
        assert check_hierarchical_permission(user_permissions, "role:read_client")
        assert check_hierarchical_permission(user_permissions, "role:read_platform")
        assert check_hierarchical_permission(user_permissions, "role:manage_client")
        assert check_hierarchical_permission(user_permissions, "role:manage_platform")
        assert not check_hierarchical_permission(user_permissions, "role:read_all")
        assert not check_hierarchical_permission(user_permissions, "role:manage_all")

        # role:manage_all includes ALL role permissions
        user_permissions = {"role:manage_all"}
        assert check_hierarchical_permission(user_permissions, "role:read_client")
        assert check_hierarchical_permission(user_permissions, "role:read_platform")
        assert check_hierarchical_permission(user_permissions, "role:read_all")
        assert check_hierarchical_permission(user_permissions, "role:manage_client")
        assert check_hierarchical_permission(user_permissions, "role:manage_platform")
        assert check_hierarchical_permission(user_permissions, "role:manage_all")

    def test_group_permission_hierarchy(self):
        """Test group permission cascading logic."""
        # group:manage_client includes group:read_client
        user_permissions = {"group:manage_client"}
        assert check_hierarchical_permission(user_permissions, "group:read_client")
        assert check_hierarchical_permission(user_permissions, "group:manage_client")
        assert not check_hierarchical_permission(user_permissions, "group:read_platform")

        # group:manage_all includes ALL group permissions
        user_permissions = {"group:manage_all"}
        assert check_hierarchical_permission(user_permissions, "group:read_client")
        assert check_hierarchical_permission(user_permissions, "group:read_platform")
        assert check_hierarchical_permission(user_permissions, "group:read_all")
        assert check_hierarchical_permission(user_permissions, "group:manage_client")
        assert check_hierarchical_permission(user_permissions, "group:manage_platform")
        assert check_hierarchical_permission(user_permissions, "group:manage_all")

    def test_permission_permission_hierarchy(self):
        """Test permission permission cascading logic (meta-permissions)."""
        # permission:manage_platform includes permission:manage_client + all platform/client read permissions
        user_permissions = {"permission:manage_platform"}
        assert check_hierarchical_permission(user_permissions, "permission:read_client")
        assert check_hierarchical_permission(user_permissions, "permission:read_platform")
        assert check_hierarchical_permission(user_permissions, "permission:manage_client")
        assert check_hierarchical_permission(user_permissions, "permission:manage_platform")
        assert not check_hierarchical_permission(user_permissions, "permission:read_all")

        # permission:manage_all includes ALL permission permissions
        user_permissions = {"permission:manage_all"}
        assert check_hierarchical_permission(user_permissions, "permission:read_client")
        assert check_hierarchical_permission(user_permissions, "permission:read_platform")
        assert check_hierarchical_permission(user_permissions, "permission:read_all")
        assert check_hierarchical_permission(user_permissions, "permission:manage_client")
        assert check_hierarchical_permission(user_permissions, "permission:manage_platform")
        assert check_hierarchical_permission(user_permissions, "permission:manage_all")

    def test_client_permission_hierarchy(self):
        """Test client permission cascading logic."""
        # client:read_platform includes client:read_own
        user_permissions = {"client:read_platform"}
        assert check_hierarchical_permission(user_permissions, "client:read_own")
        assert check_hierarchical_permission(user_permissions, "client:read_platform")
        assert not check_hierarchical_permission(user_permissions, "client:read_all")

        # client:manage_all includes ALL client permissions
        user_permissions = {"client:manage_all"}
        assert check_hierarchical_permission(user_permissions, "client:read_own")
        assert check_hierarchical_permission(user_permissions, "client:read_platform")
        assert check_hierarchical_permission(user_permissions, "client:read_all")
        assert check_hierarchical_permission(user_permissions, "client:manage_platform")
        assert check_hierarchical_permission(user_permissions, "client:manage_all")

    def test_multiple_permissions_any_match(self):
        """Test that having multiple permissions works correctly."""
        user_permissions = {"user:read_self", "role:manage_client", "group:read_platform"}
        
        # Should match direct permissions
        assert check_hierarchical_permission(user_permissions, "user:read_self")
        assert check_hierarchical_permission(user_permissions, "role:manage_client")
        assert check_hierarchical_permission(user_permissions, "group:read_platform")
        
        # Should match hierarchical permissions
        assert check_hierarchical_permission(user_permissions, "role:read_client")  # from role:manage_client
        assert check_hierarchical_permission(user_permissions, "group:read_client")  # from group:read_platform
        
        # Should NOT match permissions not covered
        assert not check_hierarchical_permission(user_permissions, "user:read_client")
        assert not check_hierarchical_permission(user_permissions, "role:manage_platform")

    def test_cross_resource_isolation(self):
        """Test that permissions for one resource don't grant permissions for another."""
        user_permissions = {"user:manage_all"}
        
        # Should work for user permissions
        assert check_hierarchical_permission(user_permissions, "user:read_client")
        assert check_hierarchical_permission(user_permissions, "user:manage_platform")
        
        # Should NOT work for role/group/permission/client permissions
        assert not check_hierarchical_permission(user_permissions, "role:read_client")
        assert not check_hierarchical_permission(user_permissions, "group:manage_client")
        assert not check_hierarchical_permission(user_permissions, "permission:read_platform")
        assert not check_hierarchical_permission(user_permissions, "client:read_own")

    def test_edge_cases(self):
        """Test edge cases and potential security issues."""
        # Empty permissions
        user_permissions = set()
        assert not check_hierarchical_permission(user_permissions, "user:read_self")
        
        # Non-existent permission
        user_permissions = {"user:read_self"}
        assert not check_hierarchical_permission(user_permissions, "nonexistent:permission")
        
        # Malformed permission names
        user_permissions = {"invalid_permission_format"}
        assert not check_hierarchical_permission(user_permissions, "user:read_self")
        
        # Case sensitivity
        user_permissions = {"USER:READ_SELF"}  # Wrong case
        assert not check_hierarchical_permission(user_permissions, "user:read_self")

    def test_all_permission_combinations(self):
        """Test all valid permission combinations to ensure no gaps."""
        all_permissions = {
            # User permissions
            "user:read_self", "user:read_client", "user:read_platform", "user:read_all",
            "user:manage_client", "user:manage_platform", "user:manage_all",
            
            # Role permissions
            "role:read_client", "role:read_platform", "role:read_all",
            "role:manage_client", "role:manage_platform", "role:manage_all",
            
            # Group permissions
            "group:read_client", "group:read_platform", "group:read_all",
            "group:manage_client", "group:manage_platform", "group:manage_all",
            
            # Permission permissions
            "permission:read_client", "permission:read_platform", "permission:read_all",
            "permission:manage_client", "permission:manage_platform", "permission:manage_all",
            
            # Client permissions
            "client:read_own", "client:read_platform", "client:read_all",
            "client:manage_platform", "client:manage_all"
        }
        
        # Test that each permission at least grants itself
        for permission in all_permissions:
            user_permissions = {permission}
            assert check_hierarchical_permission(user_permissions, permission), f"Permission {permission} should grant itself"

    def test_hierarchical_dependency_completeness(self):
        """Test that our dependency definitions use the hierarchical logic correctly."""
        # Test cases that should work with our current dependencies
        test_cases = [
            # can_read_users dependency: any_of=["user:read_all", "user:read_platform", "user:read_client"]
            ({"user:read_all"}, "user:read_client", True),  # user:read_all should include user:read_client
            ({"user:read_platform"}, "user:read_client", True),  # user:read_platform should include user:read_client
            ({"user:manage_all"}, "user:read_client", True),  # user:manage_all should include user:read_client
            ({"user:manage_platform"}, "user:read_client", True),  # user:manage_platform should include user:read_client
            ({"user:manage_client"}, "user:read_client", True),  # user:manage_client should include user:read_client
            
            # can_manage_users dependency: any_of=["user:manage_all", "user:manage_platform", "user:manage_client"]
            ({"user:manage_all"}, "user:manage_platform", True),  # user:manage_all should include user:manage_platform
            ({"user:manage_all"}, "user:manage_client", True),  # user:manage_all should include user:manage_client
            ({"user:manage_platform"}, "user:manage_client", True),  # user:manage_platform should include user:manage_client
            
            # Negative cases
            ({"user:read_self"}, "user:read_client", False),  # user:read_self should NOT include user:read_client
            ({"user:manage_client"}, "user:manage_platform", False),  # user:manage_client should NOT include user:manage_platform
        ]
        
        for user_permissions, required_permission, expected in test_cases:
            result = check_hierarchical_permission(user_permissions, required_permission)
            assert result == expected, f"Failed: {user_permissions} -> {required_permission} should be {expected}, got {result}"

    def test_manage_to_manage_cascading(self):
        """Test that manage permissions cascade to other manage permissions correctly."""
        # This was the bug we found - ensure manage_all includes manage_platform, etc.
        user_permissions = {"user:manage_all"}
        assert check_hierarchical_permission(user_permissions, "user:manage_platform")
        assert check_hierarchical_permission(user_permissions, "user:manage_client")
        
        user_permissions = {"user:manage_platform"}
        assert check_hierarchical_permission(user_permissions, "user:manage_client")
        assert not check_hierarchical_permission(user_permissions, "user:manage_all")

    def test_super_admin_scenario(self):
        """Test a super admin with all top-level permissions."""
        super_admin_permissions = {
            "user:manage_all",
            "role:manage_all", 
            "group:manage_all",
            "permission:manage_all",
            "client:manage_all"
        }
        
        # Should have access to everything
        all_test_permissions = [
            "user:read_self", "user:read_client", "user:read_platform", "user:read_all",
            "user:manage_client", "user:manage_platform", "user:manage_all",
            "role:read_client", "role:read_platform", "role:read_all",
            "role:manage_client", "role:manage_platform", "role:manage_all",
            "group:read_client", "group:read_platform", "group:read_all",
            "group:manage_client", "group:manage_platform", "group:manage_all",
            "permission:read_client", "permission:read_platform", "permission:read_all",
            "permission:manage_client", "permission:manage_platform", "permission:manage_all",
            "client:read_own", "client:read_platform", "client:read_all",
            "client:manage_platform", "client:manage_all"
        ]
        
        for permission in all_test_permissions:
            assert check_hierarchical_permission(super_admin_permissions, permission), f"Super admin should have {permission}"

    def test_minimal_user_scenario(self):
        """Test a minimal user with only self-access permissions."""
        minimal_permissions = {"user:read_self"}
        
        # Should only have self-access
        assert check_hierarchical_permission(minimal_permissions, "user:read_self")
        
        # Should NOT have any other permissions
        restricted_permissions = [
            "user:read_client", "user:read_platform", "user:read_all",
            "user:manage_client", "user:manage_platform", "user:manage_all",
            "role:read_client", "group:read_client", "permission:read_client", "client:read_own"
        ]
        
        for permission in restricted_permissions:
            assert not check_hierarchical_permission(minimal_permissions, permission), f"Minimal user should NOT have {permission}"


class TestHierarchicalPermissionsIntegration:
    """Integration tests to ensure hierarchical permissions work with actual API endpoints."""

    @pytest.mark.asyncio
    async def test_user_endpoints_with_hierarchical_permissions(self, client: AsyncClient):
        """Test that user endpoints respect hierarchical permissions."""
        # This would require setting up test users with specific permissions
        # and testing that the endpoints work correctly with hierarchical logic
        pass  # Placeholder for future integration tests

    @pytest.mark.asyncio
    async def test_role_endpoints_with_hierarchical_permissions(self, client: AsyncClient):
        """Test that role endpoints respect hierarchical permissions."""
        pass  # Placeholder for future integration tests

    @pytest.mark.asyncio
    async def test_group_endpoints_with_hierarchical_permissions(self, client: AsyncClient):
        """Test that group endpoints respect hierarchical permissions."""
        pass  # Placeholder for future integration tests

    @pytest.mark.asyncio
    async def test_permission_endpoints_with_hierarchical_permissions(self, client: AsyncClient):
        """Test that permission endpoints respect hierarchical permissions."""
        pass  # Placeholder for future integration tests

    @pytest.mark.asyncio
    async def test_client_account_endpoints_with_hierarchical_permissions(self, client: AsyncClient):
        """Test that client account endpoints respect hierarchical permissions."""
        pass  # Placeholder for future integration tests


class TestMissingPermissionScenarios:
    """Test scenarios that might be missing from our current test coverage."""

    def test_permission_boundary_conditions(self):
        """Test boundary conditions that might cause issues."""
        # Test the exact boundary between scopes
        user_permissions = {"user:read_client"}
        assert check_hierarchical_permission(user_permissions, "user:read_self")  # Should work
        assert not check_hierarchical_permission(user_permissions, "user:read_platform")  # Should not work

    def test_read_to_read_cascading(self):
        """Test that read permissions cascade correctly across all scopes."""
        user_permissions = {"user:read_all"}
        assert check_hierarchical_permission(user_permissions, "user:read_platform")
        assert check_hierarchical_permission(user_permissions, "user:read_client")
        assert check_hierarchical_permission(user_permissions, "user:read_self")

    def test_mixed_permission_types(self):
        """Test users with mixed permission types across different resources."""
        user_permissions = {
            "user:manage_all",
            "role:read_platform", 
            "group:manage_client",
            "permission:read_client",
            "client:read_own"
        }
        
        # Test user permissions work fully
        assert check_hierarchical_permission(user_permissions, "user:read_self")
        assert check_hierarchical_permission(user_permissions, "user:manage_platform")
        
        # Test role permissions work at platform level
        assert check_hierarchical_permission(user_permissions, "role:read_client")
        assert not check_hierarchical_permission(user_permissions, "role:manage_client")
        
        # Test group permissions work at client level
        assert check_hierarchical_permission(user_permissions, "group:read_client")
        assert not check_hierarchical_permission(user_permissions, "group:manage_platform")
        
        # Test permission permissions work at client level
        assert check_hierarchical_permission(user_permissions, "permission:read_client")
        assert not check_hierarchical_permission(user_permissions, "permission:read_platform")
        
        # Test client permissions work at own level
        assert check_hierarchical_permission(user_permissions, "client:read_own")
        assert not check_hierarchical_permission(user_permissions, "client:read_platform")

    def test_platform_admin_scenario(self):
        """Test a platform admin with platform-level permissions."""
        platform_admin_permissions = {
            "user:manage_platform",
            "role:read_all", 
            "group:manage_platform",
            "client:manage_platform"
        }
        
        # Should have platform and below access
        assert check_hierarchical_permission(platform_admin_permissions, "user:read_self")
        assert check_hierarchical_permission(platform_admin_permissions, "user:read_client")
        assert check_hierarchical_permission(platform_admin_permissions, "user:read_platform")
        assert check_hierarchical_permission(platform_admin_permissions, "user:manage_client")
        assert check_hierarchical_permission(platform_admin_permissions, "user:manage_platform")
        
        # Should NOT have system-level access
        assert not check_hierarchical_permission(platform_admin_permissions, "user:read_all")
        assert not check_hierarchical_permission(platform_admin_permissions, "user:manage_all")

    def test_client_admin_scenario(self):
        """Test a client admin with client-level permissions."""
        client_admin_permissions = {
            "user:manage_client",
            "role:read_client", 
            "group:manage_client",
            "client:read_own"
        }
        
        # Should have client and self access
        assert check_hierarchical_permission(client_admin_permissions, "user:read_self")
        assert check_hierarchical_permission(client_admin_permissions, "user:read_client")
        assert check_hierarchical_permission(client_admin_permissions, "user:manage_client")
        assert check_hierarchical_permission(client_admin_permissions, "role:read_client")
        assert check_hierarchical_permission(client_admin_permissions, "group:read_client")
        assert check_hierarchical_permission(client_admin_permissions, "group:manage_client")
        
        # Should NOT have platform or system access
        assert not check_hierarchical_permission(client_admin_permissions, "user:read_platform")
        assert not check_hierarchical_permission(client_admin_permissions, "user:manage_platform")
        assert not check_hierarchical_permission(client_admin_permissions, "role:read_platform")

    def test_security_isolation_between_resources(self):
        """Test that permissions are properly isolated between different resource types."""
        # Having user:manage_all should not grant role permissions
        user_permissions = {"user:manage_all"}
        assert not check_hierarchical_permission(user_permissions, "role:read_client")
        assert not check_hierarchical_permission(user_permissions, "group:manage_client")
        assert not check_hierarchical_permission(user_permissions, "permission:read_platform")
        assert not check_hierarchical_permission(user_permissions, "client:read_own")
        
        # Having role:manage_all should not grant user permissions
        user_permissions = {"role:manage_all"}
        assert not check_hierarchical_permission(user_permissions, "user:read_client")
        assert not check_hierarchical_permission(user_permissions, "group:manage_client")
        assert not check_hierarchical_permission(user_permissions, "permission:read_platform")
        assert not check_hierarchical_permission(user_permissions, "client:read_own")

    def test_permission_name_variations(self):
        """Test edge cases with permission name formats."""
        # Test with valid permission names
        user_permissions = {"user:read_self"}
        assert check_hierarchical_permission(user_permissions, "user:read_self")
        
        # Test with invalid formats should not match
        user_permissions = {"user_read_self"}  # Wrong separator
        assert not check_hierarchical_permission(user_permissions, "user:read_self")
        
        user_permissions = {"user:read:self"}  # Too many separators
        assert not check_hierarchical_permission(user_permissions, "user:read_self")
        
        user_permissions = {"read_self"}  # Missing resource
        assert not check_hierarchical_permission(user_permissions, "user:read_self")

    def test_comprehensive_scope_combinations(self):
        """Test all possible scope combinations to ensure no gaps."""
        scope_combinations = [
            # Single scope permissions
            ("user:read_self", ["user:read_self"], ["user:read_client", "user:read_platform", "user:read_all"]),
            ("user:read_client", ["user:read_self", "user:read_client"], ["user:read_platform", "user:read_all"]),
            ("user:read_platform", ["user:read_self", "user:read_client", "user:read_platform"], ["user:read_all"]),
            ("user:read_all", ["user:read_self", "user:read_client", "user:read_platform", "user:read_all"], []),
            
            # Manage permissions
            ("user:manage_client", ["user:read_self", "user:read_client", "user:manage_client"], ["user:read_platform", "user:manage_platform"]),
            ("user:manage_platform", ["user:read_self", "user:read_client", "user:read_platform", "user:manage_client", "user:manage_platform"], ["user:read_all", "user:manage_all"]),
            ("user:manage_all", ["user:read_self", "user:read_client", "user:read_platform", "user:read_all", "user:manage_client", "user:manage_platform", "user:manage_all"], []),
        ]
        
        for base_permission, should_have, should_not_have in scope_combinations:
            user_permissions = {base_permission}
            
            # Test permissions that should be included
            for permission in should_have:
                assert check_hierarchical_permission(user_permissions, permission), f"{base_permission} should include {permission}"
            
            # Test permissions that should NOT be included
            for permission in should_not_have:
                assert not check_hierarchical_permission(user_permissions, permission), f"{base_permission} should NOT include {permission}"

    def test_real_world_role_scenarios(self):
        """Test realistic combinations that would be used in real roles."""
        # Super Admin role
        super_admin = {
            "user:manage_all", "role:manage_all", "group:manage_all", 
            "permission:manage_all", "client:manage_all"
        }
        
        # Platform Admin role
        platform_admin = {
            "user:manage_platform", "role:read_all", "group:manage_platform",
            "client:manage_platform", "permission:read_all"
        }
        
        # Client Admin role
        client_admin = {
            "user:manage_client", "group:manage_client", "role:read_client",
            "permission:read_client", "client:read_own"
        }
        
        # Manager role
        manager = {
            "user:read_client", "group:read_client", "client:read_own"
        }
        
        # Employee role
        employee = {
            "user:read_self", "client:read_own"
        }
        
        # Test that each role has appropriate access
        role_tests = [
            (super_admin, "user:read_self", True),
            (super_admin, "role:manage_client", True),
            (platform_admin, "user:read_client", True),
            (platform_admin, "user:manage_all", False),
            (client_admin, "user:read_self", True),
            (client_admin, "user:read_platform", False),
            (manager, "user:read_self", True),
            (manager, "user:manage_client", False),
            (employee, "user:read_self", True),
            (employee, "user:read_client", False),
        ]
        
        for role_permissions, test_permission, expected in role_tests:
            result = check_hierarchical_permission(role_permissions, test_permission)
            assert result == expected, f"Role {role_permissions} -> {test_permission} should be {expected}, got {result}"


class TestDependencyCompatibility:
    """Test that our hierarchical permissions work correctly with the dependency system."""

    def test_require_permissions_any_of_logic(self):
        """Test that the any_of logic in require_permissions works with hierarchical permissions."""
        # Simulate the can_read_users dependency: any_of=["user:read_all", "user:read_platform", "user:read_client"]
        
        # User with user:manage_all should satisfy any of the read requirements
        user_permissions = {"user:manage_all"}
        assert check_hierarchical_permission(user_permissions, "user:read_all")
        assert check_hierarchical_permission(user_permissions, "user:read_platform")
        assert check_hierarchical_permission(user_permissions, "user:read_client")
        
        # User with user:read_platform should satisfy client read requirement
        user_permissions = {"user:read_platform"}
        assert check_hierarchical_permission(user_permissions, "user:read_client")
        assert not check_hierarchical_permission(user_permissions, "user:read_all")
        
        # User with only user:read_self should not satisfy any client read requirement
        user_permissions = {"user:read_self"}
        assert not check_hierarchical_permission(user_permissions, "user:read_client")

    def test_require_permissions_all_of_logic(self):
        """Test that the all_of logic works correctly with hierarchical permissions."""
        # Test a scenario where a user needs both user and role permissions
        user_permissions = {"user:manage_all", "role:read_platform"}
        
        # Should satisfy both requirements
        assert check_hierarchical_permission(user_permissions, "user:read_client")
        assert check_hierarchical_permission(user_permissions, "role:read_client")
        
        # User with only one permission should not satisfy both requirements
        user_permissions = {"user:manage_all"}
        assert check_hierarchical_permission(user_permissions, "user:read_client")
        assert not check_hierarchical_permission(user_permissions, "role:read_client")

    def test_backward_compatibility(self):
        """Test that hierarchical permissions maintain backward compatibility."""
        # Old direct permission checks should still work
        user_permissions = {"user:read_client"}
        assert check_hierarchical_permission(user_permissions, "user:read_client")
        
        # New hierarchical checks should also work
        user_permissions = {"user:manage_client"}
        assert check_hierarchical_permission(user_permissions, "user:read_client")
        
        # Mixed scenarios should work
        user_permissions = {"user:read_client", "role:manage_platform"}
        assert check_hierarchical_permission(user_permissions, "user:read_client")
        assert check_hierarchical_permission(user_permissions, "role:read_client")
        assert check_hierarchical_permission(user_permissions, "role:manage_client") 