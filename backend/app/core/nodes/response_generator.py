"""Response generation node."""

import logging
import json

from app.models.state import SearchState
from app.services.llm_service import LLMService
from app.core.prompts.response_generation import (
    RESPONSE_GENERATION_PROMPT,
    NO_RESULTS_RESPONSE,
    ERROR_RESPONSE,
)

logger = logging.getLogger(__name__)


async def generate_response_node(state: SearchState) -> dict:
    """Generate natural language response from results.

    This node creates a user-friendly response based on the
    search results and query intent.

    Args:
        state: Current workflow state

    Returns:
        Updated state with response
    """
    query = state["query"]
    intent = state["intent"]
    results = state.get("reranked_results") or state.get("fused_results", [])
    error = state.get("error")

    # Handle errors
    if error:
        return {
            "response": ERROR_RESPONSE.format(error=error),
            "response_type": "error",
        }

    # Handle no results
    if not results:
        return {
            "response": NO_RESULTS_RESPONSE.format(query=query),
            "response_type": "answer",
        }

    # Format results for prompt
    formatted_results = format_results_for_prompt(results, intent)

    # Generate response using LLM
    prompt = RESPONSE_GENERATION_PROMPT.format(
        query=query,
        intent=intent,
        formatted_results=formatted_results,
    )

    llm = LLMService()

    try:
        response = await llm.generate(prompt, temperature=0.3)

        logger.info(f"Generated response: {response[:100]}...")

        return {
            "response": response,
            "response_type": "answer",
        }

    except Exception as e:
        logger.error(f"Response generation failed: {e}")
        # Fallback to structured response
        return {
            "response": generate_fallback_response(query, results, intent),
            "response_type": "answer",
        }


def format_results_for_prompt(results: list[dict], intent: str) -> str:
    """Format results for inclusion in LLM prompt.

    Args:
        results: Search results
        intent: Query intent

    Returns:
        Formatted results string
    """
    if not results:
        return "No results found."

    # Limit results for context
    max_results = 10
    display_results = results[:max_results]

    formatted = []

    for i, result in enumerate(display_results, 1):
        parts = [f"{i}. "]

        # Entity info
        entity_type = result.get("entity_type", "Unknown")
        result_id = result.get("id", "")
        if result_id:
            parts.append(f"[{entity_type}: {result_id}] ")

        # Content
        content = result.get("content", "")
        if content:
            # Truncate long content
            if len(content) > 500:
                content = content[:500] + "..."
            parts.append(content)

        # Key properties based on intent
        properties = result.get("properties", {})
        if isinstance(properties, dict):
            props_to_show = get_relevant_properties(properties, intent)
            if props_to_show:
                parts.append(f"\n   Properties: {props_to_show}")

        # Score for debugging/transparency
        score = result.get("score") or result.get("rrf_score")
        if score:
            parts.append(f"\n   (relevance: {score:.2f})")

        formatted.append("".join(parts))

    result_text = "\n\n".join(formatted)

    # Add count info
    if len(results) > max_results:
        result_text += f"\n\n... and {len(results) - max_results} more results"

    return result_text


def get_relevant_properties(properties: dict, intent: str) -> str:
    """Get relevant properties to display based on intent.

    Args:
        properties: Result properties
        intent: Query intent

    Returns:
        Formatted property string
    """
    # Properties to show by intent
    property_map = {
        "ASSET_STATUS": ["status", "location", "last_updated"],
        "ASSET_SEARCH": ["location", "type", "status"],
        "INCIDENT_DETAIL": ["severity", "status", "created_at", "location"],
        "INCIDENT_SEARCH": ["severity", "status", "incident_type", "created_at"],
        "AGGREGATION": ["count", "total"],
        "RELATIONSHIP": ["connected_to", "relationship_type"],
        "SIMILARITY": ["similarity_score"],
        "HYBRID": ["location", "status", "severity"],
    }

    keys_to_show = property_map.get(intent, ["status", "location"])

    props = []
    for key in keys_to_show:
        if key in properties and properties[key]:
            props.append(f"{key}: {properties[key]}")

    return ", ".join(props)


def generate_fallback_response(
    query: str,
    results: list[dict],
    intent: str,
) -> str:
    """Generate fallback response without LLM.

    Args:
        query: User query
        results: Search results
        intent: Query intent

    Returns:
        Fallback response string
    """
    if not results:
        return f"I couldn't find any results for: {query}"

    # Build simple response based on intent
    count = len(results)

    if intent == "AGGREGATION":
        return f"Found {count} matching records."

    if intent in ["ASSET_STATUS", "ASSET_SEARCH"]:
        items = []
        for r in results[:5]:
            props = r.get("properties", {})
            status = props.get("status", "unknown") if isinstance(props, dict) else "unknown"
            items.append(f"- {r.get('id', 'Unknown')}: {status}")
        return f"Found {count} assets:\n" + "\n".join(items)

    if intent in ["INCIDENT_DETAIL", "INCIDENT_SEARCH"]:
        items = []
        for r in results[:5]:
            content = r.get("content", "")[:100]
            items.append(f"- {r.get('incident_id', r.get('id', 'Unknown'))}: {content}")
        return f"Found {count} incidents:\n" + "\n".join(items)

    # Generic response
    return f"Found {count} results matching your query."


def add_citations(response: str, results: list[dict]) -> str:
    """Add citations to response referencing source data.

    Args:
        response: Generated response
        results: Source results

    Returns:
        Response with citations
    """
    # Find mentions of IDs in response and add source reference
    citations = []

    for i, result in enumerate(results[:10], 1):
        result_id = result.get("id", "")
        if result_id and result_id in response:
            source = result.get("source", "unknown")
            citations.append(f"[{i}] {result_id} (from {source})")

    if citations:
        response += "\n\nSources:\n" + "\n".join(citations)

    return response


def format_aggregation_response(results: list[dict], query: str) -> str:
    """Format response for aggregation queries.

    Args:
        results: Aggregation results
        query: Original query

    Returns:
        Formatted aggregation response
    """
    if not results:
        return "No data available for aggregation."

    # Check if results contain count/aggregation data
    total = 0
    breakdowns = []

    for result in results:
        props = result.get("properties", {})
        if isinstance(props, dict):
            if "count" in props:
                total += props["count"]
                group = props.get("group", result.get("id", "Unknown"))
                breakdowns.append(f"- {group}: {props['count']}")

    if total > 0:
        response = f"Total count: {total}"
        if breakdowns:
            response += "\n\nBreakdown:\n" + "\n".join(breakdowns[:10])
        return response

    # Fallback to simple count
    return f"Found {len(results)} records."
