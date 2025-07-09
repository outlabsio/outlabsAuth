#!/usr/bin/env python3
"""
Database seeding script for outlabsAuth

This script creates essential test data including:
- System users with different permission levels
- Platform and entity hierarchy
- Roles with various permission sets
- Entity memberships and role assignments

Usage:
    uv run python scripts/seed_database.py
"""
import asyncio
import sys
import os
from datetime import datetime, timezone
from typing import List, Dict, Any

# Add the project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from api.database import init_db
from api.models import UserModel, EntityModel, RoleModel, EntityMembershipModel
from api.models.user_model import UserProfile
from api.services.auth_service import AuthService
from api.services.entity_service import EntityService
from api.services.role_service import RoleService
from api.services.entity_membership_service import EntityMembershipService


class DatabaseSeeder:
    """Database seeding utility"""
    
    def __init__(self):
        self.created_users = {}
        self.created_entities = {}
        self.created_roles = {}
        
    async def seed_all(self, clear_existing: bool = False):
        """Seed the database with all test data"""
        print("🌱 Starting database seeding...")
        
        if clear_existing:
            await self.clear_database()
        
        # Create users first
        await self.create_test_users()
        
        # Create entity hierarchy
        await self.create_entity_hierarchy()
        
        # Create roles
        await self.create_system_roles()
        
        # Create memberships
        await self.create_entity_memberships()
        
        print("✅ Database seeding completed!")
        self.print_summary()
        
    async def clear_database(self):
        """Clear existing test data"""
        print("🧹 Clearing existing test data...")
        
        # Delete in reverse dependency order
        await EntityMembershipModel.delete_all()
        await RoleModel.delete_all()
        await EntityModel.delete_all()
        await UserModel.delete_all()
        
        print("✅ Database cleared")
        
    async def create_test_users(self):
        """Create test users with different roles"""
        print("👥 Creating test users...")
        
        users_to_create = [
            {
                "email": "system@outlabs.com",
                "password": "outlabs123",
                "first_name": "System",
                "last_name": "Admin",
                "role": "system_admin"
            },
            {
                "email": "platform@outlabs.com", 
                "password": "platform123",
                "first_name": "Platform",
                "last_name": "Manager",
                "role": "platform_admin"
            },
            {
                "email": "org@outlabs.com",
                "password": "org123",
                "first_name": "Organization",
                "last_name": "Admin",
                "role": "org_admin"
            },
            {
                "email": "team@outlabs.com",
                "password": "team123",
                "first_name": "Team",
                "last_name": "Lead",
                "role": "team_lead"
            },
            {
                "email": "user@outlabs.com",
                "password": "user123",
                "first_name": "Regular",
                "last_name": "User",
                "role": "user"
            },
            {
                "email": "viewer@outlabs.com",
                "password": "viewer123",
                "first_name": "Read",
                "last_name": "Only",
                "role": "viewer"
            }
        ]
        
        for user_data in users_to_create:
            # Check if user already exists
            existing_user = await UserModel.find_one(UserModel.email == user_data["email"])
            if existing_user:
                print(f"  ℹ️  User {user_data['email']} already exists")
                self.created_users[user_data["role"]] = existing_user
                continue
                
            # Hash password
            hashed_password = AuthService.hash_password(user_data["password"])
            
            # Create user
            user = UserModel(
                email=user_data["email"],
                hashed_password=hashed_password,
                profile=UserProfile(
                    first_name=user_data["first_name"],
                    last_name=user_data["last_name"]
                ),
                status="active",
                email_verified=True,
                created_at=datetime.now(timezone.utc)
            )
            
            await user.save()
            self.created_users[user_data["role"]] = user
            print(f"  ✅ Created user: {user_data['email']}")
            
    async def create_entity_hierarchy(self):
        """Create a complete entity hierarchy for testing"""
        print("🏢 Creating entity hierarchy...")
        
        # Create platform
        platform = EntityModel(
            name="outlabs-platform",
            display_name="OutLabs Platform",
            description="Main OutLabs platform",
            entity_class="STRUCTURAL",
            entity_type="platform",
            status="active",
            direct_permissions=[],
            config={},
            created_at=datetime.now(timezone.utc)
        )
        await platform.save()
        self.created_entities["platform"] = platform
        print(f"  ✅ Created platform: {platform.display_name}")
        
        # Create organization
        organization = EntityModel(
            name="acme-corp",
            display_name="ACME Corporation",
            description="ACME Corporation - Demo Organization",
            entity_class="STRUCTURAL", 
            entity_type="organization",
            parent_entity=platform,
            platform_id=platform.id,
            status="active",
            direct_permissions=[],
            config={"max_members": 1000},
            created_at=datetime.now(timezone.utc)
        )
        await organization.save()
        self.created_entities["organization"] = organization
        print(f"  ✅ Created organization: {organization.display_name}")
        
        # Create branch
        branch = EntityModel(
            name="acme-engineering",
            display_name="ACME Engineering Branch",
            description="Engineering division of ACME Corp",
            entity_class="STRUCTURAL",
            entity_type="branch", 
            parent_entity=organization,
            platform_id=platform.id,
            status="active",
            direct_permissions=[],
            config={"department": "engineering"},
            created_at=datetime.now(timezone.utc)
        )
        await branch.save()
        self.created_entities["branch"] = branch
        print(f"  ✅ Created branch: {branch.display_name}")
        
        # Create teams
        teams = [
            {
                "name": "backend-team",
                "display_name": "Backend Development Team",
                "description": "Backend API development team"
            },
            {
                "name": "frontend-team", 
                "display_name": "Frontend Development Team",
                "description": "Frontend UI development team"
            }
        ]
        
        self.created_entities["teams"] = []
        for team_data in teams:
            team = EntityModel(
                name=team_data["name"],
                display_name=team_data["display_name"],
                description=team_data["description"],
                entity_class="STRUCTURAL",
                entity_type="team",
                parent_entity=branch,
                platform_id=platform.id,
                status="active",
                direct_permissions=[],
                config={"team_type": "development"},
                created_at=datetime.now(timezone.utc)
            )
            await team.save()
            self.created_entities["teams"].append(team)
            print(f"  ✅ Created team: {team.display_name}")
            
        # Create access group
        access_group = EntityModel(
            name="senior-devs",
            display_name="Senior Developers",
            description="Access group for senior developers with elevated permissions",
            entity_class="ACCESS_GROUP",
            entity_type="access_group",
            parent_entity=branch,
            platform_id=platform.id,
            status="active",
            direct_permissions=["code:review", "deploy:staging"],
            config={"access_level": "senior"},
            created_at=datetime.now(timezone.utc)
        )
        await access_group.save()
        self.created_entities["access_group"] = access_group
        print(f"  ✅ Created access group: {access_group.display_name}")
        
    async def create_system_roles(self):
        """Create system and entity-specific roles"""
        print("🎭 Creating roles...")
        
        # Global system roles
        system_roles = [
            {
                "name": "system_admin",
                "display_name": "System Administrator", 
                "description": "Full system access",
                "permissions": ["*"],
                "is_global": True,
                "assignable_at_types": ["platform"]
            },
            {
                "name": "platform_admin",
                "display_name": "Platform Administrator",
                "description": "Platform-wide administration",
                "permissions": [
                    "user:manage_all", "entity:manage_all", "role:manage_all",
                    "platform:manage", "organization:manage_all"
                ],
                "is_global": True,
                "assignable_at_types": ["platform", "organization"]
            }
        ]
        
        for role_data in system_roles:
            role = await RoleService.create_role(
                name=role_data["name"],
                display_name=role_data["display_name"],
                description=role_data["description"],
                permissions=role_data["permissions"],
                assignable_at_types=role_data["assignable_at_types"],
                is_global=role_data["is_global"],
                created_by=self.created_users["system_admin"]
            )
            self.created_roles[role_data["name"]] = role
            print(f"  ✅ Created global role: {role.display_name}")
        
        # Create default roles for entities
        for entity_name, entity in self.created_entities.items():
            if entity_name in ["teams", "access_group"]:
                continue  # Skip lists and access groups for now
                
            if entity_name == "platform":
                # Platform-specific roles
                roles = await RoleService.create_default_roles(str(entity.id))
                for role in roles:
                    self.created_roles[f"{entity_name}_{role.name}"] = role
                    print(f"  ✅ Created {entity_name} role: {role.display_name}")
                    
    async def create_entity_memberships(self):
        """Create entity memberships and role assignments"""
        print("🔗 Creating entity memberships...")
        
        # System admin to platform
        system_admin = self.created_users["system_admin"]
        platform = self.created_entities["platform"]
        
        # Get the system admin role for platform
        system_role = self.created_roles.get("system_admin")
        if system_role:
            membership = EntityMembershipModel(
                user=system_admin,
                entity=platform,
                role=system_role,
                status="active",
                created_at=datetime.now(timezone.utc)
            )
            await membership.save()
            print(f"  ✅ Added {system_admin.email} as system admin to platform")
        
        # Platform admin to organization
        platform_admin = self.created_users["platform_admin"]
        organization = self.created_entities["organization"]
        
        platform_role = self.created_roles.get("platform_admin") 
        if platform_role:
            membership = EntityMembershipModel(
                user=platform_admin,
                entity=organization,
                role=platform_role,
                status="active",
                created_at=datetime.now(timezone.utc)
            )
            await membership.save()
            print(f"  ✅ Added {platform_admin.email} as platform admin to organization")
        
        # Org admin to organization
        org_admin = self.created_users["org_admin"]
        org_admin_role = self.created_roles.get("organization_admin")
        if org_admin_role:
            membership = EntityMembershipModel(
                user=org_admin,
                entity=organization,
                role=org_admin_role,
                status="active", 
                created_at=datetime.now(timezone.utc)
            )
            await membership.save()
            print(f"  ✅ Added {org_admin.email} as admin to organization")
        
        # Team leads to teams
        team_lead = self.created_users["team_lead"]
        teams = self.created_entities.get("teams", [])
        
        for team in teams:
            # Create admin role for team if needed
            team_roles = await RoleService.create_default_roles(str(team.id))
            admin_role = next((r for r in team_roles if "admin" in r.name), None)
            
            if admin_role:
                membership = EntityMembershipModel(
                    user=team_lead,
                    entity=team,
                    role=admin_role,
                    status="active",
                    created_at=datetime.now(timezone.utc)
                )
                await membership.save()
                print(f"  ✅ Added {team_lead.email} as admin to {team.display_name}")
        
        # Regular users to teams
        regular_user = self.created_users["user"]
        viewer_user = self.created_users["viewer"]
        
        for i, team in enumerate(teams):
            # Get or create member roles
            team_roles = await RoleModel.find(RoleModel.entity_id == team.id).to_list()
            member_role = next((r for r in team_roles if "member" in r.name), None)
            viewer_role = next((r for r in team_roles if "viewer" in r.name), None)
            
            # Add regular user as member to first team
            if i == 0 and member_role:
                membership = EntityMembershipModel(
                    user=regular_user,
                    entity=team,
                    role=member_role,
                    status="active",
                    created_at=datetime.now(timezone.utc)
                )
                await membership.save()
                print(f"  ✅ Added {regular_user.email} as member to {team.display_name}")
            
            # Add viewer to second team
            if i == 1 and viewer_role:
                membership = EntityMembershipModel(
                    user=viewer_user,
                    entity=team,
                    role=viewer_role,
                    status="active",
                    created_at=datetime.now(timezone.utc)
                )
                await membership.save()
                print(f"  ✅ Added {viewer_user.email} as viewer to {team.display_name}")
                
    def print_summary(self):
        """Print summary of created data"""
        print("\n📊 Seeding Summary:")
        print(f"  👥 Users created: {len(self.created_users)}")
        print(f"  🏢 Entities created: {len([k for k, v in self.created_entities.items() if not isinstance(v, list)]) + len(self.created_entities.get('teams', []))}")
        print(f"  🎭 Roles created: {len(self.created_roles)}")
        
        print("\n🔑 Test Credentials:")
        credentials = [
            ("system@outlabs.com", "outlabs123", "System Admin - Full access"),
            ("platform@outlabs.com", "platform123", "Platform Admin - Cross-org access"),
            ("org@outlabs.com", "org123", "Organization Admin - Org-level access"),
            ("team@outlabs.com", "team123", "Team Lead - Team management"),
            ("user@outlabs.com", "user123", "Regular User - Team member"),
            ("viewer@outlabs.com", "viewer123", "Viewer - Read-only access")
        ]
        
        for email, password, description in credentials:
            print(f"  📧 {email:<25} 🔐 {password:<15} - {description}")
            
        print("\n🔗 Test Login Command:")
        print("  curl -X POST http://localhost:8030/v1/auth/login/json \\")
        print("    -H 'Content-Type: application/json' \\") 
        print("    -d '{\"email\": \"system@outlabs.com\", \"password\": \"outlabs123\"}'")


async def main():
    """Main seeding function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Seed the outlabsAuth database")
    parser.add_argument("--clear", action="store_true", help="Clear existing data before seeding")
    args = parser.parse_args()
    
    try:
        # Initialize database connection
        await init_db()
        print("📡 Connected to database")
        
        # Run seeding
        seeder = DatabaseSeeder()
        await seeder.seed_all(clear_existing=args.clear)
        
    except Exception as e:
        print(f"❌ Seeding failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())