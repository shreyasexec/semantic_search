"""Cypher query generation prompts."""

CYPHER_GENERATION_PROMPT = """You are a Neo4j Cypher expert. Generate a Cypher query based on the schema and user query.

SCHEMA:
Node Labels: {labels}
Relationship Types: {relationship_types}

Properties by Label:
{properties_by_label}

Sample Values:
{sample_values}

Vector Indexes: {vector_indexes}

RULES:
1. Use ONLY labels, relationships, and properties from the schema
2. Use toLower() for case-insensitive string matching
3. For vector similarity search, use:
   CALL db.index.vector.queryNodes($index_name, $k, $embedding) YIELD node, score
4. Always include relevant properties in RETURN
5. Use LIMIT {limit} for safety
6. For aggregations, use COUNT(), SUM(), AVG() as appropriate
7. Handle NULL values with COALESCE() or IS NOT NULL
8. Use parameterized queries with $ prefix for values

VECTOR SEARCH PATTERN:
When semantic similarity is needed:
```
CALL db.index.vector.queryNodes('index_name', 10, $embedding)
YIELD node, score
WHERE score > 0.7
RETURN node, score
ORDER BY score DESC
```

USER QUERY: {user_query}
INTENT: {intent}
EXTRACTED ENTITIES: {entities}

Generate ONLY the Cypher query, no explanation. If the query needs an embedding parameter, use $embedding."""


CYPHER_CORRECTION_PROMPT = """The following Cypher query failed with an error. Please fix it.

ORIGINAL QUERY:
{original_query}

ERROR:
{error_message}

SCHEMA:
Node Labels: {labels}
Relationship Types: {relationship_types}

Common fixes:
1. Check if labels and property names match the schema exactly (case-sensitive)
2. Ensure relationship directions are correct
3. Use proper syntax for functions (toLower, CONTAINS, etc.)
4. Check parameter names start with $
5. Verify vector index names exist

Generate ONLY the corrected Cypher query, no explanation."""
