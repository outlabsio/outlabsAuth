"""
Redis-backed cache service for permission checks.
"""

import asyncio
import contextlib
from typing import Any, Optional, cast

from outlabs_auth.core.config import AuthConfig


class CacheService:
    """Manages cached RBAC permission checks and invalidation broadcasts."""

    def __init__(self, redis_client, config: AuthConfig):
        self.redis_client = redis_client
        self.config = config
        self._pubsub: Any = None
        self._listener_task: Optional[asyncio.Task[None]] = None

    def make_permission_check_key(
        self,
        user_id: str,
        permission: str,
        entity_id: Optional[str] = None,
    ) -> str:
        scope = entity_id or "global"
        return str(
            self.redis_client.make_key(
                "auth",
                "permission-check",
                user_id,
                scope,
                permission,
            )
        )

    def make_entity_relation_key(
        self,
        ancestor_id: str,
        descendant_id: str,
        *,
        version: int = 0,
    ) -> str:
        return str(
            self.redis_client.make_key(
                "auth",
                "entity-relation",
                str(version),
                ancestor_id,
                descendant_id,
            )
        )

    def make_api_key_auth_snapshot_version_key(
        self,
        scope: str,
        subject_id: Optional[str] = None,
    ) -> str:
        parts = ["auth", "api-key-snapshot-version", scope]
        if subject_id is not None:
            parts.append(subject_id)
        return str(self.redis_client.make_key(*parts))

    async def get_api_key_auth_snapshot_versions(
        self,
        *,
        user_id: Optional[str] = None,
        integration_principal_id: Optional[str] = None,
        entity_id: Optional[str] = None,
    ) -> dict[str, int]:
        if not self.redis_client or not self.redis_client.is_available:
            return {}

        versions = {
            "global": await self._get_version("global"),
        }
        if user_id:
            versions[f"user:{user_id}"] = await self._get_version("user", user_id)
        if integration_principal_id:
            versions[f"integration_principal:{integration_principal_id}"] = await self._get_version(
                "integration_principal",
                integration_principal_id,
            )
        if entity_id:
            versions[f"entity:{entity_id}"] = await self._get_version("entity", entity_id)
        return versions

    async def bump_api_key_auth_snapshot_version(
        self,
        scope: str,
        subject_id: Optional[str] = None,
    ) -> int:
        if not self.redis_client or not self.redis_client.is_available:
            return 0
        key = self.make_api_key_auth_snapshot_version_key(scope, subject_id)
        value = await self.redis_client.increment(key, amount=1)
        return int(value or 0)

    async def bump_global_api_key_auth_snapshot_version(self) -> int:
        return await self.bump_api_key_auth_snapshot_version("global")

    async def bump_user_api_key_auth_snapshot_version(self, user_id: str) -> int:
        return await self.bump_api_key_auth_snapshot_version("user", user_id)

    async def bump_integration_principal_api_key_auth_snapshot_version(
        self,
        integration_principal_id: str,
    ) -> int:
        return await self.bump_api_key_auth_snapshot_version(
            "integration_principal",
            integration_principal_id,
        )

    async def bump_entity_api_key_auth_snapshot_version(self, entity_id: str) -> int:
        return await self.bump_api_key_auth_snapshot_version("entity", entity_id)

    async def _get_version(self, scope: str, subject_id: Optional[str] = None) -> int:
        key = self.make_api_key_auth_snapshot_version_key(scope, subject_id)
        get_counter = getattr(self.redis_client, "get_counter", None)
        if get_counter is not None:
            return int(await get_counter(key))

        value = await self.redis_client.get(key)
        if value is None:
            return 0
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

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
        return bool(
            await self.redis_client.set(
                self.make_permission_check_key(user_id, permission, entity_id),
                result,
                ttl=self.config.cache_permission_ttl,
            )
        )

    async def get_entity_relation(
        self,
        ancestor_id: str,
        descendant_id: str,
        *,
        version: int = 0,
    ) -> Optional[bool]:
        if not self.redis_client or not self.redis_client.is_available:
            return None
        cached = await self.redis_client.get(
            self.make_entity_relation_key(
                ancestor_id,
                descendant_id,
                version=version,
            )
        )
        return cached if isinstance(cached, bool) else None

    async def set_entity_relation(
        self,
        ancestor_id: str,
        descendant_id: str,
        result: bool,
        *,
        version: int = 0,
    ) -> bool:
        if not self.redis_client or not self.redis_client.is_available:
            return False
        return bool(
            await self.redis_client.set(
                self.make_entity_relation_key(
                    ancestor_id,
                    descendant_id,
                    version=version,
                ),
                result,
                ttl=self.config.cache_entity_ttl,
            )
        )

    async def invalidate_user_permissions(self, user_id: str) -> int:
        if not self.redis_client or not self.redis_client.is_available:
            return 0
        pattern = self.redis_client.make_key("auth", "permission-check", user_id, "*")
        return int(await self.redis_client.delete_pattern(pattern))

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
        return int(await self.redis_client.delete_pattern(pattern))

    async def invalidate_all_permissions(self) -> int:
        if not self.redis_client or not self.redis_client.is_available:
            return 0
        pattern = self.redis_client.make_key("auth", "permission-check", "*")
        return int(await self.redis_client.delete_pattern(pattern))

    async def publish_user_permissions_invalidation(self, user_id: str) -> bool:
        await self.bump_user_api_key_auth_snapshot_version(user_id)
        return bool(await self._publish(f"permissions:user:{user_id}"))

    async def publish_entity_permissions_invalidation(self, entity_id: str) -> bool:
        await self.bump_entity_api_key_auth_snapshot_version(entity_id)
        return bool(await self._publish(f"permissions:entity:{entity_id}"))

    async def publish_all_permissions_invalidation(self) -> bool:
        await self.bump_global_api_key_auth_snapshot_version()
        return bool(await self._publish("permissions:all"))

    async def publish_role_permissions_invalidation(self, role_id: str) -> bool:
        return bool(await self.publish_all_permissions_invalidation())

    async def _publish(self, message: str) -> bool:
        if not self.redis_client or not self.redis_client.is_available:
            return False
        return bool(
            await self.redis_client.publish(
                self.config.redis_invalidation_channel,
                message,
            )
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
        if self._pubsub is None:
            return

        while True:
            pubsub = cast(Any, self._pubsub)
            message = await pubsub.get_message(
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
