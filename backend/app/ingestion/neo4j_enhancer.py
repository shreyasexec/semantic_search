"""Neo4j enhancement pipeline for adding embeddings."""

import logging
from typing import Any

from app.config import get_settings
from app.services.neo4j_service import Neo4jService
from app.services.llm_service import LLMService
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class Neo4jEnhancer:
    """Enhance Neo4j nodes with descriptions and embeddings."""

    def __init__(self):
        self.settings = get_settings()
        self.neo4j = Neo4jService()
        self.llm = LLMService()
        self.embedding_service = EmbeddingService()

    async def enhance_all_nodes(self, tenant_id: str = None) -> dict:
        """Enhance all nodes with descriptions and embeddings.

        Args:
            tenant_id: Optional tenant identifier

        Returns:
            Enhancement statistics
        """
        logger.info("Starting Neo4j enhancement pipeline")

        await self.neo4j.connect()

        try:
            # Get all labels
            labels = await self.neo4j.get_labels()
            logger.info(f"Found {len(labels)} labels to process")

            total_enhanced = 0
            total_skipped = 0

            for label in labels:
                enhanced, skipped = await self._enhance_label(label)
                total_enhanced += enhanced
                total_skipped += skipped

            # Create/update vector indexes
            await self._create_vector_indexes(labels)

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

    async def _enhance_label(self, label: str) -> tuple[int, int]:
        """Enhance all nodes of a specific label.

        Args:
            label: Node label

        Returns:
            Tuple of (enhanced_count, skipped_count)
        """
        logger.info(f"Processing label: {label}")

        # Get nodes without embeddings
        nodes = await self.neo4j.run(f"""
            MATCH (n:{label})
            WHERE n.embedding IS NULL
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
                label, batch
            )
            enhanced += batch_enhanced
            skipped += batch_skipped

        return enhanced, skipped

    async def _enhance_batch(
        self,
        label: str,
        nodes: list[dict],
    ) -> tuple[int, int]:
        """Enhance a batch of nodes.

        Args:
            label: Node label
            nodes: List of nodes to enhance

        Returns:
            Tuple of (enhanced_count, skipped_count)
        """
        enhanced = 0
        skipped = 0

        # Prepare descriptions
        descriptions = []
        node_ids = []

        for node_data in nodes:
            node = node_data["n"]
            node_id = node_data["nodeId"]

            # Check if already has description
            if node.get("description"):
                description = node["description"]
            else:
                # Generate description
                description = await self._generate_description(label, dict(node))

            if description:
                descriptions.append(description)
                node_ids.append(node_id)
            else:
                skipped += 1

        if not descriptions:
            return enhanced, skipped

        # Generate embeddings in batch
        embeddings = await self.embedding_service.embed_batch(descriptions)

        # Update nodes
        for node_id, description, embedding in zip(node_ids, descriptions, embeddings):
            try:
                await self.neo4j.run("""
                    MATCH (n)
                    WHERE id(n) = $node_id
                    SET n.description = $description,
                        n.embedding = $embedding,
                        n.embedding_updated_at = datetime()
                """, {
                    "node_id": node_id,
                    "description": description,
                    "embedding": embedding,
                })
                enhanced += 1
            except Exception as e:
                logger.error(f"Failed to update node {node_id}: {e}")
                skipped += 1

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

    async def _create_vector_indexes(self, labels: list[str]) -> None:
        """Create vector indexes for all labels.

        Args:
            labels: List of labels
        """
        logger.info("Creating vector indexes")

        # Get existing indexes
        existing = await self.neo4j.get_vector_indexes()
        existing_names = {idx.get("name", "") for idx in existing}

        for label in labels:
            index_name = f"{label.lower()}_embedding"

            if index_name in existing_names:
                logger.debug(f"Index {index_name} already exists")
                continue

            try:
                await self.neo4j.create_vector_index(
                    index_name=index_name,
                    label=label,
                    property_name="embedding",
                    dimensions=self.settings.app.embedding_dimension,
                    similarity_function="cosine",
                )
                logger.info(f"Created vector index: {index_name}")
            except Exception as e:
                logger.warning(f"Failed to create index {index_name}: {e}")

    async def enhance_new_nodes(self, label: str = None) -> dict:
        """Enhance only new nodes without embeddings.

        Args:
            label: Optional specific label to process

        Returns:
            Enhancement statistics
        """
        await self.neo4j.connect()

        try:
            if label:
                labels = [label]
            else:
                labels = await self.neo4j.get_labels()

            total_enhanced = 0

            for lbl in labels:
                enhanced, _ = await self._enhance_label(lbl)
                total_enhanced += enhanced

            return {"enhanced": total_enhanced}

        finally:
            await self.neo4j.close()


async def enhance_neo4j_data(tenant_id: str = None) -> dict:
    """Convenience function to enhance Neo4j data.

    Args:
        tenant_id: Optional tenant identifier

    Returns:
        Enhancement statistics
    """
    enhancer = Neo4jEnhancer()
    return await enhancer.enhance_all_nodes(tenant_id)
