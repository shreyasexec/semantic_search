"""Query routing node."""

import logging

from app.models.state import SearchState

logger = logging.getLogger(__name__)


# Intent to data source mapping
INTENT_SOURCE_MAP = {
    "ASSET_STATUS": "neo4j",
    "ASSET_SEARCH": "neo4j",
    "INCIDENT_DETAIL": "milvus",
    "INCIDENT_SEARCH": "milvus",
    "AGGREGATION": "hybrid",  # Could be either source
    "RELATIONSHIP": "neo4j",
    "SIMILARITY": "hybrid",  # Depends on entity type
    "HYBRID": "hybrid",
}


async def route_query_node(state: SearchState) -> dict:
    """Route query to appropriate data source(s).

    This node determines whether to query Neo4j, Milvus, or both
    based on the intent and extracted entities.

    Args:
        state: Current workflow state

    Returns:
        Updated state with query_strategy
    """
    intent = state["intent"]
    entities = state.get("entities", {})

    # Get base strategy from intent
    strategy = INTENT_SOURCE_MAP.get(intent, "hybrid")

    # Refine strategy based on entities
    strategy = refine_strategy(strategy, intent, entities)

    logger.info(f"Routed query with intent {intent} to strategy: {strategy}")

    return {"query_strategy": strategy}


def refine_strategy(base_strategy: str, intent: str, entities: dict) -> str:
    """Refine routing strategy based on entities.

    Args:
        base_strategy: Initial strategy from intent
        intent: Query intent
        entities: Extracted entities

    Returns:
        Refined strategy
    """
    # For aggregation, determine source based on entity type
    if intent == "AGGREGATION":
        entity_type = entities.get("entity_type", "").lower()

        if entity_type in ["incident", "event", "alert"]:
            return "milvus"
        elif entity_type in ["camera", "sensor", "device", "nvr", "asset"]:
            return "neo4j"
        # Default to hybrid for mixed or unspecified

    # For similarity, determine based on entity type
    if intent == "SIMILARITY":
        entity_type = entities.get("entity_type", "").lower()
        entity_id = entities.get("entity_id", "")

        if "inc" in entity_id.lower() or entity_type == "incident":
            return "milvus"
        elif entity_id:
            return "neo4j"

    # For hybrid intent, check if we actually need both
    if intent == "HYBRID":
        has_incident_ref = bool(entities.get("incident_id") or entities.get("incident_type"))
        has_asset_ref = bool(entities.get("entity_id") and "inc" not in entities.get("entity_id", "").lower())

        if has_incident_ref and not has_asset_ref:
            return "milvus"
        elif has_asset_ref and not has_incident_ref:
            return "neo4j"

    return base_strategy


def get_query_priority(intent: str, strategy: str) -> list[str]:
    """Get priority order for data sources.

    When using hybrid strategy, determines which source to query first.

    Args:
        intent: Query intent
        strategy: Query strategy

    Returns:
        Ordered list of sources
    """
    if strategy != "hybrid":
        return [strategy]

    # For hybrid queries, determine priority
    priority_map = {
        "AGGREGATION": ["milvus", "neo4j"],  # Incidents usually more relevant for counts
        "SIMILARITY": ["milvus", "neo4j"],
        "HYBRID": ["neo4j", "milvus"],  # Assets first, then incidents
    }

    return priority_map.get(intent, ["neo4j", "milvus"])


def should_use_vector_search(intent: str, entities: dict) -> bool:
    """Determine if vector search should be used.

    Args:
        intent: Query intent
        entities: Extracted entities

    Returns:
        True if vector search is appropriate
    """
    # Vector search is useful for:
    # - Similarity queries
    # - Vague/semantic queries without specific IDs
    # - When searching by description/content

    if intent == "SIMILARITY":
        return True

    # If we have specific IDs, prefer direct lookup
    if entities.get("entity_id") or entities.get("incident_id"):
        return False

    # For search intents without specific filters
    if intent in ["ASSET_SEARCH", "INCIDENT_SEARCH"]:
        has_specific_filters = any([
            entities.get("location"),
            entities.get("status"),
            entities.get("severity"),
            entities.get("incident_type"),
        ])
        # Use vector search if no specific filters
        return not has_specific_filters

    return False
