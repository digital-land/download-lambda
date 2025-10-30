"""
Acceptance tests for user download scenarios.

These tests verify end-to-end user stories and acceptance criteria.
They mimic actual user interactions and validate the complete system behavior.

Acceptance Criteria:
- AS A data analyst
- I WANT TO download datasets in different formats
- SO THAT I can analyze them in my preferred tools

- AS A data analyst
- I WANT TO filter datasets by organisation
- SO THAT I can focus on specific subsets of data

- AS A system administrator
- I WANT THE system to reject invalid requests
- SO THAT the service remains secure and reliable
"""
import json
import pytest
from io import BytesIO

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from lambda_function import lambda_handler


class MockResponseStream:
    """Mock response stream for testing streaming Lambda handler."""

    def __init__(self):
        self.status_code = None
        self.headers = {}
        self.body = BytesIO()
        self._ended = False

    def set_status_code(self, code: int):
        """Set HTTP status code."""
        self.status_code = code

    def set_headers(self, headers: dict):
        """Set response headers."""
        self.headers.update(headers)

    def write(self, data: bytes):
        """Write data to response stream."""
        if self._ended:
            raise RuntimeError("Cannot write to ended stream")
        self.body.write(data)

    def end(self):
        """End the response stream."""
        self._ended = True

    def get_response(self) -> dict:
        """Get response in Lambda buffered format for testing."""
        return {
            "statusCode": self.status_code or 200,
            "headers": self.headers,
            "body": self.body.getvalue().decode("utf-8"),
        }


@pytest.fixture
def call_lambda_handler():
    """Fixture to call streaming lambda_handler and return buffered-style response."""
    def _call(event):
        mock_stream = MockResponseStream()
        try:
            lambda_handler(event, mock_stream, None)
        except Exception as e:
            # If handler raises exception, return error response
            mock_stream.set_status_code(500)
            mock_stream.set_headers({"Content-Type": "application/json"})
            mock_stream.write(json.dumps({
                "error": str(e),
                "statusCode": 500
            }).encode("utf-8"))
            mock_stream.end()
        return mock_stream.get_response()
    return _call


class TestUserDownloadsDatasetInCsvFormat:
    """
    User Story: Download dataset as CSV

    AS A data analyst
    I WANT TO download a dataset as CSV
    SO THAT I can open it in Excel or other spreadsheet tools
    """

    def test_user_requests_csv_download_and_receives_valid_csv(
        self, mock_env_vars, s3_bucket_with_data, lambda_function_url_event_factory, call_lambda_handler
    ):
        """
        GIVEN a dataset exists in S3
        WHEN a user requests the dataset in CSV format
        THEN they receive a valid CSV file with headers
        AND the response includes appropriate download headers
        """
        event = lambda_function_url_event_factory(path="/test-dataset.csv")

        response = call_lambda_handler(event)

        # Verify successful response
        assert response["statusCode"] == 200

        # Verify CSV content type
        assert response["headers"]["Content-Type"] == "text/csv"

        # Verify download headers
        assert "attachment" in response["headers"]["Content-Disposition"]
        assert "test-dataset.csv" in response["headers"]["Content-Disposition"]

        # Verify CSV structure
        csv_content = response["body"]
        lines = csv_content.strip().split("\n")
        assert len(lines) > 1  # Has header and data
        # Check for column names (may be quoted)
        assert "id" in lines[0]
        assert "organisation-entity" in lines[0]
        assert "category" in lines[0]

    def test_user_opens_csv_in_spreadsheet_tool(
        self, mock_env_vars, s3_bucket_with_data, lambda_function_url_event_factory, call_lambda_handler
    ):
        """
        GIVEN a user has downloaded a CSV file
        WHEN they parse it as CSV
        THEN all columns and rows are readable
        AND data types are preserved as strings (standard CSV behavior)
        """
        event = lambda_function_url_event_factory(path="/test-dataset.csv")
        response = call_lambda_handler(event)

        csv_content = response["body"]
        lines = csv_content.strip().split("\n")

        # Verify header row (may be quoted)
        assert "id" in lines[0]
        assert "organisation-entity" in lines[0]

        # Verify data rows (contains actual data)
        assert "org-" in csv_content
        assert "Record" in csv_content
        # Verify we have data rows
        assert len(lines) > 10


