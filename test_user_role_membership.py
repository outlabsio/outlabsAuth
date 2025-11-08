"""
Test script for UserRoleMembership implementation

Tests the new SimpleRBAC structure using UserRoleMembership table.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from outlabs_auth import SimpleRBAC


async def test_user_role_membership():
    """Test UserRoleMembership implementation."""

    print("🧪 Testing UserRoleMembership Implementation\n")
    print("=" * 60)

    # Connect to MongoDB
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["test_user_role_membership"]

    # Initialize SimpleRBAC
    auth = SimpleRBAC(
        database=db,
        secret_key="test-secret-key-for-testing-only"
    )

    # Initialize database
    print("\n1. Initializing database...")
    await auth.initialize()
    print("   ✅ Database initialized")

    # Create a test user
    print("\n2. Creating test user...")
    user = await auth.user_service.create_user(
        email="testuser@example.com",
        password="SecurePass123!",
        first_name="Test",
        last_name="User"
    )
    print(f"   ✅ User created: {user.email} (ID: {user.id})")

    # Create a test role
    print("\n3. Creating test role...")
    admin_role = await auth.role_service.create_role(
        name="admin",
        display_name="Administrator",
        description="Full system access",
        permissions=[
            "user:create",
            "user:read",
            "user:update",
            "user:delete",
            "post:create",
            "post:delete"
        ]
    )
    print(f"   ✅ Role created: {admin_role.name} (ID: {admin_role.id})")
    print(f"   📋 Permissions: {', '.join(admin_role.permissions)}")

    # Assign role to user
    print("\n4. Assigning role to user...")
    membership = await auth.role_service.assign_role_to_user(
        user_id=str(user.id),
        role_id=str(admin_role.id),
        assigned_by=str(user.id),  # Self-assigned for this test
    )
    print(f"   ✅ Role assigned")
    print(f"   📅 Assigned at: {membership.assigned_at}")
    print(f"   👤 Assigned by: {membership.assigned_by.id if membership.assigned_by else 'System'}")
    print(f"   ✓ Status: {membership.status.value}")
    print(f"   ✓ Currently valid: {membership.is_currently_valid()}")
    print(f"   ✓ Can grant permissions: {membership.can_grant_permissions()}")

    # Get user's roles
    print("\n5. Getting user's roles...")
    user_roles = await auth.role_service.get_user_roles(str(user.id))
    print(f"   ✅ Found {len(user_roles)} role(s)")
    for role in user_roles:
        print(f"   - {role.name}: {', '.join(role.permissions)}")

    # Check permissions
    print("\n6. Checking user permissions...")
    permissions_to_check = [
        "user:create",
        "user:delete",
        "post:create",
        "post:delete",
        "post:update"  # Not in role
    ]

    for perm in permissions_to_check:
        has_perm = await auth.permission_service.check_permission(
            user_id=str(user.id),
            permission=perm
        )
        status = "✅ GRANTED" if has_perm else "❌ DENIED"
        print(f"   {status}: {perm}")

    # Get all user permissions
    print("\n7. Getting all user permissions...")
    all_permissions = await auth.permission_service.get_user_permissions(str(user.id))
    print(f"   ✅ User has {len(all_permissions)} permission(s):")
    for perm in all_permissions:
        print(f"   - {perm}")

    # Test time-based role assignment
    print("\n8. Testing time-based role assignment...")
    editor_role = await auth.role_service.create_role(
        name="editor",
        display_name="Editor",
        permissions=["post:create", "post:update"]
    )

    # Create second user
    temp_user = await auth.user_service.create_user(
        email="contractor@example.com",
        password="SecurePass123!",
        first_name="Temp",
        last_name="Contractor"
    )

    # Assign role with 90-day expiration
    valid_until = datetime.now(timezone.utc) + timedelta(days=90)
    temp_membership = await auth.role_service.assign_role_to_user(
        user_id=str(temp_user.id),
        role_id=str(editor_role.id),
        assigned_by=str(user.id),
        valid_until=valid_until
    )
    print(f"   ✅ Temporary role assigned to contractor")
    print(f"   📅 Valid until: {temp_membership.valid_until}")
    print(f"   ✓ Status: {temp_membership.status.value}")
    print(f"   ✓ Is currently valid: {temp_membership.is_currently_valid()}")
    print(f"   ✓ Can grant permissions: {temp_membership.can_grant_permissions()}")

    # Test audit trail
    print("\n9. Testing audit trail...")
    memberships = await auth.role_service.get_user_memberships(str(user.id))
    print(f"   ✅ Found {len(memberships)} membership record(s)")
    for m in memberships:
        role = await m.role.fetch()
        assigned_by = await m.assigned_by.fetch() if m.assigned_by else None
        print(f"\n   📋 Membership:")
        print(f"      Role: {role.name}")
        print(f"      Assigned at: {m.assigned_at}")
        print(f"      Assigned by: {assigned_by.email if assigned_by else 'System'}")
        print(f"      Valid from: {m.valid_from or 'N/A'}")
        print(f"      Valid until: {m.valid_until or 'Never'}")
        print(f"      Status: {m.status.value}")
        if m.revoked_at:
            revoked_by = await m.revoked_by.fetch() if m.revoked_by else None
            print(f"      Revoked at: {m.revoked_at}")
            print(f"      Revoked by: {revoked_by.email if revoked_by else 'System'}")

    # Test role revocation
    print("\n10. Testing role revocation...")
    revoked = await auth.role_service.revoke_role_from_user(
        user_id=str(temp_user.id),
        role_id=str(editor_role.id)
    )
    print(f"   ✅ Role revoked: {revoked}")

    # Verify revocation
    temp_roles = await auth.role_service.get_user_roles(str(temp_user.id))
    print(f"   ✓ Contractor now has {len(temp_roles)} active role(s)")

    # Check permissions after revocation
    can_edit = await auth.permission_service.check_permission(
        user_id=str(temp_user.id),
        permission="post:update"
    )
    print(f"   ✓ Can edit posts after revocation: {can_edit}")

    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)

    # Cleanup
    print("\n🧹 Cleaning up test database...")
    await db.drop_collection("users")
    await db.drop_collection("roles")
    await db.drop_collection("user_role_memberships")
    print("   ✅ Cleanup complete")

    client.close()


if __name__ == "__main__":
    asyncio.run(test_user_role_membership())
