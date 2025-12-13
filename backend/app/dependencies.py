"""FastAPI dependency injection."""

import logging
from typing import AsyncGenerator
from functools import lru_cache

from app.config import get_settings, Settings
from app.services.neo4j_service import Neo4jService
from app.services.milvus_service import MilvusService
from app.services.mssql_service import MSSQLService
from app.services.llm_service import LLMService
from app.services.embedding_service import EmbeddingService
from app.services.cache_service import CacheService

logger = logging.getLogger(__name__)


# Service singletons
_neo4j_service: Neo4jService = None
_milvus_service: MilvusService = None
_mssql_service: MSSQLService = None
_llm_service: LLMService = None
_embedding_service: EmbeddingService = None
_cache_service: CacheService = None


def get_config() -> Settings:
    """Get application configuration."""
    return get_settings()


async def get_neo4j() -> AsyncGenerator[Neo4jService, None]:
    """Get Neo4j service instance."""
    global _neo4j_service
    if _neo4j_service is None:
        _neo4j_service = Neo4jService()
        await _neo4j_service.connect()
    yield _neo4j_service


def get_milvus() -> MilvusService:
    """Get Milvus service instance."""
    global _milvus_service
    if _milvus_service is None:
        _milvus_service = MilvusService()
        _milvus_service.connect()
    return _milvus_service


def get_mssql() -> MSSQLService:
    """Get MSSQL service instance."""
    global _mssql_service
    if _mssql_service is None:
        _mssql_service = MSSQLService()
    return _mssql_service


def get_llm() -> LLMService:
    """Get LLM service instance."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service


def get_embedding() -> EmbeddingService:
    """Get embedding service instance."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


async def get_cache() -> AsyncGenerator[CacheService, None]:
    """Get cache service instance."""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
        await _cache_service.connect()
    yield _cache_service


async def init_services() -> None:
    """Initialize all services on startup."""
    logger.info("Initializing services...")

    global _neo4j_service, _milvus_service, _cache_service

    try:
        # Initialize Neo4j
        _neo4j_service = Neo4jService()
        await _neo4j_service.connect()
        logger.info("Neo4j connected")
    except Exception as e:
        logger.error(f"Neo4j connection failed: {e}")

    try:
        # Initialize Milvus
        _milvus_service = MilvusService()
        _milvus_service.connect()
        logger.info("Milvus connected")
    except Exception as e:
        logger.error(f"Milvus connection failed: {e}")

    try:
        # Initialize Redis cache
        _cache_service = CacheService()
        await _cache_service.connect()
        logger.info("Redis connected")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")

    logger.info("Service initialization complete")


async def cleanup_services() -> None:
    """Cleanup all services on shutdown."""
    logger.info("Cleaning up services...")

    global _neo4j_service, _milvus_service, _mssql_service, _cache_service

    if _neo4j_service:
        await _neo4j_service.close()

    if _milvus_service:
        _milvus_service.close()

    if _mssql_service:
        _mssql_service.close()

    if _cache_service:
        await _cache_service.close()

    logger.info("Service cleanup complete")


class TenantValidator:
    """Validate tenant access."""

    VALID_TENANTS = ["tenant_001", "tenant_002", "tenant_003", "tenant_004"]

    @classmethod
    def validate(cls, tenant_id: str) -> bool:
        """Validate tenant ID.

        Args:
            tenant_id: Tenant identifier

        Returns:
            True if valid tenant
        """
        return tenant_id in cls.VALID_TENANTS

    @classmethod
    def get_tenant_config(cls, tenant_id: str) -> dict:
        """Get tenant-specific configuration.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Tenant configuration
        """
        configs = {
            "tenant_001": {
                "name": "Smart City Alpha",
                "neo4j_database": "neo4j",
                "max_results": 100,
                "voice_enabled": True,
            },
            "tenant_002": {
                "name": "Safe City Beta",
                "neo4j_database": "neo4j",
                "max_results": 50,
                "voice_enabled": True,
            },
            "tenant_003": {
                "name": "City Gamma",
                "neo4j_database": "neo4j",
                "max_results": 100,
                "voice_enabled": False,
            },
            "tenant_004": {
                "name": "Metro Delta",
                "neo4j_database": "neo4j",
                "max_results": 75,
                "voice_enabled": True,
            },
        }

        return configs.get(tenant_id, {
            "name": tenant_id,
            "neo4j_database": "neo4j",
            "max_results": 100,
            "voice_enabled": True,
        })
