#!/usr/bin/env python3
"""
Create Client Organization Script

This script creates a new client organization and their admin user.
Useful for onboarding real clients to the platform.

Usage:
  python scripts/create_client_organization.py --org-name "Qdarte" --admin-email "system@qdarte.com" --admin-password "Asd123$$$"
"""

import asyncio
import httpx
import argparse
import sys


class ClientOrganizationCreator:
    def __init__(self, base_url: str = "http://localhost:8030"):
        self.base_url = base_url
        self.admin_token = None
    
    async def authenticate_super_admin(self, super_admin_password: str = None):
        """Authenticate the super admin to get access token."""
        # Use the system@outlabs.io super admin from seed_super_admin.py
        super_admin_email = "system@outlabs.io"
        
        if not super_admin_password:
            print("❌ Super admin password is required")
            print("💡 The system@outlabs.io user was created with a random password.")
            print("💡 Please provide the password with --super-admin-password")
            return False
        
        async with httpx.AsyncClient() as client:
            print(f"Trying to authenticate with: {super_admin_email}")
            response = await client.post(
                f"{self.base_url}/v1/auth/login",
                data={"username": super_admin_email, "password": super_admin_password}
            )
            if response.status_code == 200:
                data = response.json()
                self.admin_token = data["access_token"]
                print(f"✅ Super admin authenticated successfully")
                return True
            else:
                print(f"❌ Super admin authentication failed: {response.text}")
                print("💡 Make sure:")
                print("   1. The super admin password is correct")
                print("   2. The database has been seeded with seed_super_admin.py")
                return False
    
    async def create_client_account(self, org_name: str, description: str = None):
        """Create a new client account."""
        if not self.admin_token:
            raise Exception("Not authenticated")
        
        if not description:
            description = f"{org_name} organization"
        
        client_data = {
            "name": org_name,
            "description": description
        }
        
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/client_accounts/", 
                headers=headers, 
                json=client_data
            )
            if response.status_code == 201:
                account = response.json()
                account_id = account.get("id", account.get("_id"))
                print(f"✅ Created client account: {org_name}")
                print(f"   Account ID: {account_id}")
                return account_id
            elif response.status_code == 409:
                print(f"⚠️  Client account '{org_name}' already exists")
                # Get existing account ID
                response = await client.get(f"{self.base_url}/v1/client_accounts/", headers=headers)
                if response.status_code == 200:
                    accounts = response.json()
                    for account in accounts:
                        if account["name"] == org_name:
                            account_id = account.get("id", account.get("_id"))
                            print(f"   Using existing account ID: {account_id}")
                            return account_id
                return None
            else:
                print(f"❌ Failed to create client account: {response.text}")
                return None
    
    async def create_admin_user(self, client_account_id: str, email: str, password: str, first_name: str, last_name: str):
        """Create an admin user for the client organization."""
        if not self.admin_token:
            raise Exception("Not authenticated")
        
        user_data = {
            "email": email,
            "password": password,
            "first_name": first_name,
            "last_name": last_name,
            "is_main_client": True,  # This makes them the main admin for their org
            "roles": ["client_admin"],  # Standard client admin role
            "client_account_id": client_account_id
        }
        
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/users/", 
                headers=headers, 
                json=user_data
            )
            if response.status_code == 201:
                user = response.json()
                user_id = user.get("id", user.get("_id"))
                print(f"✅ Created admin user: {email}")
                print(f"   User ID: {user_id}")
                print(f"   Role: client_admin")
                print(f"   Main client: Yes")
                return user_id
            elif response.status_code == 409:
                print(f"⚠️  User {email} already exists")
                return True
            else:
                print(f"❌ Failed to create admin user: {response.text}")
                print(f"   Response: {response.status_code}")
                return None


async def main():
    parser = argparse.ArgumentParser(description="Create a new client organization and admin user")
    parser.add_argument("--org-name", required=True, help="Organization name (e.g., 'Qdarte')")
    parser.add_argument("--admin-email", required=True, help="Admin user email (e.g., 'system@qdarte.com')")
    parser.add_argument("--admin-password", required=True, help="Admin user password")
    parser.add_argument("--admin-first-name", default="System", help="Admin first name (default: System)")
    parser.add_argument("--admin-last-name", default="Admin", help="Admin last name (default: Admin)")
    parser.add_argument("--description", help="Organization description (optional)")
    parser.add_argument("--super-admin-password", required=True, help="Password for system@outlabs.io super admin")
    parser.add_argument(
        "--api-url",
        default="http://localhost:8030",
        help="API base URL (default: http://localhost:8030)"
    )
    
    args = parser.parse_args()
    
    print("🚀 Creating new client organization...")
    print(f"   Organization: {args.org_name}")
    print(f"   Admin Email: {args.admin_email}")
    print(f"   Admin Name: {args.admin_first_name} {args.admin_last_name}")
    print(f"   API: {args.api_url}")
    print()
    
    creator = ClientOrganizationCreator(args.api_url)
    
    # Authenticate super admin
    if not await creator.authenticate_super_admin(args.super_admin_password):
        print("❌ Cannot proceed without super admin authentication")
        sys.exit(1)
    
    # Create the client account
    client_account_id = await creator.create_client_account(
        args.org_name, 
        args.description
    )
    
    if not client_account_id:
        print(f"❌ Failed to create client account for {args.org_name}")
        sys.exit(1)
    
    # Create the admin user
    user_id = await creator.create_admin_user(
        client_account_id,
        args.admin_email,
        args.admin_password,
        args.admin_first_name,
        args.admin_last_name
    )
    
    if user_id:
        print(f"\n🎉 Successfully created {args.org_name} organization!")
        print("\n📋 Summary:")
        print(f"   Organization: {args.org_name}")
        print(f"   Account ID: {client_account_id}")
        print(f"   Admin User: {args.admin_email}")
        print(f"   Admin Role: client_admin (main client)")
        print("\nNext steps:")
        print(f"   1. Admin can login with: {args.admin_email} / {args.admin_password}")
        print("   2. Admin can create additional users for their organization")
        print("   3. Admin can manage groups and permissions within their organization")
    else:
        print(f"\n❌ Failed to create admin user for {args.org_name}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 