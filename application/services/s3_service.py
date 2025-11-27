"""
S3 Service for AWS S3 operations.

Handles all S3-related operations including configuration,
credential management, and bucket access.
"""

import logging
import os
from typing import Optional

import boto3
from botocore.client import BaseClient

logger = logging.getLogger(__name__)


class S3Service:
    """
    Service for S3 operations and configuration.

    Provides:
    - S3 client configuration with LocalStack support
    - Credential management
    - Region detection
    - Endpoint URL handling for testing/development
    """

    def __init__(self, bucket: str, prefix: str = ""):
        """
        Initialize S3 service.

        Args:
            bucket: S3 bucket name
            prefix: Optional S3 key prefix (folder path)
        """
        self.bucket = bucket
        self.prefix = prefix.strip("/") if prefix else ""
        self.session = boto3.Session()
        self.region = self.session.region_name or "eu-west-2"

        # Support custom S3 endpoint (for LocalStack, moto, etc.)
        self.endpoint_url = os.environ.get("AWS_ENDPOINT_URL") or os.environ.get(
            "S3_ENDPOINT"
        )
        self._client: Optional[BaseClient] = None

        logger.info(
            f"Initialized S3 service for bucket='{bucket}', "
            f"prefix='{self.prefix}', region='{self.region}'"
        )
        if self.endpoint_url:
            logger.info(f"Using custom S3 endpoint: {self.endpoint_url}")

    @property
    def client(self) -> BaseClient:
        """
        Get or create S3 client.

        Returns:
            Configured boto3 S3 client
        """
        if self._client is None:
            self._client = boto3.client("s3", endpoint_url=self.endpoint_url)
        return self._client

    def get_object_path(self, dataset: str) -> str:
        """
        Get the full S3 path for a dataset.

        Args:
            dataset: Dataset name (without .parquet extension)

        Returns:
            Full S3 key path
        """
        if self.prefix:
            return f"{self.prefix}/{dataset}.parquet"
        return f"{dataset}.parquet"

    def get_s3_uri(self, dataset: str) -> str:
        """
        Get the full S3 URI for a dataset.

        Args:
            dataset: Dataset name

        Returns:
            Full S3 URI (s3://bucket/path/dataset.parquet)
        """
        path = self.get_object_path(dataset)
        return f"s3://{self.bucket}/{path}"

    def get_credentials(self) -> Optional[dict]:
        """
        Get AWS credentials from session.

        Returns:
            Dictionary with access_key, secret_key, and optional token,
            or None if no credentials available
        """
        credentials = self.session.get_credentials()
        if credentials:
            frozen_creds = credentials.get_frozen_credentials()
            return {
                "access_key": frozen_creds.access_key,
                "secret_key": frozen_creds.secret_key,
                "token": frozen_creds.token,
            }
        return None

    def dataset_exists(self, dataset: str) -> bool:
        """
        Check if a dataset exists in S3.

        Args:
            dataset: Dataset name

        Returns:
            True if dataset exists, False otherwise
        """
        try:
            key = self.get_object_path(dataset)
            s3_uri = f"s3://{self.bucket}/{key}"
            logger.info(f"Checking if dataset exists: {s3_uri}")
            self.client.head_object(Bucket=self.bucket, Key=key)
            logger.info(f"Dataset found: {s3_uri}")
            return True
        except Exception as e:
            s3_uri = f"s3://{self.bucket}/{self.get_object_path(dataset)}"
            logger.warning(f"Dataset not found: {s3_uri} - {type(e).__name__}: {e}")
            return False
