"""FastAPI REST API routes."""

import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, BackgroundTasks
from fastapi.responses import StreamingResponse

from app.models.request import QueryRequest, ClarifyRequest
from app.models.response import (
    QueryResponse,
    VoiceResponse,
    HealthResponse,
    ResponseMetadata,
    SearchResult,
    ClarificationResponse,
    ClarificationOption,
)
from app.core.workflow import run_search, continue_search
from app.services.cache_service import CacheService
from app.dependencies import (
    get_config,
    get_cache,
    TenantValidator,
    init_services,
)
from app.ingestion.scheduler import get_scheduler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Search"])


@router.post("/query", response_model=QueryResponse)
async def execute_query(
    request: QueryRequest,
    cache: CacheService = Depends(get_cache),
) -> QueryResponse:
    """Execute a semantic search query.

    Args:
        request: Query request with query text and tenant_id
        cache: Cache service for conversation state

    Returns:
        Query response with results or clarification
    """
    # Validate tenant
    if not TenantValidator.validate(request.tenant_id):
        raise HTTPException(status_code=400, detail="Invalid tenant_id")

    logger.info(f"Query received: {request.query[:50]}... from {request.tenant_id}")

    try:
        # Run search workflow
        result = await run_search(
            query=request.query,
            tenant_id=request.tenant_id,
            conversation_id=request.conversation_id,
        )

        # Cache conversation state for potential follow-up
        if result.get("conversation_id"):
            await cache.set_conversation(
                result["conversation_id"],
                {
                    "query": request.query,
                    "tenant_id": request.tenant_id,
                    "intent": result["metadata"]["intent"],
                    "entities": result.get("entities", {}),
                },
            )

        # Build response
        return QueryResponse(
            response_type=result["response_type"],
            response=result["response"],
            clarification=_build_clarification(result) if result.get("clarification") else None,
            results=[_build_search_result(r) for r in result.get("results", [])[:20]],
            metadata=ResponseMetadata(
                intent=result["metadata"]["intent"],
                query_strategy=result["metadata"]["query_strategy"],
                execution_time_ms=result["metadata"]["execution_time_ms"],
                neo4j_results_count=result["metadata"]["neo4j_results_count"],
                milvus_results_count=result["metadata"]["milvus_results_count"],
                cypher_query=result["metadata"].get("cypher_query"),
            ),
            conversation_id=result["conversation_id"],
        )

    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clarify", response_model=QueryResponse)
async def submit_clarification(
    request: ClarifyRequest,
    cache: CacheService = Depends(get_cache),
) -> QueryResponse:
    """Submit a clarification response.

    Args:
        request: Clarification request with conversation_id and response
        cache: Cache service for conversation state

    Returns:
        Query response with results
    """
    # Get previous conversation state
    previous_state = await cache.get_conversation(request.conversation_id)

    if not previous_state:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found or expired",
        )

    logger.info(f"Clarification received for {request.conversation_id}")

    try:
        # Continue search with clarification
        result = await continue_search(
            clarification_response=request.clarification_response,
            conversation_id=request.conversation_id,
            previous_state=previous_state,
        )

        # Update conversation state
        await cache.set_conversation(
            request.conversation_id,
            {
                **previous_state,
                "clarification": request.clarification_response,
            },
        )

        return QueryResponse(
            response_type=result["response_type"],
            response=result["response"],
            clarification=_build_clarification(result) if result.get("clarification") else None,
            results=[_build_search_result(r) for r in result.get("results", [])[:20]],
            metadata=ResponseMetadata(
                intent=result["metadata"]["intent"],
                query_strategy=result["metadata"]["query_strategy"],
                execution_time_ms=result["metadata"]["execution_time_ms"],
                neo4j_results_count=result["metadata"]["neo4j_results_count"],
                milvus_results_count=result["metadata"]["milvus_results_count"],
                cypher_query=result["metadata"].get("cypher_query"),
            ),
            conversation_id=request.conversation_id,
        )

    except Exception as e:
        logger.error(f"Clarification processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/voice", response_model=VoiceResponse)
