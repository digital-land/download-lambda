"""
Lambda function for streaming filtered dataset downloads.

This function uses AWS Lambda response streaming to handle large dataset downloads
without buffering the entire response in memory.

Features:
- Validates path and query parameters using Pydantic
- Reads Parquet files from S3 using DuckDB
- Applies filters efficiently at the Parquet metadata level
- Supports CSV, JSON, and Parquet output formats
- Streams data directly to client without size limits

Expected URL format: /{dataset}.{extension}?organisation-entity={value}

S3 Structure:
All Parquet files are expected to be in the 'dataset' prefix within the bucket:
- URL: /sales.csv → S3: s3://{DATASET_BUCKET}/dataset/sales.parquet
- URL: /users.json → S3: s3://{DATASET_BUCKET}/dataset/users.parquet

Configuration:
- DATASET_BUCKET: S3 bucket name containing the Parquet datasets (required)

Deployment requirements:
1. Configure Lambda Function URL with InvokeMode: RESPONSE_STREAM
2. Set handler to: lambda_function.lambda_handler
3. Ensure awslambdaric is included in your deployment package

Benefits of streaming:
- No 6MB Lambda response size limit
- Lower memory usage (constant, not proportional to response size)
- Faster time to first byte
- Can handle gigabyte-sized responses
- Better user experience with progress indicators
"""

import json
import logging
import os
import traceback
from typing import Dict, Any, Iterator

from pydantic import ValidationError

try:
    # Lambda environment (flat structure)
    from models import RequestContext
    from utils import parse_cloudfront_request, get_content_type, get_filename
    from data_processor import DataProcessor
except ImportError:
    # Local/test environment (package structure)
    from .models import RequestContext
    from .utils import parse_cloudfront_request, get_content_type, get_filename
    from .data_processor import DataProcessor


# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], response_stream, _context) -> None:
    """
    Lambda handler for streaming dataset download responses.

    This handler uses AWS Lambda's response streaming feature to stream large
    datasets without buffering the entire response in memory.

    The response_stream object provides methods to:
    - set_status_code(status_code: int) - Set HTTP status code
    - set_headers(headers: Dict[str, str]) - Set HTTP headers
    - write(data: bytes) - Write a chunk of data to the stream
    - end() - Complete the response

    Args:
        event: Lambda event (Function URL format)
        response_stream: StreamingBody object for writing response chunks
        _context: Lambda context (unused but required by AWS Lambda signature)
    """
    logger.info(f"Received streaming event: {json.dumps(event)}")

    try:
        # Validate bucket configuration
        dataset_bucket = os.environ.get("DATASET_BUCKET", "")
        if not dataset_bucket:
            response_stream.set_status_code(500)
            response_stream.set_headers({"Content-Type": "application/json"})
            response_stream.write(
                json.dumps(
                    {
                        "error": "Server configuration error: DATASET_BUCKET not set",
                        "statusCode": 500,
                    }
                ).encode("utf-8")
            )
            response_stream.end()
            return

        # Parse and validate request
        try:
            request_ctx = parse_cloudfront_request(event)
            logger.info(
                f"Parsed request: dataset={request_ctx.path_params.dataset}, "
                f"format={request_ctx.output_format}, "
                f"filter={request_ctx.filter_value}"
            )
        except (ValidationError, ValueError) as e:
            logger.warning(f"Request error: {e}")
            response_stream.set_status_code(400)
            response_stream.set_headers({"Content-Type": "application/json"})
            response_stream.write(
                json.dumps({"error": str(e), "statusCode": 400}).encode("utf-8")
            )
            response_stream.end()
            return

        # Set response headers
        response_stream.set_status_code(200)

        file_name = get_filename(
            request_ctx.path_params.dataset, request_ctx.output_format
        )
        content_type = get_content_type(request_ctx.output_format)
        response_stream.set_headers(
            {
                "Content-Type": content_type,
                "Content-Disposition": f'attachment; filename="{file_name}"',
                "Cache-Control": "public, max-age=3600",
            }
        )

        # Stream the data
        for chunk in stream_response(request_ctx, dataset_bucket):
            response_stream.write(chunk)

        # Complete the response
        response_stream.end()
        logger.info(
            f"Successfully completed streaming response for {request_ctx.path_params.dataset}"
        )

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        response_stream.set_status_code(404)
        response_stream.set_headers({"Content-Type": "application/json"})
        response_stream.write(
            json.dumps({"error": str(e), "statusCode": 404}).encode("utf-8")
        )
        response_stream.end()

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}\n{traceback.format_exc()}")
        response_stream.set_status_code(500)
        response_stream.set_headers({"Content-Type": "application/json"})
        response_stream.write(
            json.dumps(
                {"error": f"Internal server error: {str(e)}", "statusCode": 500}
            ).encode("utf-8")
        )
        response_stream.end()


def stream_response(request_ctx: RequestContext, bucket: str) -> Iterator[bytes]:
    """
    Create a streaming response for Lambda Function URL with response streaming.

    This function returns an iterator that yields chunks of data, which AWS Lambda
    will stream directly to the client without buffering the entire response.

    Parameters automatically flow from validated models to the data processor:
    - dataset: From PathParams.dataset (e.g., "my-dataset")
    - extension: From PathParams.extension (e.g., "csv", "json", "parquet")
    - Query params: All QueryParams fields automatically unpacked (e.g., organisation_entity)

    To add new query parameters:
    1. Add field to QueryParams model in models.py
    2. Add parameter to stream_data() signature in data_processor.py
    3. That's it! The parameter will automatically flow through.

    To use this handler, your Lambda function URL must be configured with:
    - InvokeMode: RESPONSE_STREAM

    Args:
        request_ctx: Validated request context
        bucket: S3 bucket name containing the datasets

    Yields:
        Chunks of data in the requested format
    """
    try:
        # Log the streaming request
        logger.info(
            f"Starting streaming response for {request_ctx.path_params.dataset}"
        )

        # Create data processor with S3 configuration
        data_processor = DataProcessor(bucket=bucket, prefix="dataset")

        # Build parameters automatically from models
        stream_params = {
            # Path parameters (dataset and extension both flow through)
            **request_ctx.path_params.model_dump(exclude_none=True),
            # Query parameters (all parameters automatically included)
            **request_ctx.query_params.model_dump(exclude_none=True),
        }

        # Generate the data stream using the data processor
        for chunk in data_processor.stream_data(**stream_params):
            yield chunk

        logger.info(
            f"Completed streaming response for {request_ctx.path_params.dataset}"
        )

    except Exception as e:
        logger.error(f"Error during streaming: {str(e)}")
        # In streaming mode, if headers are already sent, we can't send an error response
        # The connection will be terminated
        raise