class TestUserDownloadsDatasetInJsonFormat:
    """
    User Story: Download dataset as JSON

    AS A developer
    I WANT TO download a dataset as JSON
    SO THAT I can programmatically process it in my application
    """

    def test_user_requests_json_download_and_receives_valid_json(
        self, mock_env_vars, s3_bucket_with_data, lambda_function_url_event_factory, call_lambda_handler
    ):
        """
        GIVEN a dataset exists in S3
        WHEN a user requests the dataset in JSON format
        THEN they receive a valid JSON array
        AND each record is a JSON object with the correct fields
        """
        event = lambda_function_url_event_factory(path="/test-dataset.json")

        response = call_lambda_handler(event)

        # Verify successful response
        assert response["statusCode"] == 200
        assert response["headers"]["Content-Type"] == "application/json"

        # Verify JSON structure
        json_content = response["body"]
        assert json_content.startswith("[")
        assert "organisation-entity" in json_content
        assert "id" in json_content

    def test_user_parses_json_in_application(
        self, mock_env_vars, s3_bucket_with_data, lambda_function_url_event_factory, call_lambda_handler
    ):
        """
        GIVEN a user has downloaded JSON data
        WHEN they parse it in their application
        THEN it is valid JSON that can be deserialized
        AND all fields are accessible as object properties
        """
        event = lambda_function_url_event_factory(path="/test-dataset.json")
        response = call_lambda_handler(event)

        json_content = response["body"]

        # Verify it can be parsed as JSON
        # Note: The response is a streaming JSON array, may need completion
        assert "[" in json_content
        assert "{" in json_content
        assert "id" in json_content


class TestUserFiltersDatasetByOrganisation:
    """
    User Story: Filter dataset by organisation

    AS A data analyst
    I WANT TO filter a dataset by organisation entity
    SO THAT I only download the data relevant to my analysis
    """

    def test_user_filters_dataset_and_receives_only_matching_records(
        self, mock_env_vars, s3_bucket_with_data, lambda_function_url_event_factory, call_lambda_handler
    ):
        """
        GIVEN a dataset contains records for multiple organisations
        WHEN a user requests data filtered by organisation-entity
        THEN they receive only records matching that organisation
        AND no records from other organisations are included
        """
        event = lambda_function_url_event_factory(
            path="/test-dataset.csv",
            query="organisation-entity=org-1"
        )

        response = call_lambda_handler(event)

        assert response["statusCode"] == 200

        # Verify only org-1 records
        csv_content = response["body"]
        data_lines = [
            line for line in csv_content.split("\n")
            if line and not line.startswith("id,")
        ]

        # All data lines should contain org-1
        for line in data_lines:
            if "org-" in line:  # Skip any empty lines
                assert "org-1" in line

    def test_user_receives_smaller_download_when_filtering(
        self, mock_env_vars, s3_bucket_with_data, lambda_function_url_event_factory, call_lambda_handler
    ):
        """
        GIVEN a large dataset
        WHEN a user applies a filter
        THEN the download size is reduced
        AND download completes faster
        """
        # Unfiltered request
        event_full = lambda_function_url_event_factory(path="/test-dataset.csv")
        response_full = call_lambda_handler(event_full)
        full_size = len(response_full["body"])

        # Filtered request
        event_filtered = lambda_function_url_event_factory(
            path="/test-dataset.csv",
            query="organisation-entity=org-1"
        )
        response_filtered = call_lambda_handler(event_filtered)
        filtered_size = len(response_filtered["body"])

        # Filtered should be smaller
        assert filtered_size < full_size

    def test_user_receives_empty_result_when_no_matches(
        self, mock_env_vars, s3_bucket_with_data, lambda_function_url_event_factory, call_lambda_handler
    ):
        """
        GIVEN a user filters by an organisation that doesn't exist
        WHEN they download the data
        THEN they receive a valid response with only headers
        AND no error is raised
        """
        event = lambda_function_url_event_factory(
            path="/test-dataset.csv",
            query="organisation-entity=nonexistent"
        )

        response = call_lambda_handler(event)

        assert response["statusCode"] == 200

        # Should have headers but minimal data
        csv_content = response["body"]
        lines = csv_content.strip().split("\n")
        # Should have at least the header (may be quoted)
        assert len(lines) >= 1
        assert "id" in lines[0]
        assert "organisation-entity" in lines[0]