async def transcribe_voice(
    audio: UploadFile = File(...),
) -> VoiceResponse:
    """Transcribe voice input to text.

    Args:
        audio: Audio file upload

    Returns:
        Transcribed text
    """
    logger.info(f"Voice transcription request: {audio.filename}")

    try:
        # Read audio data
        audio_data = await audio.read()

        # TODO: Implement Whisper transcription
        # For now, return placeholder
        # whisper_service = WhisperService()
        # result = await whisper_service.transcribe(audio_data)

        return VoiceResponse(
            text="Voice transcription not yet implemented",
            confidence=0.0,
        )

    except Exception as e:
        logger.error(f"Voice transcription failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Check system health.

    Returns:
        Health status of all components
    """
    from app.services.neo4j_service import Neo4jService
    from app.services.milvus_service import MilvusService
    from app.services.llm_service import LLMService
    from app.services.cache_service import CacheService

    components = {}

    # Check Neo4j
    try:
        neo4j = Neo4jService()
        await neo4j.connect()
        healthy = await neo4j.health_check()
        components["neo4j"] = "healthy" if healthy else "unhealthy"
        await neo4j.close()
    except Exception as e:
        components["neo4j"] = f"unhealthy: {e}"

    # Check Milvus
    try:
        milvus = MilvusService()
        healthy = milvus.health_check()
        components["milvus"] = "healthy" if healthy else "unhealthy"
    except Exception as e:
        components["milvus"] = f"unhealthy: {e}"

    # Check LLM
    try:
        llm = LLMService()
        healthy = await llm.health_check()
        components["ollama"] = "healthy" if healthy else "unhealthy"
    except Exception as e:
        components["ollama"] = f"unhealthy: {e}"

    # Check Redis
    try:
        cache = CacheService()
        healthy = await cache.health_check()
        components["redis"] = "healthy" if healthy else "unhealthy"
    except Exception as e:
        components["redis"] = f"unhealthy: {e}"

    # Determine overall status
    unhealthy_count = sum(1 for v in components.values() if "unhealthy" in v)

    if unhealthy_count == 0:
        status = "healthy"
    elif unhealthy_count < len(components):
        status = "degraded"
    else:
        status = "unhealthy"

    return HealthResponse(
        status=status,
        components=components,
        timestamp=datetime.utcnow(),
    )


@router.post("/sync/{tenant_id}")
async def trigger_sync(
    tenant_id: str,
    full: bool = False,
    background_tasks: BackgroundTasks = None,
) -> dict:
    """Trigger data sync for a tenant.

    Args:
        tenant_id: Tenant identifier
        full: Whether to run full sync
        background_tasks: Background task handler

    Returns:
        Sync status
    """
    if not TenantValidator.validate(tenant_id):
        raise HTTPException(status_code=400, detail="Invalid tenant_id")

    logger.info(f"Sync triggered for {tenant_id} (full={full})")

    scheduler = get_scheduler()

    if background_tasks:
        # Run in background
        background_tasks.add_task(
            scheduler.run_manual_sync,
            tenant_id,
            full,
        )
        return {"status": "started", "tenant_id": tenant_id, "full": full}
    else:
        # Run synchronously
        result = await scheduler.run_manual_sync(tenant_id, full)
        return {"status": "completed", "tenant_id": tenant_id, **result}


@router.get("/schema/{tenant_id}")
async def get_schema(
    tenant_id: str,
    cache: CacheService = Depends(get_cache),
) -> dict:
    """Get discovered schema for a tenant.

    Args:
        tenant_id: Tenant identifier
        cache: Cache service

    Returns:
        Schema information
    """
    if not TenantValidator.validate(tenant_id):
        raise HTTPException(status_code=400, detail="Invalid tenant_id")

    neo4j_schema = await cache.get_schema(tenant_id, "neo4j")
    mssql_schema = await cache.get_schema(tenant_id, "mssql")

    return {
        "tenant_id": tenant_id,
        "neo4j": neo4j_schema or {"status": "not_cached"},
        "mssql": mssql_schema or {"status": "not_cached"},
    }


def _build_clarification(result: dict) -> Optional[ClarificationResponse]:
    """Build clarification response from result."""
    clarification = result.get("clarification")
    if not clarification:
        return None

    return ClarificationResponse(
        question=clarification.get("question", ""),
        options=[
            ClarificationOption(label=o["label"], value=o["value"])
            for o in clarification.get("options", [])
        ],
        allow_free_text=clarification.get("allow_free_text", True),
    )


def _build_search_result(result: dict) -> SearchResult:
    """Build search result from raw result."""
    return SearchResult(
        id=result.get("id", ""),
        source=result.get("source", "unknown"),
        entity_type=result.get("entity_type", "Unknown"),
        content=result.get("content", ""),
        properties=result.get("properties", {}),
        score=result.get("score") or result.get("rrf_score"),
        rank=result.get("final_rank") or result.get("fused_rank"),
    )
