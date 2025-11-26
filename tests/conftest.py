"""
Shared test fixtures and configuration.

This file contains pytest fixtures that are shared across unit, integration,
and acceptance tests. Fixtures are organized by scope and purpose.
"""

import os
import time
from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest
import boto3
from moto.server import ThreadedMotoServer
from fastapi.testclient import TestClient


# ============================================================================
# Path and Environment Fixtures
# ============================================================================


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="function")
def mock_env_vars(monkeypatch):
    """Set up mock environment variables for the application."""
    monkeypatch.setenv("DATASET_BUCKET", "test-bucket")
    monkeypatch.setenv("AWS_ENDPOINT_URL", "http://localhost:5000")
    monkeypatch.setenv("ENVIRONMENT", "test")

    return {
        "DATASET_BUCKET": "test-bucket",
        "AWS_ENDPOINT_URL": "http://localhost:5000",
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
    return pd.DataFrame(
        {
            "id": range(1, 101),
            "organisation-entity": [f"org-{i % 5}" for i in range(100)],
            "name": [f"Record {i}" for i in range(1, 101)],
            "value": [i * 100 for i in range(1, 101)],
            "category": [f"Category {i % 3}" for i in range(100)],
        }
    )


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
def s3_mock(aws_credentials, moto_server):
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
        aws_secret_access_key="testing",
    )

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
# FastAPI Test Client Fixtures
# ============================================================================


@pytest.fixture(scope="function")
def client(mock_env_vars, s3_bucket_with_data):
    """
    Create a FastAPI test client with mocked S3.

    This fixture automatically sets up the environment and S3 bucket
    before creating the app, ensuring clean imports.
    """
    # Import app after environment is configured
    from application.main import app

    return TestClient(app)


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
