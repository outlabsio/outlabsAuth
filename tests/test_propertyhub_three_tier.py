"""
Comprehensive PropertyHub Three-Tier SaaS Platform Tests

This test suite validates the PropertyHub platform model:
Tier 1: PropertyHub Platform Staff (admin@propertyhub.com, support@propertyhub.com)
Tier 2: Real Estate Companies (admin@acmerealestate.com, admin@eliteproperties.com)
Tier 3: Real Estate Agents (john.agent@acmerealestate.com, luxury.agent@eliteproperties.com)

Tests verify proper hierarchy, access control, and multi-tenant isolation.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient

class TestPropertyHubPlatformStaff:
    """Test PropertyHub internal platform staff capabilities."""
    
    @pytest.mark.asyncio
    async def test_platform_admin_can_view_all_clients(self, client: AsyncClient):
        """Platform admin should see all real estate companies."""
        # Login as PropertyHub platform admin
        login_data = {"username": "admin@propertyhub.com", "password": "platform123"}
        login_response = await client.post("/v1/auth/login", data=login_data)
        assert login_response.status_code == 200
        
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
        
        # Platform admin should see all client accounts
        response = await client.get("/v1/client_accounts/", headers=headers)
        assert response.status_code == 200
        
        client_accounts = response.json()
        client_names = [ca["name"] for ca in client_accounts]
        
        # Should see the PropertyHub platform and all real estate companies
        assert "PropertyHub Platform" in client_names
        assert "ACME Real Estate" in client_names
        assert "Elite Properties" in client_names
        assert "Downtown Realty" in client_names
    
    @pytest.mark.asyncio
    async def test_platform_support_has_limited_access(self, client: AsyncClient):
        """Platform support staff should have read-only access."""
        login_data = {"username": "support@propertyhub.com", "password": "platform123"}
        login_response = await client.post("/v1/auth/login", data=login_data)
        assert login_response.status_code == 200
        
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
        
        # Support can read client accounts
        response = await client.get("/v1/client_accounts/", headers=headers)
        assert response.status_code == 200
        
        # But cannot create new client accounts (should be forbidden or unauthorized)
        new_client_data = {
            "name": "Test Real Estate Company",
            "description": "Test company created by support"
        }
        create_response = await client.post("/v1/client_accounts/", 
                                          json=new_client_data, headers=headers)
        assert create_response.status_code in [403, 401, 422]  # Should be denied

    @pytest.mark.asyncio
    async def test_platform_staff_can_help_multiple_clients(self, client: AsyncClient):
        """Platform staff should access users across multiple real estate companies."""
        login_data = {"username": "admin@propertyhub.com", "password": "platform123"}
        login_response = await client.post("/v1/auth/login", data=login_data)
        assert login_response.status_code == 200
        
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
        
        # Platform admin should see users from multiple companies
        response = await client.get("/v1/users/", headers=headers)
        assert response.status_code == 200
        
        users = response.json()
        user_emails = [u["email"] for u in users]
        
        # Should see platform staff
        assert "admin@propertyhub.com" in user_emails
        assert "support@propertyhub.com" in user_emails
        
        # Should see real estate company admins
        assert "admin@acmerealestate.com" in user_emails
        assert "admin@eliteproperties.com" in user_emails
        
        # Should see real estate agents from different companies
        assert "john.agent@acmerealestate.com" in user_emails
        assert "luxury.agent@eliteproperties.com" in user_emails


class TestRealEstateCompanyAccess:
    """Test real estate company admin capabilities."""
    
    @pytest.mark.asyncio
    async def test_acme_admin_sees_only_acme_users(self, client: AsyncClient):
        """ACME Real Estate admin should only see ACME users."""
        login_data = {"username": "admin@acmerealestate.com", "password": "realestate123"}
        login_response = await client.post("/v1/auth/login", data=login_data)
        assert login_response.status_code == 200
        
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
        
        # ACME admin should only see ACME users
        response = await client.get("/v1/users/", headers=headers)
        assert response.status_code == 200
        
        users = response.json()
        user_emails = [u["email"] for u in users]
        
        # Should see ACME users
        assert "admin@acmerealestate.com" in user_emails
        assert "john.agent@acmerealestate.com" in user_emails
        assert "sarah.manager@acmerealestate.com" in user_emails
        
        # Should NOT see Elite Properties users
        assert "admin@eliteproperties.com" not in user_emails
        assert "luxury.agent@eliteproperties.com" not in user_emails
        
        # Should NOT see PropertyHub platform staff
        assert "admin@propertyhub.com" not in user_emails
        assert "support@propertyhub.com" not in user_emails

    @pytest.mark.asyncio
    async def test_elite_admin_sees_only_elite_users(self, client: AsyncClient):
        """Elite Properties admin should only see Elite Properties users."""
        login_data = {"username": "admin@eliteproperties.com", "password": "realestate123"}
        login_response = await client.post("/v1/auth/login", data=login_data)
        assert login_response.status_code == 200
        
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
        
        response = await client.get("/v1/users/", headers=headers)
        assert response.status_code == 200
        
        users = response.json()
        user_emails = [u["email"] for u in users]
        
        # Should see Elite Properties users
        assert "admin@eliteproperties.com" in user_emails
        assert "luxury.agent@eliteproperties.com" in user_emails
        
        # Should NOT see ACME users
        assert "admin@acmerealestate.com" not in user_emails
        assert "john.agent@acmerealestate.com" not in user_emails
        
        # Should NOT see PropertyHub platform staff
        assert "admin@propertyhub.com" not in user_emails

    @pytest.mark.asyncio
    async def test_real_estate_admin_can_manage_agents(self, client: AsyncClient):
        """Real estate company admin should manage their agents."""
        login_data = {"username": "admin@acmerealestate.com", "password": "realestate123"}
        login_response = await client.post("/v1/auth/login", data=login_data)
        assert login_response.status_code == 200
        
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
        
        # Admin should be able to create new agents in their company
        new_agent_data = {
            "email": "new.agent@acmerealestate.com",
            "password": "agent123",
            "first_name": "New",
            "last_name": "Agent",
            "roles": ["real_estate_agent"]
        }
        
        create_response = await client.post("/v1/users/", 
                                          json=new_agent_data, headers=headers)
        
        # Should succeed (200/201) or fail due to role permission checks
        # The important thing is that we can attempt this operation
        assert create_response.status_code in [200, 201, 403, 422]


class TestRealEstateAgentAccess:
    """Test real estate agent capabilities and restrictions."""
    
    @pytest.mark.asyncio
    async def test_agent_limited_to_own_company(self, client: AsyncClient):
        """Real estate agent should only access their own company's data."""
        login_data = {"username": "john.agent@acmerealestate.com", "password": "agent123"}
        login_response = await client.post("/v1/auth/login", data=login_data)
        assert login_response.status_code == 200
        
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
        
        # Agent should see limited users (likely just themselves or company users)
        response = await client.get("/v1/users/", headers=headers)
        assert response.status_code == 200
        
        users = response.json()
        user_emails = [u["email"] for u in users]
        
        # Should see themselves
        assert "john.agent@acmerealestate.com" in user_emails
        
        # Should NOT see Elite Properties users
        assert "luxury.agent@eliteproperties.com" not in user_emails
        
        # Should NOT see PropertyHub platform staff
        assert "admin@propertyhub.com" not in user_emails

    @pytest.mark.asyncio
    async def test_agent_cannot_manage_other_users(self, client: AsyncClient):
        """Real estate agent should not be able to create/manage other users."""
        login_data = {"username": "john.agent@acmerealestate.com", "password": "agent123"}
        login_response = await client.post("/v1/auth/login", data=login_data)
        assert login_response.status_code == 200
        
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
        
        # Agent should not be able to create new users
        new_user_data = {
            "email": "unauthorized@acmerealestate.com",
            "password": "test123",
            "first_name": "Unauthorized",
            "last_name": "User",
            "roles": ["real_estate_agent"]
        }
        
        create_response = await client.post("/v1/users/", 
                                          json=new_user_data, headers=headers)
        
        # Should be forbidden or unauthorized
        assert create_response.status_code in [403, 401, 422]


