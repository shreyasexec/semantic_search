"""Milvus vector database service for incident data."""

import logging
from typing import Any, Optional
from datetime import datetime

from pymilvus import (
    connections,
    Collection,
    CollectionSchema,
    FieldSchema,
    DataType,
    utility,
)

from app.config import get_settings

logger = logging.getLogger(__name__)


class MilvusService:
    """Service for Milvus vector database operations."""

    _connected: bool = False

    def __init__(self):
        self.settings = get_settings().milvus
        self.app_settings = get_settings().app

    def connect(self) -> None:
        """Establish connection to Milvus."""
        if not self._connected:
            connections.connect(
                alias="default",
                host=self.settings.host,
                port=self.settings.port,
            )
            self._connected = True
            logger.info(f"Connected to Milvus at {self.settings.host}:{self.settings.port}")

    def close(self) -> None:
        """Close Milvus connection."""
        if self._connected:
            connections.disconnect("default")
            self._connected = False
            logger.info("Closed Milvus connection")

    def ensure_connected(self) -> None:
        """Ensure connection is established."""
        if not self._connected:
            self.connect()

    def create_entities_collection(self) -> Collection:
        """Create the entities collection for incident chunks.

        Returns:
            Created or existing Collection
        """
        self.ensure_connected()

        collection_name = self.settings.collection_entities

        if utility.has_collection(collection_name):
            logger.info(f"Collection {collection_name} already exists")
            return Collection(collection_name)

        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=100, is_primary=True),
            FieldSchema(name="tenant_id", dtype=DataType.VARCHAR, max_length=50, is_partition_key=True),
            FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=20),
            FieldSchema(name="entity_type", dtype=DataType.VARCHAR, max_length=50),
            FieldSchema(name="incident_id", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="chunk_type", dtype=DataType.VARCHAR, max_length=50),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="properties", dtype=DataType.JSON),
            FieldSchema(name="location_hierarchy", dtype=DataType.JSON),
            FieldSchema(name="created_at", dtype=DataType.INT64),
            FieldSchema(name="updated_at", dtype=DataType.INT64),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.app_settings.embedding_dimension),
        ]

        schema = CollectionSchema(fields=fields, description="Incident entity chunks")
        collection = Collection(name=collection_name, schema=schema)

        # Create HNSW index
        index_params = {
            "metric_type": "COSINE",
            "index_type": "HNSW",
            "params": {
                "M": self.settings.hnsw_m,
                "efConstruction": self.settings.hnsw_ef_construction,
            },
        }
        collection.create_index(field_name="embedding", index_params=index_params)

        logger.info(f"Created collection {collection_name} with HNSW index")
        return collection

    def create_schema_collection(self) -> Collection:
        """Create the schema metadata collection.

        Returns:
            Created or existing Collection
        """
        self.ensure_connected()

        collection_name = self.settings.collection_schema

        if utility.has_collection(collection_name):
            return Collection(collection_name)

        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=100, is_primary=True),
            FieldSchema(name="tenant_id", dtype=DataType.VARCHAR, max_length=50, is_partition_key=True),
            FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=20),
            FieldSchema(name="entity_types", dtype=DataType.JSON),
            FieldSchema(name="properties_by_type", dtype=DataType.JSON),
            FieldSchema(name="sample_values", dtype=DataType.JSON),
            FieldSchema(name="location_fields", dtype=DataType.JSON),
            FieldSchema(name="status_fields", dtype=DataType.JSON),
            FieldSchema(name="time_fields", dtype=DataType.JSON),
            FieldSchema(name="description", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.app_settings.embedding_dimension),
            FieldSchema(name="updated_at", dtype=DataType.INT64),
        ]

        schema = CollectionSchema(fields=fields, description="Schema metadata")
        collection = Collection(name=collection_name, schema=schema)

        index_params = {
            "metric_type": "COSINE",
            "index_type": "HNSW",
            "params": {"M": 8, "efConstruction": 64},
        }
        collection.create_index(field_name="embedding", index_params=index_params)

        logger.info(f"Created collection {collection_name}")
        return collection

    def create_assets_collection(self) -> Collection:
        """Create the assets collection for Neo4j node embeddings.

        Since Neo4j is transactional and cannot store embeddings efficiently,
        we store asset embeddings in Milvus for vector search.

        Returns:
            Created or existing Collection
        """
        self.ensure_connected()

        collection_name = self.settings.collection_assets

        if utility.has_collection(collection_name):
            logger.info(f"Collection {collection_name} already exists")
            return Collection(collection_name)

        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=100, is_primary=True),
            FieldSchema(name="tenant_id", dtype=DataType.VARCHAR, max_length=50, is_partition_key=True),
            FieldSchema(name="neo4j_node_id", dtype=DataType.INT64),
            FieldSchema(name="label", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="name", dtype=DataType.VARCHAR, max_length=500),
            FieldSchema(name="description", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="properties", dtype=DataType.JSON),
            FieldSchema(name="location", dtype=DataType.VARCHAR, max_length=500),
            FieldSchema(name="status", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="updated_at", dtype=DataType.INT64),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.app_settings.embedding_dimension),
        ]

        schema = CollectionSchema(fields=fields, description="Neo4j asset embeddings")
        collection = Collection(name=collection_name, schema=schema)

        # Create HNSW index
        index_params = {
            "metric_type": "COSINE",
            "index_type": "HNSW",
            "params": {
                "M": self.settings.hnsw_m,
                "efConstruction": self.settings.hnsw_ef_construction,
            },
        }
        collection.create_index(field_name="embedding", index_params=index_params)

        logger.info(f"Created collection {collection_name} with HNSW index")
        return collection

    def create_statistics_collection(self) -> Collection:
        """Create the statistics collection.

        Returns:
            Created or existing Collection
        """
        self.ensure_connected()

        collection_name = self.settings.collection_stats

        if utility.has_collection(collection_name):
            return Collection(collection_name)

        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=100, is_primary=True),
            FieldSchema(name="tenant_id", dtype=DataType.VARCHAR, max_length=50, is_partition_key=True),
            FieldSchema(name="stat_type", dtype=DataType.VARCHAR, max_length=50),
            FieldSchema(name="stat_date", dtype=DataType.VARCHAR, max_length=20),
            FieldSchema(name="period", dtype=DataType.VARCHAR, max_length=20),
            FieldSchema(name="aggregations", dtype=DataType.JSON),
            FieldSchema(name="description", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.app_settings.embedding_dimension),
            FieldSchema(name="updated_at", dtype=DataType.INT64),
        ]

        schema = CollectionSchema(fields=fields, description="Pre-computed statistics")
        collection = Collection(name=collection_name, schema=schema)

        index_params = {
            "metric_type": "COSINE",
            "index_type": "HNSW",
            "params": {"M": 8, "efConstruction": 64},
        }
        collection.create_index(field_name="embedding", index_params=index_params)

        logger.info(f"Created collection {collection_name}")
        return collection

    def get_collection(self, name: str) -> Collection:
        """Get a collection by name."""
        self.ensure_connected()
        return Collection(name)

    async def search(
        self,
        collection_name: str,
        query_vector: list[float],
        filter_expr: str = "",
        output_fields: Optional[list[str]] = None,
        limit: int = 20,
        partition_names: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """Perform vector similarity search.

        Args:
            collection_name: Name of the collection
            query_vector: Query embedding vector
            filter_expr: Optional filter expression
            output_fields: Fields to return
            limit: Maximum results
            partition_names: Partitions to search

        Returns:
            List of search results
        """
        self.ensure_connected()

        collection = Collection(collection_name)
        collection.load()

        search_params = {
            "metric_type": "COSINE",
            "params": {"ef": self.settings.hnsw_ef_search},
        }

        if output_fields is None or output_fields == ["*"]:
            output_fields = [
                "id", "tenant_id", "source", "entity_type", "incident_id",
                "chunk_type", "content", "properties", "created_at",
            ]

        results = collection.search(
            data=[query_vector],
            anns_field="embedding",
            param=search_params,
            limit=limit,
            expr=filter_expr if filter_expr else None,
            output_fields=output_fields,
            partition_names=partition_names,
        )

        formatted_results = []
        for hits in results:
            for hit in hits:
                result = {
                    "id": hit.id,
                    "score": hit.score,
                }
                for field in output_fields:
                    if hasattr(hit.entity, field):
                        result[field] = getattr(hit.entity, field)
                formatted_results.append(result)

        return formatted_results

    async def upsert(
        self,
        collection_name: str,
        entities: list[dict[str, Any]],
        partition_name: Optional[str] = None,
    ) -> int:
        """Upsert entities into collection.

        Args:
            collection_name: Name of the collection
            entities: List of entities to upsert
            partition_name: Optional partition name

        Returns:
            Number of entities upserted
        """
        self.ensure_connected()

        collection = Collection(collection_name)

        # Create partition if needed
        if partition_name and partition_name not in collection.partitions:
            collection.create_partition(partition_name)

        # Prepare data for insertion
        data = []
        for entity in entities:
            data.append(entity)

        collection.upsert(data, partition_name=partition_name)
        collection.flush()

        logger.info(f"Upserted {len(entities)} entities to {collection_name}")
        return len(entities)

    async def delete(
        self,
        collection_name: str,
        filter_expr: str,
        partition_name: Optional[str] = None,
    ) -> int:
        """Delete entities matching filter.

        Args:
            collection_name: Name of the collection
            filter_expr: Filter expression for deletion
            partition_name: Optional partition name

        Returns:
            Number of entities deleted
        """
        self.ensure_connected()

        collection = Collection(collection_name)
        result = collection.delete(filter_expr, partition_name=partition_name)

        logger.info(f"Deleted entities from {collection_name} with filter: {filter_expr}")
        return result.delete_count

    async def get_schema_metadata(self, tenant_id: str) -> Optional[dict]:
        """Get schema metadata for a tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Schema metadata or None
        """
        self.ensure_connected()

        collection = Collection(self.settings.collection_schema)
        collection.load()

        results = collection.query(
            expr=f'tenant_id == "{tenant_id}" AND source == "mssql"',
            output_fields=["*"],
            limit=1,
        )

        if results:
            return results[0]
        return None

    async def get_statistics(
        self,
        tenant_id: str,
        stat_type: str,
        period: str = "daily",
    ) -> list[dict]:
        """Get pre-computed statistics.

        Args:
            tenant_id: Tenant identifier
            stat_type: Type of statistic
            period: Time period

        Returns:
            List of statistics
        """
        self.ensure_connected()

        collection = Collection(self.settings.collection_stats)
        collection.load()

        results = collection.query(
            expr=f'tenant_id == "{tenant_id}" AND stat_type == "{stat_type}" AND period == "{period}"',
            output_fields=["*"],
            limit=100,
        )

        return results

    async def search_assets(
        self,
        query_vector: list[float],
        filter_expr: str = "",
        limit: int = 20,
        tenant_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Search Neo4j assets stored in Milvus.

        Args:
            query_vector: Query embedding vector
            filter_expr: Optional filter expression
            limit: Maximum results
            tenant_id: Optional tenant filter

        Returns:
            List of search results
        """
        self.ensure_connected()

        collection = Collection(self.settings.collection_assets)
        collection.load()

        search_params = {
            "metric_type": "COSINE",
            "params": {"ef": self.settings.hnsw_ef_search},
        }

        output_fields = [
            "id", "tenant_id", "neo4j_node_id", "label", "name",
            "description", "properties", "location", "status",
        ]

        # Add tenant filter if provided
        if tenant_id and not filter_expr:
            filter_expr = f'tenant_id == "{tenant_id}"'
        elif tenant_id and filter_expr:
            filter_expr = f'tenant_id == "{tenant_id}" AND ({filter_expr})'

        results = collection.search(
            data=[query_vector],
            anns_field="embedding",
            param=search_params,
            limit=limit,
            expr=filter_expr if filter_expr else None,
            output_fields=output_fields,
        )

        formatted_results = []
        for hits in results:
            for hit in hits:
                result = {
                    "id": hit.id,
                    "score": hit.score,
                    "source": "neo4j",
                }
                for field in output_fields:
                    if hasattr(hit.entity, field):
                        result[field] = getattr(hit.entity, field)
                formatted_results.append(result)

        return formatted_results

    async def upsert_assets(
        self,
        assets: list[dict[str, Any]],
        tenant_id: str = "default",
    ) -> int:
        """Upsert Neo4j assets into Milvus.

        Args:
            assets: List of asset records with embeddings
            tenant_id: Tenant identifier

        Returns:
            Number of assets upserted
        """
        self.ensure_connected()

        collection = Collection(self.settings.collection_assets)

        # Ensure all required fields are present
        for asset in assets:
            if "tenant_id" not in asset:
                asset["tenant_id"] = tenant_id

        collection.upsert(assets)
        collection.flush()

        logger.info(f"Upserted {len(assets)} assets to {self.settings.collection_assets}")
        return len(assets)

    def health_check(self) -> bool:
        """Check if Milvus is accessible."""
        try:
            self.ensure_connected()
            return utility.has_collection(self.settings.collection_entities) or True
        except Exception as e:
            logger.error(f"Milvus health check failed: {e}")
            return False
