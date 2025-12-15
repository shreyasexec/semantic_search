"""Neo4j enhancement pipeline for adding embeddings.

Embeddings are stored in Milvus (not Neo4j) since Neo4j is transactional
and cannot efficiently store high-dimensional vectors.
"""

import logging
from typing import Any
from datetime import datetime
import hashlib

from app.config import get_settings
from app.services.neo4j_service import Neo4jService
from app.services.milvus_service import MilvusService
from app.services.llm_service import LLMService
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class Neo4jEnhancer:
    """Enhance Neo4j nodes with descriptions and store embeddings in Milvus."""

    def __init__(self):
        self.settings = get_settings()
        self.neo4j = Neo4jService()
        self.milvus = MilvusService()
        self.llm = LLMService()
        self.embedding_service = EmbeddingService()

    async def enhance_all_nodes(self, tenant_id: str = "default") -> dict:
        """Enhance all nodes with descriptions and store embeddings in Milvus.

        Args:
            tenant_id: Tenant identifier for multi-tenant isolation

        Returns:
            Enhancement statistics
        """
        logger.info("Starting Neo4j enhancement pipeline")

        await self.neo4j.connect()
        self.milvus.connect()

        # Ensure assets collection exists
        self.milvus.create_assets_collection()

        try:
            # Get all labels
            labels = await self.neo4j.get_labels()
            logger.info(f"Found {len(labels)} labels to process")

            total_enhanced = 0
            total_skipped = 0

            for label in labels:
                enhanced, skipped = await self._enhance_label(label, tenant_id)
                total_enhanced += enhanced
                total_skipped += skipped

            logger.info(
                f"Enhancement complete: {total_enhanced} enhanced, "
                f"{total_skipped} skipped"
            )

            return {
                "enhanced": total_enhanced,
                "skipped": total_skipped,
                "labels_processed": len(labels),
            }

        finally:
            await self.neo4j.close()
            self.milvus.close()

    async def _enhance_label(self, label: str, tenant_id: str) -> tuple[int, int]:
        """Enhance all nodes of a specific label.

        Args:
            label: Node label
            tenant_id: Tenant identifier

        Returns:
            Tuple of (enhanced_count, skipped_count)
        """
        logger.info(f"Processing label: {label}")

        # Get all nodes (we track processed nodes in Milvus now)
        nodes = await self.neo4j.run(f"""
            MATCH (n:{label})
            RETURN n, id(n) as nodeId
            LIMIT 1000
        """)

        if not nodes:
            logger.info(f"No nodes to enhance for {label}")
            return 0, 0

        enhanced = 0
        skipped = 0
        batch_size = 50

        for i in range(0, len(nodes), batch_size):
            batch = nodes[i:i + batch_size]
            batch_enhanced, batch_skipped = await self._enhance_batch(
                label, batch, tenant_id
            )
            enhanced += batch_enhanced
            skipped += batch_skipped

        return enhanced, skipped

    async def _enhance_batch(
        self,
        label: str,
        nodes: list[dict],
        tenant_id: str,
    ) -> tuple[int, int]:
        """Enhance a batch of nodes and store embeddings in Milvus.

        Args:
            label: Node label
            nodes: List of nodes to enhance
            tenant_id: Tenant identifier

        Returns:
            Tuple of (enhanced_count, skipped_count)
        """
        enhanced = 0
        skipped = 0

        # Prepare descriptions and asset records for Milvus
        assets_to_upsert = []

        for node_data in nodes:
            node = dict(node_data["n"])
            node_id = node_data["nodeId"]

            # Check if already has description
            if node.get("description"):
                description = node["description"]
            else:
                # Generate description
                description = await self._generate_description(label, node)

            if not description:
                skipped += 1
                continue

            # Generate embedding
            try:
                embedding = await self.embedding_service.embed_query(description)
            except Exception as e:
                logger.error(f"Failed to generate embedding for node {node_id}: {e}")
                skipped += 1
                continue

            # Create unique ID for this asset
            asset_id = f"{tenant_id}_{label}_{node_id}"

            # Extract common fields for filtering
            name = node.get("name", node.get("id", str(node_id)))
            location = node.get("location", node.get("floor", node.get("area", "")))
            status = node.get("status", "")

            # Prepare asset record for Milvus
            asset = {
                "id": asset_id,
                "tenant_id": tenant_id,
                "neo4j_node_id": node_id,
                "label": label,
                "name": str(name)[:500] if name else "",
                "description": description[:65535],
                "properties": node,
                "location": str(location)[:500] if location else "",
                "status": str(status)[:100] if status else "",
                "updated_at": int(datetime.now().timestamp()),
                "embedding": embedding,
            }
            assets_to_upsert.append(asset)

        # Batch upsert to Milvus
        if assets_to_upsert:
            try:
                await self.milvus.upsert_assets(assets_to_upsert, tenant_id)
                enhanced = len(assets_to_upsert)

                # Update Neo4j nodes with description only (not embedding)
                for asset in assets_to_upsert:
                    try:
                        await self.neo4j.run("""
                            MATCH (n)
                            WHERE id(n) = $node_id
                            SET n.description = $description,
                                n.milvus_asset_id = $asset_id
                        """, {
                            "node_id": asset["neo4j_node_id"],
                            "description": asset["description"],
                            "asset_id": asset["id"],
                        })
                    except Exception as e:
                        logger.warning(f"Failed to update Neo4j node description: {e}")

            except Exception as e:
                logger.error(f"Failed to upsert assets to Milvus: {e}")
                skipped = len(assets_to_upsert)
                enhanced = 0

        return enhanced, skipped

    async def _generate_description(
        self,
        label: str,
        properties: dict,
    ) -> str:
        """Generate description for a node.

        Args:
            label: Node label
            properties: Node properties

        Returns:
            Generated description
        """
        # Filter out internal properties
        filtered_props = {
            k: v for k, v in properties.items()
            if not k.startswith("_") and k not in ["embedding", "description"]
            and v is not None
        }

        if not filtered_props:
            return ""

        try:
            description = await self.llm.generate_description(
                entity_type=label,
                properties=filtered_props,
            )
            return description
        except Exception as e:
            logger.warning(f"Description generation failed: {e}")

            # Fallback to simple description
            parts = [f"{label}"]
            for key in ["name", "id", "type", "location", "status"]:
                if key in filtered_props:
                    parts.append(f"{key}: {filtered_props[key]}")

            return ". ".join(parts[:4])

    async def enhance_new_nodes(self, label: str = None, tenant_id: str = "default") -> dict:
        """Enhance only new nodes and store embeddings in Milvus.

        Args:
            label: Optional specific label to process
            tenant_id: Tenant identifier

        Returns:
            Enhancement statistics
        """
        await self.neo4j.connect()
        self.milvus.connect()
        self.milvus.create_assets_collection()

        try:
            if label:
                labels = [label]
            else:
                labels = await self.neo4j.get_labels()

            total_enhanced = 0

            for lbl in labels:
                enhanced, _ = await self._enhance_label(lbl, tenant_id)
                total_enhanced += enhanced

            return {"enhanced": total_enhanced}

        finally:
            await self.neo4j.close()
            self.milvus.close()


async def enhance_neo4j_data(tenant_id: str = "default") -> dict:
    """Convenience function to enhance Neo4j data.

    Embeddings are stored in Milvus for vector search.

    Args:
        tenant_id: Tenant identifier for multi-tenant isolation

    Returns:
        Enhancement statistics
    """
    enhancer = Neo4jEnhancer()
    return await enhancer.enhance_all_nodes(tenant_id)
