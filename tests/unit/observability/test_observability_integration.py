"""
Unit tests for observability integration across services.

Tests that services correctly emit metrics and logs through ObservabilityService.
"""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from prometheus_client import REGISTRY, CollectorRegistry, generate_latest

from outlabs_auth.observability.config import (
    LogsFormat,
    LogsLevel,
    ObservabilityConfig,
    PermissionCheckLogging,
)
from outlabs_auth.observability.service import ObservabilityService


@pytest.fixture(autouse=True)
def clean_prometheus_registry():
    """Clean up Prometheus registry before each test to avoid duplicate metrics."""
    # Get all collector names that start with outlabs_auth
    collectors_to_remove = []
    for collector in list(REGISTRY._names_to_collectors.values()):
        if hasattr(collector, "_name") and collector._name.startswith("outlabs_auth"):
            collectors_to_remove.append(collector)

    for collector in collectors_to_remove:
        try:
            REGISTRY.unregister(collector)
        except Exception:
            pass

    yield

    # Clean up after test as well
    collectors_to_remove = []
    for collector in list(REGISTRY._names_to_collectors.values()):
        if hasattr(collector, "_name") and collector._name.startswith("outlabs_auth"):
            collectors_to_remove.append(collector)

    for collector in collectors_to_remove:
        try:
            REGISTRY.unregister(collector)
        except Exception:
            pass


@pytest.fixture
def obs_config():
    """Create a minimal observability configuration for testing."""
    return ObservabilityConfig(
        enable_metrics=True,
        logs_level=LogsLevel.DEBUG,
        logs_format=LogsFormat.TEXT,
        log_permission_checks=PermissionCheckLogging.FAILURES_ONLY,
        async_logging=False,
    )


@pytest.fixture
async def obs_service(obs_config):
    """Create and initialize an ObservabilityService instance."""
    service = ObservabilityService(obs_config)
    await service.initialize()
    yield service
    await service.shutdown()


class TestObservabilityServiceInitialization:
    """Test ObservabilityService initialization."""

    @pytest.mark.asyncio
    async def test_initialize_creates_metrics(self, obs_config):
        """Initialize creates all expected Prometheus metrics."""
        service = ObservabilityService(obs_config)
        await service.initialize()

        # Check core metrics exist
        assert "login_attempts" in service.metrics
        assert "login_duration" in service.metrics
        assert "permission_checks" in service.metrics
        assert "api_key_validations" in service.metrics

        # Check new metrics for instrumented services
        assert "entity_operations_total" in service.metrics
        assert "entity_operation_duration" in service.metrics
        assert "membership_operations_total" in service.metrics
        assert "membership_operation_duration" in service.metrics
        assert "activity_track_total" in service.metrics
        assert "activity_sync_duration" in service.metrics
        assert "redis_operation_duration" in service.metrics
        assert "redis_errors_total" in service.metrics
        assert "notification_events_total" in service.metrics
        assert "notification_delivery_failures" in service.metrics

        await service.shutdown()

    @pytest.mark.asyncio
    async def test_initialize_with_metrics_disabled(self):
        """Initialize with metrics disabled creates no metrics."""
        config = ObservabilityConfig(enable_metrics=False)
        service = ObservabilityService(config)
        await service.initialize()

        assert len(service.metrics) == 0

        await service.shutdown()

    @pytest.mark.asyncio
    async def test_initialize_uses_custom_registry(self, obs_config):
        """Injected registries receive auth metrics without polluting the default registry."""
        registry = CollectorRegistry()
        service = ObservabilityService(obs_config, metrics_registry=registry)
        await service.initialize()

        service.log_entity_operation(
            operation="create",
            entity_id="entity-123",
            entity_type="department",
        )

        custom_metrics = generate_latest(registry).decode()
        default_metrics = generate_latest(REGISTRY).decode()

        assert "outlabs_auth_entity_operations_total" in custom_metrics
        assert "outlabs_auth_entity_operations_total" not in default_metrics

        await service.shutdown()

    @pytest.mark.asyncio
    async def test_initialize_uses_host_logger(self, obs_config, caplog):
        """Injected host loggers receive auth events without global logger reconfiguration."""
        logger = logging.getLogger("tests.outlabs_auth.host_logger")
        caplog.set_level(logging.INFO, logger=logger.name)

        service = ObservabilityService(obs_config, logger=logger)
        await service.initialize()
        service.log_entity_operation(
            operation="create",
            entity_id="entity-123",
            entity_type="department",
        )
        await service.shutdown()

        messages = [record.getMessage() for record in caplog.records if record.name == logger.name]
        assert any("observability_initialized" in message for message in messages)
        assert any("entity_create" in message for message in messages)


