"""
Integration tests for streaming response functionality.

These tests verify stream_response with real (mocked) S3 integration.
"""

import pytest

from lambda_function import stream_response
from utils import parse_cloudfront_request


def test_stream_response_returns_csv_data(
    mock_env_vars, s3_bucket_with_data, lambda_function_url_event_factory
):
    """Test stream_response returns CSV data."""
    event = lambda_function_url_event_factory(path="/test-dataset.csv", query="")
    request_ctx = parse_cloudfront_request(event)
    bucket = mock_env_vars["DATASET_BUCKET"]

    chunks = list(stream_response(request_ctx, bucket))
    body = b"".join(chunks).decode("utf-8")

    assert "organisation-entity" in body
    assert "org-" in body
    assert "Record" in body


def test_stream_response_returns_json_data(
    mock_env_vars, s3_bucket_with_data, cloudfront_event
):
    """Test stream_response returns JSON data."""
    request_ctx = parse_cloudfront_request(cloudfront_event)
    bucket = mock_env_vars["DATASET_BUCKET"]

    chunks = list(stream_response(request_ctx, bucket))
    body = b"".join(chunks).decode("utf-8")

    assert body.startswith("[")
    assert "organisation-entity" in body


def test_stream_response_filters_by_organisation_entity(
    mock_env_vars, s3_bucket_with_data, lambda_function_url_event_factory
):
    """Test stream_response correctly filters data."""
    event = lambda_function_url_event_factory(
        path="/test-dataset.csv", query="organisation-entity=org-1"
    )
    request_ctx = parse_cloudfront_request(event)
    bucket = mock_env_vars["DATASET_BUCKET"]

    chunks = list(stream_response(request_ctx, bucket))
    body = b"".join(chunks).decode("utf-8")

    assert "org-1" in body
    lines = body.split("\n")
    data_lines = [line for line in lines if line and not line.startswith("id,")]
    for line in data_lines:
        if "org-" in line:
            assert "org-1" in line


def test_stream_response_raises_error_for_missing_file(
    mock_env_vars, s3_bucket_with_data, lambda_function_url_event_factory
):
    """Test stream_response raises error when dataset doesn't exist."""
    event = lambda_function_url_event_factory(path="/nonexistent.csv", query="")
    request_ctx = parse_cloudfront_request(event)
    bucket = mock_env_vars["DATASET_BUCKET"]

    with pytest.raises(FileNotFoundError):
        list(stream_response(request_ctx, bucket))


def test_stream_response_exports_csv_from_parquet(
    mock_env_vars, s3_bucket_with_data, lambda_function_url_event_factory
):
    """Test stream_response converts Parquet to CSV format."""
    event = lambda_function_url_event_factory(path="/test-dataset.csv")
    request_ctx = parse_cloudfront_request(event)
    bucket = mock_env_vars["DATASET_BUCKET"]

    chunks = list(stream_response(request_ctx, bucket))
    csv_data = b"".join(chunks).decode("utf-8")

    lines = csv_data.strip().split("\n")
    assert len(lines) > 1  # Header + data
    headers_line = lines[0].replace('"', "")
    headers = headers_line.split(",")
    assert "id" in headers
    assert "organisation-entity" in headers


def test_stream_response_exports_json_from_parquet(
    mock_env_vars, s3_bucket_with_data, lambda_function_url_event_factory
):
    """Test stream_response converts Parquet to JSON format."""
    event = lambda_function_url_event_factory(path="/test-dataset.json")
    request_ctx = parse_cloudfront_request(event)
    bucket = mock_env_vars["DATASET_BUCKET"]

    chunks = list(stream_response(request_ctx, bucket))
    json_data = b"".join(chunks).decode("utf-8")

    assert json_data.startswith("[")
    assert "organisation-entity" in json_data
    assert "id" in json_data


def test_stream_response_returns_fewer_rows_when_filtered(
    mock_env_vars, s3_bucket_with_data, lambda_function_url_event_factory
):
    """Test stream_response returns subset when filter applied."""
    # Full export
    event_full = lambda_function_url_event_factory(path="/test-dataset.csv")
    request_ctx_full = parse_cloudfront_request(event_full)
    bucket = mock_env_vars["DATASET_BUCKET"]

    chunks_full = list(stream_response(request_ctx_full, bucket))
    lines_full = b"".join(chunks_full).decode("utf-8").strip().split("\n")

    # Filtered export
    event_filtered = lambda_function_url_event_factory(
        path="/test-dataset.csv", query="organisation-entity=org-1"
    )
    request_ctx_filtered = parse_cloudfront_request(event_filtered)

    chunks_filtered = list(stream_response(request_ctx_filtered, bucket))
    lines_filtered = b"".join(chunks_filtered).decode("utf-8").strip().split("\n")

    # Filtered should have fewer lines
    assert len(lines_filtered) < len(lines_full)
    assert len(lines_filtered) > 1  # Still has header + data


def test_stream_response_exports_parquet_format(
    mock_env_vars, s3_bucket_with_data, lambda_function_url_event_factory
):
    """Test stream_response supports Parquet output format."""
    event = lambda_function_url_event_factory(path="/test-dataset.parquet")
    request_ctx = parse_cloudfront_request(event)
    bucket = mock_env_vars["DATASET_BUCKET"]

    chunks = list(stream_response(request_ctx, bucket))
    body = b"".join(chunks)

    # Parquet is binary, verify it's not text
    assert isinstance(body, bytes)
    assert len(body) > 0
    # Parquet magic number is "PAR1"
    assert body[:4] == b"PAR1" or b"PAR1" in body  # Could be at start or end
