"""Milvus query execution node."""

import logging
from datetime import datetime, timedelta

from app.models.state import SearchState
from app.services.milvus_service import MilvusService
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


async def milvus_query_node(state: SearchState) -> dict:
    """Execute semantic search on Milvus.

    This node performs vector similarity search on the incidents
    collection with optional metadata filters.

    Args:
        state: Current workflow state

    Returns:
        Updated state with milvus_results
    """
    query = state["query"]
    intent = state["intent"]
    entities = state.get("entities", {})
    tenant_id = state["tenant_id"]

    milvus = MilvusService()
    embedding_service = EmbeddingService()

    try:
        # Generate query embedding
        query_embedding = await embedding_service.embed_query(query)

        # Build filter expression
        filter_expr = build_milvus_filter(entities)

        # Execute search
        results = await milvus.search(
            collection_name="entities",
            query_vector=query_embedding,
            filter_expr=filter_expr,
            output_fields=["*"],
            limit=20,
            partition_names=[tenant_id],
        )

        # Format results
        formatted_results = format_milvus_results(results)

        logger.info(f"Milvus search returned {len(formatted_results)} results")

        return {
            "milvus_query_embedding": query_embedding,
            "milvus_filter": filter_expr,
            "milvus_results": formatted_results,
        }

    except Exception as e:
        logger.error(f"Milvus search failed: {e}")
        return {
            "milvus_query_embedding": [],
            "milvus_filter": "",
            "milvus_results": [],
            "error": str(e),
        }


def build_milvus_filter(entities: dict) -> str:
    """Build Milvus filter expression from entities.

    Args:
        entities: Extracted entities

    Returns:
        Filter expression string
    """
    conditions = []

    # Time filter
    time_range = entities.get("time_range", {})
    if time_range:
        start = time_range.get("start")
        end = time_range.get("end")

        if start:
            start_ts = int(datetime.fromisoformat(start).timestamp())
            conditions.append(f"created_at >= {start_ts}")

        if end:
            end_ts = int(datetime.fromisoformat(end).timestamp())
            conditions.append(f"created_at <= {end_ts}")

    # Entity type filter
    entity_type = entities.get("entity_type")
    if entity_type:
        conditions.append(f'entity_type == "{entity_type}"')

    # Incident ID filter
    incident_id = entities.get("incident_id")
    if incident_id:
        conditions.append(f'incident_id == "{incident_id}"')

    # Location filter (using JSON path)
    location = entities.get("location")
    if location:
        # Milvus JSON filtering syntax
        conditions.append(f'JSON_CONTAINS_ANY(properties["location"], ["{location}"])')

    # Severity filter
    severity = entities.get("severity")
    if severity:
        conditions.append(f'JSON_CONTAINS(properties, \'{{"severity": "{severity}"}}\', "$")')

    # Incident type filter
    incident_type = entities.get("incident_type")
    if incident_type:
        conditions.append(f'JSON_CONTAINS(properties, \'{{"incident_type": "{incident_type}"}}\', "$")')

    # Status filter
    status = entities.get("status")
    if status:
        conditions.append(f'JSON_CONTAINS(properties, \'{{"status": "{status}"}}\', "$")')

    return " and ".join(conditions) if conditions else ""


def format_milvus_results(results: list[dict]) -> list[dict]:
    """Format Milvus results for response.

    Args:
        results: Raw Milvus results

    Returns:
        Formatted results
    """
    formatted = []

    for result in results:
        properties = result.get("properties", {})
        if isinstance(properties, str):
            import json
            try:
                properties = json.loads(properties)
            except:
                properties = {}

        formatted.append({
            "id": result.get("id", ""),
            "source": "milvus",
            "entity_type": result.get("entity_type", "Incident"),
            "incident_id": result.get("incident_id", ""),
            "chunk_type": result.get("chunk_type", ""),
            "content": result.get("content", ""),
            "properties": properties,
            "score": result.get("score"),
        })

    return formatted


async def get_incident_statistics(
    milvus: MilvusService,
    tenant_id: str,
    stat_type: str = "count",
    period: str = "daily",
) -> list[dict]:
    """Get pre-computed incident statistics.

    Args:
        milvus: Milvus service
        tenant_id: Tenant identifier
        stat_type: Type of statistic
        period: Time period

    Returns:
        Statistics results
    """
    try:
        stats = await milvus.get_statistics(tenant_id, stat_type, period)
        return stats
    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        return []


def aggregate_results_by_incident(results: list[dict]) -> list[dict]:
    """Aggregate chunk results by incident ID.

    Multiple chunks from the same incident are combined.

    Args:
        results: Raw search results

    Returns:
        Aggregated results per incident
    """
    incidents = {}

    for result in results:
        incident_id = result.get("incident_id", result.get("id"))

        if incident_id not in incidents:
            incidents[incident_id] = {
                "id": incident_id,
                "source": "milvus",
                "entity_type": "Incident",
                "chunks": [],
                "properties": result.get("properties", {}),
                "max_score": result.get("score", 0),
            }

        incidents[incident_id]["chunks"].append({
            "type": result.get("chunk_type", ""),
            "content": result.get("content", ""),
            "score": result.get("score", 0),
        })

        # Track max score
        if result.get("score", 0) > incidents[incident_id]["max_score"]:
            incidents[incident_id]["max_score"] = result["score"]

    # Convert to list and sort by max score
    aggregated = list(incidents.values())
    aggregated.sort(key=lambda x: x["max_score"], reverse=True)

    # Combine chunk content
    for incident in aggregated:
        chunks = incident.pop("chunks")
        incident["content"] = "\n".join([
            f"[{c['type']}] {c['content']}" for c in chunks
        ])
        incident["score"] = incident.pop("max_score")

    return aggregated
