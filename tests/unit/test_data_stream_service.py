"""
Unit tests for DataStreamService.

Tests data conversion methods with mocked Arrow data.
"""

import json
from io import BytesIO
from unittest.mock import Mock

import pytest
import pyarrow as pa
import pyarrow.parquet as pq

from application.services.data_stream_service import DataStreamService


@pytest.fixture
def mock_s3_service():
    """Create a mock S3Service."""
    mock = Mock()
    mock.bucket = "test-bucket"
    mock.prefix = "dataset"
    mock.region = "us-east-1"
    mock.endpoint_url = None
    mock.get_s3_uri.return_value = "s3://test-bucket/dataset/test-dataset.parquet"
    mock.get_credentials.return_value = {
        "access_key": "test-key",
        "secret_key": "test-secret",
        "token": None,
    }
    return mock


@pytest.fixture
def sample_record_batch():
    """Create a sample Arrow RecordBatch for testing."""
    return pa.RecordBatch.from_arrays(
        [
            pa.array([1, 2, 3], type=pa.int64()),
            pa.array(["org-1", "org-1", "org-2"], type=pa.string()),
            pa.array(["Record 1", "Record 2", "Record 3"], type=pa.string()),
        ],
        names=["id", "organisation-entity", "name"],
    )


@pytest.fixture
def empty_record_batch():
    """Create an empty Arrow RecordBatch with schema."""
    schema = pa.schema(
        [
            pa.field("id", pa.int64()),
            pa.field("organisation-entity", pa.string()),
            pa.field("name", pa.string()),
        ]
    )
    return pa.RecordBatch.from_arrays(
        [
            pa.array([], type=pa.int64()),
            pa.array([], type=pa.string()),
            pa.array([], type=pa.string()),
        ],
        schema=schema,
    )


class TestDataStreamServiceInitialization:
    """Tests for DataStreamService initialization."""

    def test_initialize_with_s3_service(self, mock_s3_service):
        """Test DataStreamService initializes with S3Service."""
        service = DataStreamService(s3_service=mock_s3_service)

        assert service.s3_service == mock_s3_service


class TestArrowToCsv:
    """Tests for _arrow_to_csv method."""

    def test_arrow_to_csv_without_header(self, mock_s3_service, sample_record_batch):
        """Test CSV conversion without header."""
        service = DataStreamService(s3_service=mock_s3_service)

        result = list(service._arrow_to_csv(sample_record_batch, include_header=False))

        csv_output = b"".join(result).decode()
        lines = csv_output.strip().split("\n")

        # Should not have header
        assert "id" not in lines[0]
        # Should have 3 data rows
        assert len(lines) == 3

    def test_arrow_to_csv_with_header(self, mock_s3_service, sample_record_batch):
        """Test CSV conversion with header."""
        service = DataStreamService(s3_service=mock_s3_service)

        result = list(service._arrow_to_csv(sample_record_batch, include_header=True))

        csv_output = b"".join(result).decode()
        lines = csv_output.strip().split("\n")

        # Should have header + 3 data rows
        assert len(lines) == 4
        assert "id" in lines[0]
        assert "organisation-entity" in lines[0]
        assert "name" in lines[0]

    def test_arrow_to_csv_contains_correct_data(
        self, mock_s3_service, sample_record_batch
    ):
        """Test CSV output contains correct data values."""
        service = DataStreamService(s3_service=mock_s3_service)

        result = list(service._arrow_to_csv(sample_record_batch, include_header=True))

        csv_output = b"".join(result).decode()

        assert "org-1" in csv_output
        assert "org-2" in csv_output
        assert "Record 1" in csv_output

    def test_arrow_to_csv_empty_batch(self, mock_s3_service, empty_record_batch):
        """Test CSV conversion with empty batch."""
        service = DataStreamService(s3_service=mock_s3_service)

        result = list(service._arrow_to_csv(empty_record_batch, include_header=True))

        csv_output = b"".join(result).decode()
        lines = csv_output.strip().split("\n")

        # Should have only header
        assert len(lines) == 1
        assert "id" in lines[0]


