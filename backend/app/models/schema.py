"""Schema models for dynamic schema discovery."""

from pydantic import BaseModel, Field
from typing import Any, Optional


class SchemaProperty(BaseModel):
    """Property definition in schema."""

    name: str = Field(..., description="Property name")
    types: list[str] = Field(default_factory=list, description="Property types")
    sample_values: list[Any] = Field(
        default_factory=list,
        description="Sample values for the property",
    )
    is_location: bool = Field(
        default=False,
        description="Whether this property represents location",
    )
    is_time: bool = Field(
        default=False,
        description="Whether this property represents time",
    )
    is_status: bool = Field(
        default=False,
        description="Whether this property represents status",
    )


class Neo4jSchema(BaseModel):
    """Discovered Neo4j schema."""

    labels: list[str] = Field(default_factory=list, description="Node labels")
    relationship_types: list[str] = Field(
        default_factory=list,
        description="Relationship types",
    )
    properties_by_label: dict[str, list[SchemaProperty]] = Field(
        default_factory=dict,
        description="Properties grouped by label",
    )
    sample_values: dict[str, list[Any]] = Field(
        default_factory=dict,
        description="Sample values for properties",
    )
    description: str = Field(
        default="",
        description="Human-readable schema description",
    )
    vector_indexes: list[str] = Field(
        default_factory=list,
        description="Available vector indexes",
    )

    def to_prompt_format(self) -> str:
        """Format schema for inclusion in LLM prompts."""
        lines = [
            "Neo4j Schema:",
            f"  Labels: {', '.join(self.labels)}",
            f"  Relationships: {', '.join(self.relationship_types)}",
            "  Properties by Label:",
        ]

        for label, props in self.properties_by_label.items():
            prop_names = [p.name for p in props]
            lines.append(f"    {label}: {', '.join(prop_names)}")

        if self.sample_values:
            lines.append("  Sample Values:")
            for key, values in list(self.sample_values.items())[:10]:
                lines.append(f"    {key}: {values[:3]}")

        return "\n".join(lines)


class MSSQLSchema(BaseModel):
    """Discovered MSSQL/Incident schema."""

    entity_types: list[str] = Field(
        default_factory=list,
        description="Discovered entity types",
    )
    properties: dict[str, list[SchemaProperty]] = Field(
        default_factory=dict,
        description="Properties by entity type",
    )
    location_fields: list[str] = Field(
        default_factory=list,
        description="Fields representing location",
    )
    status_fields: list[str] = Field(
        default_factory=list,
        description="Fields representing status",
    )
    time_fields: list[str] = Field(
        default_factory=list,
        description="Fields representing time",
    )
    sample_values: dict[str, list[Any]] = Field(
        default_factory=dict,
        description="Sample values for properties",
    )
    description: str = Field(
        default="",
        description="Human-readable schema description",
    )

    def to_prompt_format(self) -> str:
        """Format schema for inclusion in LLM prompts."""
        lines = [
            "Incident Schema (MSSQL/Milvus):",
            f"  Entity Types: {', '.join(self.entity_types)}",
        ]

        for entity_type, props in self.properties.items():
            prop_names = [p.name for p in props]
            lines.append(f"  {entity_type} Properties: {', '.join(prop_names)}")

        if self.location_fields:
            lines.append(f"  Location Fields: {', '.join(self.location_fields)}")

        if self.status_fields:
            lines.append(f"  Status Fields: {', '.join(self.status_fields)}")

        if self.time_fields:
            lines.append(f"  Time Fields: {', '.join(self.time_fields)}")

        return "\n".join(lines)


class TenantConfig(BaseModel):
    """Tenant-specific configuration."""

    id: str = Field(..., description="Tenant identifier")
    name: str = Field(..., description="Tenant display name")
    neo4j_database: str = Field(
        default="neo4j",
        description="Neo4j database for this tenant",
    )
    features: dict[str, Any] = Field(
        default_factory=lambda: {
            "voice_enabled": True,
            "max_results": 100,
        },
        description="Tenant-specific feature flags",
    )


class CombinedSchema(BaseModel):
    """Combined schema from all sources."""

    neo4j: Neo4jSchema = Field(default_factory=Neo4jSchema)
    mssql: MSSQLSchema = Field(default_factory=MSSQLSchema)
    tenant_id: str = Field(default="", description="Tenant ID")
    last_updated: Optional[str] = Field(
        default=None,
        description="Last schema update timestamp",
    )

    def to_prompt_format(self) -> str:
        """Format combined schema for LLM prompts."""
        return f"{self.neo4j.to_prompt_format()}\n\n{self.mssql.to_prompt_format()}"
