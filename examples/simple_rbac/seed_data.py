"""
SimpleRBAC Blog Seed Data

Creates demo users, roles, and blog posts using Phase 1.5 implementation:
- UserService.create_user() for users
- RoleService.assign_role_to_user() for role assignments
- UserRoleMembership with full audit trail
- MembershipStatus enum support

Run this to quickly populate a fresh database for testing.
"""

import asyncio
import os
from datetime import datetime, timedelta, timezone

from beanie import init_beanie
from models import BlogPost, Comment
from motor.motor_asyncio import AsyncIOMotorClient

from outlabs_auth import SimpleRBAC
from outlabs_auth.models.permission import PermissionModel
from outlabs_auth.models.role import RoleModel
from outlabs_auth.models.token import RefreshTokenModel
from outlabs_auth.models.user import UserModel, UserStatus
from outlabs_auth.models.user_role_membership import UserRoleMembership

# Configuration
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "blog_simple_rbac")
SECRET_KEY = os.getenv("SECRET_KEY", "development-secret-key-change-in-production")


async def seed_all():
    """Main seed function - creates users, roles, and sample data"""
    print("=" * 80)
    print("🌱 SEEDING SIMPLE RBAC BLOG EXAMPLE")
    print("=" * 80)

    # 1. Connect to MongoDB
    print("\n📦 Connecting to MongoDB...")
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[DATABASE_NAME]

    # 2. Initialize SimpleRBAC
    print("🔐 Initializing OutlabsAuth SimpleRBAC...")
    auth = SimpleRBAC(
        database=db,
        secret_key=SECRET_KEY,
        enable_caching=False,  # Disable caching for seeding
    )

    # 3. Initialize Beanie with all document models
    await init_beanie(
        database=db,
        document_models=[
            UserModel,
            RoleModel,
            PermissionModel,
            UserRoleMembership,
            RefreshTokenModel,
            BlogPost,
            Comment,
        ],
    )

    await auth.initialize()
    print("✅ Database initialized\n")

    # 4. Get roles (created automatically in main.py startup)
    print("👥 Fetching roles...")
    roles = {}
    for role_name in ["reader", "writer", "editor", "admin"]:
        role = await auth.role_service.get_role_by_name(role_name)
        if role:
            roles[role_name] = role
            print(f"  ✓ Found role: {role_name} ({len(role.permissions)} permissions)")
        else:
            print(
                f"  ⚠️  Role '{role_name}' not found - make sure to run main.py first!"
            )

    if len(roles) == 0:
        print("\n❌ No roles found! Run the API first to create default roles:")
        print("   docker compose up")
        client.close()
        return

    # 5. Create users using Phase 1.5 service
    print("\n👤 Creating users...")
    users = {}

    # Admin user (system account)
    admin_user = await auth.user_service.create_user(
        email="system@outlabs.io",
        password="Asd123$$$",
        first_name="System",
        last_name="Admin",
    )
    users["admin"] = admin_user
    print(f"  ✓ Created user: system@outlabs.io (System Admin)")

    # Writer
    writer_user = await auth.user_service.create_user(
        email="writer@example.com",
        password="Asd123$$$",
        first_name="Sarah",
        last_name="Writer",
    )
    users["writer"] = writer_user
    print(f"  ✓ Created user: writer@example.com (Sarah Writer)")

    # Editor
    editor_user = await auth.user_service.create_user(
        email="editor@example.com",
        password="Asd123$$$",
        first_name="John",
        last_name="Editor",
    )
    users["editor"] = editor_user
    print(f"  ✓ Created user: editor@example.com (John Editor)")

    # Reader (no role assigned - just registered user)
    reader_user = await auth.user_service.create_user(
        email="reader@example.com",
        password="Asd123$$$",
        first_name="Jane",
        last_name="Reader",
    )
    users["reader"] = reader_user
    print(f"  ✓ Created user: reader@example.com (Jane Reader - no role)")

    # Temporary contractor
    contractor_user = await auth.user_service.create_user(
        email="contractor@example.com",
        password="Asd123$$$",
        first_name="Temp",
        last_name="Contractor",
    )
    users["contractor"] = contractor_user
    print(f"  ✓ Created user: contractor@example.com (Temp Contractor)")

    # 6. Assign roles using Phase 1.5 service
    print("\n🎭 Assigning roles...")

    if "admin" in roles:
        # Admin gets admin role (self-assigned for demo)
        admin_membership = await auth.role_service.assign_role_to_user(
            user_id=str(admin_user.id),
            role_id=str(roles["admin"].id),
            assigned_by=str(admin_user.id),
        )
        print(f"  ✓ Assigned admin role to system@outlabs.io")
        print(f"    - Status: {admin_membership.status.value}")
        print(f"    - Assigned at: {admin_membership.assigned_at}")
        print(
            f"    - Can grant permissions: {admin_membership.can_grant_permissions()}"
        )

    if "writer" in roles:
        # Writer gets writer role
        writer_membership = await auth.role_service.assign_role_to_user(
            user_id=str(writer_user.id),
            role_id=str(roles["writer"].id),
            assigned_by=str(admin_user.id),
        )
        print(f"  ✓ Assigned writer role to writer@example.com (by admin)")

    if "editor" in roles:
        # Editor gets editor role
        editor_membership = await auth.role_service.assign_role_to_user(
            user_id=str(editor_user.id),
            role_id=str(roles["editor"].id),
            assigned_by=str(admin_user.id),
        )
        print(f"  ✓ Assigned editor role to editor@example.com (by admin)")

    if "writer" in roles:
        # Contractor gets temporary writer role (90 days)
        temp_membership = await auth.role_service.assign_role_to_user(
            user_id=str(contractor_user.id),
            role_id=str(roles["writer"].id),
            assigned_by=str(admin_user.id),
            valid_until=datetime.now(timezone.utc) + timedelta(days=90),
        )
        print(f"  ✓ Assigned temporary writer role to contractor@example.com")
        print(f"    - Valid until: {temp_membership.valid_until}")

    # 7. Create sample blog posts
    print("\n📝 Creating sample blog posts...")

    # Admin's welcome post
    welcome_post = BlogPost(
        title="Welcome to Our Blog!",
        content="""Welcome to our blog powered by OutlabsAuth SimpleRBAC!

This is a demo blog that showcases role-based access control:
- **Readers** can view published posts
- **Writers** can create posts and comments
- **Editors** can edit/delete their own content
- **Admins** can manage everything

Try logging in with different user accounts to see how permissions work!""",
        author_id=str(admin_user.id),
        status="published",
        tags=["welcome", "announcement"],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    await welcome_post.insert()
    print(f"  ✓ Created post: 'Welcome to Our Blog!' (by admin)")

    # Writer's first post
    first_post = BlogPost(
        title="My First Blog Post",
        content="""Hi everyone! I'm Sarah, a writer on this blog.

I'm excited to share my thoughts and ideas here. This post demonstrates how writers can create content in the system.

Writers have the `post:create` permission, which allows them to create new posts like this one.""",
        author_id=str(writer_user.id),
        status="published",
        tags=["introduction", "first-post"],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    await first_post.insert()
    print(f"  ✓ Created post: 'My First Blog Post' (by writer)")

    # Editor's draft
    draft_post = BlogPost(
        title="Understanding RBAC in Modern Applications",
        content="""Role-Based Access Control (RBAC) is a crucial security pattern...

(This is a draft post that's not yet published)""",
        author_id=str(editor_user.id),
        status="draft",
        tags=["rbac", "security", "tutorial"],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    await draft_post.insert()
    print(f"  ✓ Created post: 'Understanding RBAC...' (by editor, draft)")

    # 8. Create sample comments
    print("\n💬 Creating sample comments...")

    comment1 = Comment(
        post_id=str(welcome_post.id),
        author_id=str(writer_user.id),
        content="Great to be part of this blog! Looking forward to sharing content.",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    await comment1.insert()
    print(f"  ✓ Created comment on 'Welcome...' post (by writer)")

    comment2 = Comment(
        post_id=str(first_post.id),
        author_id=str(editor_user.id),
        content="Nice first post, Sarah! Welcome to the team.",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    await comment2.insert()
    print(f"  ✓ Created comment on 'My First...' post (by editor)")

    # 9. Summary
    print("\n" + "=" * 80)
    print("✅ SEEDING COMPLETE!")
    print("=" * 80)

    total_users = await UserModel.find().count()
    total_roles = await RoleModel.find().count()
    total_memberships = await UserRoleMembership.find().count()
    total_posts = await BlogPost.find().count()
    total_comments = await Comment.find().count()

    print(f"\n📊 Summary:")
    print(f"  • {total_roles} roles")
    print(f"  • {total_users} users")
    print(f"  • {total_memberships} role memberships (with audit trail)")
    print(f"  • {total_posts} blog posts")
    print(f"  • {total_comments} comments")

    print(f"\n🔐 Demo Credentials:")
    print(f"  system@outlabs.io        / Asd123$$$  (Admin - full access)")
    print(f"  writer@example.com       / Asd123$$$  (Writer - create posts)")
    print(f"  editor@example.com       / Asd123$$$  (Editor - edit own posts)")
    print(f"  reader@example.com       / Asd123$$$  (No role - view only)")
    print(f"  contractor@example.com   / Asd123$$$  (Temp writer, 90 days)")

    print(f"\n🚀 API Endpoints:")
    print(f"  http://localhost:8003         - API root")
    print(f"  http://localhost:8003/docs    - OpenAPI docs")
    print(f"  http://localhost:8003/health  - Health check")

    print(f"\n🎯 Try It:")
    print(f"  1. Login: POST /auth/login")
    print(f"  2. Get roles: GET /roles")
    print(f"  3. List posts: GET /posts")
    print(f"  4. Create post: POST /posts (writer+ only)")
    print(f"  5. View memberships: GET /memberships/me")

    print("\n" + "=" * 80)

    # Close connection
    client.close()


# ============================================================================
# Run Script
# ============================================================================

if __name__ == "__main__":
    print("This script will populate the blog database with demo data.")
    print("Make sure the API is running first: docker compose up\n")

    try:
        asyncio.run(seed_all())
    except KeyboardInterrupt:
        print("\n\n❌ Seeding cancelled by user")
    except Exception as e:
        print(f"\n\n❌ Error during seeding: {e}")
        import traceback

        traceback.print_exc()
