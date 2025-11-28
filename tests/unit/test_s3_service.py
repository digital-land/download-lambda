"""
Unit tests for S3Service.

Tests S3 service configuration and path generation with mocked boto3.
"""

from unittest.mock import Mock, patch

from application.services.s3_service import S3Service


class TestS3ServiceInitialization:
    """Tests for S3Service initialization."""

    def test_initialize_with_bucket_and_prefix(self):
        """Test S3Service initializes with bucket and prefix."""
        with patch("boto3.Session"):
            service = S3Service(bucket="test-bucket", prefix="dataset")

            assert service.bucket == "test-bucket"
            assert service.prefix == "dataset"

    def test_initialize_strips_prefix_slashes(self):
        """Test prefix slashes are stripped."""
        with patch("boto3.Session"):
            service = S3Service(bucket="test-bucket", prefix="/dataset/")

            assert service.prefix == "dataset"

    def test_initialize_without_prefix(self):
        """Test S3Service initializes without prefix."""
        with patch("boto3.Session"):
            service = S3Service(bucket="test-bucket", prefix="")

            assert service.prefix == ""

    def test_initialize_detects_region_from_session(self):
        """Test region detection from boto3 session."""
        mock_session = Mock()
        mock_session.region_name = "eu-west-2"

        with patch("boto3.Session", return_value=mock_session):
            service = S3Service(bucket="test-bucket")

            assert service.region == "eu-west-2"

    def test_initialize_defaults_to_eu_west_2_without_region(self):
        """Test defaults to us-east-1 when no region configured."""
        mock_session = Mock()
        mock_session.region_name = None

        with patch("boto3.Session", return_value=mock_session):
            service = S3Service(bucket="test-bucket")

            assert service.region == "eu-west-2"

    def test_initialize_reads_endpoint_from_environment(self, monkeypatch):
        """Test endpoint URL read from AWS_ENDPOINT_URL environment variable."""
        monkeypatch.setenv("AWS_ENDPOINT_URL", "http://localhost:4566")

        with patch("boto3.Session"):
            service = S3Service(bucket="test-bucket")

            assert service.endpoint_url == "http://localhost:4566"

    def test_initialize_reads_s3_endpoint_from_environment(self, monkeypatch):
        """Test endpoint URL read from S3_ENDPOINT environment variable."""
        monkeypatch.setenv("S3_ENDPOINT", "http://moto:5000")

        with patch("boto3.Session"):
            service = S3Service(bucket="test-bucket")

            assert service.endpoint_url == "http://moto:5000"


class TestS3ServiceClient:
    """Tests for S3Service client property."""

    def test_client_creates_boto3_client(self):
        """Test client property creates boto3 S3 client."""
        with patch("boto3.Session"), patch("boto3.client") as mock_client:
            service = S3Service(bucket="test-bucket")
            _ = service.client

            mock_client.assert_called_once_with("s3", endpoint_url=None)

    def test_client_uses_custom_endpoint(self, monkeypatch):
        """Test client uses custom endpoint URL."""
        monkeypatch.setenv("AWS_ENDPOINT_URL", "http://localhost:4566")

        with patch("boto3.Session"), patch("boto3.client") as mock_client:
            service = S3Service(bucket="test-bucket")
            _ = service.client

            mock_client.assert_called_once_with(
                "s3", endpoint_url="http://localhost:4566"
            )

    def test_client_caches_boto3_client(self):
        """Test client property caches boto3 client instance."""
        with patch("boto3.Session"), patch("boto3.client") as mock_client:
            mock_client.return_value = Mock()

            service = S3Service(bucket="test-bucket")
            client1 = service.client
            client2 = service.client

            assert client1 is client2
            mock_client.assert_called_once()


class TestGetObjectPath:
    """Tests for get_object_path method."""

    def test_get_object_path_without_prefix(self):
        """Test object path generation without prefix."""
        with patch("boto3.Session"):
            service = S3Service(bucket="test-bucket", prefix="")

            path = service.get_object_path("test-dataset")

            assert path == "test-dataset.parquet"

    def test_get_object_path_with_prefix(self):
        """Test object path generation with prefix."""
        with patch("boto3.Session"):
            service = S3Service(bucket="test-bucket", prefix="dataset")

            path = service.get_object_path("test-dataset")

            assert path == "dataset/test-dataset.parquet"

    def test_get_object_path_with_nested_prefix(self):
        """Test object path generation with nested prefix."""
        with patch("boto3.Session"):
            service = S3Service(bucket="test-bucket", prefix="data/parquet")

            path = service.get_object_path("sales-data")

            assert path == "data/parquet/sales-data.parquet"


class TestGetS3Uri:
    """Tests for get_s3_uri method."""

    def test_get_s3_uri_without_prefix(self):
        """Test S3 URI generation without prefix."""
        with patch("boto3.Session"):
            service = S3Service(bucket="my-bucket", prefix="")

            uri = service.get_s3_uri("test-dataset")

            assert uri == "s3://my-bucket/test-dataset.parquet"

    def test_get_s3_uri_with_prefix(self):
        """Test S3 URI generation with prefix."""
        with patch("boto3.Session"):
            service = S3Service(bucket="my-bucket", prefix="dataset")

            uri = service.get_s3_uri("test-dataset")

            assert uri == "s3://my-bucket/dataset/test-dataset.parquet"


class TestGetCredentials:
    """Tests for get_credentials method."""

    def test_get_credentials_returns_credentials(self):
        """Test get_credentials returns access key and secret."""
        mock_session = Mock()
        mock_creds = Mock()
        mock_frozen = Mock()
        mock_frozen.access_key = "AKIATEST"
        mock_frozen.secret_key = "secret123"
        mock_frozen.token = None
        mock_creds.get_frozen_credentials.return_value = mock_frozen
        mock_session.get_credentials.return_value = mock_creds

        with patch("boto3.Session", return_value=mock_session):
            service = S3Service(bucket="test-bucket")

            credentials = service.get_credentials()

            assert credentials == {
                "access_key": "AKIATEST",
                "secret_key": "secret123",
                "token": None,
            }

    def test_get_credentials_includes_session_token(self):
        """Test get_credentials includes session token for temporary credentials."""
        mock_session = Mock()
        mock_creds = Mock()
        mock_frozen = Mock()
        mock_frozen.access_key = "ASIATEST"
        mock_frozen.secret_key = "secret123"
        mock_frozen.token = "session-token-xyz"
        mock_creds.get_frozen_credentials.return_value = mock_frozen
        mock_session.get_credentials.return_value = mock_creds

        with patch("boto3.Session", return_value=mock_session):
            service = S3Service(bucket="test-bucket")

            credentials = service.get_credentials()

            assert credentials["token"] == "session-token-xyz"

    def test_get_credentials_returns_none_when_no_credentials(self):
        """Test get_credentials returns None when no credentials available."""
        mock_session = Mock()
        mock_session.get_credentials.return_value = None

        with patch("boto3.Session", return_value=mock_session):
            service = S3Service(bucket="test-bucket")

            credentials = service.get_credentials()

            assert credentials is None
