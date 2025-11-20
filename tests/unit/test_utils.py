"""
Unit tests for utility functions.

These tests verify path parsing, request parsing, and utility functions
without external dependencies. All AWS services are mocked.
"""

import pytest

from src.utils import (
    parse_cloudfront_request,
    _parse_path,
    _extract_request_info,
    get_content_type,
    get_filename,
)
from src.models import RequestContext


class TestParsePath:
    """Unit tests for _parse_path function."""

    def test_parse_path_with_csv_extension(self):
        """Test parsing path with CSV extension."""
        dataset, extension = _parse_path("/test-dataset.csv")

        assert dataset == "test-dataset"
        assert extension == "csv"

    def test_parse_path_with_json_extension(self):
        """Test parsing path with JSON extension."""
        dataset, extension = _parse_path("/customers.json")

        assert dataset == "customers"
        assert extension == "json"

    def test_parse_path_with_parquet_extension(self):
        """Test parsing path with Parquet extension."""
        dataset, extension = _parse_path("/large-dataset.parquet")

        assert dataset == "large-dataset"
        assert extension == "parquet"

    def test_parse_path_without_leading_slash(self):
        """Test parsing path without leading slash."""
        dataset, extension = _parse_path("test.csv")

        assert dataset == "test"
        assert extension == "csv"

    def test_parse_path_with_trailing_slash_removed(self):
        """Test that trailing slashes are removed."""
        dataset, extension = _parse_path("/test.json/")

        assert dataset == "test"
        assert extension == "json"

    def test_parse_path_with_hyphens_in_dataset_name(self):
        """Test parsing dataset names with hyphens."""
        dataset, extension = _parse_path("/my-test-dataset-2024.csv")

        assert dataset == "my-test-dataset-2024"
        assert extension == "csv"

    def test_parse_path_with_underscores_in_dataset_name(self):
        """Test parsing dataset names with underscores."""
        dataset, extension = _parse_path("/my_test_dataset.json")

        assert dataset == "my_test_dataset"
        assert extension == "json"

    def test_parse_path_with_empty_path_raises_value_error(self):
        """Test that empty path raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            _parse_path("")

        assert "Path cannot be empty" in str(exc_info.value)

    def test_parse_path_with_only_slashes_raises_value_error(self):
        """Test that path with only slashes raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            _parse_path("///")

        assert "Path cannot be empty" in str(exc_info.value)

    def test_parse_path_without_extension_raises_value_error(self):
        """Test that path without extension raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            _parse_path("/test-dataset")

        assert "Invalid path format" in str(exc_info.value)

    def test_parse_path_with_multiple_dots_uses_last_as_extension(self):
        """Test that only the last dot is treated as extension separator."""
        dataset, extension = _parse_path("/test.backup.csv")

        assert dataset == "test.backup"
        assert extension == "csv"


class TestExtractRequestInfo:
    """Unit tests for _extract_request_info function."""

    def test_extract_from_lambda_function_url_event(self, lambda_function_url_event):
        """Test extracting path and query from Lambda Function URL event."""
        path, query_string = _extract_request_info(lambda_function_url_event)

        assert path == "/test-dataset.csv"
        assert query_string == "organisation-entity=org-1"

    def test_extract_from_cloudfront_event(self, cloudfront_event):
        """Test extracting path and query from CloudFront event."""
        path, query_string = _extract_request_info(cloudfront_event)

        assert path == "/test-dataset.json"
        assert query_string == "organisation-entity=org-2"

    def test_extract_from_function_url_with_url_encoded_path(self):
        """Test that URL-encoded paths are decoded."""
        event = {
            "requestContext": {"http": {"method": "GET"}},
            "rawPath": "/test%20dataset.csv",
            "rawQueryString": "",
        }

        path, query_string = _extract_request_info(event)

        assert path == "/test dataset.csv"
        assert query_string == ""

    def test_extract_from_function_url_with_empty_query_string(self):
        """Test extracting when query string is empty."""
        event = {
            "requestContext": {"http": {"method": "GET"}},
            "rawPath": "/test.csv",
            "rawQueryString": "",
        }

        path, query_string = _extract_request_info(event)

        assert path == "/test.csv"
        assert query_string == ""

    def test_extract_from_api_gateway_event(self):
        """Test extracting from API Gateway event format."""
        event = {
            "path": "/test-dataset.csv",
            "queryStringParameters": {"organisation-entity": "org-1"},
        }

        path, query_string = _extract_request_info(event)

        assert path == "/test-dataset.csv"
        assert "organisation-entity=org-1" in query_string

    def test_extract_from_api_gateway_with_none_query_params(self):
        """Test API Gateway event with None queryStringParameters."""
        event = {
            "path": "/test.json",
            "queryStringParameters": None,
        }

        path, query_string = _extract_request_info(event)

        assert path == "/test.json"
        assert query_string == ""

    def test_extract_from_unsupported_event_format_raises_value_error(self):
        """Test that unsupported event format raises ValueError."""
        event = {"unsupported": "format"}

        with pytest.raises(ValueError) as exc_info:
            _extract_request_info(event)

        assert "Unsupported event format" in str(exc_info.value)


class TestParseCloudFrontRequest:
    """Unit tests for parse_cloudfront_request function."""

    def test_parse_function_url_event_with_csv(self, lambda_function_url_event):
        """Test parsing Lambda Function URL event for CSV download."""
        context = parse_cloudfront_request(lambda_function_url_event)

        assert isinstance(context, RequestContext)
        assert context.path_params.dataset == "test-dataset"
        assert context.path_params.extension == "csv"
        assert context.query_params.organisation_entity == "org-1"

    def test_parse_cloudfront_event_with_json(self, cloudfront_event):
        """Test parsing CloudFront event for JSON download."""
        context = parse_cloudfront_request(cloudfront_event)

        assert isinstance(context, RequestContext)
        assert context.path_params.dataset == "test-dataset"
        assert context.path_params.extension == "json"
        assert context.query_params.organisation_entity == "org-2"

    def test_parse_request_without_filter_query_param(
        self, lambda_function_url_event_factory
    ):
        """Test parsing request without organisation-entity filter."""
        event = lambda_function_url_event_factory(path="/customers.csv", query="")

        context = parse_cloudfront_request(event)

        assert context.path_params.dataset == "customers"
        assert context.query_params.organisation_entity is None

    def test_parse_request_with_parquet_extension(
        self, lambda_function_url_event_factory
    ):
        """Test parsing request for Parquet output format."""
        event = lambda_function_url_event_factory(
            path="/large-dataset.parquet", query="organisation-entity=org-5"
        )

        context = parse_cloudfront_request(event)

        assert context.path_params.extension == "parquet"
        assert context.output_format == "parquet"

    def test_parse_request_extracts_dataset_name(
        self, lambda_function_url_event_factory
    ):
        """Test that dataset name is correctly extracted from path."""
        event = lambda_function_url_event_factory(path="/my-data.json")

        context = parse_cloudfront_request(event)

        assert context.path_params.dataset == "my-data"
        assert context.path_params.extension == "json"

    def test_parse_request_with_invalid_path_raises_value_error(
        self, lambda_function_url_event_factory
    ):
        """Test that invalid path format raises ValueError."""
        event = lambda_function_url_event_factory(path="/invalid")

        with pytest.raises(ValueError) as exc_info:
            parse_cloudfront_request(event)

        assert "Invalid path format" in str(exc_info.value)

    def test_parse_request_with_path_traversal_raises_validation_error(
        self, lambda_function_url_event_factory
    ):
        """Test that path traversal attempt raises ValidationError."""
        event = lambda_function_url_event_factory(path="/../etc/passwd.csv")

        with pytest.raises(Exception):  # ValidationError from Pydantic
            parse_cloudfront_request(event)


class TestGetContentType:
    """Unit tests for get_content_type function."""

    def test_get_content_type_for_csv(self):
        """Test that CSV format returns correct content type."""
        content_type = get_content_type("csv")

        assert content_type == "text/csv"

    def test_get_content_type_for_json(self):
        """Test that JSON format returns correct content type."""
        content_type = get_content_type("json")

        assert content_type == "application/json"

    def test_get_content_type_for_parquet(self):
        """Test that Parquet format returns correct content type."""
        content_type = get_content_type("parquet")

        assert content_type == "application/octet-stream"

    def test_get_content_type_for_unknown_format_returns_default(self):
        """Test that unknown format returns default content type."""
        content_type = get_content_type("unknown")

        assert content_type == "application/octet-stream"


class TestGetFilename:
    """Unit tests for get_filename function."""

    def test_get_filename_for_csv(self):
        """Test generating filename for CSV format."""
        filename = get_filename("customers", "csv")

        assert filename == "customers.csv"

    def test_get_filename_for_json(self):
        """Test generating filename for JSON format."""
        filename = get_filename("transactions", "json")

        assert filename == "transactions.json"

    def test_get_filename_for_parquet(self):
        """Test generating filename for Parquet format."""
        filename = get_filename("large-dataset", "parquet")

        assert filename == "large-dataset.parquet"

    def test_get_filename_preserves_dataset_name_with_hyphens(self):
        """Test that hyphens in dataset name are preserved."""
        filename = get_filename("test-dataset-2024", "csv")

        assert filename == "test-dataset-2024.csv"

    def test_get_filename_preserves_dataset_name_with_underscores(self):
        """Test that underscores in dataset name are preserved."""
        filename = get_filename("test_dataset", "json")

        assert filename == "test_dataset.json"
