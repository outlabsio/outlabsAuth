"""
Tests for ServiceTokenService

Tests long-lived JWT service tokens with embedded permissions.
"""
import pytest
import time
from datetime import datetime, timedelta, timezone

from outlabs_auth.services.service_token import ServiceTokenService
from outlabs_auth.core.config import AuthConfig
from outlabs_auth.core.exceptions import TokenInvalidError


@pytest.fixture
def config():
    """Create test configuration"""
    return AuthConfig(
        secret_key="test-secret-key-for-service-tokens-12345",
        algorithm="HS256",
    )


@pytest.fixture
def service_token_service(config):
    """Create ServiceTokenService instance"""
    return ServiceTokenService(config=config)


def test_create_service_token(service_token_service):
    """Test creating a service token"""
    token = service_token_service.create_service_token(
        service_id="test-service",
        service_name="Test Service",
        permissions=["data:read", "data:write"],
        expires_days=365,
        metadata={"environment": "test"}
    )

    assert isinstance(token, str)
    assert len(token) > 0


def test_validate_service_token(service_token_service):
    """Test validating a service token"""
    # Create token
    token = service_token_service.create_service_token(
        service_id="test-service",
        service_name="Test Service",
        permissions=["data:read", "data:write"],
    )

    # Validate token
    payload = service_token_service.validate_service_token(token)

    assert payload["sub"] == "test-service"
    assert payload["type"] == "service"
    assert payload["service_name"] == "Test Service"
    assert "data:read" in payload["permissions"]
    assert "data:write" in payload["permissions"]


def test_validate_service_token_performance(service_token_service):
    """Test that service token validation is fast (~0.5ms)"""
    # Create token
    token = service_token_service.create_service_token(
        service_id="perf-test",
        service_name="Performance Test",
        permissions=["test:read", "test:write"],
    )

    # Warm up
    service_token_service.validate_service_token(token)

    # Measure validation time over 100 iterations
    iterations = 100
    start_time = time.perf_counter()

    for _ in range(iterations):
        service_token_service.validate_service_token(token)

    end_time = time.perf_counter()
    elapsed_ms = ((end_time - start_time) / iterations) * 1000

    # Should be under 1ms (targeting ~0.5ms)
    assert elapsed_ms < 1.0, f"Validation took {elapsed_ms:.2f}ms, should be < 1ms"
    print(f"\n✓ Service token validation: {elapsed_ms:.3f}ms per validation")


def test_check_service_permission_exact_match(service_token_service):
    """Test checking exact permission match"""
    token = service_token_service.create_service_token(
        service_id="test-service",
        service_name="Test Service",
        permissions=["report:generate", "data:read"],
    )

    payload = service_token_service.validate_service_token(token)

    # Should have exact permission
    assert service_token_service.check_service_permission(payload, "report:generate") is True
    assert service_token_service.check_service_permission(payload, "data:read") is True

    # Should not have other permissions
    assert service_token_service.check_service_permission(payload, "data:delete") is False


def test_check_service_permission_wildcard(service_token_service):
    """Test checking wildcard permissions"""
    token = service_token_service.create_service_token(
        service_id="test-service",
        service_name="Test Service",
        permissions=["data:*"],  # Wildcard for all data actions
    )

    payload = service_token_service.validate_service_token(token)

    # Should match any data action
    assert service_token_service.check_service_permission(payload, "data:read") is True
    assert service_token_service.check_service_permission(payload, "data:write") is True
    assert service_token_service.check_service_permission(payload, "data:delete") is True

    # Should not match other resources
    assert service_token_service.check_service_permission(payload, "user:read") is False


def test_check_service_permission_full_wildcard(service_token_service):
    """Test checking full wildcard permission"""
    token = service_token_service.create_service_token(
        service_id="admin-service",
        service_name="Admin Service",
        permissions=["*:*"],  # Full wildcard
    )

    payload = service_token_service.validate_service_token(token)

    # Should match any permission
    assert service_token_service.check_service_permission(payload, "data:read") is True
    assert service_token_service.check_service_permission(payload, "user:update") is True
    assert service_token_service.check_service_permission(payload, "report:generate") is True


def test_get_service_permissions(service_token_service):
    """Test getting all permissions from token"""
    permissions = ["report:generate", "data:read", "user:update"]

    token = service_token_service.create_service_token(
        service_id="test-service",
        service_name="Test Service",
        permissions=permissions,
    )

    payload = service_token_service.validate_service_token(token)
    retrieved_perms = service_token_service.get_service_permissions(payload)

    assert set(retrieved_perms) == set(permissions)


