"""Utility functions for request parsing and data processing."""

from typing import Dict, Any, Tuple
from urllib.parse import parse_qs, unquote

from models import PathParams, QueryParams, RequestContext


def parse_cloudfront_request(event: Dict[str, Any]) -> RequestContext:
    """
    Parse CloudFront Lambda@Edge or Function URL request.

    Supports both CloudFront Lambda@Edge format and Lambda Function URL format.

    Expected path format: /{dataset}.{extension}
    Expected query parameter: organisation-entity

    Args:
        event: Lambda event from CloudFront or Function URL

    Returns:
        RequestContext with validated parameters

    Raises:
        ValueError: If path format is invalid or validation fails
    """
    # Detect event type and extract path/query
    path, query_string = _extract_request_info(event)

    # Parse path parameters
    dataset, extension = _parse_path(path)
    path_params = PathParams(dataset=dataset, extension=extension)

    # Parse query parameters
    query_dict = parse_qs(query_string) if query_string else {}
    organisation_entity = query_dict.get("organisation-entity", [None])[0]
    query_params = QueryParams(organisation_entity=organisation_entity)

    return RequestContext(
        path_params=path_params,
        query_params=query_params,
    )


def _extract_request_info(event: Dict[str, Any]) -> Tuple[str, str]:
    """
    Extract path and query string from different Lambda event formats.

    Returns:
        Tuple of (path, query_string)
    """
    # Lambda Function URL format
    if "requestContext" in event and "http" in event["requestContext"]:
        raw_path = event.get("rawPath", "")
        raw_query = event.get("rawQueryString", "")
        return unquote(raw_path), raw_query

    # CloudFront Lambda@Edge format
    elif "Records" in event:
        request = event["Records"][0]["cf"]["request"]
        uri = request.get("uri", "")
        query_string = request.get("querystring", "")
        return unquote(uri), query_string

    # API Gateway format (fallback)
    elif "path" in event:
        path = event.get("path", "")
        query_string = event.get("queryStringParameters", {})
        if isinstance(query_string, dict):
            query_string = "&".join(f"{k}={v}" for k, v in query_string.items())
        return unquote(path), query_string or ""

    else:
        raise ValueError(f"Unsupported event format: {event.keys()}")


def _parse_path(path: str) -> Tuple[str, str]:
    """
    Parse dataset and extension from path.

    Expected format: /{dataset}.{extension}

    Args:
        path: URL path

    Returns:
        Tuple of (dataset, extension)

    Raises:
        ValueError: If path format is invalid
    """
    # Remove leading/trailing slashes
    path = path.strip("/")

    if not path:
        raise ValueError("Path cannot be empty")

    # Split by dots - last part is extension, everything before is dataset name
    # This allows dataset names like "test.backup" to work correctly
    parts = path.rsplit(".", 1)  # Split from right, max 1 split

    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(
            f"Invalid path format: '{path}'. Expected format: /{{dataset}}.{{extension}}"
        )

    dataset, extension = parts
    return dataset, extension


def get_content_type(format: str) -> str:
    """Get content type for the given format."""
    content_types = {
        "csv": "text/csv",
        "json": "application/json",
        "parquet": "application/octet-stream",
    }
    return content_types.get(format, "application/octet-stream")


def get_filename(dataset: str, format: str) -> str:
    """Generate filename for Content-Disposition header."""
    return f"{dataset}.{format}"
