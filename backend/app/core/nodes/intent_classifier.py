"""Intent classification node."""

import logging
from typing import Optional

from app.models.state import SearchState, INTENT_TYPES
from app.services.llm_service import LLMService
from app.core.prompts.intent_classification import INTENT_CLASSIFICATION_PROMPT

logger = logging.getLogger(__name__)


async def classify_intent_node(state: SearchState) -> dict:
    """Classify user query intent using LLM.

    This node analyzes the user's query and classifies it into one of
    the predefined intent types to determine the query strategy.

    Args:
        state: Current workflow state

    Returns:
        Updated state with intent
    """
    query = state["query"]
    schema_neo4j = state.get("schema_neo4j", {})
    schema_mssql = state.get("schema_mssql", {})

    # Format schema context for prompt
    schema_context = format_schema_context(schema_neo4j, schema_mssql)

    # Format intent types
    intent_types_str = "\n".join(f"- {intent}" for intent in INTENT_TYPES)

    # Build prompt
    prompt = INTENT_CLASSIFICATION_PROMPT.format(
        schema_context=schema_context,
        intent_types=intent_types_str,
        user_query=query,
    )

    # Classify using LLM
    llm = LLMService()

    try:
        response = await llm.generate(prompt, temperature=0.1)
        intent = parse_intent_response(response)

        logger.info(f"Classified query '{query[:50]}...' as intent: {intent}")

        return {"intent": intent}

    except Exception as e:
        logger.error(f"Intent classification failed: {e}")
        # Default to HYBRID for resilience
        return {"intent": "HYBRID"}


def format_schema_context(schema_neo4j: dict, schema_mssql: dict) -> str:
    """Format schemas for inclusion in LLM prompt.

    Args:
        schema_neo4j: Neo4j schema dictionary
        schema_mssql: MSSQL schema dictionary

    Returns:
        Formatted schema context string
    """
    lines = []

    # Neo4j schema
    if schema_neo4j:
        lines.append("NEO4J (Assets/Graph Data):")
        labels = schema_neo4j.get("labels", [])
        lines.append(f"  Node Types: {', '.join(labels[:15])}")

        relationships = schema_neo4j.get("relationship_types", [])
        lines.append(f"  Relationships: {', '.join(relationships[:10])}")

        # Key properties
        props = schema_neo4j.get("properties_by_label", {})
        for label in labels[:5]:
            if label in props:
                prop_names = [p["name"] for p in props[label][:5]]
                lines.append(f"  {label}: {', '.join(prop_names)}")

    # MSSQL schema
    if schema_mssql:
        lines.append("\nMSSQL/MILVUS (Incidents):")
        entity_types = schema_mssql.get("entity_types", [])
        lines.append(f"  Entity Types: {', '.join(entity_types)}")

        props = schema_mssql.get("properties", {})
        for etype in entity_types[:3]:
            if etype in props:
                prop_names = [p["name"] for p in props[etype][:8]]
                lines.append(f"  {etype}: {', '.join(prop_names)}")

        location_fields = schema_mssql.get("location_fields", [])
        if location_fields:
            lines.append(f"  Location Fields: {', '.join(location_fields)}")

        time_fields = schema_mssql.get("time_fields", [])
        if time_fields:
            lines.append(f"  Time Fields: {', '.join(time_fields)}")

    return "\n".join(lines)


def parse_intent_response(response: str) -> str:
    """Parse LLM response to extract intent.

    Args:
        response: LLM response string

    Returns:
        Validated intent type
    """
    response = response.strip().upper()

    # Direct match
    if response in INTENT_TYPES:
        return response

    # Partial match
    for intent in INTENT_TYPES:
        if intent in response:
            return intent

    # Keyword-based fallback
    response_lower = response.lower()

    keyword_map = {
        "ASSET_STATUS": ["status", "working", "online", "offline", "active"],
        "ASSET_SEARCH": ["find", "show", "list", "where", "locate"],
        "INCIDENT_DETAIL": ["response plan", "action", "detail", "specific incident"],
        "INCIDENT_SEARCH": ["incident", "event", "happened", "occurred"],
        "AGGREGATION": ["how many", "count", "total", "number of", "statistics"],
        "RELATIONSHIP": ["connected", "related", "linked", "near", "associated"],
        "SIMILARITY": ["similar", "like", "same as", "comparable"],
        "HYBRID": ["cameras near incident", "assets at location"],
    }

    for intent, keywords in keyword_map.items():
        if any(kw in response_lower for kw in keywords):
            return intent

    # Default fallback
    logger.warning(f"Could not parse intent from: {response}, defaulting to HYBRID")
    return "HYBRID"


def get_intent_data_sources(intent: str) -> list[str]:
    """Get data sources needed for an intent.

    Args:
        intent: Intent type

    Returns:
        List of data sources (neo4j, milvus)
    """
    source_map = {
        "ASSET_STATUS": ["neo4j"],
        "ASSET_SEARCH": ["neo4j"],
        "INCIDENT_DETAIL": ["milvus"],
        "INCIDENT_SEARCH": ["milvus"],
        "AGGREGATION": ["neo4j", "milvus"],  # Could be either
        "RELATIONSHIP": ["neo4j"],
        "SIMILARITY": ["neo4j", "milvus"],
        "HYBRID": ["neo4j", "milvus"],
    }

    return source_map.get(intent, ["neo4j", "milvus"])