def test_get_service_metadata(service_token_service):
    """Test getting metadata from token"""
    metadata = {
        "environment": "production",
        "version": "2.0",
        "region": "us-west-2"
    }

    token = service_token_service.create_service_token(
        service_id="test-service",
        service_name="Test Service",
        permissions=["test:read"],
        metadata=metadata,
    )

    payload = service_token_service.validate_service_token(token)
    retrieved_metadata = service_token_service.get_service_metadata(payload)

    assert retrieved_metadata == metadata


def test_get_service_info(service_token_service):
    """Test getting service information from token"""
    token = service_token_service.create_service_token(
        service_id="analytics-service",
        service_name="Analytics Service",
        permissions=["analytics:read", "data:export"],
        metadata={"tier": "premium"}
    )

    payload = service_token_service.validate_service_token(token)
    info = service_token_service.get_service_info(payload)

    assert info["service_id"] == "analytics-service"
    assert info["service_name"] == "Analytics Service"
    assert info["token_type"] == "service"
    assert "analytics:read" in info["permissions"]
    assert info["metadata"]["tier"] == "premium"


def test_create_api_service_token(service_token_service):
    """Test convenience method for API service tokens"""
    token = service_token_service.create_api_service_token(
        api_name="reporting",
        permissions=["report:*"],
    )

    payload = service_token_service.validate_service_token(token)

    assert payload["sub"] == "api-reporting"
    assert payload["service_name"] == "Reporting API"
    assert payload["metadata"]["service_type"] == "api"
    assert "report:*" in payload["permissions"]


def test_create_worker_service_token(service_token_service):
    """Test convenience method for worker service tokens"""
    token = service_token_service.create_worker_service_token(
        worker_name="email-sender",
        permissions=["email:send", "user:read"],
    )

    payload = service_token_service.validate_service_token(token)

    assert payload["sub"] == "worker-email-sender"
    assert payload["service_name"] == "Email-Sender Worker"
    assert payload["metadata"]["service_type"] == "worker"
    assert "email:send" in payload["permissions"]


def test_invalid_token_raises_error(service_token_service):
    """Test that invalid tokens raise TokenInvalidError"""
    with pytest.raises(TokenInvalidError):
        service_token_service.validate_service_token("invalid-token")


def test_user_token_rejected_as_service_token(service_token_service, config):
    """Test that user tokens are rejected when validating as service token"""
    from jose import jwt

    # Create a user token (without type="service")
    user_token = jwt.encode(
        {
            "sub": "user-123",
            "type": "access",  # Not "service"
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        },
        config.secret_key,
        algorithm=config.algorithm,
    )

    # Should raise error when validating as service token
    with pytest.raises(TokenInvalidError) as exc_info:
        service_token_service.validate_service_token(user_token)

    assert "not a service token" in str(exc_info.value)


def test_custom_expiration(service_token_service):
    """Test creating token with custom expiration"""
    token = service_token_service.create_service_token(
        service_id="short-lived-service",
        service_name="Short Lived Service",
        permissions=["test:read"],
        expires_days=30,  # 30 days instead of 365
    )

    payload = service_token_service.validate_service_token(token)

    # Verify expiration is approximately 30 days from now
    exp_timestamp = payload["exp"]
    exp_date = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
    expected_exp = datetime.now(timezone.utc) + timedelta(days=30)

    # Should be within 1 minute of expected
    assert abs((exp_date - expected_exp).total_seconds()) < 60


def test_token_with_many_permissions_still_fast(service_token_service):
    """Test that tokens with many embedded permissions are still fast to validate"""
    # Create token with 50 permissions
    permissions = [f"resource{i}:action{j}" for i in range(10) for j in range(5)]

    token = service_token_service.create_service_token(
        service_id="many-perms-service",
        service_name="Many Permissions Service",
        permissions=permissions,
    )

    # Measure validation time
    iterations = 100
    start_time = time.perf_counter()

    for _ in range(iterations):
        payload = service_token_service.validate_service_token(token)
        # Also check a permission
        service_token_service.check_service_permission(payload, "resource5:action3")

    end_time = time.perf_counter()
    elapsed_ms = ((end_time - start_time) / iterations) * 1000

    # Should still be under 2ms even with 50 permissions
    assert elapsed_ms < 2.0, f"Validation took {elapsed_ms:.2f}ms with 50 permissions"
    print(f"\n✓ Validation with 50 permissions: {elapsed_ms:.3f}ms")
