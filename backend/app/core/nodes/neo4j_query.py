"""Neo4j query execution node."""

import logging
import json

from app.models.state import SearchState
from app.services.neo4j_service import Neo4jService
from app.services.llm_service import LLMService
from app.services.embedding_service import EmbeddingService
from app.core.prompts.cypher_generation import (
    CYPHER_GENERATION_PROMPT,
    CYPHER_CORRECTION_PROMPT,
)

logger = logging.getLogger(__name__)


async def neo4j_query_node(state: SearchState) -> dict:
    """Generate and execute Cypher query on Neo4j.

    This node uses LLM to generate a Cypher query based on the
    schema and user query, then executes it.

    Args:
        state: Current workflow state

    Returns:
        Updated state with cypher_query and neo4j_results
    """
    query = state["query"]
    intent = state["intent"]
    entities = state.get("entities", {})
    schema = state.get("schema_neo4j", {})

    neo4j = Neo4jService()
    llm = LLMService()
    embedding_service = EmbeddingService()

    await neo4j.connect()

    try:
        # Check if we should use vector search
        use_vector = should_use_vector_search(intent, entities, schema)

        if use_vector:
            # Generate query embedding
            query_embedding = await embedding_service.embed_query(query)

            # Execute vector search
            results = await execute_vector_search(
                neo4j, query_embedding, schema, entities
            )

            return {
                "neo4j_results": results,
                "cypher_query": "Vector search executed",
            }

        # Generate Cypher query using LLM
        cypher_query = await generate_cypher(
            llm, query, intent, entities, schema
        )

        # Execute query
        try:
            # Check if query needs embedding parameter
            if "$embedding" in cypher_query:
                query_embedding = await embedding_service.embed_query(query)
                results = await neo4j.run(cypher_query, {"embedding": query_embedding})
            else:
                results = await neo4j.run(cypher_query)

            # Format results
            formatted_results = format_neo4j_results(results)

            logger.info(f"Neo4j query returned {len(formatted_results)} results")

            return {
                "cypher_query": cypher_query,
                "neo4j_results": formatted_results,
            }

        except Exception as e:
            logger.warning(f"Cypher query failed: {e}, attempting correction")

            # Try to self-correct
            corrected_query = await correct_cypher(
                llm, cypher_query, str(e), schema
            )

            if corrected_query != cypher_query:
                results = await neo4j.run(corrected_query)
                formatted_results = format_neo4j_results(results)

                return {
                    "cypher_query": corrected_query,
                    "neo4j_results": formatted_results,
                }
            else:
                raise

    except Exception as e:
        logger.error(f"Neo4j query execution failed: {e}")
        return {
            "cypher_query": "",
            "neo4j_results": [],
            "error": str(e),
        }

    finally:
        await neo4j.close()


def should_use_vector_search(intent: str, entities: dict, schema: dict) -> bool:
    """Determine if vector search should be used.

    Args:
        intent: Query intent
        entities: Extracted entities
        schema: Neo4j schema

    Returns:
        True if vector search is appropriate
    """
    # Check if vector indexes exist
    vector_indexes = schema.get("vector_indexes", [])
    if not vector_indexes:
        return False

    # Use vector for similarity queries
    if intent == "SIMILARITY":
        return True

    # For search without specific IDs, consider vector
    if intent in ["ASSET_SEARCH", "ASSET_STATUS"]:
        if not entities.get("entity_id"):
            # Use vector if query seems semantic
            return True

    return False


async def execute_vector_search(
    neo4j: Neo4jService,
    query_embedding: list[float],
    schema: dict,
    entities: dict,
) -> list[dict]:
    """Execute vector similarity search.

    Args:
        neo4j: Neo4j service
        query_embedding: Query embedding vector
        schema: Neo4j schema
        entities: Extracted entities

    Returns:
        Search results
    """
    # Get first available vector index
    vector_indexes = schema.get("vector_indexes", [])
    if not vector_indexes:
        return []

    index_name = vector_indexes[0]

    # Build filter if entities specify constraints
    filter_query = build_vector_filter(entities)

    results = await neo4j.vector_search(
        index_name=index_name,
        query_vector=query_embedding,
        k=20,
        filter_query=filter_query,
    )

    return [
        {
            "id": r["node"].get("id", ""),
            "source": "neo4j",
            "entity_type": list(r["node"].keys())[0] if r["node"] else "Unknown",
            "content": r["node"].get("description", str(r["node"])),
            "properties": r["node"],
            "score": r["score"],
        }
        for r in results
    ]


