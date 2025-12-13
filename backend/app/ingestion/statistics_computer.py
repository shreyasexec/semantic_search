"""Statistics computation for pre-computed aggregations."""

import logging
from datetime import datetime, timedelta
from typing import Any

from app.services.mssql_service import MSSQLService
from app.services.milvus_service import MilvusService
from app.services.embedding_service import EmbeddingService
from app.config import get_settings

logger = logging.getLogger(__name__)


class StatisticsComputer:
    """Compute and store statistics for incident data."""

    def __init__(
        self,
        mssql: MSSQLService = None,
        milvus: MilvusService = None,
        embedding_service: EmbeddingService = None,
    ):
        self.mssql = mssql or MSSQLService()
        self.milvus = milvus or MilvusService()
        self.embedding_service = embedding_service or EmbeddingService()
        self.settings = get_settings()

    async def compute_and_store(self, tenant_id: str) -> dict:
        """Compute and store all statistics.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Statistics summary
        """
        logger.info(f"Computing statistics for tenant {tenant_id}")

        stats = []

        # Daily statistics
        daily_stats = await self._compute_daily_stats(tenant_id)
        stats.extend(daily_stats)

        # Weekly statistics
        weekly_stats = await self._compute_weekly_stats(tenant_id)
        stats.extend(weekly_stats)

        # Category statistics
        category_stats = await self._compute_category_stats(tenant_id)
        stats.extend(category_stats)

        # Store all statistics
        if stats:
            await self._store_statistics(stats, tenant_id)

        logger.info(f"Computed and stored {len(stats)} statistics records")

        return {"count": len(stats)}

    async def _compute_daily_stats(self, tenant_id: str) -> list[dict]:
        """Compute daily statistics.

        Args:
            tenant_id: Tenant identifier

        Returns:
            List of daily stat records
        """
        stats = []
        today = datetime.now().date()

        # Last 7 days
        for i in range(7):
            date = today - timedelta(days=i)
            start = datetime.combine(date, datetime.min.time())
            end = datetime.combine(date, datetime.max.time())

            # Get counts
            try:
                results = self.mssql.execute(f"""
                    SELECT
                        COUNT(*) as total,
                        COUNT(CASE WHEN severity = 'critical' THEN 1 END) as critical,
                        COUNT(CASE WHEN severity = 'high' THEN 1 END) as high,
                        COUNT(CASE WHEN status = 'resolved' THEN 1 END) as resolved
                    FROM {self.mssql.settings.table}
                    WHERE created_at BETWEEN ? AND ?
                """, (start, end))

                if results:
                    row = results[0]

                    description = (
                        f"Daily statistics for {date.isoformat()}: "
                        f"{row['total']} total incidents, "
                        f"{row['critical']} critical, "
                        f"{row['high']} high priority, "
                        f"{row['resolved']} resolved."
                    )

                    stats.append({
                        "id": f"daily_{date.isoformat()}_{tenant_id}",
                        "stat_type": "daily_count",
                        "stat_date": date.isoformat(),
                        "period": "daily",
                        "aggregations": {
                            "total": row["total"],
                            "critical": row["critical"],
                            "high": row["high"],
                            "resolved": row["resolved"],
                        },
                        "description": description,
                    })

            except Exception as e:
                logger.warning(f"Failed to compute daily stats for {date}: {e}")

        return stats

    async def _compute_weekly_stats(self, tenant_id: str) -> list[dict]:
        """Compute weekly statistics.

        Args:
            tenant_id: Tenant identifier

        Returns:
            List of weekly stat records
        """
        stats = []
        today = datetime.now().date()

        # Current week
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        start_dt = datetime.combine(week_start, datetime.min.time())
        end_dt = datetime.combine(week_end, datetime.max.time())

        try:
            # Get counts by type
            type_results = self.mssql.get_aggregations(
                "incident_type",
                (start_dt, end_dt),
            )

            # Get counts by location
            location_results = self.mssql.get_aggregations(
                "location",
                (start_dt, end_dt),
            )

            # Total count
            total = sum(r.get("count", 0) for r in type_results)

            description = (
                f"Weekly statistics from {week_start} to {week_end}: "
                f"{total} total incidents. "
                f"Top types: {', '.join([f'{r.get(\"group_value\", \"Unknown\")}: {r.get(\"count\", 0)}' for r in type_results[:3]])}."
            )

            stats.append({
                "id": f"weekly_{week_start.isoformat()}_{tenant_id}",
                "stat_type": "weekly_summary",
                "stat_date": week_start.isoformat(),
                "period": "weekly",
                "aggregations": {
                    "total": total,
                    "by_type": {
                        r.get("group_value", "unknown"): r.get("count", 0)
                        for r in type_results
                    },
                    "by_location": {
                        r.get("group_value", "unknown"): r.get("count", 0)
                        for r in location_results[:10]
                    },
                },
                "description": description,
            })

        except Exception as e:
            logger.warning(f"Failed to compute weekly stats: {e}")

        return stats

    async def _compute_category_stats(self, tenant_id: str) -> list[dict]:
        """Compute statistics by category.

        Args:
            tenant_id: Tenant identifier

        Returns:
            List of category stat records
        """
        stats = []

        categories = [
            ("incident_type", "type"),
            ("severity", "severity"),
            ("status", "status"),
        ]

        for column, stat_name in categories:
            try:
                results = self.mssql.get_aggregations(column)

                if results:
                    total = sum(r.get("count", 0) for r in results)

                    top_items = [
                        f"{r.get('group_value', 'Unknown')}: {r.get('count', 0)}"
                        for r in results[:5]
                    ]

                    description = (
                        f"Incident statistics by {stat_name}. "
                        f"Total: {total}. "
                        f"Distribution: {', '.join(top_items)}."
                    )

                    stats.append({
                        "id": f"category_{stat_name}_{tenant_id}",
                        "stat_type": f"by_{stat_name}",
                        "stat_date": datetime.now().date().isoformat(),
                        "period": "all_time",
                        "aggregations": {
                            "total": total,
                            "distribution": {
                                r.get("group_value", "unknown"): r.get("count", 0)
                                for r in results
                            },
                        },
                        "description": description,
                    })

            except Exception as e:
                logger.warning(f"Failed to compute {stat_name} stats: {e}")

        return stats

    async def _store_statistics(
        self,
        stats: list[dict],
        tenant_id: str,
    ) -> None:
        """Store statistics in Milvus.

        Args:
            stats: List of statistics records
            tenant_id: Tenant identifier
        """
        # Generate embeddings for descriptions
        descriptions = [s["description"] for s in stats]
        embeddings = await self.embedding_service.embed_batch(descriptions)

        # Prepare entities
        entities = []
        for stat, embedding in zip(stats, embeddings):
            entities.append({
                "id": stat["id"],
                "tenant_id": tenant_id,
                "stat_type": stat["stat_type"],
                "stat_date": stat["stat_date"],
                "period": stat["period"],
                "aggregations": stat["aggregations"],
                "description": stat["description"],
                "embedding": embedding,
                "updated_at": int(datetime.now().timestamp()),
            })

        # Upsert to Milvus
        await self.milvus.upsert(
            collection_name=self.settings.milvus.collection_stats,
            entities=entities,
            partition_name=tenant_id,
        )