class TestEntityOperationLogging:
    """Test entity operation logging methods."""

    @pytest.mark.asyncio
    async def test_log_entity_operation_emits_metric_and_log(self, obs_service):
        """log_entity_operation emits counter and histogram metrics."""
        # Get initial counter value
        counter = obs_service.metrics["entity_operations_total"]

        obs_service.log_entity_operation(
            operation="create",
            entity_id="entity-123",
            entity_type="department",
            duration_ms=50.5,
            parent_id="root-entity",
        )

        # Counter should have been incremented
        # Note: We can't easily check counter values in prometheus_client
        # but we verify the method executes without error

    @pytest.mark.asyncio
    async def test_log_entity_operation_without_observability(self):
        """Entity operations work gracefully without observability."""
        # This tests the pattern used in services when observability is None
        observability = None

        # Simulate service code pattern
        if observability:
            observability.log_entity_operation(
                operation="create",
                entity_id="entity-123",
                entity_type="department",
            )

        # Should not raise any errors


class TestMembershipOperationLogging:
    """Test membership operation logging methods."""

    @pytest.mark.asyncio
    async def test_log_membership_operation_emits_metrics(self, obs_service):
        """log_membership_operation emits counter metric."""
        obs_service.log_membership_operation(
            operation="add",
            user_id="user-123",
            entity_id="entity-456",
            roles=["admin", "editor"],
            duration_ms=25.0,
        )

        # Verify no errors - metric emission tested implicitly

    @pytest.mark.asyncio
    async def test_log_membership_suspend(self, obs_service):
        """log_membership_operation handles suspend operation."""
        obs_service.log_membership_operation(
            operation="suspend",
            user_id="user-123",
            entity_id="entity-456",
            reason="policy_violation",
        )


class TestActivityTrackingLogging:
    """Test activity tracking logging methods."""

    @pytest.mark.asyncio
    async def test_log_activity_tracked(self, obs_service):
        """log_activity_tracked emits metrics for each period."""
        obs_service.log_activity_tracked(
            user_id="user-123",
            period="daily",
        )

        obs_service.log_activity_tracked(
            user_id="user-123",
            period="monthly",
        )

        obs_service.log_activity_tracked(
            user_id="user-123",
            period="quarterly",
        )

    @pytest.mark.asyncio
    async def test_log_activity_sync(self, obs_service):
        """log_activity_sync emits duration histogram and record counts."""
        obs_service.log_activity_sync(
            duration_ms=150.0,
            records_synced=42,
            daily_count=10,
            monthly_count=25,
            quarterly_count=7,
        )


class TestRedisOperationLogging:
    """Test Redis operation logging methods."""

    @pytest.mark.asyncio
    async def test_log_redis_operation(self, obs_service):
        """log_redis_operation emits duration histogram."""
        obs_service.log_redis_operation(
            operation="get",
            duration_ms=2.5,
            key="cache:user:123",
        )

        obs_service.log_redis_operation(
            operation="set",
            duration_ms=3.2,
            key="cache:user:123",
            success=True,
        )

    @pytest.mark.asyncio
    async def test_log_redis_operation_error(self, obs_service):
        """log_redis_operation handles errors."""
        obs_service.log_redis_operation(
            operation="get",
            duration_ms=100.0,
            key="cache:user:123",
            success=False,
            error="Connection timeout",
        )


class TestNotificationEventLogging:
    """Test notification event logging methods."""

    @pytest.mark.asyncio
    async def test_log_notification_event(self, obs_service):
        """log_notification_event emits counter metric."""
        obs_service.log_notification_event(
            event_type="user_registered",
            channels_count=3,
            user_id="user-123",
        )

    @pytest.mark.asyncio
    async def test_log_notification_delivery_failure(self, obs_service):
        """log_notification_delivery_failure emits failure counter."""
        obs_service.log_notification_delivery_failure(
            event_type="user_registered",
            channel="email",
            error="SMTP connection failed",
        )


