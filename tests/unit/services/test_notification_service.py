from __future__ import annotations

from datetime import datetime

import pytest

from outlabs_auth.services.channels.base import NotificationChannel
from outlabs_auth.services.notification import NotificationService


class RecordingObservability:
    def __init__(self) -> None:
        self.event_logs: list[tuple[str, int, str | None]] = []
        self.failure_logs: list[tuple[str, str, str]] = []

    def log_notification_event(
        self,
        *,
        event_type: str,
        channels_count: int,
        user_id: str | None,
    ) -> None:
        self.event_logs.append((event_type, channels_count, user_id))

    def log_notification_delivery_failure(
        self,
        *,
        event_type: str,
        channel: str,
        error: str,
    ) -> None:
        self.failure_logs.append((event_type, channel, error))


class RecordingChannel(NotificationChannel):
    def __init__(self, *, enabled: bool = True, event_filter: list[str] | None = None) -> None:
        super().__init__(enabled=enabled, event_filter=event_filter)
        self.events: list[dict] = []

    async def send(self, event: dict) -> None:
        self.events.append(event)


class FailingChannel(NotificationChannel):
    def __init__(self, *, enabled: bool = True, event_filter: list[str] | None = None) -> None:
        super().__init__(enabled=enabled, event_filter=event_filter)
        self.send_attempts = 0

    async def send(self, event: dict) -> None:
        self.send_attempts += 1
        raise RuntimeError("delivery exploded")


class BrokenFilterChannel(NotificationChannel):
    async def send(self, event: dict) -> None:
        raise AssertionError("send should not be called")

    def should_handle(self, event_type: str) -> bool:
        raise RuntimeError("filter exploded")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_emit_is_fire_and_forget_and_logs_observability(monkeypatch):
    observability = RecordingObservability()
    service = NotificationService(enabled=True, observability=observability)
    captured_coroutines = []
    processed: list[tuple[str, dict | None, dict | None]] = []

    async def fake_process_event(event_type: str, data: dict | None, metadata: dict | None) -> None:
        processed.append((event_type, data, metadata))

    class _FakeTask:
        def add_done_callback(self, callback):
            self._callback = callback

    def fake_create_task(coro):
        captured_coroutines.append(coro)
        return _FakeTask()

    monkeypatch.setattr(service, "_process_event", fake_process_event)
    monkeypatch.setattr("asyncio.create_task", fake_create_task)

    await service.emit(
        "user.login",
        data={"user_id": "user-1"},
        metadata={"ip": "127.0.0.1"},
    )

    assert observability.event_logs == [("user.login", 0, "user-1")]
    assert len(captured_coroutines) == 1
    assert processed == []

    await captured_coroutines[0]

    assert processed == [
        ("user.login", {"user_id": "user-1"}, {"ip": "127.0.0.1"})
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_process_event_filters_channels_and_enriches_payload():
    all_channel = RecordingChannel()
    login_channel = RecordingChannel(event_filter=["user.login"])
    deleted_channel = RecordingChannel(event_filter=["user.deleted"])
    disabled_channel = RecordingChannel(enabled=False)
    service = NotificationService(
        enabled=True,
        channels=[all_channel, login_channel, deleted_channel, disabled_channel],
    )

    await service._process_event(
        "user.login",
        data={"user_id": "user-1"},
        metadata={"ip": "127.0.0.1"},
    )

    assert len(all_channel.events) == 1
    assert len(login_channel.events) == 1
    assert deleted_channel.events == []
    assert disabled_channel.events == []

    event = all_channel.events[0]
    assert event["type"] == "user.login"
    assert event["data"] == {"user_id": "user-1"}
    assert event["metadata"] == {"ip": "127.0.0.1"}
    assert datetime.fromisoformat(event["timestamp"]) is not None
    assert login_channel.events[0] == event


@pytest.mark.unit
@pytest.mark.asyncio
async def test_process_event_isolates_channel_failures_and_logs_correct_channel():
    observability = RecordingObservability()
    skipped_channel = RecordingChannel(event_filter=["user.deleted"])
    failing_channel = FailingChannel(event_filter=["user.login"])
    succeeding_channel = RecordingChannel(event_filter=["user.login"])
    service = NotificationService(
        enabled=True,
        channels=[skipped_channel, failing_channel, succeeding_channel],
        observability=observability,
    )

    await service._process_event(
        "user.login",
        data={"user_id": "user-1"},
        metadata={"ip": "127.0.0.1"},
    )

    assert failing_channel.send_attempts == 1
    assert len(succeeding_channel.events) == 1
    assert observability.failure_logs == [
        ("user.login", "FailingChannel", "delivery exploded")
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_process_event_swallows_pre_dispatch_errors_and_logs_unknown_channel():
    observability = RecordingObservability()
    service = NotificationService(
        enabled=True,
        channels=[BrokenFilterChannel()],
        observability=observability,
    )

    await service._process_event("user.login", data=None, metadata=None)

    assert observability.failure_logs == [
        ("user.login", "unknown", "filter exploded")
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_emit_noops_when_notifications_are_disabled(monkeypatch):
    observability = RecordingObservability()
    service = NotificationService(enabled=False, observability=observability)
    created_tasks: list[object] = []

    def fake_create_task(coro):
        created_tasks.append(coro)
        return object()

    monkeypatch.setattr("asyncio.create_task", fake_create_task)

    await service.emit("user.login", data={"user_id": "user-1"})

    assert created_tasks == []
    assert observability.event_logs == []
