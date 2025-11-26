"""
FastAPI application for streaming dataset downloads.

This application runs inside AWS Lambda using the AWS Lambda Web Adapter,
which translates Lambda events to HTTP requests that FastAPI can handle.

The same application can run:
- In AWS Lambda with the Web Adapter layer
- Locally with uvicorn for development
- In Docker containers for other deployments
"""

import logging
import os
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from application.routers import router

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Download Lambda",
    description="Stream filtered dataset downloads from S3 Parquet files",
    version="2.0.0",
    docs_url="/docs" if os.getenv("ENVIRONMENT") == "development" else None,
    redoc_url="/redoc" if os.getenv("ENVIRONMENT") == "development" else None,
)

# Include API routes
app.include_router(router)


@app.get("/health")
async def health_check():
    """
    Health check endpoint for load balancers and monitoring.

    Returns:
        dict: Status information
    """
    return {"status": "healthy", "service": "download-lambda"}


@app.on_event("startup")
async def startup_event():
    """Validate configuration on application startup."""
    bucket = os.environ.get("DATASET_BUCKET")
    if not bucket:
        logger.error("DATASET_BUCKET environment variable not set")
        raise ValueError("DATASET_BUCKET must be configured")

    logger.info("Starting Download Lambda FastAPI application")
    logger.info(f"Dataset bucket: {bucket}")
    logger.info(f"Python version: {os.sys.version}")


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    Global exception handler for uncaught exceptions.

    Args:
        request: The request that caused the exception
        exc: The exception that was raised

    Returns:
        JSONResponse with error details
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if os.getenv("ENVIRONMENT") == "development" else None,
        },
    )
