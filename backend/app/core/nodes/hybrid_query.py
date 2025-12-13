"""Hybrid query execution node."""

import logging
import asyncio

from app.models.state import SearchState
from app.core.nodes.neo4j_query import neo4j_query_node
from app.core.nodes.milvus_query import milvus_query_node

logger = logging.getLogger(__name__)


async def hybrid_query_node(state: SearchState) -> dict:
    """Execute queries on both Neo4j and Milvus.

    This node runs queries on both data sources in parallel
    for hybrid intent queries.

    Args:
        state: Current workflow state

    Returns:
        Updated state with results from both sources
    """
    logger.info("Executing hybrid query on Neo4j and Milvus")

    try:
        # Execute both queries in parallel
        neo4j_task = asyncio.create_task(neo4j_query_node(state))
        milvus_task = asyncio.create_task(milvus_query_node(state))

        # Wait for both to complete
        neo4j_result, milvus_result = await asyncio.gather(
            neo4j_task,
            milvus_task,
            return_exceptions=True,
        )

        # Handle potential exceptions
        neo4j_results = []
        milvus_results = []
        cypher_query = ""
        milvus_filter = ""

        if isinstance(neo4j_result, dict):
            neo4j_results = neo4j_result.get("neo4j_results", [])
            cypher_query = neo4j_result.get("cypher_query", "")
        elif isinstance(neo4j_result, Exception):
            logger.error(f"Neo4j query failed in hybrid: {neo4j_result}")

        if isinstance(milvus_result, dict):
            milvus_results = milvus_result.get("milvus_results", [])
            milvus_filter = milvus_result.get("milvus_filter", "")
        elif isinstance(milvus_result, Exception):
            logger.error(f"Milvus query failed in hybrid: {milvus_result}")

        logger.info(
            f"Hybrid query: Neo4j={len(neo4j_results)} results, "
            f"Milvus={len(milvus_results)} results"
        )

        return {
            "neo4j_results": neo4j_results,
            "milvus_results": milvus_results,
            "cypher_query": cypher_query,
            "milvus_filter": milvus_filter,
        }

    except Exception as e:
        logger.error(f"Hybrid query failed: {e}")
        return {
            "neo4j_results": [],
            "milvus_results": [],
            "error": str(e),
        }


async def cross_reference_results(
    neo4j_results: list[dict],
    milvus_results: list[dict],
    state: SearchState,
) -> list[dict]:
    """Cross-reference results from both sources.

    For queries like "cameras near incident location", this finds
    the incident location from Milvus and queries Neo4j for cameras.

    Args:
        neo4j_results: Results from Neo4j
        milvus_results: Results from Milvus
        state: Current workflow state

    Returns:
        Cross-referenced results
    """
    intent = state["intent"]
    entities = state.get("entities", {})

    # If looking for assets near incidents
    if _is_asset_near_incident_query(intent, entities):
        return await _get_assets_near_incidents(
            milvus_results,
            state,
        )

    # If looking for incidents affecting assets
    if _is_incident_affecting_asset_query(intent, entities):
        return await _get_incidents_affecting_assets(
            neo4j_results,
            state,
        )

    # Default: return combined results
    return neo4j_results + milvus_results


def _is_asset_near_incident_query(intent: str, entities: dict) -> bool:
    """Check if query is looking for assets near an incident."""
    if intent != "HYBRID":
        return False

    keywords = entities.get("keywords", [])
    return any(
        kw in ["near", "at", "location", "affected"]
        for kw in [k.lower() for k in keywords]
    )


def _is_incident_affecting_asset_query(intent: str, entities: dict) -> bool:
    """Check if query is looking for incidents affecting an asset."""
    if intent != "HYBRID":
        return False

    entity_id = entities.get("entity_id", "")
    return bool(entity_id) and "inc" not in entity_id.lower()


async def _get_assets_near_incidents(
    incident_results: list[dict],
    state: SearchState,
) -> list[dict]:
    """Get assets near incident locations.

    Args:
        incident_results: Results from Milvus incident search
        state: Current workflow state

    Returns:
        Assets near incident locations
    """
    from app.services.neo4j_service import Neo4jService

    if not incident_results:
        return []

    # Extract locations from incidents
    locations = set()
    for incident in incident_results:
        props = incident.get("properties", {})
        if isinstance(props, dict):
            loc = props.get("location")
            if loc:
                locations.add(loc)

    if not locations:
        return incident_results

    # Query Neo4j for assets at those locations
    neo4j = Neo4jService()
    await neo4j.connect()

    try:
        # Build location filter
        loc_conditions = " OR ".join([
            f'toLower(n.location) CONTAINS toLower("{loc}")'
            for loc in locations
        ])

        entity_type = state.get("entities", {}).get("entity_type", "")

        if entity_type:
            query = f"""
                MATCH (n:{entity_type})
                WHERE {loc_conditions}
                RETURN n
                LIMIT 20
            """
        else:
            query = f"""
                MATCH (n)
                WHERE {loc_conditions}
                RETURN n
                LIMIT 20
            """

        results = await neo4j.run(query)

        asset_results = [
            {
                "id": r["n"].get("id", ""),
                "source": "neo4j",
                "entity_type": "Asset",
                "content": r["n"].get("description", str(r["n"])),
                "properties": dict(r["n"]),
                "score": 1.0,
            }
            for r in results
        ]

        return asset_results + incident_results

    finally:
        await neo4j.close()


async def _get_incidents_affecting_assets(
    asset_results: list[dict],
    state: SearchState,
) -> list[dict]:
    """Get incidents affecting specific assets.

    Args:
        asset_results: Results from Neo4j asset search
        state: Current workflow state

    Returns:
        Incidents affecting the assets
    """
    if not asset_results:
        return []

    # Extract locations from assets
    locations = set()
    for asset in asset_results:
        props = asset.get("properties", {})
        if isinstance(props, dict):
            loc = props.get("location")
            if loc:
                locations.add(loc)

    if not locations:
        return asset_results

    # The Milvus search would already have been done
    # Just filter/rank results by matching locations
    milvus_results = state.get("milvus_results", [])

    matching_incidents = []
    for incident in milvus_results:
        props = incident.get("properties", {})
        if isinstance(props, dict):
            inc_loc = props.get("location", "")
            if any(loc.lower() in inc_loc.lower() for loc in locations):
                incident["location_match"] = True
                matching_incidents.append(incident)

    return asset_results + matching_incidents
