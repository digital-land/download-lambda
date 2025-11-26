"""
FastAPI router for dataset downloads.

Defines the download endpoint that handles streaming responses
for CSV, JSON, and Parquet formats with optional filtering.

This router delegates to services for business logic, keeping
routing concerns separate from data processing.
"""

import logging
from typing import Optional, Literal
from fastapi import APIRouter, Path, Query, HTTPException, Depends
from fastapi.responses import StreamingResponse

from application.services import DataStreamService
from application.dependencies import get_data_stream_service
from application.utils import get_content_type, get_filename

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{dataset}.{extension}")
async def download_dataset(
    dataset: str = Path(
        ...,
        min_length=1,
        max_length=100,
        pattern="^[a-zA-Z0-9_-]+$",
        description="Dataset name (without .parquet extension)",
        examples=["sales", "customers", "orders"],
    ),
    extension: Literal["csv", "json", "parquet"] = Path(
        ..., description="Output format for the dataset"
    ),
    organisation_entity: Optional[str] = Query(
        None,
        alias="organisation-entity",
        max_length=100,
        description="Filter dataset by organisation entity",
        examples=["org-123", "company-abc"],
    ),
    data_stream_service: DataStreamService = Depends(get_data_stream_service),
):
    """
    Stream a dataset from S3 in the requested format with optional filtering.

    Uses DuckDB to efficiently stream data directly from S3 Parquet files
    with filter pushdown for optimal performance.

    **Features:**
    - Direct S3 access via DuckDB (no data copying)
    - Filter pushdown at Parquet metadata level (efficient filtering)
    - Streaming response (handles datasets of any size)
    - Multiple output formats (CSV, JSON, Parquet)

    **S3 Structure:**
    - Source files: `s3://{bucket}/dataset/{dataset}.parquet`
    - Example: `/sales.csv` → reads from `s3://bucket/dataset/sales.parquet`

    **Query Parameters:**
    - `organisation-entity`: Optional filter to return only rows matching this value

    Args:
        dataset: Dataset name (maps to {dataset}.parquet in S3)
        extension: Output format (csv, json, or parquet)
        organisation_entity: Optional filter value for organisation-entity column
        data_stream_service: Data streaming service (injected via dependency)

    Returns:
        StreamingResponse: Dataset in requested format with appropriate headers

    Raises:
        HTTPException 400: Invalid request parameters
        HTTPException 404: Dataset not found in S3
        HTTPException 500: Server error during processing
    """
    try:
        logger.info(
            f"Processing download: dataset={dataset}, "
            f"format={extension}, filter={organisation_entity}"
        )

        # Check if dataset exists before streaming
        if not data_stream_service.s3_service.dataset_exists(dataset):
            logger.error(f"Dataset not found: {dataset}")
            raise HTTPException(
                status_code=404, detail=f"Dataset '{dataset}' not found"
            )

        # Get response metadata
        filename = get_filename(dataset, extension)
        content_type = get_content_type(extension)

        # Stream data from service
        data_generator = data_stream_service.stream_data(
            dataset=dataset,
            extension=extension,
            organisation_entity=organisation_entity,
        )

        # Return streaming response
        return StreamingResponse(
            data_generator,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "public, max-age=3600",
                "X-Dataset": dataset,
                "X-Format": extension,
            },
        )

    except HTTPException:
        # Re-raise HTTPException as-is (already has correct status code)
        raise

    except FileNotFoundError as e:
        logger.error(f"Dataset not found: {dataset} - {e}")
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset}' not found")

    except ValueError as e:
        logger.error(f"Validation error for dataset {dataset}: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Unexpected error processing {dataset}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Internal server error while processing dataset"
        )