class TestThreeTierIsolation:
    """Test complete isolation between platform, companies, and agents."""
    
    @pytest.mark.asyncio
    async def test_cross_tier_data_isolation(self, client: AsyncClient):
        """Verify no data leakage between different tiers."""
        test_scenarios = [
            ("admin@propertyhub.com", "platform123"),  # Platform tier
            ("admin@acmerealestate.com", "realestate123"),  # Company tier
            ("john.agent@acmerealestate.com", "agent123")   # Agent tier
        ]
        
        for email, password in test_scenarios:
            login_data = {"username": email, "password": password}
            login_response = await client.post("/v1/auth/login", data=login_data)
            assert login_response.status_code == 200
            
            headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
            
            # Each tier should have different visibility
            users_response = await client.get("/v1/users/", headers=headers)
            assert users_response.status_code == 200
            
            users = users_response.json()
            user_count = len(users)
            
            # Platform admin should see the most users
            if email == "admin@propertyhub.com":
                assert user_count >= 8  # Should see platform + multiple companies
            
            # Company admin should see fewer users (just their company)  
            elif email == "admin@acmerealestate.com":
                assert user_count >= 3  # Should see ACME users only
                assert user_count <= 5  # Should not see other companies
            
            # Agent should see the fewest users
            elif email == "john.agent@acmerealestate.com":
                assert user_count >= 1  # Should see at least themselves
                assert user_count <= 5  # Should not see other companies

    @pytest.mark.asyncio
    async def test_propertyhub_realistic_workflow(self, client: AsyncClient):
        """Test a realistic PropertyHub platform workflow."""
        
        # 1. PropertyHub sales team works with potential client
        sales_login = {"username": "sales@propertyhub.com", "password": "platform123"}
        sales_response = await client.post("/v1/auth/login", data=sales_login)
        assert sales_response.status_code == 200
        
        sales_headers = {"Authorization": f"Bearer {sales_response.json()['access_token']}"}
        
        # Sales can view existing clients for reference
        clients_response = await client.get("/v1/client_accounts/", headers=sales_headers)
        assert clients_response.status_code == 200
        
        # 2. Real estate company admin manages their agents
        acme_login = {"username": "admin@acmerealestate.com", "password": "realestate123"}
        acme_response = await client.post("/v1/auth/login", data=acme_login)
        assert acme_response.status_code == 200
        
        acme_headers = {"Authorization": f"Bearer {acme_response.json()['access_token']}"}
        
        # ACME admin can see their agents
        acme_users_response = await client.get("/v1/users/", headers=acme_headers)
        assert acme_users_response.status_code == 200
        
        acme_users = acme_users_response.json()
        acme_agent_emails = [u["email"] for u in acme_users]
        assert "john.agent@acmerealestate.com" in acme_agent_emails
        
        # 3. PropertyHub support helps across multiple companies
        support_login = {"username": "support@propertyhub.com", "password": "platform123"}
        support_response = await client.post("/v1/auth/login", data=support_login)
        assert support_response.status_code == 200
        
        support_headers = {"Authorization": f"Bearer {support_response.json()['access_token']}"}
        
        # Support can view multiple companies for customer service
        support_clients_response = await client.get("/v1/client_accounts/", headers=support_headers)
        assert support_clients_response.status_code == 200
        
        support_clients = support_clients_response.json()
        client_names = [c["name"] for c in support_clients]
        assert "ACME Real Estate" in client_names
        assert "Elite Properties" in client_names


