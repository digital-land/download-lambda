"""
Utility functions for data processing.

FastAPI handles all request parsing, routing, and validation,
so this module now only contains simple helper functions.
"""


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
