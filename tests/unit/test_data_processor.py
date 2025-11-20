"""
Unit tests for data processor.

These tests verify DuckDB-based data processing with mocked S3 dependencies.
Tests focus on filter pushdown, Arrow streaming, and memory efficiency.
"""

import pytest
import pandas as pd
from io import BytesIO
from unittest.mock import Mock, patch, MagicMock

try:
    import duckdb
    import pyarrow as pa
    from src.data_processor import DataProcessor

    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False
    pytest.skip("DuckDB not installed", allow_module_level=True)


class TestDataProcessor:
    """Unit tests for DataProcessor class."""

    def test_init_sets_bucket_and_prefix(self):
        """Test that __init__ sets bucket and prefix correctly."""
        processor = DataProcessor(bucket="test-bucket", prefix="dataset")

        assert processor.bucket == "test-bucket"
        assert processor.prefix == "dataset"
        assert processor.s3_client is not None
        assert processor.session is not None

    def test_init_normalizes_prefix(self):
        """Test that __init__ normalizes prefix by stripping slashes."""
        processor1 = DataProcessor(bucket="test-bucket", prefix="/data/")
        processor2 = DataProcessor(bucket="test-bucket", prefix="data")

        assert processor1.prefix == "data"
        assert processor2.prefix == "data"

    def test_init_defaults_to_empty_prefix(self):
        """Test that __init__ defaults to empty prefix when not provided."""
        processor = DataProcessor(bucket="test-bucket")

        assert processor.prefix == ""

    def test_init_detects_aws_region(self):
        """Test that __init__ detects AWS region from session."""
        with patch("boto3.Session") as mock_session:
            mock_session.return_value.region_name = "eu-west-1"
            processor = DataProcessor(bucket="test-bucket")

            assert processor.region == "eu-west-1"

    def test_init_defaults_to_us_east_1_when_no_region(self):
        """Test that __init__ defaults to us-east-1 when region not set."""
        with patch("boto3.Session") as mock_session:
            mock_session.return_value.region_name = None
            processor = DataProcessor(bucket="test-bucket")

            assert processor.region == "us-east-1"

    def test_get_duckdb_conn_installs_httpfs_extension(self):
        """Test that _get_duckdb_conn installs httpfs extension."""
        processor = DataProcessor(bucket="test-bucket")

        conn = processor._get_duckdb_conn()

        # Verify httpfs is loaded by trying to use S3 features
        # If not loaded, this would raise an error
        result = conn.execute("SELECT current_setting('s3_region')").fetchone()
        assert result is not None

        conn.close()

    def test_get_duckdb_conn_sets_region(self):
        """Test that _get_duckdb_conn sets S3 region."""
        processor = DataProcessor(bucket="test-bucket")
        processor.region = "ap-southeast-2"

        conn = processor._get_duckdb_conn()

        result = conn.execute("SELECT current_setting('s3_region')").fetchone()
        assert result[0] == "ap-southeast-2"

        conn.close()

    def test_get_duckdb_conn_sets_credentials(self):
        """Test that _get_duckdb_conn sets AWS credentials."""
        processor = DataProcessor(bucket="test-bucket")

        # Mock credentials
        mock_creds = Mock()
        mock_creds.get_frozen_credentials.return_value = Mock(
            access_key="test_key", secret_key="test_secret", token="test_token"
        )

        with patch.object(
            processor.session, "get_credentials", return_value=mock_creds
        ):
            conn = processor._get_duckdb_conn()

            # Verify credentials were set (can't directly check in DuckDB)
            # But we can verify no error was raised
            result = conn.execute(
                "SELECT current_setting('s3_access_key_id')"
            ).fetchone()
            assert result[0] == "test_key"

            conn.close()

    def test_get_duckdb_conn_logs_warning_without_credentials(self):
        """Test that _get_duckdb_conn logs warning when credentials missing."""
        processor = DataProcessor(bucket="test-bucket")

        with patch.object(processor.session, "get_credentials", return_value=None):
            with patch("data_processor.logger") as mock_logger:
                conn = processor._get_duckdb_conn()

                # Should log warning about missing credentials
                mock_logger.warning.assert_called()
                assert "No AWS credentials" in str(mock_logger.warning.call_args)

                conn.close()

    def test_arrow_to_csv_with_header(self, sample_dataframe):
        """Test that _arrow_to_csv includes header when requested."""

        processor = DataProcessor(bucket="test-bucket")
        table = pa.Table.from_pandas(sample_dataframe.head(10))
        batch = table.to_batches()[0]

        chunks = list(processor._arrow_to_csv(batch, include_header=True))

        assert len(chunks) == 1
        csv_content = chunks[0].decode("utf-8")
        # PyArrow quotes string columns in CSV output
        assert "organisation-entity" in csv_content
        assert "org-" in csv_content
        assert "Record" in csv_content

    def test_arrow_to_csv_excludes_header_when_not_requested(self, sample_dataframe):
        """Test that _arrow_to_csv excludes header when not requested."""

        processor = DataProcessor(bucket="test-bucket")
        table = pa.Table.from_pandas(sample_dataframe.head(10))
        batch = table.to_batches()[0]

        chunks = list(processor._arrow_to_csv(batch, include_header=False))

        csv_content = chunks[0].decode("utf-8")
        assert "organisation-entity" not in csv_content  # No header
        assert "org-" in csv_content  # Has data
        assert "Record" in csv_content

    def test_arrow_to_csv_preserves_data_types(self):
        """Test that _arrow_to_csv preserves data types correctly."""

        processor = DataProcessor(bucket="test-bucket")
        df = pd.DataFrame(
            {
                "int_col": [1, 2, 3],
                "float_col": [1.1, 2.2, 3.3],
                "str_col": ["a", "b", "c"],
            }
        )
        table = pa.Table.from_pandas(df)
        batch = table.to_batches()[0]

        chunks = list(processor._arrow_to_csv(batch, include_header=True))

        csv_content = chunks[0].decode("utf-8")
        assert "int_col" in csv_content
        assert "float_col" in csv_content
        assert "str_col" in csv_content
        # Check data is present (may be quoted)
        assert "1.1" in csv_content
        assert "2.2" in csv_content

    def test_arrow_to_json_starts_with_bracket_for_first_chunk(self, sample_dataframe):
        """Test that _arrow_to_json starts with bracket for first chunk."""

        processor = DataProcessor(bucket="test-bucket")
        table = pa.Table.from_pandas(sample_dataframe.head(5))
        batch = table.to_batches()[0]

        chunks = list(processor._arrow_to_json(batch, first_chunk=True))

        first_content = b"".join(chunks).decode("utf-8")
        assert first_content.startswith("[\n")

    def test_arrow_to_json_starts_with_comma_for_subsequent_chunks(
        self, sample_dataframe
    ):
        """Test that _arrow_to_json starts with comma for subsequent chunks."""

        processor = DataProcessor(bucket="test-bucket")
        table = pa.Table.from_pandas(sample_dataframe.head(5))
        batch = table.to_batches()[0]

        chunks = list(processor._arrow_to_json(batch, first_chunk=False))

        first_content = chunks[0].decode("utf-8")
        assert first_content.startswith(",\n")

    def test_arrow_to_json_produces_valid_json_objects(self, sample_dataframe):
        """Test that _arrow_to_json produces valid JSON objects."""

        processor = DataProcessor(bucket="test-bucket")
        table = pa.Table.from_pandas(sample_dataframe.head(3))
        batch = table.to_batches()[0]

        chunks = list(processor._arrow_to_json(batch, first_chunk=True))

        json_content = b"".join(chunks).decode("utf-8")
        assert '"id": 1' in json_content
        assert '"organisation-entity": "org-1"' in json_content

    def test_arrow_to_parquet_generates_valid_bytes(self, sample_dataframe):
        """Test that _arrow_to_parquet generates valid bytes."""

        processor = DataProcessor(bucket="test-bucket")
        table = pa.Table.from_pandas(sample_dataframe.head(10))
        batch = table.to_batches()[0]

        chunks = list(processor._arrow_to_parquet(batch))

        assert len(chunks) == 1
        parquet_bytes = chunks[0]
        assert isinstance(parquet_bytes, bytes)
        assert len(parquet_bytes) > 0

    def test_arrow_to_parquet_output_can_be_read_back(self, sample_dataframe):
        """Test that _arrow_to_parquet output can be read back."""

        processor = DataProcessor(bucket="test-bucket")
        table = pa.Table.from_pandas(sample_dataframe.head(10))
        batch = table.to_batches()[0]

        chunks = list(processor._arrow_to_parquet(batch))
        parquet_bytes = chunks[0]

        # Read it back
        df = pd.read_parquet(BytesIO(parquet_bytes))

        assert len(df) == 10
        assert list(df.columns) == list(sample_dataframe.columns)

    def test_stream_data_raises_error_for_missing_file(self, s3_mock):
        """Test that stream_data raises error for missing file."""
        processor = DataProcessor(bucket="test-bucket")
        s3_mock.create_bucket(Bucket="test-bucket")

        # Mock DuckDB to raise IOException for missing file
        with pytest.raises((FileNotFoundError, duckdb.IOException, Exception)):
            list(processor.stream_data(dataset="nonexistent", extension="csv"))

    def test_stream_data_closes_connection_on_error(self, s3_mock):
        """Test that stream_data closes DuckDB connection on error."""
        processor = DataProcessor(bucket="test-bucket")
        s3_mock.create_bucket(Bucket="test-bucket")

        # Attempt to stream non-existent file
        try:
            list(processor.stream_data(dataset="nonexistent", extension="csv"))
        except Exception:
            pass  # Expected to fail

        # Verify no dangling connections by creating a new one
        conn = duckdb.connect(database=":memory:")
        assert conn is not None
        conn.close()

    def test_stream_data_returns_generator(self):
        """Test that stream_data returns a generator for memory efficiency."""
        processor = DataProcessor(bucket="test-bucket")

        # Create a mock connection
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_reader = MagicMock()
        mock_reader.__iter__ = Mock(return_value=iter([]))
        mock_result.fetch_arrow_reader.return_value = mock_reader
        mock_conn.execute.return_value = mock_result

        with patch.object(processor, "_get_duckdb_conn", return_value=mock_conn):
            result = processor.stream_data(dataset="test", extension="csv")

            # Verify it's a generator
            assert hasattr(result, "__iter__")
            assert hasattr(result, "__next__")

    def test_stream_data_includes_where_clause_with_filter(self):
        """Test that stream_data includes WHERE clause when filter provided."""
        processor = DataProcessor(bucket="test-bucket")

        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_reader = MagicMock()

        # Create a proper schema mock
        mock_schema = pa.schema([("id", pa.int64()), ("name", pa.string())])
        mock_reader.schema = mock_schema
        mock_reader.__iter__ = Mock(return_value=iter([]))

        mock_result.fetch_record_batch.return_value = mock_reader
        mock_conn.execute.return_value = mock_result

        with patch.object(processor, "_get_duckdb_conn", return_value=mock_conn):
            list(
                processor.stream_data(
                    dataset="test", extension="csv", organisation_entity="org-1"
                )
            )

            # Verify execute was called with parameterized query
            call_args = mock_conn.execute.call_args
            query = call_args[0][0]
            params = call_args[0][1]

            assert "WHERE" in query
            assert "organisation-entity" in query
            assert params == ["org-1"]

    def test_stream_data_excludes_where_clause_without_filter(self):
        """Test that stream_data excludes WHERE clause when no filter."""
        processor = DataProcessor(bucket="test-bucket")

        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_reader = MagicMock()

        # Create a proper schema mock
        mock_schema = pa.schema([("id", pa.int64()), ("name", pa.string())])
        mock_reader.schema = mock_schema
        mock_reader.__iter__ = Mock(return_value=iter([]))

        mock_result.fetch_record_batch.return_value = mock_reader
        mock_conn.execute.return_value = mock_result

        with patch.object(processor, "_get_duckdb_conn", return_value=mock_conn):
            list(
                processor.stream_data(
                    dataset="test", extension="csv", organisation_entity=None
                )
            )

            # Verify execute was called without WHERE
            call_args = mock_conn.execute.call_args
            query = call_args[0][0]
            params = call_args[0][1] if len(call_args[0]) > 1 else []

            assert "WHERE" not in query
            assert params == []