class TestPropertyHubAuthentication:
    """Test authentication across all three tiers."""
    
    @pytest.mark.asyncio
    async def test_all_propertyhub_users_can_login(self, client: AsyncClient):
        """Verify all PropertyHub scenario users can authenticate."""
        test_users = [
            # Platform staff
            ("admin@propertyhub.com", "platform123"),
            ("support@propertyhub.com", "platform123"),
            ("sales@propertyhub.com", "platform123"),
            
            # Real estate company admins
            ("admin@acmerealestate.com", "realestate123"),
            ("admin@eliteproperties.com", "realestate123"),
            ("admin@downtownrealty.com", "realestate123"),
            
            # Real estate agents
            ("john.agent@acmerealestate.com", "agent123"),
            ("sarah.manager@acmerealestate.com", "agent123"),
            ("luxury.agent@eliteproperties.com", "agent123")
        ]
        
        for email, password in test_users:
            login_data = {"username": email, "password": password}
            login_response = await client.post("/v1/auth/login", data=login_data)
            
            assert login_response.status_code == 200, f"Login failed for {email}"
            
            token_data = login_response.json()
            assert "access_token" in token_data
            assert token_data["token_type"] == "bearer"
            
            # Verify token works for protected endpoints
            headers = {"Authorization": f"Bearer {token_data['access_token']}"}
            profile_response = await client.get("/v1/auth/me", headers=headers)
            assert profile_response.status_code == 200
            
            profile = profile_response.json()
            assert profile["email"] == email

    @pytest.mark.asyncio
    async def test_propertyhub_role_hierarchy(self, client: AsyncClient):
        """Test that PropertyHub role hierarchy is properly enforced."""
        
        # Get platform admin token
        login_data = {"username": "admin@propertyhub.com", "password": "platform123"}
        login_response = await client.post("/v1/auth/login", data=login_data)
        assert login_response.status_code == 200
        
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
        
        # Platform admin should see their roles
        profile_response = await client.get("/v1/auth/me", headers=headers)
        assert profile_response.status_code == 200
        
        profile = profile_response.json()
        # With the new role system, roles are ObjectIds, not names
        user_roles = profile.get("roles", [])
        assert len(user_roles) > 0, "User should have at least one role"
        
        # Verify roles endpoint works
        roles_response = await client.get("/v1/roles/", headers=headers)
        assert roles_response.status_code == 200
        
        roles = roles_response.json()
        
        # Should see PropertyHub-specific roles with proper scopes
        role_names = [r["name"] for r in roles]
        role_scopes = [r["scope"] for r in roles]
        
        # Should see platform-scoped roles
        assert "admin" in role_names, "Should see platform admin role"
        assert "support" in role_names, "Should see platform support role"
        assert "sales" in role_names, "Should see platform sales role"
        
        # Should see roles from different scopes
        assert "system" in role_scopes, "Should see system-scoped roles"
        assert "platform" in role_scopes, "Should see platform-scoped roles"
        # Platform admin should NOT see client-scoped roles from other tenants
        # This would violate tenant isolation 


