"""Milvus collection management and loading utilities."""

import logging
from typing import Any

from app.services.milvus_service import MilvusService
from app.config import get_settings

logger = logging.getLogger(__name__)


class MilvusLoader:
    """Utility for managing Milvus collections."""

    def __init__(self):
        self.milvus = MilvusService()
        self.settings = get_settings()

    def setup_collections(self) -> dict:
        """Create all required collections.

        Returns:
            Creation status
        """
        logger.info("Setting up Milvus collections")

        results = {}

        try:
            # Create entities collection
            self.milvus.create_entities_collection()
            results["entities"] = "created"
        except Exception as e:
            logger.error(f"Failed to create entities collection: {e}")
            results["entities"] = f"error: {e}"

        try:
            # Create schema metadata collection
            self.milvus.create_schema_collection()
            results["schema_metadata"] = "created"
        except Exception as e:
            logger.error(f"Failed to create schema collection: {e}")
            results["schema_metadata"] = f"error: {e}"

        try:
            # Create statistics collection
            self.milvus.create_statistics_collection()
            results["statistics"] = "created"
        except Exception as e:
            logger.error(f"Failed to create statistics collection: {e}")
            results["statistics"] = f"error: {e}"

        logger.info(f"Collection setup complete: {results}")
        return results

    def create_partitions(self, tenant_ids: list[str]) -> dict:
        """Create partitions for tenants.

        Args:
            tenant_ids: List of tenant identifiers

        Returns:
            Creation status
        """
        logger.info(f"Creating partitions for tenants: {tenant_ids}")

        results = {}
        collection_names = [
            self.settings.milvus.collection_entities,
            self.settings.milvus.collection_schema,
            self.settings.milvus.collection_stats,
        ]

        for tenant_id in tenant_ids:
            tenant_results = {}

            for collection_name in collection_names:
                try:
                    collection = self.milvus.get_collection(collection_name)

                    if tenant_id not in [p.name for p in collection.partitions]:
                        collection.create_partition(tenant_id)
                        tenant_results[collection_name] = "created"
                    else:
                        tenant_results[collection_name] = "exists"

                except Exception as e:
                    logger.error(
                        f"Failed to create partition {tenant_id} in {collection_name}: {e}"
                    )
                    tenant_results[collection_name] = f"error: {e}"

            results[tenant_id] = tenant_results

        return results

    def get_collection_stats(self) -> dict:
        """Get statistics for all collections.

        Returns:
            Collection statistics
        """
        stats = {}
        collection_names = [
            self.settings.milvus.collection_entities,
            self.settings.milvus.collection_schema,
            self.settings.milvus.collection_stats,
        ]

        for name in collection_names:
            try:
                collection = self.milvus.get_collection(name)
                collection.flush()

                stats[name] = {
                    "num_entities": collection.num_entities,
                    "partitions": [p.name for p in collection.partitions],
                }
            except Exception as e:
                stats[name] = {"error": str(e)}

        return stats

    def drop_collection(self, name: str) -> bool:
        """Drop a collection.

        Args:
            name: Collection name

        Returns:
            True if successful
        """
        from pymilvus import utility

        try:
            self.milvus.ensure_connected()
            utility.drop_collection(name)
            logger.info(f"Dropped collection: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to drop collection {name}: {e}")
            return False

    def reset_collections(self) -> dict:
        """Drop and recreate all collections.

        WARNING: This will delete all data!

        Returns:
            Reset status
        """
        logger.warning("Resetting all Milvus collections - all data will be deleted!")

        collection_names = [
            self.settings.milvus.collection_entities,
            self.settings.milvus.collection_schema,
            self.settings.milvus.collection_stats,
        ]

        # Drop collections
        for name in collection_names:
            self.drop_collection(name)

        # Recreate collections
        return self.setup_collections()


async def setup_milvus(tenant_ids: list[str] = None) -> dict:
    """Setup Milvus collections and partitions.

    Args:
        tenant_ids: Optional list of tenant IDs to create partitions for

    Returns:
        Setup results
    """
    loader = MilvusLoader()

    results = {
        "collections": loader.setup_collections(),
    }

    if tenant_ids:
        results["partitions"] = loader.create_partitions(tenant_ids)

    return results
