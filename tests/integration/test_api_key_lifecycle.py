"""
API Key Lifecycle and Security Integration Tests

Tests the complete API key lifecycle:
- Creating API keys
- Listing API keys
- Deleting API keys
- API key security features (prefix, ownership)

These tests ensure API key management works correctly end-to-end.
Note: API key authentication tests require additional setup and are
tested separately via the ABAC/Enterprise examples.
"""

import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from outlabs_auth import SimpleRBAC
from outlabs_auth.fastapi import register_exception_handlers
from outlabs_auth.routers import get_api_keys_router, get_auth_router, get_users_router
from outlabs_auth.utils.jwt import create_access_token

# ============================================================================
# Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def auth_instance(test_engine) -> SimpleRBAC:
    """Create SimpleRBAC instance for API key testing."""
    auth = SimpleRBAC(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        access_token_expire_minutes=60,
    )
    await auth.initialize()
    return auth


@pytest_asyncio.fixture
async def app(auth_instance: SimpleRBAC) -> FastAPI:
    """Create FastAPI app with routers."""
    app = FastAPI()
    register_exception_handlers(app, debug=True)
    app.include_router(get_auth_router(auth_instance, prefix="/v1/auth"))
    app.include_router(get_users_router(auth_instance, prefix="/v1/users"))
    app.include_router(get_api_keys_router(auth_instance, prefix="/v1/api-keys"))
    return app


@pytest_asyncio.fixture
async def client(app: FastAPI) -> httpx.AsyncClient:
    """Async HTTP client."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=True, timeout=20.0
    ) as client:
        yield client


@pytest_asyncio.fixture
async def admin_user(auth_instance: SimpleRBAC) -> dict:
    """Create admin user (superuser) and return credentials."""
    async with auth_instance.get_session() as session:
        admin = await auth_instance.user_service.create_user(
            session=session,
            email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
            password="AdminPass123!",
            first_name="Admin",
            last_name="User",
            is_superuser=True,
        )
        await session.commit()

        token = create_access_token(
            {"sub": str(admin.id)},
            secret_key=auth_instance.config.secret_key,
            algorithm=auth_instance.config.algorithm,
        )

        return {
            "id": str(admin.id),
            "email": admin.email,
            "token": token,
        }


@pytest_asyncio.fixture
async def regular_user(auth_instance: SimpleRBAC) -> dict:
    """Create regular user and return credentials."""
    async with auth_instance.get_session() as session:
        user = await auth_instance.user_service.create_user(
            session=session,
            email=f"regular-{uuid.uuid4().hex[:8]}@example.com",
            password="RegularPass123!",
            first_name="Regular",
            last_name="User",
            is_superuser=False,
        )
        await session.commit()

        token = create_access_token(
            {"sub": str(user.id)},
            secret_key=auth_instance.config.secret_key,
            algorithm=auth_instance.config.algorithm,
        )

        return {
            "id": str(user.id),
            "email": user.email,
            "token": token,
        }


# ============================================================================
# API Key CRUD Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_can_create_api_key(client: httpx.AsyncClient, admin_user: dict):
    """Test that admin can create an API key."""
    resp = await client.post(
        "/v1/api-keys/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={
            "name": f"test-key-{uuid.uuid4().hex[:8]}",
            "description": "Test API key",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "api_key" in data  # Full key returned only on creation
    assert "prefix" in data
    assert data["api_key"].startswith(data["prefix"])


@pytest.mark.integration
@pytest.mark.asyncio
async def test_api_key_only_returned_on_creation(
    client: httpx.AsyncClient, admin_user: dict
):
    """Test that full API key is only returned on creation, not on subsequent requests."""
    # Create key
    create_resp = await client.post(
        "/v1/api-keys/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"name": f"key-{uuid.uuid4().hex[:8]}"},
    )
    assert create_resp.status_code == 201
    key_id = create_resp.json()["id"]

    # Get key - should not include full key
    get_resp = await client.get(
        f"/v1/api-keys/{key_id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert get_resp.status_code == 200
    data = get_resp.json()
    # Full key should NOT be present (api_key field should be absent or None)
    assert data.get("api_key") is None or "api_key" not in data


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_can_list_api_keys(client: httpx.AsyncClient, admin_user: dict):
    """Test that admin can list API keys."""
    # Create a key
    await client.post(
        "/v1/api-keys/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"name": f"listable-{uuid.uuid4().hex[:8]}"},
    )

    # List keys
    resp = await client.get(
        "/v1/api-keys/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert resp.status_code == 200
    keys = resp.json()
    assert isinstance(keys, list)
    assert len(keys) >= 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_can_get_single_api_key(
    client: httpx.AsyncClient, admin_user: dict
):
    """Test that admin can get a single API key by ID."""
    # Create key
    create_resp = await client.post(
        "/v1/api-keys/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"name": f"gettable-{uuid.uuid4().hex[:8]}"},
    )
    key_id = create_resp.json()["id"]

    # Get key
    get_resp = await client.get(
        f"/v1/api-keys/{key_id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["id"] == key_id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_can_delete_api_key(client: httpx.AsyncClient, admin_user: dict):
    """Test that admin can delete an API key."""
    # Create key
    create_resp = await client.post(
        "/v1/api-keys/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"name": f"deletable-{uuid.uuid4().hex[:8]}"},
    )
    key_id = create_resp.json()["id"]

    # Delete key
    delete_resp = await client.delete(
        f"/v1/api-keys/{key_id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert delete_resp.status_code == 204

    # Verify key is deleted (soft delete - it may still return 200 but with revoked status)
    get_resp = await client.get(
        f"/v1/api-keys/{key_id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    # May return 404 or 200 with revoked status depending on implementation
    if get_resp.status_code == 200:
        data = get_resp.json()
        assert data.get("status") == "revoked"
    else:
        assert get_resp.status_code == 404


# ============================================================================
# API Key Ownership Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_can_see_own_api_keys(
    client: httpx.AsyncClient, regular_user: dict, auth_instance: SimpleRBAC
):
    """Test that user can see their own API keys."""
    # Create key via service for the regular user
    async with auth_instance.get_session() as session:
        full_key, key_model = await auth_instance.api_key_service.create_api_key(
            session,
            owner_id=uuid.UUID(regular_user["id"]),
            name=f"user-key-{uuid.uuid4().hex[:8]}",
        )
        await session.commit()
        key_id = str(key_model.id)

    # User lists their keys
    resp = await client.get(
        "/v1/api-keys/",
        headers={"Authorization": f"Bearer {regular_user['token']}"},
    )
    assert resp.status_code == 200
    keys = resp.json()
    assert any(k["id"] == key_id for k in keys)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_cannot_see_other_user_keys(
    client: httpx.AsyncClient,
    admin_user: dict,
    regular_user: dict,
    auth_instance: SimpleRBAC,
):
    """Test that user cannot see another user's API keys in list."""
    # Admin creates a key
    admin_key_resp = await client.post(
        "/v1/api-keys/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"name": f"admin-key-{uuid.uuid4().hex[:8]}"},
    )
    admin_key_id = admin_key_resp.json()["id"]

    # Regular user lists their keys - should not see admin's key
    resp = await client.get(
        "/v1/api-keys/",
        headers={"Authorization": f"Bearer {regular_user['token']}"},
    )
    assert resp.status_code == 200
    keys = resp.json()
    assert not any(k["id"] == admin_key_id for k in keys)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_cannot_delete_other_user_key(
    client: httpx.AsyncClient,
    admin_user: dict,
    regular_user: dict,
):
    """Test that user cannot delete another user's API key."""
    # Admin creates a key
    admin_key_resp = await client.post(
        "/v1/api-keys/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"name": f"admin-key-{uuid.uuid4().hex[:8]}"},
    )
    admin_key_id = admin_key_resp.json()["id"]

    # Regular user tries to delete admin's key - should fail
    resp = await client.delete(
        f"/v1/api-keys/{admin_key_id}",
        headers={"Authorization": f"Bearer {regular_user['token']}"},
    )
    assert resp.status_code in [
        403,
        404,
    ]  # Forbidden or Not Found (if filtered by ownership)