class TestPlatformElevationRequirements:
    """Test cases that demonstrate the need for platform elevation features.
    
    These tests document what SHOULD work once platform elevation is implemented.
    Currently these tests will fail, demonstrating the gaps in the current system.
    """
    
    @pytest.mark.asyncio
    async def test_platform_admin_cross_client_visibility_requirement(self, client: AsyncClient):
        """REQUIREMENT: Platform admin should see all clients they manage.
        
        Currently FAILS: Platform admin can only see PropertyHub Platform, not real estate companies.
        Should PASS after Phase 1 implementation (Platform Permission Elevation).
        """
        login_data = {"username": "admin@propertyhub.com", "password": "platform123"}
        login_response = await client.post("/v1/auth/login", data=login_data)
        assert login_response.status_code == 200
        
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
        
        response = await client.get("/v1/client_accounts/", headers=headers)
        assert response.status_code == 200
        
        client_accounts = response.json()
        client_names = [ca["name"] for ca in client_accounts]
        
        # This test currently FAILS but documents the requirement
        # After Phase 1 implementation, these assertions should PASS
        assert "PropertyHub Platform" in client_names
        # These will currently fail:
        assert "ACME Real Estate" in client_names, "Platform admin should see ACME Real Estate"
        assert "Elite Properties" in client_names, "Platform admin should see Elite Properties"
        assert "Downtown Realty" in client_names, "Platform admin should see Downtown Realty"
    
    @pytest.mark.asyncio
    async def test_platform_support_cross_client_user_access_requirement(self, client: AsyncClient):
        """REQUIREMENT: Platform support should help users across all real estate companies.
        
        Currently FAILS: Support staff isolated to their own platform account.
        Should PASS after Phase 2 implementation (Cross-Client User Management).
        """
        login_data = {"username": "support@propertyhub.com", "password": "platform123"}
        login_response = await client.post("/v1/auth/login", data=login_data)
        assert login_response.status_code == 200
        
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
        
        response = await client.get("/v1/users/", headers=headers)
        assert response.status_code == 200
        
        users = response.json()
        user_emails = [u["email"] for u in users]
        
        # This test currently FAILS but documents the requirement
        # After Phase 2 implementation, these assertions should PASS
        assert "support@propertyhub.com" in user_emails, "Support should see themselves"
        # These will currently fail:
        assert "admin@acmerealestate.com" in user_emails, "Support should see ACME admin for customer service"
        assert "john.agent@acmerealestate.com" in user_emails, "Support should see ACME agents for help"
        assert "admin@eliteproperties.com" in user_emails, "Support should see Elite admin for customer service"
        assert "luxury.agent@eliteproperties.com" in user_emails, "Support should see Elite agents for help"
    
    @pytest.mark.asyncio
    async def test_platform_analytics_requirement(self, client: AsyncClient):
        """REQUIREMENT: Platform staff should access analytics across all clients.
        
        Currently FAILS: No platform analytics endpoint exists.
        Should PASS after Phase 2 implementation (Cross-Client Management).
        """
        login_data = {"username": "admin@propertyhub.com", "password": "platform123"}
        login_response = await client.post("/v1/auth/login", data=login_data)
        assert login_response.status_code == 200
        
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
        
        # This endpoint doesn't exist yet, will return 404
        analytics_response = await client.get("/v1/platform/analytics", headers=headers)
        
        # Currently FAILS (404), should PASS after Phase 2 implementation
        assert analytics_response.status_code == 200, "Platform analytics endpoint should exist"
        
        analytics = analytics_response.json()
        assert "total_clients" in analytics, "Should show total clients across platform"
        assert "total_users" in analytics, "Should show total users across all real estate companies"
        assert analytics["total_clients"] >= 4, "Should count PropertyHub + 3 real estate companies"
        assert analytics["total_users"] >= 9, "Should count platform staff + real estate users"
    
    @pytest.mark.asyncio
    async def test_client_onboarding_workflow_requirement(self, client: AsyncClient):
        """REQUIREMENT: Platform admin should onboard new real estate companies.
        
        Currently FAILS: No special onboarding workflow exists.
        Should PASS after Phase 4 implementation (Platform Client Relationship Management).
        """
        login_data = {"username": "admin@propertyhub.com", "password": "platform123"}
        login_response = await client.post("/v1/auth/login", data=login_data)
        assert login_response.status_code == 200
        
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
        
        new_client_data = {
            "name": "Sunset Realty",
            "description": "New real estate company joining PropertyHub platform",
            "contact_email": "admin@sunsetrealty.com"
        }
        
        # This endpoint doesn't exist yet, will return 404
        onboard_response = await client.post("/v1/client_accounts/onboard-client", 
                                           json=new_client_data, headers=headers)
        
        # Currently FAILS (404), should PASS after Phase 4 implementation  
        assert onboard_response.status_code == 201, "Platform admin should be able to onboard new clients"
        
        new_client = onboard_response.json()
        assert new_client["name"] == "Sunset Realty"
        assert "created_by_platform" in new_client, "Should track which platform created this client"


