import asyncio
import httpx
import json
import os
from typing import Dict, Any, List


class APISeedingClient:
    """Client to seed data through the API endpoints, simulating real user behavior."""
    
    def __init__(self, base_url: str = "http://localhost:8030"):
        self.base_url = base_url
        self.tokens: Dict[str, str] = {}  # Store access tokens for different users
        
    async def authenticate(self, email: str, password: str) -> str:
        """Authenticate a user and return access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/auth/login",
                data={"username": email, "password": password}
            )
            if response.status_code == 200:
                data = response.json()
                access_token = data["access_token"]
                self.tokens[email] = access_token
                print(f"✓ Authenticated {email}")
                return access_token
            else:
                print(f"✗ Failed to authenticate {email}: {response.text}")
                raise Exception(f"Authentication failed for {email}")
    
    async def make_authenticated_request(
        self, 
        method: str, 
        endpoint: str, 
        user_email: str, 
        json_data: Dict[str, Any] = None
    ) -> httpx.Response:
        """Make an authenticated request on behalf of a user."""
        if user_email not in self.tokens:
            raise Exception(f"No token found for user {user_email}")
        
        headers = {"Authorization": f"Bearer {self.tokens[user_email]}"}
        
        async with httpx.AsyncClient() as client:
            if method.upper() == "GET":
                response = await client.get(f"{self.base_url}{endpoint}", headers=headers)
            elif method.upper() == "POST":
                response = await client.post(f"{self.base_url}{endpoint}", headers=headers, json=json_data)
            elif method.upper() == "PUT":
                response = await client.put(f"{self.base_url}{endpoint}", headers=headers, json=json_data)
            elif method.upper() == "DELETE":
                response = await client.delete(f"{self.base_url}{endpoint}", headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            return response
    
    async def create_client_account(self, admin_email: str, account_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a client account as platform admin."""
        response = await self.make_authenticated_request(
            "POST", "/v1/client_accounts/", admin_email, account_data
        )
        if response.status_code == 201:
            account = response.json()
            # Handle both 'id' and '_id' field names
            account_id = account.get('id', account.get('_id'))
            print(f"✓ Created client account: {account['name']} (ID: {account_id})")
            # Ensure 'id' field exists for compatibility
            if 'id' not in account and '_id' in account:
                account['id'] = account['_id']
            return account
        elif response.status_code == 409:  # Conflict - already exists
            # Get existing accounts and find the one with matching name
            existing_response = await self.make_authenticated_request(
                "GET", "/v1/client_accounts/", admin_email
            )
            if existing_response.status_code == 200:
                accounts = existing_response.json()
                for account in accounts:
                    if account['name'] == account_data['name']:
                        # Ensure 'id' field exists for compatibility
                        if 'id' not in account and '_id' in account:
                            account['id'] = account['_id']
                        print(f"✓ Found existing client account: {account['name']} (ID: {account.get('id', account.get('_id'))})")
                        return account
            print(f"✗ Failed to create client account: {response.text}")
            raise Exception(f"Failed to create client account: {response.text}")
        else:
            print(f"✗ Failed to create client account: {response.text}")
            raise Exception(f"Failed to create client account: {response.text}")
    
    async def create_user(self, creator_email: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a user."""
        response = await self.make_authenticated_request(
            "POST", "/v1/users/", creator_email, user_data
        )
        if response.status_code == 201:
            user = response.json()
            print(f"✓ Created user: {user['email']} ({user['first_name']} {user['last_name']})")
            # Ensure 'id' field exists for compatibility
            if 'id' not in user and '_id' in user:
                user['id'] = user['_id']
            return user
        elif response.status_code == 409:  # Conflict - already exists
            # Get existing users and find the one with matching email
            existing_response = await self.make_authenticated_request(
                "GET", "/v1/users/", creator_email
            )
            if existing_response.status_code == 200:
                users = existing_response.json()
                for user in users:
                    if user['email'] == user_data['email']:
                        # Ensure 'id' field exists for compatibility
                        if 'id' not in user and '_id' in user:
                            user['id'] = user['_id']
                        print(f"✓ Found existing user: {user['email']} ({user['first_name']} {user['last_name']})")
                        return user
            print(f"✗ Failed to create user: {response.text}")
            raise Exception(f"Failed to create user: {response.text}")
        else:
            print(f"✗ Failed to create user: {response.text}")
            raise Exception(f"Failed to create user: {response.text}")
    
    async def create_group(self, creator_email: str, group_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a group."""
        response = await self.make_authenticated_request(
            "POST", "/v1/groups/", creator_email, group_data
        )
        if response.status_code == 201:
            group = response.json()
            # Handle both 'id' and '_id' field names
            group_id = group.get('id', group.get('_id'))
            print(f"✓ Created group: {group['name']} (ID: {group_id})")
            # Ensure 'id' field exists for compatibility
            if 'id' not in group and '_id' in group:
                group['id'] = group['_id']
            return group
        else:
            print(f"✗ Failed to create group: {response.text}")
            raise Exception(f"Failed to create group: {response.text}")
    
    async def get_users(self, requester_email: str) -> List[Dict[str, Any]]:
        """Get users list."""
        response = await self.make_authenticated_request(
            "GET", "/v1/users/", requester_email
        )
        if response.status_code == 200:
            users = response.json()
            print(f"✓ Retrieved {len(users)} users for {requester_email}")
            # Ensure 'id' field exists for compatibility
            for user in users:
                if 'id' not in user and '_id' in user:
                    user['id'] = user['_id']
            return users
        else:
            print(f"✗ Failed to get users: {response.text}")
            raise Exception(f"Failed to get users: {response.text}")


async def seed_via_api():
    """
    Seed the database through API calls, simulating real client behavior.
    
    This approach:
    1. Platform admin creates client accounts 
    2. Client admins create their own users and groups
    3. Tests realistic access patterns and permissions
    """
    
    print("=== API-Based Seeding Started ===")
    print("This script simulates real client behavior by making HTTP requests\n")
    
    # Ensure the API server is running
    print("⚠️  Make sure the API server is running on http://localhost:8030")
    print("⚠️  Make sure the database has been seeded with basic data (run seed_main.py first)\n")
    
    client = APISeedingClient()
    
    # Step 1: Platform admin authenticates and creates client accounts
    print("🔐 Step 1: Platform Admin Authentication")
    try:
        platform_admin_email = "admin@test.com"
        await client.authenticate(platform_admin_email, "admin123")
    except Exception as e:
        print(f"❌ Platform admin authentication failed: {e}")
        print("💡 Run scripts/seed_main.py first to create the platform admin user")
        return
    
    print("\n🏢 Step 2: Platform Admin Creates Client Accounts")
    
    # Create GreenTech Industries
    greentech_account = await client.create_client_account(
        platform_admin_email,
        {
            "name": "GreenTech Industries",
            "description": "Renewable energy solutions company"
        }
    )
    
    # Create MedCorp Healthcare
    medcorp_account = await client.create_client_account(
        platform_admin_email,
        {
            "name": "MedCorp Healthcare",
            "description": "Healthcare technology solutions"
        }
    )
    
    # Create RetailPlus
    retailplus_account = await client.create_client_account(
        platform_admin_email,
        {
            "name": "RetailPlus",
            "description": "Modern retail management platform"
        }
    )
    
    print("\n👤 Step 3: Platform Admin Creates Client Administrators")
    
    # Create GreenTech admin
    greentech_admin = await client.create_user(
        platform_admin_email,
        {
            "email": "admin@greentech.com",
            "password": "greentech123",
            "first_name": "Sarah",
            "last_name": "Green",
            "is_main_client": True,
            "roles": ["client_admin"],
            "client_account_id": greentech_account["id"]
        }
    )
    
    # Create MedCorp admin
    medcorp_admin = await client.create_user(
        platform_admin_email,
        {
            "email": "admin@medcorp.com",
            "password": "medcorp123",
            "first_name": "Dr. Michael",
            "last_name": "Care",
            "is_main_client": True,
            "roles": ["client_admin"],
            "client_account_id": medcorp_account["id"]
        }
    )
    
    # Create RetailPlus admin
    retailplus_admin = await client.create_user(
        platform_admin_email,
        {
            "email": "admin@retailplus.com",
            "password": "retail123",
            "first_name": "Emma",
            "last_name": "Shop",
            "is_main_client": True,
            "roles": ["client_admin"],
            "client_account_id": retailplus_account["id"]
        }
    )
    
    print("\n🔐 Step 4: Client Admins Authenticate")
    await client.authenticate("admin@greentech.com", "greentech123")
    await client.authenticate("admin@medcorp.com", "medcorp123")
    await client.authenticate("admin@retailplus.com", "retail123")
    
    print("\n👥 Step 5: Client Admins Create Their Teams")
    
    # === GreenTech Industries Team ===
    print("\n🌱 GreenTech Industries Team Creation:")
    
    # GreenTech manager
    await client.create_user(
        "admin@greentech.com",
        {
            "email": "manager@greentech.com",
            "password": "green123",
            "first_name": "James",
            "last_name": "Solar",
            "is_main_client": False,
            "roles": ["manager"],
            "client_account_id": greentech_account["id"]
        }
    )
    
    # GreenTech engineers
    greentech_engineers = []
    for i, name in enumerate([("Lisa", "Wind"), ("Mark", "Hydro"), ("Anna", "Solar")], 1):
        engineer = await client.create_user(
            "admin@greentech.com",
            {
                "email": f"engineer{i}@greentech.com",
                "password": "green123",
                "first_name": name[0],
                "last_name": name[1],
                "is_main_client": False,
                "roles": ["employee"],
                "client_account_id": greentech_account["id"]
            }
        )
        greentech_engineers.append(engineer)
    
    # === MedCorp Healthcare Team ===
    print("\n🏥 MedCorp Healthcare Team Creation:")
    
    # MedCorp manager
    await client.create_user(
        "admin@medcorp.com",
        {
            "email": "manager@medcorp.com",
            "password": "med123",
            "first_name": "Dr. Jennifer",
            "last_name": "Health",
            "is_main_client": False,
            "roles": ["manager"],
            "client_account_id": medcorp_account["id"]
        }
    )
    
    # MedCorp staff
    medcorp_staff = []
    for i, name in enumerate([("Robert", "Nurse"), ("Kate", "Tech"), ("David", "Support")], 1):
        staff = await client.create_user(
            "admin@medcorp.com",
            {
                "email": f"staff{i}@medcorp.com",
                "password": "med123",
                "first_name": name[0],
                "last_name": name[1],
                "is_main_client": False,
                "roles": ["employee"],
                "client_account_id": medcorp_account["id"]
            }
        )
        medcorp_staff.append(staff)
    
    # === RetailPlus Team ===
    print("\n🛍️ RetailPlus Team Creation:")
    
    # RetailPlus manager
    await client.create_user(
        "admin@retailplus.com",
        {
            "email": "manager@retailplus.com",
            "password": "retail123",
            "first_name": "Tom",
            "last_name": "Sales",
            "is_main_client": False,
            "roles": ["manager"],
            "client_account_id": retailplus_account["id"]
        }
    )
    
    # RetailPlus employees
    retailplus_employees = []
    for i, name in enumerate([("Susan", "Cashier"), ("Mike", "Stock"), ("Amy", "Service")], 1):
        employee = await client.create_user(
            "admin@retailplus.com",
            {
                "email": f"employee{i}@retailplus.com",
                "password": "retail123",
                "first_name": name[0],
                "last_name": name[1],
                "is_main_client": False,
                "roles": ["employee"],
                "client_account_id": retailplus_account["id"]
            }
        )
        retailplus_employees.append(employee)
    
    print("\n🔍 Step 6: Get Users for Group Creation")
    
    # Get users for each client to create groups
    greentech_users = await client.get_users("admin@greentech.com")
    medcorp_users = await client.get_users("admin@medcorp.com")
    retailplus_users = await client.get_users("admin@retailplus.com")
    
    print("\n👥 Step 7: Client Admins Create Groups")
    
    # === GreenTech Groups ===
    print("\n🌱 GreenTech Industries Groups:")
    
    # Engineering team
    greentech_employee_ids = [u["id"] for u in greentech_users if "engineer" in u["email"]]
    await client.create_group(
        "admin@greentech.com",
        {
            "name": "Engineering Team",
            "description": "Renewable energy engineers",
            "client_account_id": greentech_account["id"],
            "members": greentech_employee_ids
        }
    )
    
    # Management team
    greentech_mgmt_ids = [u["id"] for u in greentech_users if u["email"] in ["admin@greentech.com", "manager@greentech.com"]]
    await client.create_group(
        "admin@greentech.com",
        {
            "name": "Management Team",
            "description": "GreenTech leadership",
            "client_account_id": greentech_account["id"],
            "members": greentech_mgmt_ids
        }
    )
    
    # === MedCorp Groups ===
    print("\n🏥 MedCorp Healthcare Groups:")
    
    # Medical staff
    medcorp_staff_ids = [u["id"] for u in medcorp_users if "staff" in u["email"]]
    await client.create_group(
        "admin@medcorp.com",
        {
            "name": "Medical Staff",
            "description": "Healthcare professionals",
            "client_account_id": medcorp_account["id"],
            "members": medcorp_staff_ids
        }
    )
    
    # Leadership team
    medcorp_mgmt_ids = [u["id"] for u in medcorp_users if u["email"] in ["admin@medcorp.com", "manager@medcorp.com"]]
    await client.create_group(
        "admin@medcorp.com",
        {
            "name": "Leadership Team",
            "description": "MedCorp management",
            "client_account_id": medcorp_account["id"],
            "members": medcorp_mgmt_ids
        }
    )
    
    # === RetailPlus Groups ===
    print("\n🛍️ RetailPlus Groups:")
    
    # Store team
    retailplus_employee_ids = [u["id"] for u in retailplus_users if "employee" in u["email"]]
    await client.create_group(
        "admin@retailplus.com",
        {
            "name": "Store Team",
            "description": "Front-line retail staff",
            "client_account_id": retailplus_account["id"],
            "members": retailplus_employee_ids
        }
    )
    
    # Operations team
    retailplus_ops_ids = [u["id"] for u in retailplus_users if u["email"] in ["admin@retailplus.com", "manager@retailplus.com"]]
    await client.create_group(
        "admin@retailplus.com",
        {
            "name": "Operations Team",
            "description": "Retail operations management",
            "client_account_id": retailplus_account["id"],
            "members": retailplus_ops_ids
        }
    )
    
    print("\n🎉 API-Based Seeding Complete!")
    print("=" * 50)
    print("Summary of created data:")
    print("📋 3 Client Accounts:")
    print("   • GreenTech Industries (renewable energy)")
    print("   • MedCorp Healthcare (healthcare tech)")
    print("   • RetailPlus (retail management)")
    print("\n👤 12 Users:")
    print("   • 3 Client Admins (main client users)")
    print("   • 3 Managers")
    print("   • 9 Employees")
    print("\n👥 6 Groups:")
    print("   • 2 per client account (operational + management)")
    print("\n🔑 All users have realistic passwords for testing:")
    print("   • Platform admin: admin@test.com / admin123")
    print("   • GreenTech admin: admin@greentech.com / greentech123")
    print("   • MedCorp admin: admin@medcorp.com / medcorp123")
    print("   • RetailPlus admin: admin@retailplus.com / retail123")
    print("   • All other users: password matches company (green123, med123, retail123)")
    print("\n🧪 Perfect for testing access control scenarios!")


if __name__ == "__main__":
    print("🚀 Starting API-based seeding...")
    print("This creates realistic test data by making HTTP requests to the API\n")
    
    try:
        asyncio.run(seed_via_api())
    except KeyboardInterrupt:
        print("\n⚠️  Seeding interrupted by user")
    except Exception as e:
        print(f"\n❌ Seeding failed: {e}")
        print("\n💡 Troubleshooting tips:")
        print("1. Make sure the API server is running: uvicorn api.main:app --reload")
        print("2. Make sure the database is seeded with basic data: python scripts/seed_main.py")
        print("3. Check if the database is accessible") 