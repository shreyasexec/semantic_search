"""Tests for proposition chunking."""

import pytest

from app.ingestion.chunker import PropositionChunker, chunk_incident_record


class TestPropositionChunker:
    """Test proposition chunking logic."""

    def test_chunk_description(self):
        """Test description chunking."""
        chunker = PropositionChunker()
        chunks = chunker.chunk_incident(
            incident_id="INC-001",
            description="Fire detected at Building A. Emergency response initiated.",
        )

        # Should have summary + description chunks
        assert len(chunks) >= 2
        assert any(c["chunk_type"] == "summary" for c in chunks)
        assert any(c["chunk_type"] == "description" for c in chunks)

    def test_chunk_response_plan_list(self):
        """Test response plan chunking with list."""
        chunker = PropositionChunker()
        chunks = chunker.chunk_incident(
            incident_id="INC-001",
            response_plan=["Step 1: Evacuate", "Step 2: Call fire dept"],
        )

        rp_chunks = [c for c in chunks if c["chunk_type"] == "response_plan"]
        assert len(rp_chunks) == 2

    def test_chunk_action_items(self):
        """Test action items chunking."""
        chunker = PropositionChunker()
        chunks = chunker.chunk_incident(
            incident_id="INC-001",
            action_items=[
                {"action": "Evacuate", "assignee": "Team A", "status": "Complete"},
                {"action": "Notify", "assignee": "Team B", "status": "Pending"},
            ],
        )

        action_chunks = [c for c in chunks if c["chunk_type"] == "action_item"]
        assert len(action_chunks) == 2
        assert "Team A" in action_chunks[0]["content"]

    def test_chunk_with_all_fields(self):
        """Test chunking with all fields."""
        chunker = PropositionChunker()
        chunks = chunker.chunk_incident(
            incident_id="INC-001",
            description="Fire incident",
            response_plan=["Step 1"],
            action_items=[{"action": "Evacuate"}],
            context="Additional context",
            properties={"severity": "high"},
        )

        chunk_types = {c["chunk_type"] for c in chunks}
        assert "summary" in chunk_types
        assert "description" in chunk_types
        assert "response_plan" in chunk_types
        assert "action_item" in chunk_types
        assert "context" in chunk_types

    def test_chunk_incident_record(self):
        """Test convenience function."""
        record = {
            "incident_id": "INC-001",
            "description": "Test incident",
            "incident_type": "Fire",
            "severity": "high",
        }

        chunks = chunk_incident_record(record)
        assert len(chunks) > 0
        assert all("incident_id" not in c or c.get("incident_id") for c in chunks)

    def test_chunk_ids_are_unique(self):
        """Test chunk IDs are unique."""
        chunker = PropositionChunker()
        chunks = chunker.chunk_incident(
            incident_id="INC-001",
            description="Sentence one. Sentence two. Sentence three.",
        )

        ids = [c["id"] for c in chunks]
        assert len(ids) == len(set(ids)), "Chunk IDs must be unique"

    def test_split_sentences(self):
        """Test sentence splitting."""
        chunker = PropositionChunker()

        sentences = chunker._split_sentences(
            "First sentence. Second sentence! Third sentence?"
        )
        assert len(sentences) == 3

    def test_extract_steps_numbered(self):
        """Test numbered step extraction."""
        chunker = PropositionChunker()

        steps = chunker._extract_steps("1. First step. 2. Second step. 3. Third step.")
        assert len(steps) >= 2