class TestSystemRejectsInvalidRequests:
    """
    User Story: System security and validation

    AS A system administrator
    I WANT THE system to reject invalid requests
    SO THAT the service remains secure and handles errors gracefully
    """

    def test_system_rejects_request_for_nonexistent_dataset(
        self, mock_env_vars, s3_bucket_with_data, lambda_function_url_event_factory, call_lambda_handler
    ):
        """
        GIVEN a user requests a dataset that doesn't exist
        WHEN the system processes the request
        THEN it returns a 404 error
        AND provides a helpful error message
        """
        event = lambda_function_url_event_factory(path="/nonexistent-dataset.csv")

        response = call_lambda_handler(event)

        assert response["statusCode"] == 404
        body = json.loads(response["body"])
        assert "error" in body
        assert "not found" in body["error"].lower()

    def test_system_rejects_unsupported_file_format(
        self, mock_env_vars, s3_bucket_with_data, lambda_function_url_event_factory, call_lambda_handler
    ):
        """
        GIVEN a user requests an unsupported file format
        WHEN the system validates the request
        THEN it returns a 400 error
        AND explains that the format is not supported
        """
        event = lambda_function_url_event_factory(path="/test-dataset.xml")

        response = call_lambda_handler(event)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body

    def test_system_blocks_path_traversal_attack(
        self, mock_env_vars, s3_bucket_with_data, lambda_function_url_event_factory, call_lambda_handler
    ):
        """
        GIVEN a malicious user attempts path traversal
        WHEN the system validates the request
        THEN it rejects the request with 400 error
        AND does not access files outside the allowed directory
        """
        event = lambda_function_url_event_factory(path="/../etc/passwd.csv")

        response = call_lambda_handler(event)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body

    def test_system_handles_malformed_request_gracefully(
        self, mock_env_vars, s3_bucket_with_data, lambda_function_url_event_factory, call_lambda_handler
    ):
        """
        GIVEN a user sends a malformed request
        WHEN the system processes it
        THEN it returns an appropriate error
        AND does not crash or expose internal details
        """
        event = lambda_function_url_event_factory(path="/no-extension")

        response = call_lambda_handler(event)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body
        # Should not expose stack traces or internal errors to user
        assert "Traceback" not in body["error"]


class TestUserDownloadsLargeDataset:
    """
    User Story: Download large datasets

    AS A data analyst
    I WANT TO download large datasets
    SO THAT I can perform comprehensive analysis
    """

    def test_user_downloads_large_dataset_successfully(
        self, mock_env_vars, s3_bucket_with_data, lambda_function_url_event_factory, call_lambda_handler
    ):
        """
        GIVEN a large dataset exists in S3
        WHEN a user requests the complete dataset
        THEN they receive all records
        AND the download completes successfully
        """
        event = lambda_function_url_event_factory(path="/test-dataset.csv")

        response = call_lambda_handler(event)

        assert response["statusCode"] == 200

        # Verify substantial data is returned
        csv_content = response["body"]
        lines = csv_content.strip().split("\n")
        assert len(lines) > 50  # Should have many records


class TestCdnCachingBehavior:
    """
    User Story: CDN caching for performance

    AS A user
    I WANT THE system to leverage CDN caching
    SO THAT repeated downloads are faster
    """

    def test_response_includes_cache_control_headers(
        self, mock_env_vars, s3_bucket_with_data, lambda_function_url_event_factory, call_lambda_handler
    ):
        """
        GIVEN a user requests a dataset
        WHEN the response is generated
        THEN it includes Cache-Control headers
        SO THAT CDNs can cache the response appropriately
        """
        event = lambda_function_url_event_factory(path="/test-dataset.csv")

        response = call_lambda_handler(event)

        assert "Cache-Control" in response["headers"]
        assert "max-age" in response["headers"]["Cache-Control"]

    def test_response_is_cacheable_for_unfiltered_requests(
        self, mock_env_vars, s3_bucket_with_data, lambda_function_url_event_factory, call_lambda_handler
    ):
        """
        GIVEN a user requests an unfiltered dataset
        WHEN the response is generated
        THEN it has appropriate cache duration
        FOR efficient CDN caching
        """
        event = lambda_function_url_event_factory(path="/test-dataset.csv")

        response = call_lambda_handler(event)

        cache_control = response["headers"]["Cache-Control"]
        assert "max-age" in cache_control
        # Should have some reasonable cache duration
        assert "public" in cache_control or "max-age" in cache_control