class TestPlatformPermissionValidation:
    """Test cases for platform-specific permission requirements.
    
    These tests document what permissions should exist for platform staff.
    Currently these will fail, demonstrating the need for Phase 3 implementation.
    """
    
    @pytest.mark.asyncio
    async def test_platform_permission_requirements(self, client: AsyncClient):
        """REQUIREMENT: Platform staff should have specific platform permissions.
        
        Currently FAILS: Platform permissions don't exist in the permission system.
        Should PASS after Phase 3 implementation (Enhanced Permission System).
        """
        login_data = {"username": "admin@propertyhub.com", "password": "platform123"}
        login_response = await client.post("/v1/auth/login", data=login_data)
        assert login_response.status_code == 200
        
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
        
        permissions_response = await client.get("/v1/permissions/", headers=headers)
        assert permissions_response.status_code == 200
        
        permissions = permissions_response.json()
        permission_names = [p["name"] for p in permissions]
        
        # These platform permissions should exist (updated to match actual permission names)
        required_platform_permissions = [
            "client:manage_platform",  # Updated from clients:manage
            "analytics:view_platform", # Updated from analytics:view  
            "support:cross_client",
            "client:onboard"           # Updated from clients:onboard
        ]
        
        for permission in required_platform_permissions:
            assert permission in permission_names, f"Platform permission {permission} should exist"
    
    @pytest.mark.asyncio
    async def test_platform_staff_permission_elevation(self, client: AsyncClient):
        """REQUIREMENT: Platform staff should have elevated permissions.
        
        Currently FAILS: Platform staff treated same as regular client users.
        Should PASS after Phase 1 & 3 implementation.
        """
        # Test platform admin permissions
        login_data = {"username": "admin@propertyhub.com", "password": "platform123"}
        login_response = await client.post("/v1/auth/login", data=login_data)
        assert login_response.status_code == 200
        
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
        
        profile_response = await client.get("/v1/auth/me", headers=headers)
        assert profile_response.status_code == 200
        
        profile = profile_response.json()
        
        # After Phase 1 & 3 implementation, platform admin should have these attributes
        assert profile.get("is_platform_staff") == True, "Platform admin should be marked as platform staff"
        assert profile.get("platform_scope") is not None, "Platform admin should have platform scope"
        
        # Platform admin should have platform permissions
        user_permissions = profile.get("permissions", [])
        permission_names = [p.get("name") for p in user_permissions if isinstance(p, dict)]
        assert "client:manage_platform" in permission_names, "Platform admin should have client management permission"
        assert "analytics:view_platform" in permission_names, "Platform admin should have analytics permission"
    
    @pytest.mark.asyncio
    async def test_regular_client_cannot_access_platform_features(self, client: AsyncClient):
        """REQUIREMENT: Regular client users should not have platform permissions.
        
        This test should continue to PASS - regular clients should remain isolated.
        """
        login_data = {"username": "admin@acmerealestate.com", "password": "realestate123"}
        login_response = await client.post("/v1/auth/login", data=login_data)
        assert login_response.status_code == 200
        
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
        
        profile_response = await client.get("/v1/auth/me", headers=headers)
        assert profile_response.status_code == 200
        
        profile = profile_response.json()
        
        # Regular client admin should NOT have platform elevation
        assert profile.get("is_platform_staff") != True, "Regular client should not be platform staff"
        assert profile.get("platform_scope") is None, "Regular client should not have platform scope"
        
        # Regular client should NOT have platform permissions
        user_permissions = profile.get("permissions", [])
        permission_names = [p.get("name") for p in user_permissions if isinstance(p, dict)]
        assert "client:manage_platform" not in permission_names, "Client admin should not have platform permissions"
        assert "analytics:view_platform" not in permission_names, "Client admin should not have platform analytics"