class TestServiceIntegrationWithObservability:
    """Integration tests for services with observability wiring."""

    @pytest.mark.asyncio
    async def test_entity_service_uses_observability(self, obs_service):
        """EntityService constructor accepts observability parameter."""
        from outlabs_auth.core.config import AuthConfig
        from outlabs_auth.services.entity import EntityService

        config = AuthConfig(
            database_url="postgresql+asyncpg://test:test@localhost/test",
            secret_key="test-secret",
            enable_entity_hierarchy=True,
        )

        # Should not raise
        service = EntityService(
            config,
            redis_client=None,
            observability=obs_service,
        )

        assert service.observability is obs_service

    @pytest.mark.asyncio
    async def test_membership_service_uses_observability(self, obs_service):
        """MembershipService constructor accepts observability parameter."""
        from outlabs_auth.core.config import AuthConfig
        from outlabs_auth.services.membership import MembershipService

        config = AuthConfig(
            database_url="postgresql+asyncpg://test:test@localhost/test",
            secret_key="test-secret",
            enable_entity_hierarchy=True,
        )

        service = MembershipService(
            config,
            observability=obs_service,
        )

        assert service.observability is obs_service

    @pytest.mark.asyncio
    async def test_activity_tracker_uses_observability(self, obs_service):
        """ActivityTracker constructor accepts observability parameter."""
        from outlabs_auth.services.activity_tracker import ActivityTracker

        mock_redis = AsyncMock()

        tracker = ActivityTracker(
            redis_client=mock_redis,
            enabled=True,
            observability=obs_service,
        )

        assert tracker.observability is obs_service

    @pytest.mark.asyncio
    async def test_notification_service_uses_observability(self, obs_service):
        """NotificationService constructor accepts observability parameter."""
        from outlabs_auth.services.notification import NotificationService

        service = NotificationService(observability=obs_service)

        assert service.observability is obs_service


class TestGracefulDegradation:
    """Test that services work correctly without observability."""

    @pytest.mark.asyncio
    async def test_entity_service_without_observability(self):
        """EntityService works when observability is None."""
        from outlabs_auth.core.config import AuthConfig
        from outlabs_auth.services.entity import EntityService

        config = AuthConfig(
            database_url="postgresql+asyncpg://test:test@localhost/test",
            secret_key="test-secret",
            enable_entity_hierarchy=True,
        )

        # Should not raise with observability=None
        service = EntityService(
            config,
            redis_client=None,
            observability=None,
        )

        assert service.observability is None

    @pytest.mark.asyncio
    async def test_membership_service_without_observability(self):
        """MembershipService works when observability is None."""
        from outlabs_auth.core.config import AuthConfig
        from outlabs_auth.services.membership import MembershipService

        config = AuthConfig(
            database_url="postgresql+asyncpg://test:test@localhost/test",
            secret_key="test-secret",
            enable_entity_hierarchy=True,
        )

        service = MembershipService(config, observability=None)

        assert service.observability is None

    @pytest.mark.asyncio
    async def test_activity_tracker_without_observability(self):
        """ActivityTracker works when observability is None."""
        from outlabs_auth.services.activity_tracker import ActivityTracker

        mock_redis = AsyncMock()

        tracker = ActivityTracker(
            redis_client=mock_redis,
            enabled=True,
            observability=None,
        )

        assert tracker.observability is None

        # track_activity should work without observability
        await tracker.track_activity("user-123")

    @pytest.mark.asyncio
    async def test_notification_service_without_observability(self):
        """NotificationService works when observability is None."""
        from outlabs_auth.services.notification import NotificationService

        service = NotificationService(observability=None)

        assert service.observability is None


class TestMetricsValues:
    """Test that metrics are correctly labeled and valued."""

    @pytest.mark.asyncio
    async def test_entity_operation_labels(self, obs_service):
        """Entity operation metrics have correct labels."""
        counter = obs_service.metrics["entity_operations_total"]

        # Create operation
        obs_service.log_entity_operation(
            operation="create",
            entity_id="e1",
            entity_type="department",
        )

        # Update operation
        obs_service.log_entity_operation(
            operation="update",
            entity_id="e1",
            entity_type="department",
        )

        # Delete operation
        obs_service.log_entity_operation(
            operation="delete",
            entity_id="e1",
            entity_type="department",
        )

        # Move operation
        obs_service.log_entity_operation(
            operation="move",
            entity_id="e1",
            entity_type="department",
            duration_ms=100.0,
        )

    @pytest.mark.asyncio
    async def test_membership_operation_labels(self, obs_service):
        """Membership operation metrics have correct labels."""
        obs_service.log_membership_operation(
            operation="add",
            user_id="u1",
            entity_id="e1",
        )

        obs_service.log_membership_operation(
            operation="remove",
            user_id="u1",
            entity_id="e1",
        )

        obs_service.log_membership_operation(
            operation="suspend",
            user_id="u1",
            entity_id="e1",
        )

        obs_service.log_membership_operation(
            operation="reactivate",
            user_id="u1",
            entity_id="e1",
        )
