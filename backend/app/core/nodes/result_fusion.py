"""Result fusion node using Reciprocal Rank Fusion (RRF)."""

import logging
from collections import defaultdict
from typing import Any

from app.models.state import SearchState
from app.config import get_settings

logger = logging.getLogger(__name__)


async def fuse_results_node(state: SearchState) -> dict:
    """Fuse results from multiple sources using RRF.

    This node combines results from Neo4j and Milvus using
    Reciprocal Rank Fusion to produce a unified ranking.

    Args:
        state: Current workflow state

    Returns:
        Updated state with fused_results
    """
    neo4j_results = state.get("neo4j_results", [])
    milvus_results = state.get("milvus_results", [])
    query_strategy = state.get("query_strategy", "hybrid")

    # If only one source, return those results
    if query_strategy == "neo4j":
        logger.info(f"Single source (Neo4j): {len(neo4j_results)} results")
        return {"fused_results": neo4j_results}

    if query_strategy == "milvus":
        logger.info(f"Single source (Milvus): {len(milvus_results)} results")
        return {"fused_results": milvus_results}

    # Fuse results from both sources
    if not neo4j_results and not milvus_results:
        return {"fused_results": []}

    if not neo4j_results:
        return {"fused_results": milvus_results}

    if not milvus_results:
        return {"fused_results": neo4j_results}

    # Apply RRF fusion
    fused = reciprocal_rank_fusion(
        [neo4j_results, milvus_results],
        k=get_settings().app.rrf_k,
    )

    logger.info(
        f"Fused {len(neo4j_results)} Neo4j + {len(milvus_results)} Milvus = "
        f"{len(fused)} results"
    )

    return {"fused_results": fused}


def reciprocal_rank_fusion(
    rankings: list[list[dict]],
    k: int = 60,
) -> list[dict]:
    """Apply Reciprocal Rank Fusion to combine multiple rankings.

    RRF formula: score(d) = sum(1 / (k + rank(d)))
    where k is a constant (typically 60) to prevent high-ranked
    items from dominating.

    Args:
        rankings: List of ranked result lists
        k: RRF constant (default 60)

    Returns:
        Fused ranking as list of results
    """
    # Calculate RRF scores
    scores = defaultdict(float)
    result_map = {}  # Store full result objects

    for ranking in rankings:
        for rank, result in enumerate(ranking, start=1):
            # Use id as unique key
            result_id = get_result_id(result)

            # RRF score contribution
            scores[result_id] += 1 / (k + rank)

            # Store result (prefer newer/more complete version)
            if result_id not in result_map:
                result_map[result_id] = result
            else:
                # Merge properties if from different sources
                existing = result_map[result_id]
                if existing.get("source") != result.get("source"):
                    result_map[result_id] = merge_results(existing, result)

    # Sort by RRF score
    sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

    # Build final list with RRF scores
    fused_results = []
    for rank, result_id in enumerate(sorted_ids, start=1):
        result = result_map[result_id].copy()
        result["rrf_score"] = scores[result_id]
        result["fused_rank"] = rank
        fused_results.append(result)

    return fused_results


def get_result_id(result: dict) -> str:
    """Get unique identifier for a result.

    Args:
        result: Result dictionary

    Returns:
        Unique identifier string
    """
    # Prefer explicit id
    if result.get("id"):
        return str(result["id"])

    # Fall back to incident_id for Milvus results
    if result.get("incident_id"):
        return f"incident:{result['incident_id']}"

    # Generate from content hash
    content = result.get("content", "")
    return f"hash:{hash(content)}"


def merge_results(result1: dict, result2: dict) -> dict:
    """Merge two results from different sources.

    Args:
        result1: First result
        result2: Second result

    Returns:
        Merged result
    """
    merged = result1.copy()

    # Track sources
    sources = {result1.get("source"), result2.get("source")}
    merged["sources"] = list(sources - {None})

    # Merge properties
    props1 = result1.get("properties", {})
    props2 = result2.get("properties", {})

    if isinstance(props1, dict) and isinstance(props2, dict):
        merged["properties"] = {**props1, **props2}

    # Use higher score
    score1 = result1.get("score") or 0
    score2 = result2.get("score") or 0
    merged["score"] = max(score1, score2)

    # Combine content if different
    content1 = result1.get("content", "")
    content2 = result2.get("content", "")
    if content1 != content2 and content2:
        merged["content"] = f"{content1}\n---\n{content2}"

    return merged


def deduplicate_results(results: list[dict]) -> list[dict]:
    """Remove duplicate results.

    Args:
        results: List of results

    Returns:
        Deduplicated list
    """
    seen = set()
    unique = []

    for result in results:
        result_id = get_result_id(result)
        if result_id not in seen:
            seen.add(result_id)
            unique.append(result)

    return unique


def filter_low_score_results(
    results: list[dict],
    min_score: float = 0.5,
) -> list[dict]:
    """Filter out results with low relevance scores.

    Args:
        results: List of results
        min_score: Minimum score threshold

    Returns:
        Filtered results
    """
    return [
        r for r in results
        if (r.get("score") or 0) >= min_score
        or (r.get("rrf_score") or 0) >= (1 / (60 + 10))  # Top 10 equivalent
    ]
