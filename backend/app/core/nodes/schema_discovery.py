"""Schema discovery node for loading database schemas."""

import logging
from datetime import datetime

from app.models.state import SearchState
from app.models.schema import Neo4jSchema, MSSQLSchema, SchemaProperty
from app.services.neo4j_service import Neo4jService
from app.services.milvus_service import MilvusService
from app.services.cache_service import CacheService

logger = logging.getLogger(__name__)


async def load_schema_node(state: SearchState) -> dict:
    """Load schema from cache or discover from databases.

    This node retrieves the database schemas needed for query understanding
    and Cypher/filter generation. Schemas are cached per tenant.

    Args:
        state: Current workflow state

    Returns:
        Updated state with schema_neo4j and schema_mssql
    """
    tenant_id = state["tenant_id"]
    cache = CacheService()

    # Try cache first
    cached_neo4j = await cache.get_schema(tenant_id, "neo4j")
    cached_mssql = await cache.get_schema(tenant_id, "mssql")

    if cached_neo4j and cached_mssql:
        logger.info(f"Using cached schemas for tenant {tenant_id}")
        return {
            "schema_neo4j": cached_neo4j,
            "schema_mssql": cached_mssql,
        }

    # Discover Neo4j schema
    neo4j_schema = await discover_neo4j_schema(tenant_id)
    await cache.set_schema(tenant_id, "neo4j", neo4j_schema)

    # Discover MSSQL schema (from Milvus metadata)
    mssql_schema = await discover_mssql_schema(tenant_id)
    await cache.set_schema(tenant_id, "mssql", mssql_schema)

    logger.info(f"Discovered and cached schemas for tenant {tenant_id}")

    return {
        "schema_neo4j": neo4j_schema,
        "schema_mssql": mssql_schema,
    }


async def discover_neo4j_schema(tenant_id: str) -> dict:
    """Discover schema from Neo4j.

    Args:
        tenant_id: Tenant identifier

    Returns:
        Neo4j schema dictionary
    """
    neo4j = Neo4jService()
    await neo4j.connect()

    try:
        # Get labels
        labels = await neo4j.get_labels()

        # Get relationship types
        relationship_types = await neo4j.get_relationship_types()

        # Get properties per label
        properties_raw = await neo4j.get_properties_by_label()

        # Convert to SchemaProperty format
        properties_by_label = {}
        for label, props in properties_raw.items():
            properties_by_label[label] = [
                {
                    "name": p["name"],
                    "types": p.get("types", []),
                }
                for p in props
            ]

        # Get sample values
        sample_values = await neo4j.get_sample_values(labels)

        # Get vector indexes
        vector_indexes = await neo4j.get_vector_indexes()
        index_names = [idx.get("name", "") for idx in vector_indexes]

        # Generate description
        description = generate_neo4j_description(labels, relationship_types, properties_by_label)

        schema = Neo4jSchema(
            labels=labels,
            relationship_types=relationship_types,
            properties_by_label=properties_by_label,
            sample_values=sample_values,
            description=description,
            vector_indexes=index_names,
        )

        return schema.model_dump()

    finally:
        await neo4j.close()


async def discover_mssql_schema(tenant_id: str) -> dict:
    """Discover MSSQL/Incident schema from Milvus metadata.

    Args:
        tenant_id: Tenant identifier

    Returns:
        MSSQL schema dictionary
    """
    milvus = MilvusService()

    try:
        # Try to get from Milvus schema_metadata collection
        metadata = await milvus.get_schema_metadata(tenant_id)

        if metadata:
            return {
                "entity_types": metadata.get("entity_types", ["Incident"]),
                "properties": metadata.get("properties_by_type", {}),
                "location_fields": metadata.get("location_fields", []),
                "status_fields": metadata.get("status_fields", []),
                "time_fields": metadata.get("time_fields", []),
                "sample_values": metadata.get("sample_values", {}),
                "description": metadata.get("description", ""),
            }

        # Return default schema if not discovered yet
        return get_default_mssql_schema()

    except Exception as e:
        logger.warning(f"Failed to get MSSQL schema from Milvus: {e}")
        return get_default_mssql_schema()


def get_default_mssql_schema() -> dict:
    """Get default MSSQL schema for incidents.

    Returns:
        Default schema dictionary
    """
    return {
        "entity_types": ["Incident"],
        "properties": {
            "Incident": [
                {"name": "incident_id", "types": ["string"]},
                {"name": "description", "types": ["string"]},
                {"name": "response_plan", "types": ["string", "json"]},
                {"name": "action_items", "types": ["json"]},
                {"name": "incident_type", "types": ["string"]},
                {"name": "severity", "types": ["string"]},
                {"name": "status", "types": ["string"]},
                {"name": "location", "types": ["string"]},
                {"name": "created_at", "types": ["datetime"]},
                {"name": "updated_at", "types": ["datetime"]},
            ]
        },
        "location_fields": ["location"],
        "status_fields": ["status"],
        "time_fields": ["created_at", "updated_at"],
        "sample_values": {},
        "description": "Incident records from MSSQL, including response plans and action items.",
    }


def generate_neo4j_description(
    labels: list[str],
    relationship_types: list[str],
    properties_by_label: dict,
) -> str:
    """Generate human-readable Neo4j schema description.

    Args:
        labels: Node labels
        relationship_types: Relationship types
        properties_by_label: Properties by label

    Returns:
        Schema description string
    """
    lines = [
        f"Neo4j graph database with {len(labels)} node types and {len(relationship_types)} relationship types.",
        f"Node types: {', '.join(labels[:10])}{'...' if len(labels) > 10 else ''}",
        f"Relationships: {', '.join(relationship_types[:10])}{'...' if len(relationship_types) > 10 else ''}",
    ]

    # Add key properties for main labels
    for label in labels[:5]:
        if label in properties_by_label:
            props = [p["name"] for p in properties_by_label[label][:5]]
            lines.append(f"{label} properties: {', '.join(props)}")

    return "\n".join(lines)
