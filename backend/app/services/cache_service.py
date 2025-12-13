"""Cache service using Redis."""

import logging
import json
from typing import Any, Optional

import redis.asyncio as redis

from app.config import get_settings

logger = logging.getLogger(__name__)


class CacheService:
    """Service for caching operations via Redis."""

    _client: Optional[redis.Redis] = None

    def __init__(self):
        self.settings = get_settings().redis

    async def connect(self) -> None:
        """Establish connection to Redis."""
        if self._client is None:
            self._client = redis.Redis(
                host=self.settings.host,
                port=self.settings.port,
                db=self.settings.db,
                password=self.settings.password,
                decode_responses=True,
            )
            logger.info(f"Connected to Redis at {self.settings.host}:{self.settings.port}")

    async def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("Closed Redis connection")

    async def _ensure_connected(self) -> redis.Redis:
        """Ensure connection and return client."""
        if self._client is None:
            await self.connect()
        return self._client

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        client = await self._ensure_connected()
        value = await client.get(key)

        if value is None:
            return None

        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> None:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds
        """
        client = await self._ensure_connected()

        if isinstance(value, (dict, list)):
            value = json.dumps(value)

        if ttl:
            await client.setex(key, ttl, value)
        else:
            await client.set(key, value)

    async def delete(self, key: str) -> None:
        """Delete key from cache.

        Args:
            key: Cache key
        """
        client = await self._ensure_connected()
        await client.delete(key)

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache.

        Args:
            key: Cache key

        Returns:
            True if key exists
        """
        client = await self._ensure_connected()
        return await client.exists(key) > 0

    async def get_schema(self, tenant_id: str, source: str) -> Optional[dict]:
        """Get cached schema for a tenant.

        Args:
            tenant_id: Tenant identifier
            source: Schema source (neo4j or mssql)

        Returns:
            Cached schema or None
        """
        key = f"schema:{source}:{tenant_id}"
        return await self.get(key)

    async def set_schema(
        self,
        tenant_id: str,
        source: str,
        schema: dict,
    ) -> None:
        """Cache schema for a tenant.

        Args:
            tenant_id: Tenant identifier
            source: Schema source
            schema: Schema data
        """
        key = f"schema:{source}:{tenant_id}"
        await self.set(key, schema, ttl=self.settings.schema_ttl)

    async def get_conversation(self, conversation_id: str) -> Optional[dict]:
        """Get conversation state.

        Args:
            conversation_id: Conversation identifier

        Returns:
            Conversation state or None
        """
        key = f"conversation:{conversation_id}"
        return await self.get(key)

    async def set_conversation(
        self,
        conversation_id: str,
        state: dict,
        ttl: int = 3600,
    ) -> None:
        """Cache conversation state.

        Args:
            conversation_id: Conversation identifier
            state: Conversation state
            ttl: Time-to-live in seconds
        """
        key = f"conversation:{conversation_id}"
        await self.set(key, state, ttl=ttl)

    async def get_embedding(self, text_hash: str) -> Optional[list[float]]:
        """Get cached embedding.

        Args:
            text_hash: Hash of the text

        Returns:
            Cached embedding or None
        """
        key = f"embedding:{text_hash}"
        return await self.get(key)

    async def set_embedding(
        self,
        text_hash: str,
        embedding: list[float],
    ) -> None:
        """Cache embedding.

        Args:
            text_hash: Hash of the text
            embedding: Embedding vector
        """
        key = f"embedding:{text_hash}"
        await self.set(key, embedding, ttl=self.settings.embedding_ttl)

    async def increment_counter(self, key: str, ttl: Optional[int] = None) -> int:
        """Increment a counter.

        Args:
            key: Counter key
            ttl: Time-to-live in seconds

        Returns:
            New counter value
        """
        client = await self._ensure_connected()
        value = await client.incr(key)

        if ttl and value == 1:
            await client.expire(key, ttl)

        return value

    async def health_check(self) -> bool:
        """Check if Redis is accessible."""
        try:
            client = await self._ensure_connected()
            await client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False
