"""Prompt templates for LLM interactions."""

from .intent_classification import INTENT_CLASSIFICATION_PROMPT
from .cypher_generation import CYPHER_GENERATION_PROMPT, CYPHER_CORRECTION_PROMPT
from .clarification import CLARIFICATION_PROMPT
from .response_generation import RESPONSE_GENERATION_PROMPT
from .entity_extraction import ENTITY_EXTRACTION_PROMPT

__all__ = [
    "INTENT_CLASSIFICATION_PROMPT",
    "CYPHER_GENERATION_PROMPT",
    "CYPHER_CORRECTION_PROMPT",
    "CLARIFICATION_PROMPT",
    "RESPONSE_GENERATION_PROMPT",
    "ENTITY_EXTRACTION_PROMPT",
]
