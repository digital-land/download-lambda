"""
Shared test fixtures and configuration.

This file contains pytest fixtures that are shared across unit, integration,
and acceptance tests. Fixtures are organized by scope and purpose.
"""
import json
import os
import threading
import time
from io import BytesIO
from pathlib import Path
from typing import Dict, Any

import pandas as pd
import pytest
import boto3
from moto.server import ThreadedMotoServer


# ============================================================================
# Path and Environment Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def src_path(project_root: Path) -> Path:
    """Return the src directory path."""
    return project_root / "src"


@pytest.fixture(scope="function")
def mock_env_vars(monkeypatch):
    """Set up mock environment variables for Lambda."""
    import sys
    from pathlib import Path

    # Add src to path if not already there
    src_path = Path(__file__).parent.parent / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    # Set environment variables BEFORE importing lambda_function
    monkeypatch.setenv("DATASET_BUCKET", "test-bucket")

    return {
        "DATASET_BUCKET": "test-bucket",
    }


# ============================================================================
# Sample Data Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def sample_dataframe() -> pd.DataFrame:
    """
    Create a sample DataFrame for testing.

    Returns a DataFrame with organisation-entity column and sample data.
    """
    return pd.DataFrame({
        "id": range(1, 101),
        "organisation-entity": [f"org-{i % 5}" for i in range(100)],
        "name": [f"Record {i}" for i in range(1, 101)],
        "value": [i * 100 for i in range(1, 101)],
        "category": [f"Category {i % 3}" for i in range(100)],
    })


@pytest.fixture(scope="function")
def sample_parquet_bytes(sample_dataframe: pd.DataFrame) -> bytes:
    """
    Create a Parquet file in memory from sample DataFrame.

    Returns the Parquet file content as bytes.
    """
    buffer = BytesIO()
    sample_dataframe.to_parquet(buffer, index=False, engine="pyarrow")
    buffer.seek(0)
    return buffer.read()


# ============================================================================
# AWS Mock Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def moto_server():
    """
    Start a moto server that DuckDB can connect to via HTTP.

    This is necessary because DuckDB's httpfs extension makes real HTTP requests,
    so we need an actual HTTP server rather than just mocking boto3 calls.
    """
    # Start moto server on localhost:5000
    server = ThreadedMotoServer(port="5000", verbose=False)
    server.start()

    # Wait for server to be ready
    time.sleep(0.5)

    yield server

    # Cleanup
    server.stop()


@pytest.fixture(scope="function")
def aws_credentials(monkeypatch):
    """Mock AWS credentials for boto3."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


@pytest.fixture(scope="function")
def s3_mock(aws_credentials, moto_server, monkeypatch):
    """
    Create a mock S3 service that works with both boto3 and DuckDB.

    Uses moto server to provide an actual HTTP endpoint that DuckDB can access.
    """
    # Point boto3 to the moto server
    s3_client = boto3.client(
        "s3",
        endpoint_url="http://localhost:5000",
        region_name="us-east-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing"
    )

    # Configure DuckDB to use the moto server
    monkeypatch.setenv("S3_ENDPOINT", "localhost:5000")
    monkeypatch.setenv("S3_USE_SSL", "false")

    yield s3_client


@pytest.fixture(scope="function")
def s3_bucket_with_data(s3_mock, sample_parquet_bytes) -> str:
    """
    Create a mock S3 bucket with sample Parquet data.

    Files are stored in the dataset/ prefix to match the expected S3 structure.

    Returns the bucket name.
    """
    bucket_name = "test-bucket"
    s3_mock.create_bucket(Bucket=bucket_name)

    # Upload sample datasets to dataset/ prefix
    s3_mock.put_object(
        Bucket=bucket_name,
        Key="dataset/test-dataset.parquet",
        Body=sample_parquet_bytes,
    )

    s3_mock.put_object(
        Bucket=bucket_name,
        Key="dataset/customers.parquet",
        Body=sample_parquet_bytes,
    )

    return bucket_name


# ============================================================================
# Lambda Event Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def lambda_function_url_event() -> Dict[str, Any]:
    """Sample Lambda Function URL event."""
    return {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": "/test-dataset.csv",
        "rawQueryString": "organisation-entity=org-1",
        "headers": {
            "accept": "text/csv",
            "user-agent": "test-agent",
        },
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "test-api",
            "domainName": "test.execute-api.us-east-1.amazonaws.com",
            "http": {
                "method": "GET",
                "path": "/test-dataset.csv",
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
                "userAgent": "test-agent",
            },
            "requestId": "test-request-id",
            "routeKey": "$default",
            "stage": "$default",
            "time": "01/Jan/2024:00:00:00 +0000",
            "timeEpoch": 1704067200000,
        },
    }


@pytest.fixture(scope="session")
def cloudfront_event() -> Dict[str, Any]:
    """Sample CloudFront Lambda@Edge event."""
    return {
        "Records": [
            {
                "cf": {
                    "request": {
                        "uri": "/test-dataset.json",
                        "querystring": "organisation-entity=org-2",
                        "headers": {
                            "host": [
                                {
                                    "key": "Host",
                                    "value": "d123.cloudfront.net",
                                }
                            ],
                        },
                        "method": "GET",
                    }
                }
            }
        ]
    }


@pytest.fixture(scope="function")
def lambda_function_url_event_factory():
    """
    Factory for creating Lambda Function URL events with custom parameters.

    Usage:
        event = lambda_function_url_event_factory(
            path="/dataset.csv",
            query="filter=value"
        )
    """
    def _create_event(
        path: str = "/test-dataset.csv",
        query: str = "",
        method: str = "GET",
    ) -> Dict[str, Any]:
        return {
            "version": "2.0",
            "routeKey": "$default",
            "rawPath": path,
            "rawQueryString": query,
            "headers": {},
            "requestContext": {
                "http": {
                    "method": method,
                    "path": path,
                },
            },
        }
    return _create_event


# ============================================================================
# Test Data Cleanup
# ============================================================================

@pytest.fixture(scope="function", autouse=False)
def cleanup_temp_files():
    """
    Fixture to clean up temporary files after tests.

    Use this fixture when tests create temporary files.
    """
    temp_files = []

    def register_file(filepath: str):
        temp_files.append(filepath)

    yield register_file

    # Cleanup
    for filepath in temp_files:
        if os.path.exists(filepath):
            os.remove(filepath)
