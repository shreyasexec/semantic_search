"""LLM service for text generation using Ollama."""

import logging
import httpx
from typing import Optional, AsyncIterator

from app.config import get_settings

logger = logging.getLogger(__name__)


class LLMService:
    """Service for LLM operations via Ollama."""

    def __init__(self):
        self.settings = get_settings().ollama
        self.base_url = self.settings.base_url

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
    ) -> str:
        """Generate text completion.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Generation temperature (0-1)
            max_tokens: Maximum tokens to generate
            model: Model to use (defaults to config)

        Returns:
            Generated text
        """
        model = model or self.settings.model_generation
        temperature = temperature if temperature is not None else self.settings.temperature
        max_tokens = max_tokens or self.settings.num_predict

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "num_ctx": self.settings.num_ctx,
            },
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()

            result = response.json()
            return result["message"]["content"]

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        model: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """Generate text completion with streaming.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Generation temperature
            model: Model to use

        Yields:
            Generated text tokens
        """
        model = model or self.settings.model_generation
        temperature = temperature if temperature is not None else self.settings.temperature

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "options": {
                "temperature": temperature,
                "num_ctx": self.settings.num_ctx,
            },
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        import json
                        data = json.loads(line)
                        if "message" in data and "content" in data["message"]:
                            yield data["message"]["content"]

    async def classify(
        self,
        text: str,
        categories: list[str],
        context: str = "",
    ) -> str:
        """Classify text into one of the categories.

        Args:
            text: Text to classify
            categories: List of possible categories
            context: Additional context

        Returns:
            Selected category
        """
        prompt = f"""Classify the following text into exactly one of these categories: {', '.join(categories)}

{f'Context: {context}' if context else ''}

Text: {text}

Respond with ONLY the category name, nothing else."""

        result = await self.generate(prompt, temperature=0.1)
        result = result.strip()

        # Validate result is one of the categories
        for cat in categories:
            if cat.lower() in result.lower():
                return cat

        logger.warning(f"Classification result '{result}' not in categories, returning first")
        return categories[0]

    async def extract_json(
        self,
        text: str,
        schema_description: str,
    ) -> dict:
        """Extract structured JSON from text.

        Args:
            text: Text to extract from
            schema_description: Description of expected JSON schema

        Returns:
            Extracted JSON dictionary
        """
        prompt = f"""Extract structured information from the following text.

Expected schema:
{schema_description}

Text: {text}

Respond with ONLY valid JSON, no explanation."""

        result = await self.generate(prompt, temperature=0.1)

        # Clean and parse JSON
        result = result.strip()
        if result.startswith("```json"):
            result = result[7:]
        if result.startswith("```"):
            result = result[3:]
        if result.endswith("```"):
            result = result[:-3]

        import json
        try:
            return json.loads(result)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            return {}

    async def generate_description(
        self,
        entity_type: str,
        properties: dict,
    ) -> str:
        """Generate natural language description for an entity.

        Args:
            entity_type: Type of entity
            properties: Entity properties

        Returns:
            Generated description
        """
        prop_str = "\n".join(f"  {k}: {v}" for k, v in properties.items() if v)

        prompt = f"""Generate a concise, informative description for this {entity_type} entity:

Properties:
{prop_str}

Generate a single sentence description that captures the key characteristics.
Respond with ONLY the description, no explanation."""

        result = await self.generate(prompt, temperature=0.3)
        return result.strip()

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int = 10,
    ) -> list[int]:
        """Rerank documents by relevance to query.

        Args:
            query: Search query
            documents: List of documents to rank
            top_k: Number of top results to return

        Returns:
            List of indices in ranked order
        """
        if len(documents) <= top_k:
            return list(range(len(documents)))

        # Use LLM to score relevance
        doc_str = "\n".join(f"{i+1}. {doc[:200]}" for i, doc in enumerate(documents))

        prompt = f"""Given the query and documents below, rank the documents by relevance.
Return the document numbers in order of relevance, most relevant first.

Query: {query}

Documents:
{doc_str}

Return ONLY a comma-separated list of document numbers (e.g., "3,1,5,2,4"), nothing else."""

        result = await self.generate(prompt, temperature=0.1)

        # Parse ranking
        try:
            indices = [int(x.strip()) - 1 for x in result.split(",")]
            # Validate and deduplicate
            valid_indices = []
            seen = set()
            for idx in indices:
                if 0 <= idx < len(documents) and idx not in seen:
                    valid_indices.append(idx)
                    seen.add(idx)
            return valid_indices[:top_k]
        except Exception as e:
            logger.warning(f"Failed to parse ranking: {e}")
            return list(range(min(top_k, len(documents))))

    async def health_check(self) -> bool:
        """Check if Ollama is accessible."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception as e:
            logger.error(f"LLM health check failed: {e}")
            return False
