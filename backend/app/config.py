"""Configuration management for Smart City Semantic Search."""

from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from typing import Optional


class Neo4jSettings(BaseSettings):
    """Neo4j database configuration."""

    uri: str = Field(default="neo4j://192.168.110.201:7687", env="NEO4J_URI")
    database: str = Field(default="neo4j", env="NEO4J_DATABASE")
    username: str = Field(default="neo4j", env="NEO4J_USER")
    password: str = Field(default="password123", env="NEO4J_PASSWORD")
    max_connection_pool_size: int = Field(default=50)
    connection_acquisition_timeout: int = Field(default=60)
    query_timeout: int = Field(default=30000)  # ms


class MSSQLSettings(BaseSettings):
    """MSSQL database configuration."""

    host: str = Field(default="192.168.110.56", env="MSSQL_HOST")
    port: int = Field(default=1444, env="MSSQL_PORT")
    database: str = Field(default="default", env="MSSQL_DATABASE")
    username: str = Field(default="administrator", env="MSSQL_USER")
    password: str = Field(default="trinity@123", env="MSSQL_PASSWORD")
    table: str = Field(default="INCIDENT_EXECUTION_LOGS", env="MSSQL_TABLE")
    driver: str = Field(default="ODBC Driver 17 for SQL Server")


class MilvusSettings(BaseSettings):
    """Milvus vector database configuration."""

    host: str = Field(default="localhost", env="MILVUS_HOST")
    port: int = Field(default=19530, env="MILVUS_PORT")
    collection_entities: str = Field(default="entities")
    collection_schema: str = Field(default="schema_metadata")
    collection_stats: str = Field(default="statistics")

    # HNSW index parameters
    hnsw_m: int = Field(default=16)
    hnsw_ef_construction: int = Field(default=256)
    hnsw_ef_search: int = Field(default=128)


class OllamaSettings(BaseSettings):
    """Ollama LLM configuration."""

    host: str = Field(default="192.168.1.120", env="OLLAMA_HOST")
    port: int = Field(default=11434, env="OLLAMA_PORT")
    model_generation: str = Field(default="llama3.1:8b", env="OLLAMA_MODEL_GENERATION")
    model_embedding: str = Field(default="nomic-embed-text", env="OLLAMA_MODEL_EMBEDDING")
    num_ctx: int = Field(default=4096)
    num_predict: int = Field(default=1024)
    temperature: float = Field(default=0.3)

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"


class RedisSettings(BaseSettings):
    """Redis cache configuration."""

    host: str = Field(default="localhost", env="REDIS_HOST")
    port: int = Field(default=6379, env="REDIS_PORT")
    db: int = Field(default=0, env="REDIS_DB")
    password: Optional[str] = Field(default=None, env="REDIS_PASSWORD")

    # TTL settings (seconds)
    schema_ttl: int = Field(default=300)  # 5 minutes
    embedding_ttl: int = Field(default=3600)  # 1 hour
    statistics_ttl: int = Field(default=300)  # 5 minutes


class AppSettings(BaseSettings):
    """Application settings."""

    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    debug: bool = Field(default=False, env="DEBUG")

    # Ingestion settings
    ingestion_interval_minutes: int = Field(default=5, env="INGESTION_INTERVAL_MINUTES")
    ingestion_batch_size: int = Field(default=500)

    # Search settings
    max_results: int = Field(default=100)
    embedding_dimension: int = Field(default=768)
    rrf_k: int = Field(default=60)

    # Embedding batch size
    embedding_batch_size: int = Field(default=100)

    # Target latency (seconds)
    target_latency: int = Field(default=10)


class Settings(BaseSettings):
    """Combined settings."""

    neo4j: Neo4jSettings = Neo4jSettings()
    mssql: MSSQLSettings = MSSQLSettings()
    milvus: MilvusSettings = MilvusSettings()
    ollama: OllamaSettings = OllamaSettings()
    redis: RedisSettings = RedisSettings()
    app: AppSettings = AppSettings()

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
