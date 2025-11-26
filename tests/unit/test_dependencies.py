"""
Unit tests for FastAPI dependency functions.

Tests dependency injection functions with mocked services.
"""

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from application.dependencies import (
    get_dataset_bucket,
    get_s3_service,
    get_data_stream_service,
)


class TestGetDatasetBucket:
    """Tests for get_dataset_bucket dependency."""

    def test_get_dataset_bucket_returns_value_from_environment(self, monkeypatch):
        """Test get_dataset_bucket returns DATASET_BUCKET from environment."""
        monkeypatch.setenv("DATASET_BUCKET", "my-datasets")

        result = get_dataset_bucket()

        assert result == "my-datasets"

    def test_get_dataset_bucket_raises_when_not_set(self, monkeypatch):
        """Test get_dataset_bucket raises HTTPException when not set."""
        monkeypatch.delenv("DATASET_BUCKET", raising=False)

        with pytest.raises(HTTPException) as exc_info:
            get_dataset_bucket()

        assert exc_info.value.status_code == 500
        assert "DATASET_BUCKET not set" in exc_info.value.detail


class TestGetS3Service:
    """Tests for get_s3_service dependency."""

    def test_get_s3_service_returns_s3_service_instance(self, monkeypatch):
        """Test get_s3_service returns S3Service with correct bucket."""
        monkeypatch.setenv("DATASET_BUCKET", "test-bucket")

        with patch("boto3.Session"):
            service = get_s3_service()

            assert service.bucket == "test-bucket"
            assert service.prefix == "dataset"

    def test_get_s3_service_uses_dataset_prefix(self, monkeypatch):
        """Test get_s3_service configures dataset prefix."""
        monkeypatch.setenv("DATASET_BUCKET", "my-bucket")

        with patch("boto3.Session"):
            service = get_s3_service()

            assert service.prefix == "dataset"


class TestGetDataStreamService:
    """Tests for get_data_stream_service dependency."""

    def test_get_data_stream_service_returns_data_stream_service(self, monkeypatch):
        """Test get_data_stream_service returns DataStreamService."""
        monkeypatch.setenv("DATASET_BUCKET", "test-bucket")

        with patch("boto3.Session"):
            service = get_data_stream_service()

            assert service.s3_service is not None
            assert service.s3_service.bucket == "test-bucket"

    def test_get_data_stream_service_chains_s3_service(self, monkeypatch):
        """Test get_data_stream_service uses S3Service from get_s3_service."""
        monkeypatch.setenv("DATASET_BUCKET", "chained-bucket")

        with patch("boto3.Session"):
            service = get_data_stream_service()

            assert service.s3_service.bucket == "chained-bucket"
            assert service.s3_service.prefix == "dataset"
