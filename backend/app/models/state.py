"""LangGraph state definition for search workflow."""

from typing import TypedDict, Literal, Annotated, Optional, Any
from langgraph.graph.message import add_messages


class SearchState(TypedDict):
    """State for the semantic search workflow.

    This state flows through the LangGraph workflow and accumulates
    information at each step.
    """

    # Input
    query: str  # Original user query
    tenant_id: str  # Tenant identifier for multi-tenancy
    conversation_id: str  # For multi-turn conversations
    messages: Annotated[list, add_messages]  # Conversation history

    # Schema (discovered dynamically)
    schema_neo4j: dict  # Discovered Neo4j schema
    schema_mssql: dict  # Discovered MSSQL/Milvus schema

    # Query Understanding
    intent: str  # Classified intent (ASSET_STATUS, INCIDENT_SEARCH, etc.)
    entities: dict  # Extracted entities from query
    missing_info: list  # List of missing required information
    clarification_question: str  # Question to ask user if info missing
    clarification_options: list  # Options to present to user

    # Query Execution
    query_strategy: Literal["neo4j", "milvus", "hybrid"]  # Where to query
    cypher_query: str  # Generated Cypher query for Neo4j
    milvus_filter: str  # Generated filter expression for Milvus
    milvus_query_embedding: list  # Query embedding for Milvus search

    # Results
    neo4j_results: list  # Results from Neo4j
    milvus_results: list  # Results from Milvus
    fused_results: list  # RRF-fused results from both sources
    reranked_results: list  # Results after LLM reranking

    # Output
    response: str  # Final natural language response
    response_type: Literal["answer", "clarification", "error"]  # Response type
    error: Optional[str]  # Error message if any


# Intent types
INTENT_TYPES = [
    "ASSET_STATUS",  # Status of assets (cameras, sensors)
    "ASSET_SEARCH",  # Finding/listing assets
    "INCIDENT_DETAIL",  # Specific incident details
    "INCIDENT_SEARCH",  # Finding incidents by criteria
    "AGGREGATION",  # Counting, statistics
    "RELATIONSHIP",  # Connections between entities
    "SIMILARITY",  # Finding similar entities
    "HYBRID",  # Requires both asset and incident data
]


def create_initial_state(
    query: str,
    tenant_id: str,
    conversation_id: str = "",
) -> SearchState:
    """Create initial state for a new search.

    Args:
        query: User's natural language query
        tenant_id: Tenant identifier
        conversation_id: Optional conversation ID for multi-turn

    Returns:
        Initial SearchState
    """
    return SearchState(
        query=query,
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        messages=[],
        schema_neo4j={},
        schema_mssql={},
        intent="",
        entities={},
        missing_info=[],
        clarification_question="",
        clarification_options=[],
        query_strategy="hybrid",
        cypher_query="",
        milvus_filter="",
        milvus_query_embedding=[],
        neo4j_results=[],
        milvus_results=[],
        fused_results=[],
        reranked_results=[],
        response="",
        response_type="answer",
        error=None,
    )
