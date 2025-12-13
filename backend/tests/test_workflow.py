"""Tests for LangGraph workflow."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.models.state import create_initial_state, INTENT_TYPES
from app.core.workflow import create_workflow


class TestWorkflow:
    """Test workflow creation and execution."""

    def test_create_workflow(self):
        """Test workflow can be created."""
        workflow = create_workflow()
        assert workflow is not None

    def test_initial_state_creation(self):
        """Test initial state is properly created."""
        state = create_initial_state(
            query="test query",
            tenant_id="tenant_001",
            conversation_id="conv_123",
        )

        assert state["query"] == "test query"
        assert state["tenant_id"] == "tenant_001"
        assert state["conversation_id"] == "conv_123"
        assert state["response_type"] == "answer"
        assert state["error"] is None

    def test_intent_types_defined(self):
        """Test all intent types are defined."""
        expected_intents = [
            "ASSET_STATUS",
            "ASSET_SEARCH",
            "INCIDENT_DETAIL",
            "INCIDENT_SEARCH",
            "AGGREGATION",
            "RELATIONSHIP",
            "SIMILARITY",
            "HYBRID",
        ]

        for intent in expected_intents:
            assert intent in INTENT_TYPES


class TestIntentClassification:
    """Test intent classification logic."""

    @pytest.mark.asyncio
    async def test_classify_asset_status(self):
        """Test asset status intent classification."""
        from app.core.nodes.intent_classifier import parse_intent_response

        result = parse_intent_response("ASSET_STATUS")
        assert result == "ASSET_STATUS"

    @pytest.mark.asyncio
    async def test_classify_incident_search(self):
        """Test incident search intent classification."""
        from app.core.nodes.intent_classifier import parse_intent_response

        result = parse_intent_response("INCIDENT_SEARCH")
        assert result == "INCIDENT_SEARCH"

    def test_parse_intent_with_extra_text(self):
        """Test intent parsing handles extra text."""
        from app.core.nodes.intent_classifier import parse_intent_response

        result = parse_intent_response("The intent is ASSET_STATUS based on the query")
        assert result == "ASSET_STATUS"

    def test_parse_unknown_intent_defaults_to_hybrid(self):
        """Test unknown intent defaults to HYBRID."""
        from app.core.nodes.intent_classifier import parse_intent_response

        result = parse_intent_response("UNKNOWN_INTENT")
        assert result == "HYBRID"


class TestEntityExtraction:
    """Test entity extraction logic."""

    def test_resolve_time_references_today(self):
        """Test time reference resolution for today."""
        from app.core.nodes.entity_extractor import resolve_time_references

        entities = {"time_range": {"relative": "today"}}
        result = resolve_time_references(entities)

        assert "time_range" in result
        assert "start" in result["time_range"]
        assert "end" in result["time_range"]

    def test_resolve_time_references_yesterday(self):
        """Test time reference resolution for yesterday."""
        from app.core.nodes.entity_extractor import resolve_time_references

        entities = {"time_range": {"relative": "yesterday"}}
        result = resolve_time_references(entities)

        assert "time_range" in result
        assert "start" in result["time_range"]


class TestResultFusion:
    """Test result fusion logic."""

    def test_rrf_single_source(self):
        """Test RRF with single source returns as-is."""
        from app.core.nodes.result_fusion import reciprocal_rank_fusion

        results = [{"id": "1"}, {"id": "2"}]
        fused = reciprocal_rank_fusion([results])

        assert len(fused) == 2

    def test_rrf_multiple_sources(self):
        """Test RRF combines multiple sources."""
        from app.core.nodes.result_fusion import reciprocal_rank_fusion

        neo4j = [{"id": "1"}, {"id": "2"}]
        milvus = [{"id": "2"}, {"id": "3"}]

        fused = reciprocal_rank_fusion([neo4j, milvus])

        # ID "2" should rank higher as it appears in both
        assert len(fused) == 3

    def test_get_result_id(self):
        """Test result ID extraction."""
        from app.core.nodes.result_fusion import get_result_id

        assert get_result_id({"id": "test"}) == "test"
        assert get_result_id({"incident_id": "INC-001"}) == "incident:INC-001"