def build_vector_filter(entities: dict) -> str:
    """Build filter clause for vector search.

    Args:
        entities: Extracted entities

    Returns:
        Filter clause string
    """
    conditions = []

    if entities.get("location"):
        loc = entities["location"]
        conditions.append(f'toLower(node.location) CONTAINS toLower("{loc}")')

    if entities.get("status"):
        status = entities["status"]
        conditions.append(f'toLower(node.status) = toLower("{status}")')

    if entities.get("entity_type"):
        # Can't filter by label in vector search post-filter
        pass

    return " AND ".join(conditions)


async def generate_cypher(
    llm: LLMService,
    query: str,
    intent: str,
    entities: dict,
    schema: dict,
) -> str:
    """Generate Cypher query using LLM.

    Args:
        llm: LLM service
        query: User query
        intent: Query intent
        entities: Extracted entities
        schema: Neo4j schema

    Returns:
        Generated Cypher query
    """
    # Format schema for prompt
    labels = schema.get("labels", [])
    relationships = schema.get("relationship_types", [])
    properties = schema.get("properties_by_label", {})
    samples = schema.get("sample_values", {})
    vector_indexes = schema.get("vector_indexes", [])

    # Format properties
    props_str = ""
    for label, props_list in list(properties.items())[:10]:
        prop_names = [p["name"] for p in props_list[:8]]
        props_str += f"  {label}: {', '.join(prop_names)}\n"

    # Format samples
    samples_str = ""
    for key, values in list(samples.items())[:15]:
        samples_str += f"  {key}: {values[:3]}\n"

    prompt = CYPHER_GENERATION_PROMPT.format(
        labels=", ".join(labels),
        relationship_types=", ".join(relationships),
        properties_by_label=props_str,
        sample_values=samples_str,
        vector_indexes=", ".join(vector_indexes) if vector_indexes else "None",
        limit=100,
        user_query=query,
        intent=intent,
        entities=json.dumps(entities),
    )

    response = await llm.generate(prompt, temperature=0.1)
    return clean_cypher(response)


async def correct_cypher(
    llm: LLMService,
    original_query: str,
    error: str,
    schema: dict,
) -> str:
    """Attempt to correct a failed Cypher query.

    Args:
        llm: LLM service
        original_query: Failed query
        error: Error message
        schema: Neo4j schema

    Returns:
        Corrected Cypher query
    """
    prompt = CYPHER_CORRECTION_PROMPT.format(
        original_query=original_query,
        error_message=error,
        labels=", ".join(schema.get("labels", [])),
        relationship_types=", ".join(schema.get("relationship_types", [])),
    )

    response = await llm.generate(prompt, temperature=0.1)
    return clean_cypher(response)


def clean_cypher(query: str) -> str:
    """Clean LLM-generated Cypher query.

    Args:
        query: Raw query string

    Returns:
        Cleaned query
    """
    query = query.strip()

    # Remove markdown code blocks
    if query.startswith("```cypher"):
        query = query[9:]
    elif query.startswith("```"):
        query = query[3:]

    if query.endswith("```"):
        query = query[:-3]

    return query.strip()


def format_neo4j_results(results: list[dict]) -> list[dict]:
    """Format Neo4j results for response.

    Args:
        results: Raw Neo4j results

    Returns:
        Formatted results
    """
    formatted = []

    for result in results:
        # Handle different result formats
        if "node" in result:
            node = result["node"]
            formatted.append({
                "id": node.get("id", str(id(node))),
                "source": "neo4j",
                "entity_type": "Node",
                "content": node.get("description", json.dumps(node)),
                "properties": node,
                "score": result.get("score"),
            })
        else:
            # Direct property results
            formatted.append({
                "id": result.get("id", str(id(result))),
                "source": "neo4j",
                "entity_type": "Result",
                "content": json.dumps(result),
                "properties": result,
                "score": None,
            })

    return formatted
