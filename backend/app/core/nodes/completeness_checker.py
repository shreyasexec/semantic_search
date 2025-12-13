"""Completeness checking node."""

import logging

from app.models.state import SearchState

logger = logging.getLogger(__name__)


# Required entities by intent type
REQUIRED_ENTITIES = {
    "ASSET_STATUS": {
        "optional": ["entity_type", "location"],
        "required": [],  # Can work without specifics
    },
    "ASSET_SEARCH": {
        "optional": ["entity_type", "location", "status"],
        "required": [],
    },
    "INCIDENT_DETAIL": {
        "optional": [],
        "required": ["incident_id"],  # Need specific incident
    },
    "INCIDENT_SEARCH": {
        "optional": ["time_range", "location", "severity", "incident_type"],
        "required": [],
    },
    "AGGREGATION": {
        "optional": ["time_range", "entity_type", "location"],
        "required": [],
    },
    "RELATIONSHIP": {
        "optional": ["entity_type"],
        "required": ["entity_id"],  # Need starting entity
    },
    "SIMILARITY": {
        "optional": [],
        "required": ["entity_id"],  # Need reference entity
    },
    "HYBRID": {
        "optional": ["location", "time_range"],
        "required": [],
    },
}


async def check_completeness_node(state: SearchState) -> dict:
    """Check if query has all required information.

    This node determines if clarification is needed before
    executing the query.

    Args:
        state: Current workflow state

    Returns:
        Updated state with missing_info list
    """
    intent = state["intent"]
    entities = state.get("entities", {})
    schema_neo4j = state.get("schema_neo4j", {})
    schema_mssql = state.get("schema_mssql", {})

    requirements = REQUIRED_ENTITIES.get(intent, {"required": [], "optional": []})
    missing_info = []

    # Check required entities
    for field in requirements["required"]:
        if field not in entities or not entities[field]:
            missing_info.append(field)

    # For certain intents, check if query is too vague
    if intent == "ASSET_STATUS":
        # Check if we have enough context
        has_location = bool(entities.get("location"))
        has_entity_type = bool(entities.get("entity_type"))
        has_entity_id = bool(entities.get("entity_id"))

        if not has_entity_id and not has_location and not has_entity_type:
            # Query is too vague, but might work with semantic search
            # Only ask for clarification if we have multiple buildings
            labels = schema_neo4j.get("labels", [])
            if len(labels) > 1 and not has_entity_type:
                missing_info.append("entity_type")

    elif intent == "INCIDENT_SEARCH":
        # For incident search, prefer to have at least one filter
        has_time = bool(entities.get("time_range"))
        has_location = bool(entities.get("location"))
        has_type = bool(entities.get("incident_type"))
        has_severity = bool(entities.get("severity"))

        if not any([has_time, has_location, has_type, has_severity]):
            # No filters, will return all recent incidents
            # This is acceptable, don't require clarification
            pass

    elif intent == "AGGREGATION":
        # Aggregation can work without filters
        pass

    logger.info(f"Completeness check for {intent}: missing={missing_info}")

    return {"missing_info": missing_info}


def should_clarify(intent: str, entities: dict, schema: dict) -> tuple[bool, list[str]]:
    """Determine if clarification is needed.

    Args:
        intent: Query intent
        entities: Extracted entities
        schema: Available schema

    Returns:
        Tuple of (needs_clarification, missing_fields)
    """
    requirements = REQUIRED_ENTITIES.get(intent, {"required": [], "optional": []})
    missing = []

    for field in requirements["required"]:
        if field not in entities or not entities[field]:
            missing.append(field)

    return len(missing) > 0, missing


def get_clarification_priority(missing_fields: list[str]) -> str:
    """Get highest priority field to clarify.

    Args:
        missing_fields: List of missing fields

    Returns:
        Highest priority field
    """
    priority_order = [
        "incident_id",
        "entity_id",
        "entity_type",
        "location",
        "time_range",
        "status",
        "severity",
    ]

    for field in priority_order:
        if field in missing_fields:
            return field

    return missing_fields[0] if missing_fields else ""
