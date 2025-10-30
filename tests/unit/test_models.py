"""
Unit tests for Pydantic models.

These tests verify model validation, field constraints, and data transformation
without any external dependencies.
"""
import pytest
from pydantic import ValidationError

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from models import PathParams, QueryParams, RequestContext


class TestPathParams:
    """Unit tests for PathParams model."""

    def test_valid_path_params_csv(self):
        """Test creating PathParams with valid CSV extension."""
        params = PathParams(dataset="customers", extension="csv")

        assert params.dataset == "customers"
        assert params.extension == "csv"

    def test_valid_path_params_json(self):
        """Test creating PathParams with valid JSON extension."""
        params = PathParams(dataset="transactions", extension="json")

        assert params.dataset == "transactions"
        assert params.extension == "json"

    def test_valid_path_params_parquet(self):
        """Test creating PathParams with valid Parquet extension."""
        params = PathParams(dataset="large-dataset", extension="parquet")

        assert params.dataset == "large-dataset"
        assert params.extension == "parquet"

    def test_dataset_with_hyphens_is_valid(self):
        """Test that dataset names with hyphens are accepted."""
        params = PathParams(dataset="test-dataset-2024", extension="csv")

        assert params.dataset == "test-dataset-2024"

    def test_dataset_with_underscores_is_valid(self):
        """Test that dataset names with underscores are accepted."""
        params = PathParams(dataset="test_dataset", extension="csv")

        assert params.dataset == "test_dataset"

    def test_extension_normalized_to_lowercase(self):
        """Test that extension is normalized to lowercase."""
        params = PathParams(dataset="test", extension="CSV")

        assert params.extension == "csv"

    def test_empty_dataset_raises_validation_error(self):
        """Test that empty dataset name raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            PathParams(dataset="", extension="csv")

        errors = exc_info.value.errors()
        assert any("min_length" in str(error) for error in errors)

    def test_invalid_extension_raises_validation_error(self):
        """Test that invalid extension raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            PathParams(dataset="test", extension="xml")

        errors = exc_info.value.errors()
        assert any(error["type"] == "literal_error" for error in errors)

    def test_path_traversal_with_double_dots_raises_validation_error(self):
        """Test that path traversal attempts with .. are blocked."""
        with pytest.raises(ValidationError) as exc_info:
            PathParams(dataset="../etc/passwd", extension="csv")

        errors = exc_info.value.errors()
        assert any("cannot contain path separators" in str(error) for error in errors)

    def test_path_traversal_with_forward_slash_raises_validation_error(self):
        """Test that dataset names with forward slashes are blocked."""
        with pytest.raises(ValidationError) as exc_info:
            PathParams(dataset="path/to/file", extension="csv")

        errors = exc_info.value.errors()
        assert any("cannot contain path separators" in str(error) for error in errors)

    def test_path_traversal_with_backslash_raises_validation_error(self):
        """Test that dataset names with backslashes are blocked."""
        with pytest.raises(ValidationError) as exc_info:
            PathParams(dataset="path\\to\\file", extension="csv")

        errors = exc_info.value.errors()
        assert any("cannot contain path separators" in str(error) for error in errors)

    def test_dataset_with_dot_extension_is_stripped(self):
        """Test that file extensions in dataset name are removed."""
        params = PathParams(dataset="test.parquet", extension="csv")

        assert params.dataset == "test"  # Extension should be stripped

    def test_very_long_dataset_name_raises_validation_error(self):
        """Test that dataset names exceeding max length raise ValidationError."""
        long_name = "a" * 101

        with pytest.raises(ValidationError) as exc_info:
            PathParams(dataset=long_name, extension="csv")

        errors = exc_info.value.errors()
        assert any("max_length" in str(error) for error in errors)


class TestQueryParams:
    """Unit tests for QueryParams model."""

    def test_query_params_with_organisation_entity(self):
        """Test creating QueryParams with organisation-entity filter."""
        params = QueryParams(**{"organisation-entity": "acme-corp"})

        assert params.organisation_entity == "acme-corp"

    def test_query_params_with_underscore_alias(self):
        """Test that underscore alias works for organisation_entity."""
        params = QueryParams(organisation_entity="test-org")

        assert params.organisation_entity == "test-org"

    def test_query_params_without_filter_is_none(self):
        """Test that missing organisation-entity defaults to None."""
        params = QueryParams()

        assert params.organisation_entity is None

    def test_query_params_with_empty_string_filter(self):
        """Test that empty string filter is accepted."""
        params = QueryParams(**{"organisation-entity": ""})

        assert params.organisation_entity == ""

    def test_query_params_hyphenated_name_alias_works(self):
        """Test that the hyphenated parameter name is properly aliased."""
        # Simulate query string parameter
        params = QueryParams.model_validate({"organisation-entity": "org-123"})

        assert params.organisation_entity == "org-123"


class TestRequestContext:
    """Unit tests for RequestContext model."""

    def test_request_context_creation(self):
        """Test creating a complete RequestContext."""
        path_params = PathParams(dataset="customers", extension="csv")
        query_params = QueryParams(**{"organisation-entity": "org-1"})

        context = RequestContext(
            path_params=path_params,
            query_params=query_params,
        )

        assert context.path_params.dataset == "customers"
        assert context.query_params.organisation_entity == "org-1"

    def test_output_format_property_returns_extension(self):
        """Test that output_format property returns the correct extension."""
        path_params = PathParams(dataset="test", extension="json")
        query_params = QueryParams()
        context = RequestContext(
            path_params=path_params,
            query_params=query_params,
        )

        assert context.output_format == "json"

    def test_filter_value_property_returns_organisation_entity(self):
        """Test that filter_value property returns organisation-entity value."""
        path_params = PathParams(dataset="test", extension="csv")
        query_params = QueryParams(**{"organisation-entity": "test-filter"})
        context = RequestContext(
            path_params=path_params,
            query_params=query_params,
        )

        assert context.filter_value == "test-filter"

    def test_filter_value_property_returns_none_when_not_set(self):
        """Test that filter_value returns None when no filter is set."""
        path_params = PathParams(dataset="test", extension="csv")
        query_params = QueryParams()
        context = RequestContext(
            path_params=path_params,
            query_params=query_params,
        )

        assert context.filter_value is None
