"""
Unit tests for utility functions.

Tests simple helper functions for content types and filenames.
"""

from application.utils import get_content_type, get_filename


class TestGetContentType:
    """Unit tests for get_content_type function."""

    def test_csv_content_type(self):
        """Test CSV content type."""
        assert get_content_type("csv") == "text/csv"

    def test_json_content_type(self):
        """Test JSON content type."""
        assert get_content_type("json") == "application/json"

    def test_parquet_content_type(self):
        """Test Parquet content type."""
        assert get_content_type("parquet") == "application/octet-stream"

    def test_unknown_content_type(self):
        """Test unknown format defaults to octet-stream."""
        assert get_content_type("unknown") == "application/octet-stream"


class TestGetFilename:
    """Unit tests for get_filename function."""

    def test_csv_filename(self):
        """Test CSV filename generation."""
        assert get_filename("test-dataset", "csv") == "test-dataset.csv"

    def test_json_filename(self):
        """Test JSON filename generation."""
        assert get_filename("sales-data", "json") == "sales-data.json"

    def test_parquet_filename(self):
        """Test Parquet filename generation."""
        assert get_filename("users", "parquet") == "users.parquet"

    def test_filename_with_hyphens(self):
        """Test filename with hyphens."""
        assert get_filename("my-dataset-name", "csv") == "my-dataset-name.csv"
