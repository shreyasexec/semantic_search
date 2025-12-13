"""Clarification generation node."""

import logging
import json

from app.models.state import SearchState
from app.services.llm_service import LLMService
from app.core.prompts.clarification import CLARIFICATION_PROMPT, MISSING_INFO_TEMPLATES

logger = logging.getLogger(__name__)


async def clarify_node(state: SearchState) -> dict:
    """Generate clarification question for missing information.

    This node creates a user-friendly clarification question with
    options based on the schema.

    Args:
        state: Current workflow state

    Returns:
        Updated state with clarification_question and clarification_options
    """
    intent = state["intent"]
    query = state["query"]
    entities = state.get("entities", {})
    missing_info = state.get("missing_info", [])
    schema_neo4j = state.get("schema_neo4j", {})
    schema_mssql = state.get("schema_mssql", {})

    if not missing_info:
        return {
            "clarification_question": "",
            "clarification_options": [],
            "response_type": "answer",
        }

    # Get the primary missing field
    primary_missing = missing_info[0]

    # Try template-based clarification first
    template_question = get_template_question(intent, primary_missing)

    # Get options from schema
    options = get_schema_options(primary_missing, schema_neo4j, schema_mssql)

    if template_question and options:
        # Use template with schema options
        return {
            "clarification_question": template_question,
            "clarification_options": options[:5],  # Limit to 5 options
            "response_type": "clarification",
        }

    # Use LLM for more complex clarification
    schema_options = format_schema_options(schema_neo4j, schema_mssql, primary_missing)

    prompt = CLARIFICATION_PROMPT.format(
        user_query=query,
        intent=intent,
        entities=json.dumps(entities),
        missing_info=", ".join(missing_info),
        schema_options=schema_options,
    )

    llm = LLMService()

    try:
        response = await llm.generate(prompt, temperature=0.3)
        clarification = parse_clarification_response(response)

        logger.info(f"Generated clarification: {clarification.get('question', '')[:50]}...")

        return {
            "clarification_question": clarification.get("question", ""),
            "clarification_options": clarification.get("options", []),
            "response_type": "clarification",
        }

    except Exception as e:
        logger.error(f"Clarification generation failed: {e}")
        # Fallback to simple question
        return {
            "clarification_question": f"Could you please specify the {primary_missing}?",
            "clarification_options": options[:5] if options else [],
            "response_type": "clarification",
        }


def get_template_question(intent: str, missing_field: str) -> str:
    """Get template question for common clarifications.

    Args:
        intent: Query intent
        missing_field: Missing field name

    Returns:
        Template question or empty string
    """
    intent_templates = MISSING_INFO_TEMPLATES.get(intent, {})
    return intent_templates.get(missing_field, "")


def get_schema_options(
    missing_field: str,
    schema_neo4j: dict,
    schema_mssql: dict,
) -> list[dict]:
    """Get options from schema for missing field.

    Args:
        missing_field: Missing field name
        schema_neo4j: Neo4j schema
        schema_mssql: MSSQL schema

    Returns:
        List of option dictionaries
    """
    options = []

    if missing_field == "entity_type":
        # Get labels from Neo4j
        labels = schema_neo4j.get("labels", [])
        for label in labels[:10]:
            options.append({"label": label, "value": label})

    elif missing_field == "location":
        # Get location samples from schema
        samples = schema_neo4j.get("sample_values", {})
        for key, values in samples.items():
            if "location" in key.lower() or "building" in key.lower():
                for value in values[:5]:
                    if value and str(value) not in [o["value"] for o in options]:
                        options.append({"label": str(value), "value": str(value)})

    elif missing_field == "incident_id":
        # Can't easily provide incident IDs, suggest search instead
        options.append({"label": "Search recent incidents", "value": "recent"})
        options.append({"label": "Search by location", "value": "by_location"})

    elif missing_field == "status":
        options = [
            {"label": "Online", "value": "online"},
            {"label": "Offline", "value": "offline"},
            {"label": "Active", "value": "active"},
            {"label": "Inactive", "value": "inactive"},
        ]

    elif missing_field == "severity":
        options = [
            {"label": "Critical", "value": "critical"},
            {"label": "High", "value": "high"},
            {"label": "Medium", "value": "medium"},
            {"label": "Low", "value": "low"},
        ]

    elif missing_field == "time_range":
        options = [
            {"label": "Today", "value": "today"},
            {"label": "Yesterday", "value": "yesterday"},
            {"label": "Last 7 days", "value": "last week"},
            {"label": "Last 30 days", "value": "last month"},
        ]

    return options


def format_schema_options(
    schema_neo4j: dict,
    schema_mssql: dict,
    missing_field: str,
) -> str:
    """Format schema options for LLM prompt.

    Args:
        schema_neo4j: Neo4j schema
        schema_mssql: MSSQL schema
        missing_field: Missing field name

    Returns:
        Formatted options string
    """
    lines = []

    if missing_field == "entity_type":
        labels = schema_neo4j.get("labels", [])
        lines.append(f"Available asset types: {', '.join(labels[:15])}")

    elif missing_field == "location":
        samples = schema_neo4j.get("sample_values", {})
        locations = []
        for key, values in samples.items():
            if "location" in key.lower() or "building" in key.lower():
                locations.extend([str(v) for v in values[:3]])
        if locations:
            lines.append(f"Example locations: {', '.join(set(locations)[:10])}")

    elif missing_field == "incident_type":
        samples = schema_mssql.get("sample_values", {})
        if "incident_type" in samples:
            lines.append(f"Incident types: {', '.join(samples['incident_type'][:10])}")

    return "\n".join(lines) if lines else "No specific options available"


def parse_clarification_response(response: str) -> dict:
    """Parse LLM clarification response.

    Args:
        response: LLM response string

    Returns:
        Clarification dictionary
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
        clarification = json.loads(response)
        return {
            "question": clarification.get("question", ""),
            "options": clarification.get("options", []),
            "allow_free_text": clarification.get("allow_free_text", True),
        }
    except json.JSONDecodeError:
        # Treat whole response as question
        return {
            "question": response,
            "options": [],
            "allow_free_text": True,
        }
