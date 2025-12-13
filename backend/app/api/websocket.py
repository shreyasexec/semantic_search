"""WebSocket handlers for real-time chat."""

import logging
import json
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.models.request import WebSocketMessage
from app.core.workflow import run_search, continue_search
from app.services.cache_service import CacheService
from app.dependencies import TenantValidator

logger = logging.getLogger(__name__)

websocket_router = APIRouter()


class ConnectionManager:
    """Manage WebSocket connections."""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str) -> None:
        """Accept and store connection."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"Client {client_id} connected")

    def disconnect(self, client_id: str) -> None:
        """Remove connection."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"Client {client_id} disconnected")

    async def send_json(self, client_id: str, data: dict) -> None:
        """Send JSON message to client."""
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json(data)


manager = ConnectionManager()


@websocket_router.websocket("/ws/chat/{client_id}")
async def websocket_chat(
    websocket: WebSocket,
    client_id: str,
) -> None:
    """WebSocket endpoint for real-time chat.

    Args:
        websocket: WebSocket connection
        client_id: Client identifier
    """
    await manager.connect(websocket, client_id)
    cache = CacheService()
    await cache.connect()

    try:
        while True:
            # Receive message
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                await manager.send_json(client_id, {
                    "type": "error",
                    "message": "Invalid JSON",
                })
                continue

            # Process message
            await process_message(client_id, message, cache)

    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket error for {client_id}: {e}")
        manager.disconnect(client_id)


async def process_message(
    client_id: str,
    message: dict,
    cache: CacheService,
) -> None:
    """Process incoming WebSocket message.

    Args:
        client_id: Client identifier
        message: Message data
        cache: Cache service
    """
    msg_type = message.get("type")

    if msg_type == "query":
        await handle_query(client_id, message, cache)
    elif msg_type == "clarify":
        await handle_clarify(client_id, message, cache)
    else:
        await manager.send_json(client_id, {
            "type": "error",
            "message": f"Unknown message type: {msg_type}",
        })


async def handle_query(
    client_id: str,
    message: dict,
    cache: CacheService,
) -> None:
    """Handle query message.

    Args:
        client_id: Client identifier
        message: Query message
        cache: Cache service
    """
    query = message.get("query")
    tenant_id = message.get("tenant_id")
    conversation_id = message.get("conversation_id")

    if not query or not tenant_id:
        await manager.send_json(client_id, {
            "type": "error",
            "message": "Missing query or tenant_id",
        })
        return

    if not TenantValidator.validate(tenant_id):
        await manager.send_json(client_id, {
            "type": "error",
            "message": "Invalid tenant_id",
        })
        return

    # Send processing status
    await manager.send_json(client_id, {
        "type": "processing",
        "message": "Processing your query...",
    })

    try:
        # Run search
        result = await run_search(
            query=query,
            tenant_id=tenant_id,
            conversation_id=conversation_id,
        )

        # Cache conversation state
        if result.get("conversation_id"):
            await cache.set_conversation(
                result["conversation_id"],
                {
                    "query": query,
                    "tenant_id": tenant_id,
                    "intent": result["metadata"]["intent"],
                },
            )

        # Send response
        await manager.send_json(client_id, {
            "type": "complete",
            "response_type": result["response_type"],
            "response": result["response"],
            "clarification": result.get("clarification"),
            "results": result.get("results", [])[:10],
            "metadata": result["metadata"],
            "conversation_id": result["conversation_id"],
        })

    except Exception as e:
        logger.error(f"Query processing failed: {e}")
        await manager.send_json(client_id, {
            "type": "error",
            "message": str(e),
        })


async def handle_clarify(
    client_id: str,
    message: dict,
    cache: CacheService,
) -> None:
    """Handle clarification message.

    Args:
        client_id: Client identifier
        message: Clarification message
        cache: Cache service
    """
    conversation_id = message.get("conversation_id")
    response = message.get("response")

    if not conversation_id or not response:
        await manager.send_json(client_id, {
            "type": "error",
            "message": "Missing conversation_id or response",
        })
        return

    # Get previous state
    previous_state = await cache.get_conversation(conversation_id)

    if not previous_state:
        await manager.send_json(client_id, {
            "type": "error",
            "message": "Conversation not found or expired",
        })
        return

    # Send processing status
    await manager.send_json(client_id, {
        "type": "processing",
        "message": "Processing clarification...",
    })

    try:
        # Continue search
        result = await continue_search(
            clarification_response=response,
            conversation_id=conversation_id,
            previous_state=previous_state,
        )

        # Send response
        await manager.send_json(client_id, {
            "type": "complete",
            "response_type": result["response_type"],
            "response": result["response"],
            "clarification": result.get("clarification"),
            "results": result.get("results", [])[:10],
            "metadata": result["metadata"],
            "conversation_id": conversation_id,
        })

    except Exception as e:
        logger.error(f"Clarification processing failed: {e}")
        await manager.send_json(client_id, {
            "type": "error",
            "message": str(e),
        })


async def send_streaming_response(
    client_id: str,
    response_generator,
) -> None:
    """Send streaming response to client.

    Args:
        client_id: Client identifier
        response_generator: Async generator yielding response tokens
    """
    try:
        async for token in response_generator:
            await manager.send_json(client_id, {
                "type": "streaming",
                "token": token,
            })
    except Exception as e:
        logger.error(f"Streaming error: {e}")
