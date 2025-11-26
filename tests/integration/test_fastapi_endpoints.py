"""
Integration tests for FastAPI endpoints.

These tests verify the download endpoints with real (mocked) S3 integration.
"""


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    def test_health_check_returns_200(self, client):
        """Test health endpoint returns 200 OK."""
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "healthy", "service": "download-lambda"}


class TestDownloadCSVEndpoint:
    """Tests for CSV download functionality."""

    def test_download_csv_returns_200(self, client):
        """Test CSV download returns 200 OK."""
        response = client.get("/test-dataset.csv")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "attachment" in response.headers["content-disposition"]

    def test_download_csv_contains_data(self, client):
        """Test CSV download contains expected data."""
        response = client.get("/test-dataset.csv")

        body = response.text
        assert "organisation-entity" in body
        assert "org-" in body
        assert "Record" in body

    def test_download_csv_with_filter(self, client):
        """Test CSV download with organisation-entity filter."""
        response = client.get("/test-dataset.csv?organisation-entity=org-1")

        assert response.status_code == 200
        body = response.text

        # Should only contain org-1 records
        assert "org-1" in body
        # Check that other orgs are not present (allowing for header row)
        lines = [
            line for line in body.split("\n") if line and not line.startswith('"id"')
        ]
        for line in lines:
            if "org-" in line:
                assert "org-1" in line, f"Found non-org-1 record: {line}"

    def test_download_csv_headers(self, client):
        """Test CSV download has correct headers."""
        response = client.get("/test-dataset.csv")

        assert (
            response.headers["content-disposition"]
            == 'attachment; filename="test-dataset.csv"'
        )
        assert response.headers["cache-control"] == "public, max-age=3600"
        assert response.headers["x-dataset"] == "test-dataset"
        assert response.headers["x-format"] == "csv"


class TestDownloadJSONEndpoint:
    """Tests for JSON download functionality."""

    def test_download_json_returns_200(self, client):
        """Test JSON download returns 200 OK."""
        response = client.get("/test-dataset.json")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

    def test_download_json_is_valid(self, client):
        """Test JSON download returns valid JSON."""
        response = client.get("/test-dataset.json")

        # Should be able to parse as JSON array
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_download_json_with_filter(self, client):
        """Test JSON download with organisation-entity filter."""
        response = client.get("/test-dataset.json?organisation-entity=org-2")

        data = response.json()
        assert all(record["organisation-entity"] == "org-2" for record in data)

    def test_download_json_structure(self, client):
        """Test JSON download has correct structure."""
        response = client.get("/test-dataset.json")

        data = response.json()
        first_record = data[0]

        # Check expected fields
        assert "id" in first_record
        assert "organisation-entity" in first_record
        assert "name" in first_record
        assert "value" in first_record


class TestDownloadParquetEndpoint:
    """Tests for Parquet download functionality."""

    def test_download_parquet_returns_200(self, client):
        """Test Parquet download returns 200 OK."""
        response = client.get("/test-dataset.parquet")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/octet-stream"

    def test_download_parquet_is_binary(self, client):
        """Test Parquet download returns binary data."""
        response = client.get("/test-dataset.parquet")

        # Parquet files start with 'PAR1' magic bytes
        assert response.content[:4] == b"PAR1"


class TestErrorHandling:
    """Tests for error handling."""

    def test_dataset_not_found_returns_404(self, client):
        """Test requesting non-existent dataset returns 404."""
        response = client.get("/nonexistent-dataset.csv")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_invalid_extension_returns_422(self, client):
        """Test invalid file extension returns validation error."""
        response = client.get("/test-dataset.txt")

        assert response.status_code == 422  # FastAPI validation error

    def test_invalid_dataset_name_returns_422(self, client):
        """Test invalid dataset name returns validation error."""
        # Dataset names with path traversal should be rejected
        response = client.get("/../etc/passwd.csv")

        assert response.status_code in [404, 422]


class TestConcurrentRequests:
    """Tests for concurrent request handling."""

    def test_multiple_simultaneous_requests(self, client):
        """Test handling multiple simultaneous requests."""
        # FastAPI's TestClient is synchronous, but we can test multiple sequential requests
        responses = [
            client.get("/test-dataset.csv"),
            client.get("/test-dataset.json"),
            client.get("/customers.csv"),
        ]

        assert all(r.status_code == 200 for r in responses)
