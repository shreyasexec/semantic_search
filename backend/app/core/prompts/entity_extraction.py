"""Entity extraction prompt template."""

ENTITY_EXTRACTION_PROMPT = """You are an entity extractor for a Smart City semantic search system.

SCHEMA CONTEXT:
{schema_context}

QUERY INTENT: {intent}

USER QUERY: {user_query}

Extract relevant entities and filters from the query. Consider:
- Entity types (Camera, Sensor, Incident, Building, etc.)
- Specific identifiers (CAM-001, INC-2024-001, Building A)
- Locations (building names, floors, areas, streets)
- Time references (today, yesterday, last week, specific dates)
- Status values (online, offline, active, resolved)
- Severity levels (critical, high, medium, low)
- Incident types (fire, intrusion, alarm, etc.)

OUTPUT FORMAT (JSON):
{{
  "entity_type": "<primary entity type being searched>",
  "entity_id": "<specific entity identifier if mentioned>",
  "incident_id": "<specific incident ID if mentioned>",
  "location": "<location reference if mentioned>",
  "time_range": {{
    "start": "<ISO date or null>",
    "end": "<ISO date or null>",
    "relative": "<relative time like 'today', 'yesterday', 'last week'>"
  }},
  "status": "<status filter if mentioned>",
  "severity": "<severity filter if mentioned>",
  "incident_type": "<type of incident if mentioned>",
  "keywords": ["<other important keywords>"],
  "relationships": ["<relationship types to traverse>"]
}}

Respond with ONLY valid JSON, no explanation."""
