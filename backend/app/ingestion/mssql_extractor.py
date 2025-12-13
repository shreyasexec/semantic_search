"""MSSQL to Milvus ingestion pipeline."""

import logging
import json
from datetime import datetime
from typing import Any

from app.config import get_settings
from app.services.mssql_service import MSSQLService
from app.services.milvus_service import MilvusService
from app.services.embedding_service import EmbeddingService
from app.services.neo4j_service import Neo4jService
from app.ingestion.chunker import chunk_incident_record
from app.ingestion.statistics_computer import StatisticsComputer

logger = logging.getLogger(__name__)


class MSSQLIngestion:
    """Ingestion pipeline from MSSQL to Milvus."""

    def __init__(self):
        self.settings = get_settings()
        self.mssql = MSSQLService()
        self.milvus = MilvusService()
        self.embedding_service = EmbeddingService()

    async def run_incremental_sync(
        self,
        tenant_id: str,
        last_sync: datetime,
    ) -> dict:
        """Run incremental sync from MSSQL to Milvus.

        Args:
            tenant_id: Tenant identifier
            last_sync: Timestamp of last sync

        Returns:
            Sync statistics
        """
        logger.info(f"Starting incremental sync for tenant {tenant_id} since {last_sync}")

        try:
            # Step 1: Extract changed records
            records = self.mssql.get_changed_records(last_sync)

            if not records:
                logger.info("No changed records found")
                return {"synced": 0, "chunks": 0}

            logger.info(f"Found {len(records)} changed records")

            # Step 2: Process records into chunks
            all_chunks = []
            for record in records:
                chunks = await self._process_record(record, tenant_id)
                all_chunks.extend(chunks)

            logger.info(f"Created {len(all_chunks)} chunks")

            # Step 3: Generate embeddings
            embeddings = await self._generate_embeddings_batch(all_chunks)

            # Step 4: Upsert to Milvus
            await self._upsert_to_milvus(all_chunks, embeddings, tenant_id)

            # Step 5: Compute and store statistics
            await self._compute_statistics(tenant_id, records)

            logger.info(f"Sync complete: {len(records)} records, {len(all_chunks)} chunks")

            return {
                "synced": len(records),
                "chunks": len(all_chunks),
            }

        except Exception as e:
            logger.error(f"Incremental sync failed: {e}")
            raise

    async def run_full_sync(self, tenant_id: str) -> dict:
        """Run full sync from MSSQL to Milvus.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Sync statistics
        """
        logger.info(f"Starting full sync for tenant {tenant_id}")

        try:
            total_records = 0
            total_chunks = 0
            batch_size = self.settings.app.ingestion_batch_size
            offset = 0

            while True:
                # Get batch of records
                records = self.mssql.get_all_records(batch_size, offset)

                if not records:
                    break

                # Process batch
                all_chunks = []
                for record in records:
                    chunks = await self._process_record(record, tenant_id)
                    all_chunks.extend(chunks)

                # Generate embeddings
                embeddings = await self._generate_embeddings_batch(all_chunks)

                # Upsert to Milvus
                await self._upsert_to_milvus(all_chunks, embeddings, tenant_id)

                total_records += len(records)
                total_chunks += len(all_chunks)
                offset += batch_size

                logger.info(f"Processed batch: {total_records} records so far")

            # Compute statistics
            await self._compute_statistics(tenant_id)

            # Store schema metadata
            await self._store_schema_metadata(tenant_id)

            logger.info(f"Full sync complete: {total_records} records, {total_chunks} chunks")

            return {
                "synced": total_records,
                "chunks": total_chunks,
            }

        except Exception as e:
            logger.error(f"Full sync failed: {e}")
            raise

    async def _process_record(
        self,
        record: dict,
        tenant_id: str,
    ) -> list[dict]:
        """Process a single record into chunks.

        Args:
            record: MSSQL record
            tenant_id: Tenant identifier

        Returns:
            List of chunks
        """
        # Parse JSON columns
        record = self._parse_json_fields(record)

        # Chunk the incident
        chunks = chunk_incident_record(record)

        # Resolve location from Neo4j if available
        location_hierarchy = await self._resolve_location(
            record.get("location"),
            tenant_id,
        )

        # Add metadata to each chunk
        for chunk in chunks:
            chunk["tenant_id"] = tenant_id
            chunk["source"] = "mssql"
            chunk["entity_type"] = "Incident"
            chunk["incident_id"] = record.get("incident_id") or record.get("id", "")
            chunk["properties"] = {
                "incident_type": record.get("incident_type"),
                "severity": record.get("severity"),
                "status": record.get("status"),
                "location": record.get("location"),
                "created_at": str(record.get("created_at")),
                "updated_at": str(record.get("updated_at")),
            }
            chunk["location_hierarchy"] = location_hierarchy
            chunk["created_at"] = int(datetime.now().timestamp())
            chunk["updated_at"] = int(datetime.now().timestamp())

        return chunks

    def _parse_json_fields(self, record: dict) -> dict:
        """Parse JSON string fields in record.

        Args:
            record: Raw record

        Returns:
            Record with parsed JSON fields
        """
        json_fields = ["response_plan", "action_items", "context"]

        for field in json_fields:
            if field in record and isinstance(record[field], str):
                try:
                    record[field] = json.loads(record[field])
                except json.JSONDecodeError:
                    pass  # Keep as string

        return record

    async def _resolve_location(
        self,
        location: str,
        tenant_id: str,
    ) -> dict:
        """Resolve location to hierarchy from Neo4j.

        Args:
            location: Location string
            tenant_id: Tenant identifier

        Returns:
            Location hierarchy dictionary
        """
        if not location:
            return {}

        try:
            neo4j = Neo4jService()
            await neo4j.connect()

            try:
                # Query for location hierarchy
                result = await neo4j.run("""
                    MATCH (loc)
                    WHERE toLower(loc.name) CONTAINS toLower($location)
                       OR toLower(loc.location) CONTAINS toLower($location)
                    OPTIONAL MATCH path = (loc)-[:LOCATED_IN|PART_OF*]->(parent)
                    RETURN loc, [node IN nodes(path) | node.name] as hierarchy
                    LIMIT 1
                """, {"location": location})

                if result:
                    return {
                        "matched_location": dict(result[0].get("loc", {})),
                        "hierarchy": result[0].get("hierarchy", []),
                    }

            finally:
                await neo4j.close()

        except Exception as e:
            logger.warning(f"Location resolution failed: {e}")

        return {"original": location}

    async def _generate_embeddings_batch(
        self,
        chunks: list[dict],
    ) -> list[list[float]]:
        """Generate embeddings for chunks in batches.

        Args:
            chunks: List of chunks

        Returns:
            List of embedding vectors
        """
        texts = [c["content"] for c in chunks]
        return await self.embedding_service.embed_batch(texts)

    async def _upsert_to_milvus(
        self,
        chunks: list[dict],
        embeddings: list[list[float]],
        tenant_id: str,
    ) -> None:
        """Upsert chunks with embeddings to Milvus.

        Args:
            chunks: List of chunks
            embeddings: List of embeddings
            tenant_id: Tenant identifier
        """
        entities = []

        for chunk, embedding in zip(chunks, embeddings):
            entities.append({
                "id": chunk["id"],
                "tenant_id": tenant_id,
                "source": chunk["source"],
                "entity_type": chunk["entity_type"],
                "incident_id": chunk["incident_id"],
                "chunk_type": chunk["chunk_type"],
                "content": chunk["content"],
                "properties": chunk["properties"],
                "location_hierarchy": chunk.get("location_hierarchy", {}),
                "created_at": chunk["created_at"],
                "updated_at": chunk["updated_at"],
                "embedding": embedding,
            })

        await self.milvus.upsert(
            collection_name=self.settings.milvus.collection_entities,
            entities=entities,
            partition_name=tenant_id,
        )

    async def _compute_statistics(
        self,
        tenant_id: str,
        records: list[dict] = None,
    ) -> None:
        """Compute and store statistics.

        Args:
            tenant_id: Tenant identifier
            records: Optional records for incremental update
        """
        computer = StatisticsComputer(self.mssql, self.milvus, self.embedding_service)
        await computer.compute_and_store(tenant_id)

    async def _store_schema_metadata(self, tenant_id: str) -> None:
        """Store discovered schema metadata.

        Args:
            tenant_id: Tenant identifier
        """
        # Discover schema
        schema = self.mssql.discover_schema()

        # Generate description
        description = (
            f"Incident data from {schema['table']} with {schema['record_count']} records. "
            f"Fields include: {', '.join([p['name'] for p in schema['properties'][:10]])}."
        )

        # Generate embedding for schema
        embedding = await self.embedding_service.embed(description)

        # Store in Milvus
        metadata = {
            "id": f"schema_{tenant_id}_mssql",
            "tenant_id": tenant_id,
            "source": "mssql",
            "entity_types": ["Incident"],
            "properties_by_type": {"Incident": schema["properties"]},
            "sample_values": {
                p["name"]: p.get("samples", [])
                for p in schema["properties"]
            },
            "location_fields": schema["location_fields"],
            "status_fields": schema["status_fields"],
            "time_fields": schema["time_fields"],
            "description": description,
            "embedding": embedding,
            "updated_at": int(datetime.now().timestamp()),
        }

        await self.milvus.upsert(
            collection_name=self.settings.milvus.collection_schema,
            entities=[metadata],
            partition_name=tenant_id,
        )

        logger.info(f"Stored schema metadata for tenant {tenant_id}")
