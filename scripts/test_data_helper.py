"""
Test Data Helper

This module provides easy access to test user credentials and data for testing.
Use this after running seed.py to create test data in the test database.
"""

from typing import Dict, List, Any
import httpx
import asyncio


class TestDataHelper:
    """Helper class to manage test data and user credentials for testing."""
    
    # Platform admin credentials
    PLATFORM_ADMIN = {
        "email": "admin@test.com",
        "password": "a_very_secure_password",
        "role": "platform_admin",
        "description": "Platform administrator with full system access"
    }
    
    # Client administrators 
    CLIENT_ADMINS = {
        "acme": {
            "email": "admin@acme.com",
            "password": "secure_password_123",
            "role": "client_admin",
            "company": "ACME Corporation",
            "description": "ACME client administrator"
        },
        "techstartup": {
            "email": "admin@techstartup.com",
            "password": "secure_password_123",
            "role": "client_admin",
            "company": "Tech Startup Inc",
            "description": "Tech Startup client administrator"
        }
    }
    
    # Managers (non-main clients)
    MANAGERS = {
        "acme": {
            "email": "manager@acme.com",
            "password": "secure_password_123",
            "role": "manager",
            "company": "ACME Corporation",
            "description": "ACME manager"
        }
    }
    
    # Regular employees
    EMPLOYEES = {
        "acme": [
            {
                "email": "employee1@acme.com",
                "password": "secure_password_123",
                "role": "employee",
                "company": "ACME Corporation",
                "description": "ACME employee - Employee1 Acme"
            },
            {
                "email": "employee2@acme.com",
                "password": "secure_password_123",
                "role": "employee",
                "company": "ACME Corporation",
                "description": "ACME employee - Employee2 Acme"
            },
            {
                "email": "employee3@acme.com",
                "password": "secure_password_123",
                "role": "employee",
                "company": "ACME Corporation",
                "description": "ACME employee - Employee3 Acme"
            }
        ],
        "techstartup": [
            {
                "email": "dev1@techstartup.com",
                "password": "secure_password_123",
                "role": "employee",
                "company": "Tech Startup Inc",
                "description": "Tech Startup developer - Developer1 Tech"
            },
            {
                "email": "dev2@techstartup.com",
                "password": "secure_password_123",
                "role": "employee",
                "company": "Tech Startup Inc",
                "description": "Tech Startup developer - Developer2 Tech"
            }
        ]
    }
    
    @classmethod
    def get_platform_admin(cls) -> Dict[str, str]:
        """Get platform admin credentials."""
        return cls.PLATFORM_ADMIN
    
    @classmethod
    def get_client_admin(cls, company: str) -> Dict[str, str]:
        """Get client admin for specified company."""
        if company not in cls.CLIENT_ADMINS:
            raise ValueError(f"Unknown company: {company}. Available: {list(cls.CLIENT_ADMINS.keys())}")
        return cls.CLIENT_ADMINS[company]
    
    @classmethod
    def get_manager(cls, company: str) -> Dict[str, str]:
        """Get manager for specified company."""
        if company not in cls.MANAGERS:
            raise ValueError(f"Unknown company: {company}. Available: {list(cls.MANAGERS.keys())}")
        return cls.MANAGERS[company]
    
    @classmethod
    def get_employee(cls, company: str, index: int = 0) -> Dict[str, str]:
        """Get employee for specified company and index."""
        if company not in cls.EMPLOYEES:
            raise ValueError(f"Unknown company: {company}. Available: {list(cls.EMPLOYEES.keys())}")
        if index >= len(cls.EMPLOYEES[company]):
            raise ValueError(f"Employee index {index} out of range for {company}. Max: {len(cls.EMPLOYEES[company]) - 1}")
        return cls.EMPLOYEES[company][index]
    
    @classmethod
    def get_all_employees(cls, company: str) -> List[Dict[str, str]]:
        """Get all employees for specified company."""
        if company not in cls.EMPLOYEES:
            raise ValueError(f"Unknown company: {company}. Available: {list(cls.EMPLOYEES.keys())}")
        return cls.EMPLOYEES[company]
    
    @classmethod
    def get_different_company_user(cls, exclude_company: str) -> Dict[str, str]:
        """Get a user from a different company than specified."""
        available_companies = [c for c in cls.CLIENT_ADMINS.keys() if c != exclude_company]
        if not available_companies:
            raise ValueError(f"No other companies available besides {exclude_company}")
        
        other_company = available_companies[0]
        return cls.get_client_admin(other_company)
    
    @classmethod
    def get_companies(cls) -> List[str]:
        """Get list of all available companies."""
        return list(cls.CLIENT_ADMINS.keys())
    
    @classmethod
    async def authenticate_user(cls, credentials: Dict[str, str], base_url: str = "http://localhost:8000") -> str:
        """Authenticate a user and return access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/v1/auth/login",
                data={"username": credentials["email"], "password": credentials["password"]}
            )
            if response.status_code == 200:
                data = response.json()
                return data["access_token"]
            else:
                raise Exception(f"Authentication failed for {credentials['email']}: {response.text}")
    
    @classmethod
    def print_available_users(cls):
        """Print all available test users for reference."""
        print("🔑 Available Test Users:")
        print("=" * 50)
        
        print("\n🌟 Platform Admin:")
        admin = cls.PLATFORM_ADMIN
        print(f"   Email: {admin['email']}")
        print(f"   Password: {admin['password']}")
        print(f"   Role: {admin['role']}")
        print(f"   Description: {admin['description']}")
        
        print("\n🏢 Client Administrators:")
        for company, admin in cls.CLIENT_ADMINS.items():
            print(f"   {admin['company']}:")
            print(f"     Email: {admin['email']}")
            print(f"     Password: {admin['password']}")
            print(f"     Role: {admin['role']}")
        
        print("\n👨‍💼 Managers:")
        for company, manager in cls.MANAGERS.items():
            print(f"   {manager['company']}:")
            print(f"     Email: {manager['email']}")
            print(f"     Password: {manager['password']}")
            print(f"     Role: {manager['role']}")
        
        print("\n👥 Employees:")
        for company, employees in cls.EMPLOYEES.items():
            print(f"   {employees[0]['company']}:")
            for emp in employees:
                print(f"     {emp['email']} - {emp['description']}")
        
        print("\n💡 Usage Examples:")
        print("   # Get platform admin")
        print("   admin = TestDataHelper.get_platform_admin()")
        print("   ")
        print("   # Get client admin for ACME")
        print("   acme_admin = TestDataHelper.get_client_admin('acme')")
        print("   ")
        print("   # Get first employee from Tech Startup")
        print("   employee = TestDataHelper.get_employee('techstartup', 0)")
        print("   ")
        print("   # Authenticate and get token")
        print("   token = await TestDataHelper.authenticate_user(admin)")


# Convenience functions for common test scenarios
def get_cross_company_scenario():
    """
    Get users from different companies for testing cross-company access control.
    Returns tuple of (company1_admin, company2_employee).
    """
    acme_admin = TestDataHelper.get_client_admin("acme")
    techstartup_employee = TestDataHelper.get_employee("techstartup", 0)
    return acme_admin, techstartup_employee


def get_hierarchy_scenario(company: str):
    """
    Get users representing organizational hierarchy for testing role-based access.
    Returns tuple of (admin, manager, employee).
    """
    admin = TestDataHelper.get_client_admin(company)
    if company in TestDataHelper.MANAGERS:
        manager = TestDataHelper.get_manager(company)
    else:
        # For companies without managers, use the admin as manager
        manager = admin
    employee = TestDataHelper.get_employee(company, 0)
    return admin, manager, employee


def get_platform_vs_client_scenario():
    """
    Get platform admin vs client admin for testing platform-level access control.
    Returns tuple of (platform_admin, client_admin).
    """
    platform_admin = TestDataHelper.get_platform_admin()
    client_admin = TestDataHelper.get_client_admin("acme")
    return platform_admin, client_admin


if __name__ == "__main__":
    print("🧪 Test Data Helper")
    print("This module provides easy access to test user credentials.\n")
    
    TestDataHelper.print_available_users()
    
    print("\n🎯 Common Test Scenarios:")
    print("   1. Cross-company access control:")
    print("      admin, employee = get_cross_company_scenario()")
    print("   ")
    print("   2. Role hierarchy testing:")
    print("      admin, manager, employee = get_hierarchy_scenario('acme')")
    print("   ")
    print("   3. Platform vs client access:")
    print("      platform_admin, client_admin = get_platform_vs_client_scenario()") 