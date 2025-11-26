"""
Acceptance tests for user download scenarios with FastAPI.

These tests verify end-to-end user stories and acceptance criteria.
They mimic actual user interactions and validate the complete system behavior.
"""


class TestUserDownloadsDatasetInCsvFormat:
    """
    User Story: Download dataset as CSV

    AS A data analyst
    I WANT TO download a dataset as CSV
    SO THAT I can open it in Excel or other spreadsheet tools
    """

    def test_user_requests_csv_download_and_receives_valid_csv(self, client):
        """
        GIVEN a dataset exists in S3
        WHEN a user requests the dataset in CSV format
        THEN they receive a valid CSV file with headers
        AND the response includes appropriate download headers
        """
        response = client.get("/test-dataset.csv")

        # Verify successful response
        assert response.status_code == 200

        # Verify CSV content type
        assert "text/csv" in response.headers["content-type"]

        # Verify download headers
        assert "attachment" in response.headers["content-disposition"]
        assert "test-dataset.csv" in response.headers["content-disposition"]

        # Verify CSV structure
        csv_content = response.text
        lines = csv_content.strip().split("\n")
        assert len(lines) > 1  # Has header and data
        assert "id" in lines[0]
        assert "organisation-entity" in lines[0]

    def test_user_opens_csv_in_spreadsheet_tool(self, client):
        """
        GIVEN a user has downloaded a CSV file
        WHEN they parse it as CSV
        THEN all columns and rows are readable
        """
        response = client.get("/test-dataset.csv")

        csv_content = response.text
        lines = csv_content.strip().split("\n")

        # Verify data rows
        assert "org-" in csv_content
        assert "Record" in csv_content
        assert len(lines) > 10


class TestUserDownloadsDatasetInJsonFormat:
    """
    User Story: Download dataset as JSON

    AS A developer
    I WANT TO download a dataset as JSON
    SO THAT I can programmatically process it in my application
    """

    def test_user_requests_json_download_and_receives_valid_json(self, client):
        """
        GIVEN a dataset exists in S3
        WHEN a user requests the dataset in JSON format
        THEN they receive a valid JSON array
        """
        response = client.get("/test-dataset.json")

        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]

        # Verify JSON structure
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_user_parses_json_in_application(self, client):
        """
        GIVEN a user has downloaded JSON data
        WHEN they parse it in their application
        THEN all fields are accessible
        """
        response = client.get("/test-dataset.json")

        data = response.json()
        first_record = data[0]

        # Check expected fields
        assert "id" in first_record
        assert "organisation-entity" in first_record
        assert "name" in first_record
        assert "value" in first_record


class TestUserFiltersDatasetByOrganisation:
    """
    User Story: Filter dataset by organisation

    AS A data analyst
    I WANT TO filter a dataset by organisation entity
    SO THAT I only download the data relevant to my analysis
    """

    def test_user_filters_dataset_and_receives_only_matching_records(self, client):
        """
        GIVEN a dataset contains records for multiple organisations
        WHEN a user requests data filtered by organisation-entity
        THEN they receive only records matching that organisation
        """
        response = client.get("/test-dataset.csv?organisation-entity=org-1")

        assert response.status_code == 200

        # Verify only org-1 records
        csv_content = response.text
        lines = [line for line in csv_content.split("\n") if line and "org-" in line]

        for line in lines:
            assert "org-1" in line

    def test_user_receives_smaller_download_when_filtering(self, client):
        """
        GIVEN a large dataset
        WHEN a user applies a filter
        THEN the download size is reduced
        """
        # Unfiltered request
        response_full = client.get("/test-dataset.csv")
        full_size = len(response_full.text)

        # Filtered request
        response_filtered = client.get("/test-dataset.csv?organisation-entity=org-1")
        filtered_size = len(response_filtered.text)

        # Filtered should be smaller
        assert filtered_size < full_size

    def test_user_receives_empty_result_when_no_matches(self, client):
        """
        GIVEN a user filters by an organisation that doesn't exist
        WHEN they download the data
        THEN they receive a valid response with only headers
        """
        response = client.get("/test-dataset.csv?organisation-entity=nonexistent")

        assert response.status_code == 200

        # Should have headers but minimal data
        csv_content = response.text
        lines = csv_content.strip().split("\n")
        assert len(lines) >= 1  # At least header
        assert "id" in lines[0]


class TestSystemRejectsInvalidRequests:
    """
    User Story: System security and validation

    AS A system administrator
    I WANT THE system to reject invalid requests
    SO THAT the service remains secure
    """

    def test_system_rejects_request_for_nonexistent_dataset(self, client):
        """
        GIVEN a user requests a dataset that doesn't exist
        WHEN the system processes the request
        THEN it returns a 404 error
        """
        response = client.get("/nonexistent-dataset.csv")

        assert response.status_code == 404
        body = response.json()
        assert "detail" in body
        assert "not found" in body["detail"].lower()

    def test_system_rejects_unsupported_file_format(self, client):
        """
        GIVEN a user requests an unsupported file format
        WHEN the system validates the request
        THEN it returns a validation error
        """
        response = client.get("/test-dataset.xml")

        assert response.status_code == 422  # FastAPI validation error

    def test_system_handles_malformed_request_gracefully(self, client):
        """
        GIVEN a user sends a malformed request
        WHEN the system processes it
        THEN it returns an appropriate error
        """
        response = client.get("/no-extension")

        assert response.status_code in [404, 422]


class TestCdnCachingBehavior:
    """
    User Story: CDN caching for performance

    AS A user
    I WANT THE system to leverage CDN caching
    SO THAT repeated downloads are faster
    """

    def test_response_includes_cache_control_headers(self, client):
        """
        GIVEN a user requests a dataset
        WHEN the response is generated
        THEN it includes Cache-Control headers
        """
        response = client.get("/test-dataset.csv")

        assert "cache-control" in response.headers
        assert "max-age" in response.headers["cache-control"]

    def test_response_is_cacheable_for_unfiltered_requests(self, client):
        """
        GIVEN a user requests an unfiltered dataset
        WHEN the response is generated
        THEN it has appropriate cache duration
        """
        response = client.get("/test-dataset.csv")

        cache_control = response.headers["cache-control"]
        assert "max-age" in cache_control
        assert "public" in cache_control
