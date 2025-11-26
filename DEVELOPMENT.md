# Local Development Guide

This guide explains how to develop and test the FastAPI application locally using Docker Compose with LocalStack.

## Overview

The local development stack includes:
- **LocalStack** - Mock AWS services (S3) for local testing
- **FastAPI Application** - Your application with hot-reload enabled
- **Test Data** - Automatically generated Parquet files in S3

## Prerequisites

- Docker Desktop (or Docker + Docker Compose)
- Make (optional, for convenient commands)

## Quick Start

### 1. Start the Development Environment

```bash
# Start all services
docker-compose up

# Or run in background
docker-compose up -d

# View logs
docker-compose logs -f app
```

This will:
1. Start LocalStack with S3
2. Create a `test-datasets` bucket
3. Generate and upload 3 test Parquet files
4. Start the FastAPI application on http://localhost:8000

### 2. Test the API

```bash
# Health check
curl http://localhost:8000/health

# API documentation (interactive)
open http://localhost:8000/docs

# Download test dataset as CSV
curl http://localhost:8000/test-dataset.csv

# Download with filtering
curl "http://localhost:8000/test-dataset.csv?organisation-entity=org-1"

# Download as JSON
curl http://localhost:8000/sales-data.json
```
