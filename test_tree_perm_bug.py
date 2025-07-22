#!/usr/bin/env python3
"""Test tree permission bug directly"""
import httpx
import asyncio

BASE_URL = "http://localhost:8030/v1"

async def test_tree_permissions():
    async with httpx.AsyncClient() as client:
        # Login as system admin
        login_resp = await client.post(
            f"{BASE_URL}/auth/login/json",
            json={"email": "system@outlabs.io", "password": "Asd123$$$"}
        )
        assert login_resp.status_code == 200
        sys_token = login_resp.json()["access_token"]
        sys_headers = {"Authorization": f"Bearer {sys_token}"}
        
        # Create a platform
        platform_resp = await client.post(
            f"{BASE_URL}/entities",
            headers=sys_headers,
            json={
                "name": "test_platform_direct",
                "display_name": "Test Platform Direct", 
                "entity_type": "platform",
                "entity_class": "STRUCTURAL"
            }
        )
        if platform_resp.status_code != 200:
            print(f"Platform creation failed: {platform_resp.status_code}")
            print(f"Response: {platform_resp.text}")
            return
        platform = platform_resp.json()
        print(f"Created platform: {platform['id']}")
        
        # Create an org under platform
        org_resp = await client.post(
            f"{BASE_URL}/entities",
            headers=sys_headers,
            json={
                "name": "test_org_direct",
                "display_name": "Test Org Direct",
                "entity_type": "organization", 
                "entity_class": "STRUCTURAL",
                "parent_entity_id": platform['id']
            }
        )
        assert org_resp.status_code == 200
        org = org_resp.json()
        print(f"Created org: {org['id']} with parent: {org.get('parent_entity_id')}")
        
        # Create a user
        user_resp = await client.post(
            f"{BASE_URL}/users",
            headers=sys_headers,
            json={
                "email": "test_admin_direct@test.com",
                "password": "Test123!",
                "is_active": True,
                "is_verified": True
            }
        )
        assert user_resp.status_code == 200
        user = user_resp.json()
        print(f"Created user: {user['id']}")
        
        # Create role with tree permissions at platform
        role_resp = await client.post(
            f"{BASE_URL}/roles",
            headers=sys_headers,
            json={
                "name": "platform_admin_role",
                "display_name": "Platform Admin Role",
                "entity_id": platform['id'],
                "permissions": ["entity:update_tree", "entity:read_tree"]
            }
        )
        assert role_resp.status_code == 200
        role = role_resp.json()
        print(f"Created role with permissions: {role['permissions']}")
        
        # Add user to platform with role
        member_resp = await client.post(
            f"{BASE_URL}/entities/{platform['id']}/members",
            headers=sys_headers,
            json={
                "user_id": user['id'],
                "role_ids": [role['id']]
            }
        )
        assert member_resp.status_code == 200
        print("Added user to platform with role")
        
        # Login as the test user
        user_login_resp = await client.post(
            f"{BASE_URL}/auth/login/json",
            json={"email": "test_admin_direct@test.com", "password": "Test123!"}
        )
        assert user_login_resp.status_code == 200
        user_token = user_login_resp.json()["access_token"]
        user_headers = {"Authorization": f"Bearer {user_token}"}
        
        # Try to update the org
        print("\n--- Testing Update ---")
        update_resp = await client.put(
            f"{BASE_URL}/entities/{org['id']}",
            headers=user_headers,
            json={"description": "Updated by platform admin"}
        )
        
        print(f"Update status: {update_resp.status_code}")
        print(f"Update response: {update_resp.text}")
        
        # Cleanup
        await client.delete(f"{BASE_URL}/entities/{org['id']}", headers=sys_headers)
        await client.delete(f"{BASE_URL}/entities/{platform['id']}", headers=sys_headers)


if __name__ == "__main__":
    asyncio.run(test_tree_permissions())