class TestArrowToJson:
    """Tests for _arrow_to_json method."""

    def test_arrow_to_json_first_chunk(self, mock_s3_service, sample_record_batch):
        """Test JSON conversion for first chunk."""
        service = DataStreamService(s3_service=mock_s3_service)

        result = list(service._arrow_to_json(sample_record_batch, first_chunk=True))

        json_output = b"".join(result).decode()

        # Should start with array bracket
        assert json_output.startswith("[\n")
        # Should contain data
        assert "org-1" in json_output
        assert "Record 1" in json_output

    def test_arrow_to_json_subsequent_chunk(self, mock_s3_service, sample_record_batch):
        """Test JSON conversion for subsequent chunks."""
        service = DataStreamService(s3_service=mock_s3_service)

        result = list(service._arrow_to_json(sample_record_batch, first_chunk=False))

        json_output = b"".join(result).decode()

        # Should start with comma for array continuation
        assert json_output.startswith(",\n")

    def test_arrow_to_json_valid_json_structure(
        self, mock_s3_service, sample_record_batch
    ):
        """Test JSON output is valid JSON."""
        service = DataStreamService(s3_service=mock_s3_service)

        result = list(service._arrow_to_json(sample_record_batch, first_chunk=True))

        json_output = b"".join(result).decode()
        # Add closing bracket to make complete JSON
        complete_json = json_output + "\n]"

        # Should be parseable as JSON
        data = json.loads(complete_json)
        assert isinstance(data, list)
        assert len(data) == 3

    def test_arrow_to_json_contains_correct_fields(
        self, mock_s3_service, sample_record_batch
    ):
        """Test JSON objects contain expected fields."""
        service = DataStreamService(s3_service=mock_s3_service)

        result = list(service._arrow_to_json(sample_record_batch, first_chunk=True))

        json_output = b"".join(result).decode()
        complete_json = json_output + "\n]"
        data = json.loads(complete_json)

        first_record = data[0]
        assert "id" in first_record
        assert "organisation-entity" in first_record
        assert "name" in first_record
        assert first_record["id"] == 1
        assert first_record["organisation-entity"] == "org-1"


class TestArrowToParquet:
    """Tests for _arrow_to_parquet method."""

    def test_arrow_to_parquet_produces_valid_parquet(
        self, mock_s3_service, sample_record_batch
    ):
        """Test Parquet conversion produces valid Parquet file."""
        service = DataStreamService(s3_service=mock_s3_service)

        result = list(service._arrow_to_parquet(sample_record_batch))

        parquet_bytes = b"".join(result)

        # Should start with PAR1 magic bytes
        assert parquet_bytes[:4] == b"PAR1"

    def test_arrow_to_parquet_readable(self, mock_s3_service, sample_record_batch):
        """Test Parquet output can be read back."""
        service = DataStreamService(s3_service=mock_s3_service)

        result = list(service._arrow_to_parquet(sample_record_batch))

        parquet_bytes = b"".join(result)
        buffer = BytesIO(parquet_bytes)

        # Should be readable as Parquet
        table = pq.read_table(buffer)
        assert table.num_rows == 3
        assert table.num_columns == 3

    def test_arrow_to_parquet_preserves_data(
        self, mock_s3_service, sample_record_batch
    ):
        """Test Parquet output preserves data values."""
        service = DataStreamService(s3_service=mock_s3_service)

        result = list(service._arrow_to_parquet(sample_record_batch))

        parquet_bytes = b"".join(result)
        buffer = BytesIO(parquet_bytes)
        table = pq.read_table(buffer)

        # Convert to dict for easy checking
        data = table.to_pydict()

        assert data["id"] == [1, 2, 3]
        assert data["organisation-entity"] == ["org-1", "org-1", "org-2"]
        assert data["name"] == ["Record 1", "Record 2", "Record 3"]
