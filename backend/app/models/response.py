"""API response models."""

from pydantic import BaseModel, Field
from typing import Optional, Any, Literal
from datetime import datetime


class ClarificationOption(BaseModel):
    """Option for clarification question."""

    label: str = Field(..., description="Display label for the option")
    value: str = Field(..., description="Value to use if selected")


class ClarificationResponse(BaseModel):
    """Clarification request to user."""

    question: str = Field(..., description="Clarification question")
    options: list[ClarificationOption] = Field(
        default_factory=list,
        description="Options for the user to choose from",
    )
    allow_free_text: bool = Field(
        default=True,
        description="Whether free text response is allowed",
    )


class SearchResult(BaseModel):
    """Individual search result."""

    id: str = Field(..., description="Entity ID")
    source: str = Field(..., description="Source: neo4j or milvus")
    entity_type: str = Field(..., description="Type of entity")
    content: str = Field(..., description="Main content/description")
    properties: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional properties",
    )
    score: Optional[float] = Field(
        default=None,
        description="Relevance score",
    )
    rank: Optional[int] = Field(
        default=None,
        description="Result rank",
    )


class ResponseMetadata(BaseModel):
    """Metadata about the query execution."""

    intent: str = Field(..., description="Classified intent")
    query_strategy: str = Field(..., description="Query strategy used")
    execution_time_ms: int = Field(..., description="Execution time in milliseconds")
    neo4j_results_count: int = Field(default=0, description="Results from Neo4j")
    milvus_results_count: int = Field(default=0, description="Results from Milvus")
    cypher_query: Optional[str] = Field(
        default=None,
        description="Generated Cypher query (if applicable)",
    )


class QueryResponse(BaseModel):
    """Response model for semantic search query."""

    response_type: Literal["answer", "clarification", "error"] = Field(
        ...,
        description="Type of response",
    )
    response: str = Field(..., description="Natural language response")
    clarification: Optional[ClarificationResponse] = Field(
        default=None,
        description="Clarification details if response_type is clarification",
    )
    results: list[SearchResult] = Field(
        default_factory=list,
        description="Search results",
    )
    metadata: ResponseMetadata = Field(..., description="Query metadata")
    conversation_id: str = Field(..., description="Conversation ID for follow-up")

    class Config:
        json_schema_extra = {
            "example": {
                "response_type": "answer",
                "response": "There are 5 cameras on the second floor of Building A. 4 are online and 1 is offline.",
                "clarification": None,
                "results": [
                    {
                        "id": "CAM-001",
                        "source": "neo4j",
                        "entity_type": "Camera",
                        "content": "Camera CAM-001 on Floor 2, Building A",
                        "properties": {"status": "online", "location": "Floor 2"},
                        "score": 0.95,
                        "rank": 1,
                    }
                ],
                "metadata": {
                    "intent": "ASSET_STATUS",
                    "query_strategy": "neo4j",
                    "execution_time_ms": 1250,
                    "neo4j_results_count": 5,
                    "milvus_results_count": 0,
                },
                "conversation_id": "conv_abc123",
            }
        }


class VoiceResponse(BaseModel):
    """Response model for voice transcription."""

    text: str = Field(..., description="Transcribed text")
    confidence: Optional[float] = Field(
        default=None,
        description="Transcription confidence score",
    )


class HealthResponse(BaseModel):
    """Response model for health check."""

    status: Literal["healthy", "degraded", "unhealthy"] = Field(
        ...,
        description="Overall system status",
    )
    components: dict[str, str] = Field(
        ...,
        description="Status of individual components",
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Health check timestamp",
    )


class StreamingResponse(BaseModel):
    """Streaming response chunk."""

    type: Literal["streaming", "complete", "error"] = Field(
        ...,
        description="Chunk type",
    )
    token: Optional[str] = Field(
        default=None,
        description="Token for streaming type",
    )
    response: Optional[QueryResponse] = Field(
        default=None,
        description="Full response for complete type",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message for error type",
    )
