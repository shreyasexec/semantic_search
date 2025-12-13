"""Proposition chunking for incident data."""

import re
import json
import uuid
import logging
from typing import Any

logger = logging.getLogger(__name__)


class PropositionChunker:
    """Chunk incidents into atomic propositions.

    This follows the proposition chunking strategy where each chunk
    represents a single, self-contained fact about an incident.
    """

    def chunk_incident(
        self,
        incident_id: str,
        description: str = "",
        response_plan: str | list = None,
        action_items: list = None,
        context: str = "",
        properties: dict = None,
    ) -> list[dict]:
        """Chunk an incident into proposition chunks.

        Args:
            incident_id: Incident identifier
            description: Main incident description
            response_plan: Response plan (string or list)
            action_items: List of action items
            context: Additional context
            properties: Incident properties for metadata

        Returns:
            List of chunk dictionaries
        """
        chunks = []
        properties = properties or {}

        # Chunk description into sentences
        if description:
            desc_chunks = self._chunk_description(incident_id, description)
            chunks.extend(desc_chunks)

        # Chunk response plan
        if response_plan:
            rp_chunks = self._chunk_response_plan(incident_id, response_plan)
            chunks.extend(rp_chunks)

        # Chunk action items
        if action_items:
            ai_chunks = self._chunk_action_items(incident_id, action_items)
            chunks.extend(ai_chunks)

        # Chunk context
        if context:
            ctx_chunks = self._chunk_context(incident_id, context)
            chunks.extend(ctx_chunks)

        # Add incident summary chunk
        if chunks:
            summary = self._create_summary_chunk(incident_id, properties, chunks)
            chunks.insert(0, summary)

        logger.debug(f"Created {len(chunks)} chunks for incident {incident_id}")

        return chunks

    def _chunk_description(
        self,
        incident_id: str,
        description: str,
    ) -> list[dict]:
        """Chunk description into sentences.

        Args:
            incident_id: Incident identifier
            description: Description text

        Returns:
            List of description chunks
        """
        sentences = self._split_sentences(description)
        chunks = []

        for i, sentence in enumerate(sentences):
            if sentence.strip():
                chunks.append({
                    "id": f"{incident_id}_desc_{i}",
                    "chunk_type": "description",
                    "content": f"Incident {incident_id}: {sentence.strip()}",
                })

        return chunks

    def _chunk_response_plan(
        self,
        incident_id: str,
        response_plan: str | list,
    ) -> list[dict]:
        """Chunk response plan into steps.

        Args:
            incident_id: Incident identifier
            response_plan: Response plan content

        Returns:
            List of response plan chunks
        """
        chunks = []

        # Parse if JSON string
        if isinstance(response_plan, str):
            try:
                response_plan = json.loads(response_plan)
            except json.JSONDecodeError:
                # Treat as text, extract steps
                steps = self._extract_steps(response_plan)
                for i, step in enumerate(steps):
                    chunks.append({
                        "id": f"{incident_id}_rp_{i}",
                        "chunk_type": "response_plan",
                        "content": f"Response plan for {incident_id}: {step}",
                    })
                return chunks

        # Handle list of steps
        if isinstance(response_plan, list):
            for i, step in enumerate(response_plan):
                if isinstance(step, dict):
                    step_text = step.get("step", step.get("action", str(step)))
                else:
                    step_text = str(step)

                chunks.append({
                    "id": f"{incident_id}_rp_{i}",
                    "chunk_type": "response_plan",
                    "content": f"Response plan for {incident_id}: {step_text}",
                })

        # Handle dict with steps key
        elif isinstance(response_plan, dict):
            steps = response_plan.get("steps", [])
            for i, step in enumerate(steps):
                chunks.append({
                    "id": f"{incident_id}_rp_{i}",
                    "chunk_type": "response_plan",
                    "content": f"Response plan for {incident_id}: {step}",
                })

        return chunks

    def _chunk_action_items(
        self,
        incident_id: str,
        action_items: list,
    ) -> list[dict]:
        """Chunk action items.

        Args:
            incident_id: Incident identifier
            action_items: List of action items

        Returns:
            List of action item chunks
        """
        chunks = []

        for i, item in enumerate(action_items):
            if isinstance(item, dict):
                content = self._format_action_item(item)
            else:
                content = str(item)

            chunks.append({
                "id": f"{incident_id}_action_{i}",
                "chunk_type": "action_item",
                "content": f"Action item for {incident_id}: {content}",
            })

        return chunks

    def _chunk_context(
        self,
        incident_id: str,
        context: str,
    ) -> list[dict]:
        """Chunk context information.

        Args:
            incident_id: Incident identifier
            context: Context text

        Returns:
            List of context chunks
        """
        # Parse if JSON
        if isinstance(context, str):
            try:
                context = json.loads(context)
            except json.JSONDecodeError:
                pass

        if isinstance(context, dict):
            chunks = []
            for key, value in context.items():
                if value:
                    chunks.append({
                        "id": f"{incident_id}_ctx_{key}",
                        "chunk_type": "context",
                        "content": f"Context for {incident_id} - {key}: {value}",
                    })
            return chunks

        # Simple string context
        return [{
            "id": f"{incident_id}_context",
            "chunk_type": "context",
            "content": f"Context for {incident_id}: {context}",
        }]

    def _create_summary_chunk(
        self,
        incident_id: str,
        properties: dict,
        chunks: list[dict],
    ) -> dict:
        """Create a summary chunk for the incident.

        Args:
            incident_id: Incident identifier
            properties: Incident properties
            chunks: Existing chunks

        Returns:
            Summary chunk
        """
        parts = [f"Incident {incident_id}"]

        if properties.get("incident_type"):
            parts.append(f"Type: {properties['incident_type']}")

        if properties.get("severity"):
            parts.append(f"Severity: {properties['severity']}")

        if properties.get("location"):
            parts.append(f"Location: {properties['location']}")

        if properties.get("status"):
            parts.append(f"Status: {properties['status']}")

        parts.append(f"Contains {len(chunks)} detail records")

        return {
            "id": f"{incident_id}_summary",
            "chunk_type": "summary",
            "content": ". ".join(parts),
        }

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences.

        Args:
            text: Input text

        Returns:
            List of sentences
        """
        # Split on sentence boundaries
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _extract_steps(self, text: str) -> list[str]:
        """Extract numbered steps from text.

        Args:
            text: Input text

        Returns:
            List of steps
        """
        # Try numbered pattern
        steps = re.findall(r'\d+\.\s*([^.]+\.?)', text)
        if steps:
            return [s.strip() for s in steps if s.strip()]

        # Try bullet pattern
        steps = re.findall(r'[-*]\s*([^-*\n]+)', text)
        if steps:
            return [s.strip() for s in steps if s.strip()]

        # Fall back to sentences
        return self._split_sentences(text)

    def _format_action_item(self, item: dict) -> str:
        """Format action item dictionary to string.

        Args:
            item: Action item dictionary

        Returns:
            Formatted string
        """
        parts = []

        if "action" in item:
            parts.append(item["action"])
        elif "task" in item:
            parts.append(item["task"])

        if "assignee" in item:
            parts.append(f"assigned to {item['assignee']}")

        if "due_date" in item:
            parts.append(f"due {item['due_date']}")

        if "status" in item:
            parts.append(f"({item['status']})")

        if "priority" in item:
            parts.append(f"[{item['priority']}]")

        return " ".join(parts) if parts else str(item)


def chunk_incident_record(record: dict) -> list[dict]:
    """Chunk an incident record from MSSQL.

    Convenience function for processing database records.

    Args:
        record: Incident record dictionary

    Returns:
        List of chunks
    """
    chunker = PropositionChunker()

    return chunker.chunk_incident(
        incident_id=record.get("incident_id") or record.get("id", str(uuid.uuid4())),
        description=record.get("description", ""),
        response_plan=record.get("response_plan"),
        action_items=record.get("action_items") or [],
        context=record.get("context", ""),
        properties={
            "incident_type": record.get("incident_type"),
            "severity": record.get("severity"),
            "status": record.get("status"),
            "location": record.get("location"),
            "created_at": record.get("created_at"),
            "updated_at": record.get("updated_at"),
        },
    )
