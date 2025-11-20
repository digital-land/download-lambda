"""Pydantic models for request validation."""

from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class PathParams(BaseModel):
    """Path parameters extracted from the URL."""

    dataset: str = Field(..., min_length=1, max_length=100, description="Dataset name")
    extension: Literal["csv", "json", "parquet"] = Field(
        ..., description="Output format extension"
    )

    @field_validator("dataset")
    @classmethod
    def validate_dataset(cls, v: str) -> str:
        """Validate dataset name to prevent path traversal."""
        if ".." in v or "/" in v or "\\" in v:
            raise ValueError("Dataset name cannot contain path separators or '..'")
        # Remove any file extensions if accidentally included
        if "." in v:
            v = v.split(".")[0]
        return v

    @field_validator("extension", mode="before")
    @classmethod
    def validate_extension(cls, v: str) -> str:
        """Normalize extension to lowercase before validation."""
        if isinstance(v, str):
            return v.lower().replace(".", "")
        return v


class QueryParams(BaseModel):
    """Query parameters from the request."""

    model_config = ConfigDict(populate_by_name=True)

    organisation_entity: Optional[str] = Field(
        None,
        alias="organisation-entity",
        description="Filter by organisation entity",
    )


class RequestContext(BaseModel):
    """Complete validated request context."""

    path_params: PathParams
    query_params: QueryParams

    @property
    def output_format(self) -> str:
        """Get the output format."""
        return self.path_params.extension

    @property
    def filter_value(self) -> Optional[str]:
        """Get the filter value if present."""
        return self.query_params.organisation_entity