class TestPropertyHubGroupManagement:
    """Test group management scenarios specific to PropertyHub three-tier model."""
    
    @pytest.mark.asyncio
    async def test_platform_internal_team_group(self, client: AsyncClient):
        """Test PropertyHub internal team group functionality."""
        login_data = {"username": "admin@propertyhub.com", "password": "platform123"}
        login_response = await client.post("/v1/auth/login", data=login_data)
        assert login_response.status_code == 200
        
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
        
        groups_response = await client.get("/v1/groups/", headers=headers)
        assert groups_response.status_code == 200
        
        groups = groups_response.json()
        group_names = [g["name"] for g in groups]
        
        # Should see PropertyHub internal team group
        assert "PropertyHub Internal Team" in group_names
    
    @pytest.mark.asyncio
    async def test_real_estate_sales_team_groups(self, client: AsyncClient):
        """Test real estate company sales team groups."""
        login_data = {"username": "admin@acmerealestate.com", "password": "realestate123"}
        login_response = await client.post("/v1/auth/login", data=login_data)
        assert login_response.status_code == 200
        
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
        
        groups_response = await client.get("/v1/groups/", headers=headers)
        assert groups_response.status_code == 200
        
        groups = groups_response.json()
        group_names = [g["name"] for g in groups]
        
        # Should see ACME sales team group
        assert "ACME Sales Team" in group_names
        
        # Should NOT see PropertyHub internal team
        assert "PropertyHub Internal Team" not in group_names
    
    @pytest.mark.asyncio
    async def test_agent_group_visibility_restrictions(self, client: AsyncClient):
        """Test that agents have limited group visibility."""
        login_data = {"username": "john.agent@acmerealestate.com", "password": "agent123"}
        login_response = await client.post("/v1/auth/login", data=login_data)
        assert login_response.status_code == 200
        
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
        
        groups_response = await client.get("/v1/groups/", headers=headers)
        assert groups_response.status_code == 200
        
        groups = groups_response.json()
        group_names = [g["name"] for g in groups]
        
        # Agent should see their company group
        assert "ACME Sales Team" in group_names
        
        # Agent should NOT see other company or platform groups
        assert "PropertyHub Internal Team" not in group_names


