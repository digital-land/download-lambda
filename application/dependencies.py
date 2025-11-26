"""
FastAPI dependencies for dependency injection.

Dependencies are reusable components that can be injected into route handlers
to provide services, configuration, and other shared resources following
the Dependency Injection pattern.
"""

import os
from fastapi import HTTPException

from application.services import S3Service, DataStreamService


def get_dataset_bucket() -> str:
    """
    Dependency that provides the S3 bucket name from environment variables.

    Raises:
        HTTPException: If DATASET_BUCKET environment variable is not set

    Returns:
        str: S3 bucket name containing datasets
    """
    bucket = os.environ.get("DATASET_BUCKET")
    if not bucket:
        raise HTTPException(
            status_code=500, detail="Server configuration error: DATASET_BUCKET not set"
        )
    return bucket


def get_s3_service() -> S3Service:
    """
    Dependency that provides an S3Service instance.

    Returns:
        Configured S3Service instance
    """
    bucket = get_dataset_bucket()
    return S3Service(bucket=bucket, prefix="dataset")


def get_data_stream_service() -> DataStreamService:
    """
    Dependency that provides a DataStreamService instance.

    Returns:
        Configured DataStreamService instance
    """
    s3_service = get_s3_service()
    return DataStreamService(s3_service=s3_service)