# ============================================================================
# API Key Security Features
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_api_key_has_prefix(client: httpx.AsyncClient, admin_user: dict):
    """Test that API key has a prefix for identification."""
    resp = await client.post(
        "/v1/api-keys/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"name": f"prefixed-{uuid.uuid4().hex[:8]}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "prefix" in data
    # Prefix should be at the start of the key
    assert data["api_key"].startswith(data["prefix"])


@pytest.mark.integration
@pytest.mark.asyncio
async def test_api_key_prefix_starts_with_sk(
    client: httpx.AsyncClient, admin_user: dict
):
    """Test that API key prefix starts with 'sk_' convention."""
    resp = await client.post(
        "/v1/api-keys/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={"name": f"sk-prefix-{uuid.uuid4().hex[:8]}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["prefix"].startswith("sk_")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_api_key_name_required(client: httpx.AsyncClient, admin_user: dict):
    """Test that API key name is required."""
    resp = await client.post(
        "/v1/api-keys/",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
        json={},  # No name provided
    )
    # Should fail validation
    assert resp.status_code == 422


@pytest.mark.integration
@pytest.mark.asyncio
async def test_api_key_unique_per_creation(client: httpx.AsyncClient, admin_user: dict):
    """Test that each API key creation produces a unique key."""
    keys = []
    for i in range(3):
        resp = await client.post(
            "/v1/api-keys/",
            headers={"Authorization": f"Bearer {admin_user['token']}"},
            json={"name": f"unique-{i}-{uuid.uuid4().hex[:8]}"},
        )
        assert resp.status_code == 201
        keys.append(resp.json()["api_key"])

    # All keys should be unique
    assert len(set(keys)) == 3


# ============================================================================
# API Key Service Layer Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_service_create_api_key(auth_instance: SimpleRBAC, admin_user: dict):
    """Test creating API key via service layer."""
    async with auth_instance.get_session() as session:
        full_key, key_model = await auth_instance.api_key_service.create_api_key(
            session,
            owner_id=uuid.UUID(admin_user["id"]),
            name=f"service-key-{uuid.uuid4().hex[:8]}",
            description="Created via service",
        )
        await session.commit()

        assert full_key is not None
        assert key_model.id is not None
        assert key_model.name.startswith("service-key-")
        assert key_model.description == "Created via service"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_service_create_api_key_with_expiration(
    auth_instance: SimpleRBAC, admin_user: dict
):
    """Test creating API key with expiration via service."""
    async with auth_instance.get_session() as session:
        full_key, key_model = await auth_instance.api_key_service.create_api_key(
            session,
            owner_id=uuid.UUID(admin_user["id"]),
            name=f"expiring-key-{uuid.uuid4().hex[:8]}",
            expires_in_days=30,
        )
        await session.commit()

        assert key_model.expires_at is not None
        # Should expire in approximately 30 days
        expected_expiry = datetime.now(timezone.utc) + timedelta(days=30)
        assert abs((key_model.expires_at - expected_expiry).total_seconds()) < 60


@pytest.mark.integration
@pytest.mark.asyncio
async def test_service_verify_api_key(auth_instance: SimpleRBAC, admin_user: dict):
    """Test verifying API key via service layer."""
    async with auth_instance.get_session() as session:
        # Create key
        full_key, key_model = await auth_instance.api_key_service.create_api_key(
            session,
            owner_id=uuid.UUID(admin_user["id"]),
            name=f"verify-key-{uuid.uuid4().hex[:8]}",
        )
        await session.commit()

        # Verify key - returns tuple (api_key, remaining_rate_limit)
        verified_key, remaining = await auth_instance.api_key_service.verify_api_key(
            session, full_key
        )
        assert verified_key is not None
        assert verified_key.id == key_model.id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_service_verify_invalid_key(auth_instance: SimpleRBAC):
    """Test that invalid API key fails verification."""
    async with auth_instance.get_session() as session:
        # Returns tuple (api_key, remaining) - api_key is None for invalid
        verified_key, remaining = await auth_instance.api_key_service.verify_api_key(
            session, "sk_live_invalid_key_123456789"
        )
        assert verified_key is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_service_revoke_api_key(auth_instance: SimpleRBAC, admin_user: dict):
    """Test revoking API key via service."""
    async with auth_instance.get_session() as session:
        # Create key
        full_key, key_model = await auth_instance.api_key_service.create_api_key(
            session,
            owner_id=uuid.UUID(admin_user["id"]),
            name=f"revoke-key-{uuid.uuid4().hex[:8]}",
        )
        await session.commit()

        # Verify key works - returns tuple (api_key, remaining)
        valid, _ = await auth_instance.api_key_service.verify_api_key(session, full_key)
        assert valid is not None

        # Revoke key
        await auth_instance.api_key_service.revoke_api_key(session, key_model.id)
        await session.commit()

        # Verify key no longer works
        invalid, _ = await auth_instance.api_key_service.verify_api_key(
            session, full_key
        )
        assert invalid is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_service_expired_key_verification_fails(
    auth_instance: SimpleRBAC, admin_user: dict
):
    """Test that expired API key fails verification."""
    async with auth_instance.get_session() as session:
        # Create key
        full_key, key_model = await auth_instance.api_key_service.create_api_key(
            session,
            owner_id=uuid.UUID(admin_user["id"]),
            name=f"expired-key-{uuid.uuid4().hex[:8]}",
        )
        # Manually set expiration to past
        key_model.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        await session.commit()

        # Verify - should fail because expired - returns tuple (api_key, remaining)
        verified, _ = await auth_instance.api_key_service.verify_api_key(
            session, full_key
        )
        assert verified is None


# ============================================================================
# Edge Cases
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_nonexistent_api_key(client: httpx.AsyncClient, admin_user: dict):
    """Test getting a non-existent API key returns 404."""
    fake_id = str(uuid.uuid4())
    resp = await client.get(
        f"/v1/api-keys/{fake_id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert resp.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_nonexistent_api_key(client: httpx.AsyncClient, admin_user: dict):
    """Test deleting a non-existent API key returns 404."""
    fake_id = str(uuid.uuid4())
    resp = await client.delete(
        f"/v1/api-keys/{fake_id}",
        headers={"Authorization": f"Bearer {admin_user['token']}"},
    )
    assert resp.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_api_key_list_requires_authentication(client: httpx.AsyncClient):
    """Test that API key list requires authentication."""
    resp = await client.get("/v1/api-keys/")
    assert resp.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_api_key_create_requires_authentication(client: httpx.AsyncClient):
    """Test that API key creation requires authentication."""
    resp = await client.post(
        "/v1/api-keys/",
        json={"name": "unauthorized-key"},
    )
    assert resp.status_code == 401
