"""
API Key Usage Counter Sync Worker

Background worker that syncs API key usage counters from Redis to PostgreSQL.
Runs every 5 minutes (configurable) to implement the Redis counter pattern.

This reduces primary-database writes by 99%+ for high-traffic API keys.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from outlabs_auth.services.api_key import APIKeyService
from outlabs_auth.core.config import AuthConfig

logger = logging.getLogger(__name__)


class APIKeyUsageSyncWorker:
    """
    Background worker for syncing API key usage from Redis to PostgreSQL.

    Features:
    - Runs on configurable interval (default: 5 minutes)
    - Graceful shutdown
    - Error handling and retry logic
    - Performance metrics logging

    Example:
        >>> worker = APIKeyUsageSyncWorker(
        ...     api_key_service=api_key_service,
        ...     config=config,
        ...     interval_seconds=300  # 5 minutes
        ... )
        >>> await worker.start()  # Runs in background
        >>> # ... later ...
        >>> await worker.stop()  # Graceful shutdown
    """

    def __init__(
        self,
        api_key_service: APIKeyService,
        config: AuthConfig,
        session_factory: Optional[async_sessionmaker[AsyncSession]] = None,
        interval_seconds: int = 300,  # 5 minutes
    ):
        """
        Initialize sync worker.

        Args:
            api_key_service: APIKeyService instance
            config: AuthConfig instance
            session_factory: Session factory used for sync DB writes
            interval_seconds: Sync interval in seconds (default: 300 = 5min)
        """
        self.api_key_service = api_key_service
        self.config = config
        self.session_factory = session_factory
        self.interval_seconds = interval_seconds
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._running = False

    def _require_session_factory(self) -> async_sessionmaker[AsyncSession]:
        if self.session_factory is None:
            raise RuntimeError("APIKeyUsageSyncWorker requires a session_factory")
        return self.session_factory

    async def start(self) -> None:
        """
        Start the background sync worker.

        This method returns immediately - the worker runs in the background.

        Example:
            >>> await worker.start()
            >>> logger.info("Worker started")
        """
        if self._running:
            logger.warning("Sync worker already running")
            return

        self._running = True
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run())

        logger.info(f"API key usage sync worker started " f"(interval: {self.interval_seconds}s)")

    async def stop(self) -> None:
        """
        Stop the background sync worker gracefully.

        Waits for current sync to complete before stopping.

        Example:
            >>> await worker.stop()
            >>> logger.info("Worker stopped")
        """
        if not self._running:
            logger.warning("Sync worker not running")
            return

        logger.info("Stopping API key usage sync worker...")

        self._stop_event.set()

        if self._task:
            await self._task

        self._running = False
        logger.info("API key usage sync worker stopped")

    async def _run(self) -> None:
        """
        Main worker loop.

        Runs sync on interval until stopped.
        """
        logger.info("API key usage sync worker loop started")

        while not self._stop_event.is_set():
            try:
                # Run sync
                await self._sync_once()

                # Wait for next interval (or until stopped)
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=self.interval_seconds)
                    # If we reach here, stop was requested
                    break
                except asyncio.TimeoutError:
                    # Timeout means it's time for next sync
                    continue

            except asyncio.CancelledError:
                logger.info("Sync worker cancelled")
                break
            except Exception as e:
                logger.error(f"Unexpected error in sync worker: {e}", exc_info=True)
                # Wait a bit before retrying after error
                await asyncio.sleep(10)

        logger.info("API key usage sync worker loop ended")

    async def _sync_once(self) -> None:
        """
        Run one sync cycle.

        Logs performance metrics and errors.
        """
        start_time = datetime.now()

        try:
            logger.debug("Starting API key usage counter sync cycle...")

            async with self._require_session_factory()() as session:
                stats = await self.api_key_service.sync_usage_counters_to_db(session)

            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000

            if stats["synced_keys"] > 0:
                logger.info(
                    f"✓ Synced {stats['synced_keys']} API keys "
                    f"({stats['total_usage']} total uses) "
                    f"in {elapsed_ms:.0f}ms"
                )
            else:
                logger.debug(f"No API key usage to sync (elapsed: {elapsed_ms:.0f}ms)")

            if stats["errors"] > 0:
                logger.warning(f"Sync completed with {stats['errors']} errors")

        except Exception as e:
            logger.error(f"Error during sync cycle: {e}", exc_info=True)

    async def sync_now(self) -> dict:
        """
        Trigger an immediate sync (useful for testing or manual operations).

        Returns:
            dict: Sync stats

        Example:
            >>> stats = await worker.sync_now()
            >>> print(f"Synced {stats['synced_keys']} keys")
        """
        logger.info("Manual sync triggered")
        async with self._require_session_factory()() as session:
            return await self.api_key_service.sync_usage_counters_to_db(session)

    @property
    def is_running(self) -> bool:
        """Check if worker is currently running."""
        return self._running


# Standalone function for simple usage


async def start_api_key_sync_worker(
    api_key_service: APIKeyService,
    config: AuthConfig,
    session_factory: Optional[async_sessionmaker[AsyncSession]] = None,
    interval_seconds: int = 300,
) -> APIKeyUsageSyncWorker:
    """
    Convenience function to start the API key sync worker.

    Args:
        api_key_service: APIKeyService instance
        config: AuthConfig instance
        session_factory: Session factory used for sync DB writes
        interval_seconds: Sync interval in seconds

    Returns:
        APIKeyUsageSyncWorker: Running worker instance

    Example:
        >>> worker = await start_api_key_sync_worker(
        ...     api_key_service,
        ...     config,
        ...     session_factory=session_factory,
        ...     interval_seconds=300
        ... )
        >>> # Worker is now running in background
        >>> # ... later ...
        >>> await worker.stop()
    """
    worker = APIKeyUsageSyncWorker(
        api_key_service=api_key_service,
        config=config,
        session_factory=session_factory,
        interval_seconds=interval_seconds,
    )

    await worker.start()

    return worker
