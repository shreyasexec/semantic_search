"""Ingestion scheduler for periodic data sync."""

import logging
from datetime import datetime, timedelta
from typing import Callable, Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from app.config import get_settings
from app.ingestion.mssql_extractor import MSSQLIngestion
from app.ingestion.neo4j_enhancer import Neo4jEnhancer
from app.services.cache_service import CacheService

logger = logging.getLogger(__name__)


class IngestionScheduler:
    """Scheduler for data ingestion jobs."""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.settings = get_settings()
        self._last_sync: dict[str, datetime] = {}
        self._cache = CacheService()

    async def start(self, tenant_ids: list[str] = None) -> None:
        """Start the ingestion scheduler.

        Args:
            tenant_ids: List of tenant IDs to schedule jobs for
        """
        logger.info("Starting ingestion scheduler")

        tenant_ids = tenant_ids or ["tenant_001", "tenant_002", "tenant_003", "tenant_004"]

        # Schedule MSSQL sync for each tenant
        for tenant_id in tenant_ids:
            self._schedule_mssql_sync(tenant_id)

        # Schedule Neo4j enhancement (less frequent)
        self._schedule_neo4j_enhancement()

        # Schedule statistics refresh
        self._schedule_statistics_refresh(tenant_ids)

        # Start scheduler
        self.scheduler.start()
        logger.info("Ingestion scheduler started")

    def stop(self) -> None:
        """Stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Ingestion scheduler stopped")

    def _schedule_mssql_sync(self, tenant_id: str) -> None:
        """Schedule MSSQL sync job for a tenant.

        Args:
            tenant_id: Tenant identifier
        """
        interval = self.settings.app.ingestion_interval_minutes

        self.scheduler.add_job(
            self._run_mssql_sync,
            trigger=IntervalTrigger(minutes=interval),
            args=[tenant_id],
            id=f"mssql_sync_{tenant_id}",
            name=f"MSSQL Sync - {tenant_id}",
            replace_existing=True,
        )

        logger.info(f"Scheduled MSSQL sync for {tenant_id} every {interval} minutes")

    def _schedule_neo4j_enhancement(self) -> None:
        """Schedule Neo4j enhancement job."""
        # Run every hour
        self.scheduler.add_job(
            self._run_neo4j_enhancement,
            trigger=IntervalTrigger(hours=1),
            id="neo4j_enhancement",
            name="Neo4j Enhancement",
            replace_existing=True,
        )

        logger.info("Scheduled Neo4j enhancement every hour")

    def _schedule_statistics_refresh(self, tenant_ids: list[str]) -> None:
        """Schedule statistics refresh.

        Args:
            tenant_ids: List of tenant IDs
        """
        # Run daily at midnight
        self.scheduler.add_job(
            self._run_statistics_refresh,
            trigger=CronTrigger(hour=0, minute=0),
            args=[tenant_ids],
            id="statistics_refresh",
            name="Statistics Refresh",
            replace_existing=True,
        )

        logger.info("Scheduled statistics refresh at midnight")

    async def _run_mssql_sync(self, tenant_id: str) -> None:
        """Run MSSQL sync job.

        Args:
            tenant_id: Tenant identifier
        """
        logger.info(f"Starting MSSQL sync for {tenant_id}")

        try:
            # Get last sync time
            last_sync = await self._get_last_sync(tenant_id)

            # Run sync
            ingestion = MSSQLIngestion()
            result = await ingestion.run_incremental_sync(tenant_id, last_sync)

            # Update last sync time
            await self._set_last_sync(tenant_id)

            logger.info(f"MSSQL sync complete for {tenant_id}: {result}")

        except Exception as e:
            logger.error(f"MSSQL sync failed for {tenant_id}: {e}")

    async def _run_neo4j_enhancement(self) -> None:
        """Run Neo4j enhancement job."""
        logger.info("Starting Neo4j enhancement")

        try:
            enhancer = Neo4jEnhancer()
            result = await enhancer.enhance_new_nodes()
            logger.info(f"Neo4j enhancement complete: {result}")

        except Exception as e:
            logger.error(f"Neo4j enhancement failed: {e}")

    async def _run_statistics_refresh(self, tenant_ids: list[str]) -> None:
        """Run statistics refresh for all tenants.

        Args:
            tenant_ids: List of tenant IDs
        """
        logger.info("Starting statistics refresh")

        from app.ingestion.statistics_computer import StatisticsComputer

        for tenant_id in tenant_ids:
            try:
                computer = StatisticsComputer()
                await computer.compute_and_store(tenant_id)
                logger.info(f"Statistics refreshed for {tenant_id}")

            except Exception as e:
                logger.error(f"Statistics refresh failed for {tenant_id}: {e}")

    async def _get_last_sync(self, tenant_id: str) -> datetime:
        """Get last sync timestamp for tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Last sync datetime
        """
        # Try cache
        await self._cache.connect()
        cached = await self._cache.get(f"last_sync:{tenant_id}")

        if cached:
            return datetime.fromisoformat(cached)

        # Try memory
        if tenant_id in self._last_sync:
            return self._last_sync[tenant_id]

        # Default to 1 day ago
        return datetime.now() - timedelta(days=1)

    async def _set_last_sync(self, tenant_id: str) -> None:
        """Set last sync timestamp for tenant.

        Args:
            tenant_id: Tenant identifier
        """
        now = datetime.now()

        # Save to memory
        self._last_sync[tenant_id] = now

        # Save to cache
        await self._cache.set(
            f"last_sync:{tenant_id}",
            now.isoformat(),
            ttl=86400,  # 24 hours
        )

    async def run_manual_sync(
        self,
        tenant_id: str,
        full: bool = False,
    ) -> dict:
        """Run manual sync for a tenant.

        Args:
            tenant_id: Tenant identifier
            full: Whether to run full sync

        Returns:
            Sync results
        """
        logger.info(f"Running manual sync for {tenant_id} (full={full})")

        ingestion = MSSQLIngestion()

        if full:
            result = await ingestion.run_full_sync(tenant_id)
        else:
            last_sync = await self._get_last_sync(tenant_id)
            result = await ingestion.run_incremental_sync(tenant_id, last_sync)

        await self._set_last_sync(tenant_id)

        return result


# Global scheduler instance
_scheduler: IngestionScheduler = None


def get_scheduler() -> IngestionScheduler:
    """Get or create scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = IngestionScheduler()
    return _scheduler
