"""Result reranking node using LLM."""

import logging

from app.models.state import SearchState
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


async def rerank_results_node(state: SearchState) -> dict:
    """Rerank results using LLM for better relevance.

    This node uses the LLM to reorder results based on
    their relevance to the original query.

    Args:
        state: Current workflow state

    Returns:
        Updated state with reranked_results
    """
    query = state["query"]
    fused_results = state.get("fused_results", [])

    # Skip reranking if few results
    if len(fused_results) <= 3:
        return {"reranked_results": fused_results}

    # Limit to top candidates for reranking
    candidates = fused_results[:20]

    try:
        # Prepare documents for reranking
        documents = [
            format_result_for_rerank(result)
            for result in candidates
        ]

        # Use LLM to rerank
        llm = LLMService()
        reranked_indices = await llm.rerank(query, documents, top_k=10)

        # Reorder results based on LLM ranking
        reranked = [candidates[i] for i in reranked_indices if i < len(candidates)]

        # Add remaining results that weren't in top candidates
        remaining = fused_results[20:]
        reranked.extend(remaining)

        # Update ranks
        for rank, result in enumerate(reranked, start=1):
            result["final_rank"] = rank

        logger.info(f"Reranked {len(candidates)} results to {len(reranked)}")

        return {"reranked_results": reranked}

    except Exception as e:
        logger.error(f"Reranking failed: {e}, using original order")
        return {"reranked_results": fused_results}


def format_result_for_rerank(result: dict) -> str:
    """Format a result for LLM reranking.

    Args:
        result: Result dictionary

    Returns:
        Formatted string for LLM
    """
    parts = []

    # Entity type and ID
    entity_type = result.get("entity_type", "Unknown")
    result_id = result.get("id", "")
    if result_id:
        parts.append(f"[{entity_type}: {result_id}]")
    else:
        parts.append(f"[{entity_type}]")

    # Main content
    content = result.get("content", "")
    if content:
        # Truncate long content
        parts.append(content[:300])

    # Key properties
    properties = result.get("properties", {})
    if isinstance(properties, dict):
        key_props = []
        for key in ["status", "location", "severity", "incident_type"]:
            if key in properties and properties[key]:
                key_props.append(f"{key}: {properties[key]}")
        if key_props:
            parts.append(f"({', '.join(key_props)})")

    return " ".join(parts)


def simple_rerank(
    results: list[dict],
    query: str,
    boost_factors: dict = None,
) -> list[dict]:
    """Simple rule-based reranking.

    Applies boost factors based on result properties.
    Used as fallback when LLM reranking fails.

    Args:
        results: List of results
        query: Original query
        boost_factors: Property boost factors

    Returns:
        Reranked results
    """
    if not boost_factors:
        boost_factors = {
            "exact_match": 2.0,
            "id_match": 1.5,
            "high_score": 1.2,
            "recent": 1.1,
        }

    query_lower = query.lower()
    query_words = set(query_lower.split())

    scored_results = []
    for result in results:
        boost = 1.0

        # Boost exact ID matches
        result_id = str(result.get("id", "")).lower()
        if result_id and result_id in query_lower:
            boost *= boost_factors["id_match"]

        # Boost content matches
        content = result.get("content", "").lower()
        matching_words = sum(1 for word in query_words if word in content)
        if matching_words > 0:
            boost *= 1 + (matching_words * 0.1)

        # Boost high original scores
        original_score = result.get("score", 0)
        if original_score and original_score > 0.8:
            boost *= boost_factors["high_score"]

        # Calculate final score
        base_score = result.get("rrf_score", 0) or result.get("score", 0) or 0.5
        final_score = base_score * boost

        scored_results.append((result, final_score))

    # Sort by final score
    scored_results.sort(key=lambda x: x[1], reverse=True)

    # Extract results and update ranks
    reranked = []
    for rank, (result, score) in enumerate(scored_results, start=1):
        result = result.copy()
        result["rerank_score"] = score
        result["final_rank"] = rank
        reranked.append(result)

    return reranked


def diversity_rerank(
    results: list[dict],
    diversity_weight: float = 0.3,
) -> list[dict]:
    """Rerank with diversity consideration.

    Ensures variety in result types and sources.

    Args:
        results: List of results
        diversity_weight: Weight for diversity (0-1)

    Returns:
        Diversity-reranked results
    """
    if len(results) <= 3:
        return results

    reranked = []
    remaining = results.copy()
    seen_types = set()
    seen_sources = set()

    while remaining:
        best_idx = 0
        best_score = -1

        for idx, result in enumerate(remaining):
            # Base score (position in original list)
            base_score = 1 / (idx + 1)

            # Diversity bonus
            entity_type = result.get("entity_type", "")
            source = result.get("source", "")

            diversity_bonus = 0
            if entity_type not in seen_types:
                diversity_bonus += 0.5
            if source not in seen_sources:
                diversity_bonus += 0.5

            # Combined score
            combined = base_score + (diversity_weight * diversity_bonus)

            if combined > best_score:
                best_score = combined
                best_idx = idx

        # Add best result
        selected = remaining.pop(best_idx)
        reranked.append(selected)

        # Track seen types and sources
        seen_types.add(selected.get("entity_type", ""))
        seen_sources.add(selected.get("source", ""))

    return reranked
