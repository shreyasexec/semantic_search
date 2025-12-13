"""Clarification prompt templates."""

CLARIFICATION_PROMPT = """You are a helpful assistant for a Smart City Command and Control Center.

The user's query is missing some information needed to provide an accurate answer.

USER QUERY: {user_query}
INTENT: {intent}
EXTRACTED ENTITIES: {entities}
MISSING INFORMATION: {missing_info}

AVAILABLE OPTIONS FROM SCHEMA:
{schema_options}

Generate a friendly clarification question to ask the user.
If possible, provide options based on the schema.

OUTPUT FORMAT (JSON):
{{
  "question": "<friendly question to ask the user>",
  "options": [
    {{"label": "<display label>", "value": "<value to use>"}},
    ...
  ],
  "allow_free_text": true
}}

Guidelines:
1. Keep the question concise and clear
2. Provide up to 5 most relevant options if available
3. Allow free text for flexibility
4. Reference what the user asked about

Respond with ONLY valid JSON, no explanation."""


MISSING_INFO_TEMPLATES = {
    "ASSET_STATUS": {
        "location": "Which building or area would you like to check the status for?",
        "entity_type": "What type of asset would you like to check (cameras, sensors, etc.)?",
    },
    "ASSET_SEARCH": {
        "entity_type": "What type of asset are you looking for?",
        "location": "Which location would you like to search in?",
    },
    "INCIDENT_DETAIL": {
        "incident_id": "Which incident would you like details about?",
    },
    "INCIDENT_SEARCH": {
        "time_range": "What time period would you like to search?",
        "location": "Which area would you like to search for incidents?",
    },
    "RELATIONSHIP": {
        "entity_id": "Starting from which entity would you like to find relationships?",
    },
    "SIMILARITY": {
        "entity_id": "Which entity would you like to find similar items to?",
    },
}
