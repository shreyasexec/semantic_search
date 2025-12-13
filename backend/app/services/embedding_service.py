"""Embedding service for vector generation using Ollama."""

import logging
import httpx
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating embeddings via Ollama."""

    def __init__(self):
        self.settings = get_settings().ollama
        self.app_settings = get_settings().app
        self.base_url = self.settings.base_url

    async def embed(self, text: str, model: Optional[str] = None) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Text to embed
            model: Model to use (defaults to config)

        Returns:
            Embedding vector
        """
        model = model or self.settings.model_embedding

        # Clean and truncate text if needed
        text = text.strip()
        if not text:
            # Return zero vector for empty text
            return [0.0] * self.app_settings.embedding_dimension

        payload = {
            "model": model,
            "prompt": text,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/api/embeddings",
                json=payload,
            )
            response.raise_for_status()

            result = response.json()
            return result["embedding"]

    async def embed_batch(
        self,
        texts: list[str],
        model: Optional[str] = None,
        batch_size: Optional[int] = None,
    ) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed
            model: Model to use
            batch_size: Batch size for processing

        Returns:
            List of embedding vectors
        """
        model = model or self.settings.model_embedding
        batch_size = batch_size or self.app_settings.embedding_batch_size

        embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            # Process batch concurrently
            batch_embeddings = []
            for text in batch:
                embedding = await self.embed(text, model)
                batch_embeddings.append(embedding)

            embeddings.extend(batch_embeddings)

            if i + batch_size < len(texts):
                logger.info(f"Processed {i + batch_size}/{len(texts)} embeddings")

        return embeddings

    async def embed_with_instruction(
        self,
        text: str,
        instruction: str = "search_document",
        model: Optional[str] = None,
    ) -> list[float]:
        """Generate embedding with instruction prefix.

        nomic-embed-text supports instruction-tuned embeddings.
        Common instructions:
        - search_document: For indexing documents
        - search_query: For search queries
        - clustering: For clustering tasks
        - classification: For classification tasks

        Args:
            text: Text to embed
            instruction: Instruction type
            model: Model to use

        Returns:
            Embedding vector
        """
        # For nomic-embed-text, prefix with instruction
        prefixed_text = f"{instruction}: {text}"
        return await self.embed(prefixed_text, model)

    async def embed_query(self, query: str, model: Optional[str] = None) -> list[float]:
        """Generate embedding optimized for search queries.

        Args:
            query: Search query
            model: Model to use

        Returns:
            Query embedding vector
        """
        return await self.embed_with_instruction(query, "search_query", model)

    async def embed_document(self, document: str, model: Optional[str] = None) -> list[float]:
        """Generate embedding optimized for documents.

        Args:
            document: Document text
            model: Model to use

        Returns:
            Document embedding vector
        """
        return await self.embed_with_instruction(document, "search_document", model)

    def cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Calculate cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity (-1 to 1)
        """
        import math

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    async def health_check(self) -> bool:
        """Check if embedding service is accessible."""
        try:
            test_embedding = await self.embed("test")
            return len(test_embedding) == self.app_settings.embedding_dimension
        except Exception as e:
            logger.error(f"Embedding health check failed: {e}")
            return False
