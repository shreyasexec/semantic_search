"""Entity extraction node."""

import logging
import json
from datetime import datetime, timedelta
from typing import Any

from app.models.state import SearchState
from app.services.llm_service import LLMService
from app.core.prompts.entity_extraction import ENTITY_EXTRACTION_PROMPT

logger = logging.getLogger(__name__)


async def extract_entities_node(state: SearchState) -> dict:
    """Extract entities and filters from user query.

    This node uses LLM to extract structured information like
    entity types, IDs, locations, time ranges, and filters.

    Args:
        state: Current workflow state

    Returns:
        Updated state with entities
    """
    query = state["query"]
    intent = state["intent"]
    schema_neo4j = state.get("schema_neo4j", {})
    schema_mssql = state.get("schema_mssql", {})

    # Format schema context
    schema_context = format_extraction_context(schema_neo4j, schema_mssql)

    # Build prompt
    prompt = ENTITY_EXTRACTION_PROMPT.format(
        schema_context=schema_context,
        intent=intent,
        user_query=query,
    )

    # Extract using LLM
    llm = LLMService()

    try:
        response = await llm.generate(prompt, temperature=0.1)
        entities = parse_entities_response(response)

        # Resolve relative time references
        entities = resolve_time_references(entities)

        logger.info(f"Extracted entities: {entities}")

        return {"entities": entities}

    except Exception as e:
        logger.error(f"Entity extraction failed: {e}")
        # Return empty entities for resilience
        return {"entities": {}}


def format_extraction_context(schema_neo4j: dict, schema_mssql: dict) -> str:
    """Format schemas for entity extraction prompt.

    Args:
        schema_neo4j: Neo4j schema
        schema_mssql: MSSQL schema

    Returns:
        Formatted context string
    """
    lines = []

    # Neo4j labels as entity types
    if schema_neo4j:
        labels = schema_neo4j.get("labels", [])
        lines.append(f"Asset Types: {', '.join(labels)}")

        # Sample values for reference
        samples = schema_neo4j.get("sample_values", {})
        for key, values in list(samples.items())[:5]:
            if values:
                lines.append(f"  {key} examples: {values[:3]}")

    # MSSQL entity types
    if schema_mssql:
        entity_types = schema_mssql.get("entity_types", [])
        lines.append(f"Incident Types: {', '.join(entity_types)}")

        location_fields = schema_mssql.get("location_fields", [])
        if location_fields:
            lines.append(f"Location Fields: {', '.join(location_fields)}")

    return "\n".join(lines)


def parse_entities_response(response: str) -> dict:
    """Parse LLM response to extract entities.

    Args:
        response: LLM response string

    Returns:
        Entities dictionary
    """
    # Clean response
    response = response.strip()
    if response.startswith("```json"):
        response = response[7:]
    if response.startswith("```"):
        response = response[3:]
    if response.endswith("```"):
        response = response[:-3]

    try:
        entities = json.loads(response)

        # Clean up empty values
        return {k: v for k, v in entities.items() if v and v != "null"}

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse entities JSON: {e}")
        return {}


def resolve_time_references(entities: dict) -> dict:
    """Resolve relative time references to absolute dates.

    Args:
        entities: Extracted entities

    Returns:
        Entities with resolved time ranges
    """
    time_range = entities.get("time_range", {})
    if not time_range:
        return entities

    relative = time_range.get("relative", "").lower()
    now = datetime.now()

    if relative:
        start = None
        end = now

        if relative == "today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif relative == "yesterday":
            start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        elif relative in ("last week", "this week"):
            start = now - timedelta(days=7)
        elif relative in ("last month", "this month"):
            start = now - timedelta(days=30)
        elif relative == "last hour":
            start = now - timedelta(hours=1)
        elif "days" in relative:
            # Extract number of days
            import re
            match = re.search(r"(\d+)\s*days?", relative)
            if match:
                days = int(match.group(1))
                start = now - timedelta(days=days)

        if start:
            entities["time_range"] = {
                "start": start.isoformat(),
                "end": end.isoformat(),
                "relative": relative,
            }

    return entities


def extract_simple_entities(query: str) -> dict:
    """Simple rule-based entity extraction as fallback.

    Args:
        query: User query

    Returns:
        Extracted entities
    """
    entities = {}
    query_lower = query.lower()

    # Extract common patterns

    # Time references
    if "today" in query_lower:
        entities["time_range"] = {"relative": "today"}
    elif "yesterday" in query_lower:
        entities["time_range"] = {"relative": "yesterday"}
    elif "last week" in query_lower:
        entities["time_range"] = {"relative": "last week"}

    # Status references
    if "online" in query_lower:
        entities["status"] = "online"
    elif "offline" in query_lower:
        entities["status"] = "offline"
    elif "active" in query_lower:
        entities["status"] = "active"

    # Severity references
    for severity in ["critical", "high", "medium", "low"]:
        if severity in query_lower:
            entities["severity"] = severity
            break

    # ID patterns (e.g., CAM-001, INC-2024-001)
    import re
    id_patterns = [
        r"(CAM-\d+)",
        r"(INC-\d{4}-\d+)",
        r"(SENSOR-\d+)",
        r"(NVR-\d+)",
    ]

    for pattern in id_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            entities["entity_id"] = match.group(1)
            break

    return entities
