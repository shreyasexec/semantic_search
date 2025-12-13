"""Neo4j database service for asset data and graph queries."""

import logging
from typing import Any, Optional
from contextlib import asynccontextmanager

from neo4j import AsyncGraphDatabase, AsyncDriver
from neo4j.exceptions import ServiceUnavailable, SessionExpired

from app.config import get_settings

logger = logging.getLogger(__name__)


class Neo4jService:
    """Service for Neo4j database operations."""

    _driver: Optional[AsyncDriver] = None

    def __init__(self):
        self.settings = get_settings().neo4j

    async def connect(self) -> None:
        """Establish connection to Neo4j."""
        if self._driver is None:
            self._driver = AsyncGraphDatabase.driver(
                self.settings.uri,
                auth=(self.settings.username, self.settings.password),
                max_connection_pool_size=self.settings.max_connection_pool_size,
                connection_acquisition_timeout=self.settings.connection_acquisition_timeout,
            )
            logger.info(f"Connected to Neo4j at {self.settings.uri}")

    async def close(self) -> None:
        """Close Neo4j connection."""
        if self._driver:
            await self._driver.close()
            self._driver = None
            logger.info("Closed Neo4j connection")

    @asynccontextmanager
    async def session(self, database: Optional[str] = None):
        """Get a Neo4j session context manager."""
        if self._driver is None:
            await self.connect()

        db = database or self.settings.database
        session = self._driver.session(database=db)
        try:
            yield session
        finally:
            await session.close()

    async def run(
        self,
        query: str,
        parameters: Optional[dict] = None,
        database: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Execute a Cypher query and return results.

        Args:
            query: Cypher query string
            parameters: Query parameters
            database: Optional database name

        Returns:
            List of result records as dictionaries
        """
        async with self.session(database) as session:
            try:
                result = await session.run(query, parameters or {})
                records = await result.data()
                return records
            except (ServiceUnavailable, SessionExpired) as e:
                logger.error(f"Neo4j query error: {e}")
                raise

    async def get_labels(self) -> list[str]:
        """Get all node labels in the database."""
        result = await self.run("CALL db.labels() YIELD label RETURN collect(label) as labels")
        return result[0]["labels"] if result else []

    async def get_relationship_types(self) -> list[str]:
        """Get all relationship types in the database."""
        result = await self.run(
            "CALL db.relationshipTypes() YIELD relationshipType "
            "RETURN collect(relationshipType) as types"
        )
        return result[0]["types"] if result else []

    async def get_properties_by_label(self) -> dict[str, list[dict]]:
        """Get properties for each node label."""
        result = await self.run("""
            CALL db.schema.nodeTypeProperties()
            YIELD nodeType, propertyName, propertyTypes
            RETURN nodeType, collect({name: propertyName, types: propertyTypes}) as properties
        """)

        properties = {}
        for row in result:
            # Clean label format: :`Label` -> Label
            label = row["nodeType"].replace(":`", "").replace("`", "").strip(":")
            properties[label] = [
                {"name": p["name"], "types": p["types"]}
                for p in row["properties"]
            ]
        return properties

    async def get_sample_values(
        self,
        labels: list[str],
        max_labels: int = 10,
        samples_per_property: int = 3,
    ) -> dict[str, list[Any]]:
        """Get sample values for properties of each label.

        Args:
            labels: List of node labels
            max_labels: Maximum labels to sample
            samples_per_property: Number of sample values per property

        Returns:
            Dictionary mapping "Label.property" to sample values
        """
        sample_values = {}

        for label in labels[:max_labels]:
            try:
                result = await self.run(f"""
                    MATCH (n:{label})
                    WITH n LIMIT 10
                    UNWIND keys(n) as key
                    WITH key, collect(DISTINCT n[key]) as values
                    RETURN key, values[..{samples_per_property}] as samples
                """)

                for row in result:
                    key = f"{label}.{row['key']}"
                    sample_values[key] = row["samples"]
            except Exception as e:
                logger.warning(f"Error getting samples for {label}: {e}")
                continue

        return sample_values

    async def get_vector_indexes(self) -> list[dict]:
        """Get all vector indexes."""
        try:
            result = await self.run("""
                SHOW INDEXES
                WHERE type = 'VECTOR'
                RETURN name, labelsOrTypes, properties, options
            """)
            return result
        except Exception as e:
            logger.warning(f"Error getting vector indexes: {e}")
            return []

    async def vector_search(
        self,
        index_name: str,
        query_vector: list[float],
        k: int = 10,
        filter_query: str = "",
    ) -> list[dict]:
        """Perform vector similarity search.

        Args:
            index_name: Name of the vector index
            query_vector: Query embedding vector
            k: Number of results to return
            filter_query: Optional Cypher WHERE clause

        Returns:
            List of matching nodes with scores
        """
        query = f"""
            CALL db.index.vector.queryNodes($index_name, $k, $embedding)
            YIELD node, score
            {f'WHERE {filter_query}' if filter_query else ''}
            RETURN node, score
            ORDER BY score DESC
        """

        result = await self.run(query, {
            "index_name": index_name,
            "k": k,
            "embedding": query_vector,
        })

        return [
            {
                "node": dict(r["node"]),
                "score": r["score"],
            }
            for r in result
        ]

    async def create_vector_index(
        self,
        index_name: str,
        label: str,
        property_name: str = "embedding",
        dimensions: int = 768,
        similarity_function: str = "cosine",
    ) -> None:
        """Create a vector index for a node label.

        Args:
            index_name: Name for the index
            label: Node label
            property_name: Property containing the embedding
            dimensions: Vector dimensions
            similarity_function: cosine, euclidean, or dot_product
        """
        query = f"""
            CREATE VECTOR INDEX {index_name} IF NOT EXISTS
            FOR (n:{label}) ON (n.{property_name})
            OPTIONS {{
                indexConfig: {{
                    `vector.dimensions`: {dimensions},
                    `vector.similarity_function`: '{similarity_function}'
                }}
            }}
        """

        await self.run(query)
        logger.info(f"Created vector index {index_name} for {label}.{property_name}")

    async def update_node_embedding(
        self,
        label: str,
        node_id: str,
        embedding: list[float],
        description: str,
    ) -> None:
        """Update a node with embedding and description.

        Args:
            label: Node label
            node_id: Node identifier
            embedding: Embedding vector
            description: Generated description
        """
        query = f"""
            MATCH (n:{label})
            WHERE n.id = $node_id OR id(n) = $node_id
            SET n.embedding = $embedding,
                n.description = $description,
                n.embedding_updated_at = datetime()
        """

        await self.run(query, {
            "node_id": node_id,
            "embedding": embedding,
            "description": description,
        })

    async def health_check(self) -> bool:
        """Check if Neo4j is accessible."""
        try:
            result = await self.run("RETURN 1 as health")
            return result[0]["health"] == 1
        except Exception as e:
            logger.error(f"Neo4j health check failed: {e}")
            return False