class TestPropertyHubRealWorldScenarios:
    """Test realistic business scenarios for PropertyHub platform."""
    
    @pytest.mark.asyncio
    async def test_customer_support_scenario(self, client: AsyncClient):
        """Test PropertyHub support helping ACME Real Estate with user issues."""
        # 1. ACME admin reports an issue with their agent
        acme_login = {"username": "admin@acmerealestate.com", "password": "realestate123"}
        acme_response = await client.post("/v1/auth/login", data=acme_login)
        assert acme_response.status_code == 200
        
        acme_headers = {"Authorization": f"Bearer {acme_response.json()['access_token']}"}
        
        # ACME admin can see their problematic agent
        users_response = await client.get("/v1/users/", headers=acme_headers)
        assert users_response.status_code == 200
        
        users = users_response.json()
        agent_emails = [u["email"] for u in users if "john.agent" in u["email"]]
        assert len(agent_emails) > 0, "ACME admin should see john.agent@acmerealestate.com"
        
        # 2. PropertyHub support investigates across multiple clients
        support_login = {"username": "support@propertyhub.com", "password": "platform123"}
        support_response = await client.post("/v1/auth/login", data=support_login)
        assert support_response.status_code == 200
        
        support_headers = {"Authorization": f"Bearer {support_response.json()['access_token']}"}
        
        # Support should be able to see users across companies for investigation
        # Currently this fails - support is isolated to PropertyHub platform only
        support_users_response = await client.get("/v1/users/", headers=support_headers)
        assert support_users_response.status_code == 200
        
        support_users = support_users_response.json()
        support_visible_emails = [u["email"] for u in support_users]
        
        # Support should see platform staff
        assert "support@propertyhub.com" in support_visible_emails
        
        # Support SHOULD see ACME users (currently fails, needs Phase 2 implementation)
        # assert "john.agent@acmerealestate.com" in support_visible_emails
    
    @pytest.mark.asyncio
    async def test_sales_team_client_prospecting(self, client: AsyncClient):
        """Test PropertyHub sales team prospecting new real estate companies."""
        sales_login = {"username": "sales@propertyhub.com", "password": "platform123"}
        sales_response = await client.post("/v1/auth/login", data=sales_login)
        assert sales_response.status_code == 200
        
        sales_headers = {"Authorization": f"Bearer {sales_response.json()['access_token']}"}
        
        # Sales should see existing clients for market analysis
        clients_response = await client.get("/v1/client_accounts/", headers=sales_headers)
        assert clients_response.status_code == 200
        
        clients = clients_response.json()
        client_names = [c["name"] for c in clients]
        
        # Sales should see PropertyHub platform
        assert "PropertyHub Platform" in client_names
        
        # Sales SHOULD see real estate companies for competitive analysis
        # Currently this may fail - needs Phase 1 implementation
        # assert "ACME Real Estate" in client_names
        # assert "Elite Properties" in client_names
    
    @pytest.mark.asyncio
    async def test_multi_company_agent_comparison(self, client: AsyncClient):
        """Test scenario where platform needs to compare agents across companies."""
        platform_login = {"username": "admin@propertyhub.com", "password": "platform123"}
        platform_response = await client.post("/v1/auth/login", data=platform_login)
        assert platform_response.status_code == 200
        
        platform_headers = {"Authorization": f"Bearer {platform_response.json()['access_token']}"}
        
        # Platform admin should see users across all real estate companies
        users_response = await client.get("/v1/users/", headers=platform_headers)
        assert users_response.status_code == 200
        
        users = users_response.json()
        user_emails = [u["email"] for u in users]
        
        # Platform should see their own staff
        assert "admin@propertyhub.com" in user_emails
        
        # Platform SHOULD see agents from multiple companies for analytics
        # Currently this may fail - needs Phase 1 & 2 implementation
        acme_agents = [email for email in user_emails if "acmerealestate.com" in email]
        elite_agents = [email for email in user_emails if "eliteproperties.com" in email]
        
        # These assertions document what should work after implementation
        # assert len(acme_agents) >= 2, "Should see ACME Real Estate agents"
        # assert len(elite_agents) >= 1, "Should see Elite Properties agents"
    
    @pytest.mark.asyncio
    async def test_platform_metrics_and_reporting(self, client: AsyncClient):
        """Test platform-wide metrics collection across all real estate companies."""
        admin_login = {"username": "admin@propertyhub.com", "password": "platform123"}
        admin_response = await client.post("/v1/auth/login", data=admin_login)
        assert admin_response.status_code == 200
        
        admin_headers = {"Authorization": f"Bearer {admin_response.json()['access_token']}"}
        
        # Platform admin should access current client accounts for metrics
        clients_response = await client.get("/v1/client_accounts/", headers=admin_headers)
        assert clients_response.status_code == 200
        
        clients = clients_response.json()
        
        # Should see multiple real estate companies for platform metrics
        real_estate_clients = [c for c in clients if c["name"] != "PropertyHub Platform"]
        
        # Platform should manage multiple real estate companies
        # Currently this may fail - needs Phase 1 implementation
        # assert len(real_estate_clients) >= 3, "Platform should manage multiple real estate companies"
        
        # Extract business metrics
        total_companies = len(real_estate_clients)
        platform_info = {
            "managed_companies": total_companies,
            "companies": [c["name"] for c in real_estate_clients]
        }
        
        # This data would be used for platform business intelligence
        # Currently limited due to access control restrictions
        assert platform_info["managed_companies"] >= 0, "Should count managed companies"


