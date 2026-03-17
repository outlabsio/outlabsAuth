"""
Redis-backed cache service for permission checks.
"""

import asyncio
import contextlib
from typing import Optional

from outlabs_auth.core.config import AuthConfig


class CacheService:
    """Manages cached RBAC permission checks and invalidation broadcasts."""

    def __init__(self, redis_client, config: AuthConfig):
        self.redis_client = redis_client
        self.config = config
        self._pubsub = None
        self._listener_task: Optional[asyncio.Task] = None

    def make_permission_check_key(
        self,
        user_id: str,
        permission: str,
        entity_id: Optional[str] = None,
    ) -> str:
        scope = entity_id or "global"
        return self.redis_client.make_key(
            "auth",
            "permission-check",
            user_id,
            scope,
            permission,
        )

    async def get_permission_check(
        self,
        user_id: str,
        permission: str,
        entity_id: Optional[str] = None,
    ) -> Optional[bool]:
        if not self.redis_client or not self.redis_client.is_available:
            return None
        cached = await self.redis_client.get(
            self.make_permission_check_key(user_id, permission, entity_id)
        )
        return cached if isinstance(cached, bool) else None

    async def set_permission_check(
        self,
        user_id: str,
        permission: str,
        result: bool,
        entity_id: Optional[str] = None,
    ) -> bool:
        if not self.redis_client or not self.redis_client.is_available:
            return False
        return await self.redis_client.set(
            self.make_permission_check_key(user_id, permission, entity_id),
            result,
            ttl=self.config.cache_permission_ttl,
        )

    async def invalidate_user_permissions(self, user_id: str) -> int:
        if not self.redis_client or not self.redis_client.is_available:
            return 0
        pattern = self.redis_client.make_key("auth", "permission-check", user_id, "*")
        return await self.redis_client.delete_pattern(pattern)

    async def invalidate_entity_permissions(self, entity_id: str) -> int:
        if not self.redis_client or not self.redis_client.is_available:
            return 0
        pattern = self.redis_client.make_key(
            "auth",
            "permission-check",
            "*",
            entity_id,
            "*",
        )
        return await self.redis_client.delete_pattern(pattern)

    async def invalidate_all_permissions(self) -> int:
        if not self.redis_client or not self.redis_client.is_available:
            return 0
        pattern = self.redis_client.make_key("auth", "permission-check", "*")
        return await self.redis_client.delete_pattern(pattern)

    async def publish_user_permissions_invalidation(self, user_id: str) -> bool:
        return await self._publish(f"permissions:user:{user_id}")

    async def publish_entity_permissions_invalidation(self, entity_id: str) -> bool:
        return await self._publish(f"permissions:entity:{entity_id}")

    async def publish_all_permissions_invalidation(self) -> bool:
        return await self._publish("permissions:all")

    async def publish_role_permissions_invalidation(self, role_id: str) -> bool:
        return await self.publish_all_permissions_invalidation()

    async def _publish(self, message: str) -> bool:
        if not self.redis_client or not self.redis_client.is_available:
            return False
        return await self.redis_client.publish(
            self.config.redis_invalidation_channel,
            message,
        )

    async def start(self) -> None:
        if not self.redis_client or not self.redis_client.is_available:
            return
        if self._listener_task is not None:
            return

        self._pubsub = await self.redis_client.subscribe(
            self.config.redis_invalidation_channel
        )
        if self._pubsub is None:
            return

        self._listener_task = asyncio.create_task(self._listen())

    async def shutdown(self) -> None:
        if self._listener_task is not None:
            self._listener_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listener_task
            self._listener_task = None

        if self._pubsub is not None:
            close = getattr(self._pubsub, "close", None)
            if close is not None:
                maybe_awaitable = close()
                if asyncio.iscoroutine(maybe_awaitable):
                    await maybe_awaitable
            self._pubsub = None

    async def _listen(self) -> None:
        while True:
            message = await self._pubsub.get_message(  # type: ignore[union-attr]
                ignore_subscribe_messages=True,
                timeout=1.0,
            )
            if not message:
                await asyncio.sleep(0.1)
                continue

            payload = message.get("data")
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8")
            if isinstance(payload, str):
                await self._handle_message(payload)

    async def _handle_message(self, payload: str) -> None:
        if payload == "permissions:all":
            await self.invalidate_all_permissions()
            return

        if payload == "all:entities":
            await self.invalidate_all_permissions()
            return

        if payload.startswith("entity:") and payload.endswith(":hierarchy"):
            await self.invalidate_all_permissions()
            return

        if payload.startswith("permissions:user:"):
            await self.invalidate_user_permissions(payload.rsplit(":", 1)[-1])
            return

        if payload.startswith("permissions:entity:"):
            await self.invalidate_entity_permissions(payload.rsplit(":", 1)[-1])
