"""LangGraph workflow definition for semantic search."""

import logging
import uuid
from datetime import datetime
from typing import Literal

from langgraph.graph import StateGraph, END

from app.models.state import SearchState, create_initial_state
from app.core.nodes import (
    load_schema_node,
    classify_intent_node,
    extract_entities_node,
    check_completeness_node,
    clarify_node,
    route_query_node,
    neo4j_query_node,
    milvus_query_node,
    hybrid_query_node,
    fuse_results_node,
    rerank_results_node,
    generate_response_node,
)

logger = logging.getLogger(__name__)


def create_workflow() -> StateGraph:
    """Create the LangGraph workflow for semantic search.

    Returns:
        Compiled StateGraph workflow
    """
    workflow = StateGraph(SearchState)

    # Add nodes
    workflow.add_node("load_schema", load_schema_node)
    workflow.add_node("classify_intent", classify_intent_node)
    workflow.add_node("extract_entities", extract_entities_node)
    workflow.add_node("check_completeness", check_completeness_node)
    workflow.add_node("clarify", clarify_node)
    workflow.add_node("route_query", route_query_node)
    workflow.add_node("neo4j_query", neo4j_query_node)
    workflow.add_node("milvus_query", milvus_query_node)
    workflow.add_node("hybrid_query", hybrid_query_node)
    workflow.add_node("fuse_results", fuse_results_node)
    workflow.add_node("rerank_results", rerank_results_node)
    workflow.add_node("generate_response", generate_response_node)

    # Define edges
    workflow.set_entry_point("load_schema")
    workflow.add_edge("load_schema", "classify_intent")
    workflow.add_edge("classify_intent", "extract_entities")
    workflow.add_edge("extract_entities", "check_completeness")

    # Conditional edge for completeness check
    workflow.add_conditional_edges(
        "check_completeness",
        should_clarify,
        {
            "clarify": "clarify",
            "route": "route_query",
        },
    )

    # Clarify returns to user (ends workflow)
    workflow.add_edge("clarify", END)

    # Conditional edge for query routing
    workflow.add_conditional_edges(
        "route_query",
        get_query_strategy,
        {
            "neo4j": "neo4j_query",
            "milvus": "milvus_query",
            "hybrid": "hybrid_query",
        },
    )

    # All query paths lead to fusion
    workflow.add_edge("neo4j_query", "fuse_results")
    workflow.add_edge("milvus_query", "fuse_results")
    workflow.add_edge("hybrid_query", "fuse_results")

    # Result processing
    workflow.add_edge("fuse_results", "rerank_results")
    workflow.add_edge("rerank_results", "generate_response")
    workflow.add_edge("generate_response", END)

    return workflow.compile()


def should_clarify(state: SearchState) -> Literal["clarify", "route"]:
    """Determine if clarification is needed.

    Args:
        state: Current workflow state

    Returns:
        Next node: "clarify" or "route"
    """
    missing_info = state.get("missing_info", [])
    return "clarify" if missing_info else "route"


def get_query_strategy(state: SearchState) -> Literal["neo4j", "milvus", "hybrid"]:
    """Get query strategy from state.

    Args:
        state: Current workflow state

    Returns:
        Query strategy
    """
    return state.get("query_strategy", "hybrid")


async def run_search(
    query: str,
    tenant_id: str,
    conversation_id: str = None,
) -> dict:
    """Run the semantic search workflow.

    Args:
        query: User's natural language query
        tenant_id: Tenant identifier
        conversation_id: Optional conversation ID for multi-turn

    Returns:
        Workflow result containing response and metadata
    """
    start_time = datetime.now()

    # Generate conversation ID if not provided
    if not conversation_id:
        conversation_id = f"conv_{uuid.uuid4().hex[:12]}"

    # Create initial state
    initial_state = create_initial_state(
        query=query,
        tenant_id=tenant_id,
        conversation_id=conversation_id,
    )

    # Create and run workflow
    workflow = create_workflow()

    try:
        # Execute workflow
        final_state = await workflow.ainvoke(initial_state)

        # Calculate execution time
        execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        # Build response
        result = {
            "response_type": final_state.get("response_type", "answer"),
            "response": final_state.get("response", ""),
            "conversation_id": conversation_id,
            "metadata": {
                "intent": final_state.get("intent", ""),
                "query_strategy": final_state.get("query_strategy", ""),
                "execution_time_ms": execution_time_ms,
                "neo4j_results_count": len(final_state.get("neo4j_results", [])),
                "milvus_results_count": len(final_state.get("milvus_results", [])),
                "cypher_query": final_state.get("cypher_query"),
            },
        }

        # Add clarification if needed
        if final_state.get("response_type") == "clarification":
            result["clarification"] = {
                "question": final_state.get("clarification_question", ""),
                "options": final_state.get("clarification_options", []),
                "allow_free_text": True,
            }

        # Add results
        results = final_state.get("reranked_results") or final_state.get("fused_results", [])
        result["results"] = results[:20]  # Limit results in response

        logger.info(
            f"Search completed in {execution_time_ms}ms: "
            f"intent={result['metadata']['intent']}, "
            f"results={len(result['results'])}"
        )

        return result

    except Exception as e:
        logger.error(f"Workflow execution failed: {e}")
        execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        return {
            "response_type": "error",
            "response": f"An error occurred: {str(e)}",
            "conversation_id": conversation_id,
            "metadata": {
                "intent": "",
                "query_strategy": "",
                "execution_time_ms": execution_time_ms,
                "neo4j_results_count": 0,
                "milvus_results_count": 0,
            },
            "results": [],
        }


async def continue_search(
    clarification_response: str,
    conversation_id: str,
    previous_state: dict,
) -> dict:
    """Continue search after user provides clarification.

    Args:
        clarification_response: User's clarification response
        conversation_id: Conversation ID
        previous_state: Previous workflow state

    Returns:
        Workflow result
    """
    # Update entities with clarification
    entities = previous_state.get("entities", {})
    missing_info = previous_state.get("missing_info", [])

    if missing_info:
        # Add clarification to appropriate entity field
        field = missing_info[0]
        entities[field] = clarification_response

    # Update query to include clarification context
    original_query = previous_state.get("query", "")
    updated_query = f"{original_query} ({clarification_response})"

    # Create updated state
    updated_state = {
        **previous_state,
        "query": updated_query,
        "entities": entities,
        "missing_info": [],  # Clear missing info
    }

    # Run search from routing step
    return await run_search(
        query=updated_query,
        tenant_id=previous_state.get("tenant_id", "default"),
        conversation_id=conversation_id,
    )