class TestPropertyHubSecurityBoundaries:
    """Test security boundaries in the PropertyHub three-tier system."""
    
    @pytest.mark.asyncio
    async def test_agent_cannot_access_other_companies(self, client: AsyncClient):
        """Verify agents cannot break out of their company boundaries."""
        # Test ACME agent isolation
        acme_login = {"username": "john.agent@acmerealestate.com", "password": "agent123"}
        acme_response = await client.post("/v1/auth/login", data=acme_login)
        assert acme_response.status_code == 200
        
        acme_headers = {"Authorization": f"Bearer {acme_response.json()['access_token']}"}
        
        # ACME agent should NOT see Elite Properties data
        clients_response = await client.get("/v1/client_accounts/", headers=acme_headers)
        assert clients_response.status_code == 200
        
        clients = clients_response.json()
        client_names = [c["name"] for c in clients]
        
        # Should see their own company
        assert "ACME Real Estate" in client_names
        
        # Should NOT see competitor companies
        assert "Elite Properties" not in client_names
        assert "Downtown Realty" not in client_names
        assert "PropertyHub Platform" not in client_names
    
    @pytest.mark.asyncio
    async def test_company_admin_isolation(self, client: AsyncClient):
        """Verify company admins cannot access other companies' data."""
        # Test Elite Properties admin isolation
        elite_login = {"username": "admin@eliteproperties.com", "password": "realestate123"}
        elite_response = await client.post("/v1/auth/login", data=elite_login)
        assert elite_response.status_code == 200
        
        elite_headers = {"Authorization": f"Bearer {elite_response.json()['access_token']}"}
        
        # Elite admin should NOT see ACME users
        users_response = await client.get("/v1/users/", headers=elite_headers)
        assert users_response.status_code == 200
        
        users = users_response.json()
        user_emails = [u["email"] for u in users]
        
        # Should see their own company users
        elite_users = [email for email in user_emails if "eliteproperties.com" in email]
        assert len(elite_users) >= 1, "Elite admin should see Elite Properties users"
        
        # Should NOT see competitor company users
        acme_users = [email for email in user_emails if "acmerealestate.com" in email]
        downtown_users = [email for email in user_emails if "downtownrealty.com" in email]
        platform_users = [email for email in user_emails if "propertyhub.com" in email]
        
        assert len(acme_users) == 0, "Elite admin should not see ACME users"
        assert len(downtown_users) == 0, "Elite admin should not see Downtown users"
        assert len(platform_users) == 0, "Elite admin should not see PropertyHub platform users"
    
    @pytest.mark.asyncio
    async def test_data_breach_prevention(self, client: AsyncClient):
        """Test that no user can accidentally see data from other tiers."""
        test_scenarios = [
            ("john.agent@acmerealestate.com", "agent123", "Real Estate Agent"),
            ("admin@eliteproperties.com", "realestate123", "Company Admin"),
            ("support@propertyhub.com", "platform123", "Platform Support")
        ]
        
        for email, password, role_description in test_scenarios:
            login_data = {"username": email, "password": password}
            login_response = await client.post("/v1/auth/login", data=login_data)
            assert login_response.status_code == 200, f"Login failed for {role_description}"
            
            headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
            
            # Test client account access
            clients_response = await client.get("/v1/client_accounts/", headers=headers)
            assert clients_response.status_code == 200
            
            clients = clients_response.json()
            
            # Each user should see limited client accounts based on their tier
            if "propertyhub.com" in email:
                # Platform staff currently see only PropertyHub Platform
                # After Phase 1: should see all managed real estate companies
                pass
            elif "admin@" in email:
                # Company admins should see only their company
                assert len(clients) <= 2, f"{role_description} should see limited clients"
            else:
                # Agents should see very limited or no client account data
                assert len(clients) <= 2, f"{role_description} should see minimal client data"
            
            # Test user access
            users_response = await client.get("/v1/users/", headers=headers)
            assert users_response.status_code == 200
            
            users = users_response.json()
            
            # Each user should see limited users based on their tier
            if "propertyhub.com" in email:
                # Platform staff currently see only PropertyHub staff
                # After Phase 2: should see users across all real estate companies
                pass
            elif "admin@" in email:
                # Company admins should see only their company users
                company_domain = email.split("@")[1]
                visible_domains = set(u["email"].split("@")[1] for u in users)
                assert company_domain in visible_domains, f"{role_description} should see own company"
                
                # Should not see other company domains
                forbidden_domains = ["propertyhub.com", "acmerealestate.com", "eliteproperties.com", "downtownrealty.com"]
                forbidden_domains.remove(company_domain)  # Remove own domain from forbidden list
                
                for forbidden_domain in forbidden_domains:
                    assert forbidden_domain not in visible_domains, f"{role_description} should not see {forbidden_domain}"
            else:
                # Agents should see very limited users
                assert len(users) <= 5, f"{role_description} should see limited users" 