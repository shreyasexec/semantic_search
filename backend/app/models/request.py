"""API request models."""

from pydantic import BaseModel, Field
from typing import Optional


class QueryRequest(BaseModel):
    """Request model for semantic search query."""

    query: str = Field(..., description="User's natural language query", min_length=1)
    tenant_id: str = Field(..., description="Tenant identifier")
    conversation_id: Optional[str] = Field(
        default=None,
        description="Conversation ID for multi-turn conversations",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query": "What is the status of cameras on second floor?",
                "tenant_id": "tenant_001",
                "conversation_id": "conv_abc123",
            }
        }


class ClarifyRequest(BaseModel):
    """Request model for clarification response."""

    conversation_id: str = Field(..., description="Conversation ID")
    clarification_response: str = Field(
        ...,
        description="User's response to clarification question",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "conversation_id": "conv_abc123",
                "clarification_response": "Building A",
            }
        }


class VoiceRequest(BaseModel):
    """Request model for voice transcription."""

    audio_format: str = Field(
        default="wav",
        description="Audio format (wav, mp3, etc.)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "audio_format": "wav",
            }
        }


class WebSocketMessage(BaseModel):
    """WebSocket message format."""

    type: str = Field(..., description="Message type: query, clarify")
    query: Optional[str] = Field(default=None, description="Query text")
    tenant_id: Optional[str] = Field(default=None, description="Tenant ID")
    conversation_id: Optional[str] = Field(default=None, description="Conversation ID")
    response: Optional[str] = Field(
        default=None,
        description="Clarification response",
    )
