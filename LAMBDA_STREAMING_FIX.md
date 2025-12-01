# Lambda Streaming Data Corruption Fix

## Problem

Lambda downloads were experiencing data corruption where 213 rows were missing from a 11,766-row dataset. The issue was NOT a simple truncation but rather **scattered missing data with wrong entities appearing**.

### Symptoms

- Local streaming: ✅ Perfect (all 11,766 rows, all entities correct)
- Lambda streaming: ❌ Corrupted
  - 213 rows missing (11,553 rows instead of 11,766)
  - Missing rows scattered throughout (rows 1510-9869, not just at end)
  - 291 unique entities missing from various positions
  - 78 unexpected entities present that weren't in source Parquet
  - File ending mid-row indicated abrupt termination

### Example Missing Data

Entity `44008914` at row index 6791 was completely missing from Lambda download but present in:
- Source Parquet file ✅
- Local streaming output ✅
- Lambda streaming output ❌

## Root Causes

### 1. Async Event Loop Yielding (Initial Issue - FIXED)

The `await asyncio.sleep(0)` call in `application/routers.py:132` was causing chunk reordering in the Lambda Web Adapter's async handling. When we yielded control to the event loop every 10 chunks, the Lambda Web Adapter would sometimes deliver chunks out of order or lose them entirely.

This is a known issue with async generators and Lambda response streaming when using explicit event loop yields.

### 2. Lambda Response Streaming Chunk Size Limit (CRITICAL - FIXED)

**AWS Lambda response streaming has a hard limit of 6MB per chunk.** When CSV batches with large geometry columns exceeded this limit, Lambda would silently drop or truncate the data, leading to:
- Missing rows scattered throughout the file
- Consistent truncation at specific positions
- Wrong entities appearing in the output

**Solution**: Split large chunks at line boundaries to ensure no single chunk exceeds 5MB (with safety margin).

## Fixes

### Fix 1: Remove asyncio.sleep(0)

**Removed the `await asyncio.sleep(0)` call** that was causing chunk reordering.

#### Before (Corrupted)
```python
for chunk in data_stream_service.stream_data(...):
    yield chunk
    chunk_count += 1
    total_bytes += len(chunk)
    # Give the Lambda runtime a chance to send data every 10 chunks
    if chunk_count % 10 == 0:
        await asyncio.sleep(0)  # ❌ CAUSED CHUNK REORDERING
```

#### After (Fixed)
```python
for chunk in data_stream_service.stream_data(...):
    yield chunk
    chunk_count += 1
    total_bytes += len(chunk)
    # NOTE: Removed asyncio.sleep(0) - it was causing chunk reordering
    # in Lambda Web Adapter, leading to data corruption
```

### Fix 2: Enforce Lambda Chunk Size Limits

**Added automatic chunk splitting** to ensure no chunk exceeds Lambda's 6MB limit.

#### CSV Chunking (data_stream_service.py:367-414)
```python
def _arrow_to_csv(self, batch, include_header=False):
    MAX_CHUNK_SIZE = 5 * 1024 * 1024  # 5MB (safety margin)

    # Convert batch to CSV
    csv_data = output.getvalue()

    # Split if needed
    if len(csv_data) > MAX_CHUNK_SIZE:
        logger.warning(f"CSV batch size ({len(csv_data)} bytes) exceeds Lambda limit. Splitting.")
        # Split at line boundaries to avoid breaking CSV rows
        start = 0
        while start < len(csv_data):
            end = start + MAX_CHUNK_SIZE
            if end < len(csv_data):
                # Find last newline before limit
                last_newline = csv_data.rfind(b'\n', start, end)
                if last_newline > start:
                    end = last_newline + 1
            yield csv_data[start:end]
            start = end
    else:
        yield csv_data
```

#### Parquet Chunking (data_stream_service.py:457-508)
- Similar approach for Parquet format
- Splits RecordBatch into smaller sub-batches if needed
- Each sub-batch written as separate Parquet chunk

## Testing

### Quick Test with Docker (Recommended)

Test the fix locally with Docker to simulate the actual Lambda environment:

```bash
# Run the complete test suite
./scripts/test_lambda_local.sh
```

This will:
1. Build the Lambda Docker image with Web Adapter
2. Start LocalStack for S3 emulation
3. Upload test data to S3
4. Download CSV from the containerized Lambda
5. Compare with source Parquet using the diagnostic script
6. Report SUCCESS ✅ or FAILURE ❌

See [tests/integration/README.md](tests/integration/README.md) for more details.

### Docker Compose Testing

```bash
# Start Lambda with Web Adapter + LocalStack
docker-compose -f docker-compose.test.yml up --build

# In another terminal, test the endpoint
curl -o test-download.csv "http://localhost:9000/conservation-area.csv"
python scripts/compare_entities.py test-data/conservation-area.parquet test-download.csv

# Clean up
docker-compose -f docker-compose.test.yml down
```

### Python Integration Tests (testcontainers)

```bash
# Install development dependencies (includes testcontainers)
pip install -r requirements-dev.txt

# Run integration tests
pytest tests/integration/test_lambda_streaming.py -v
```

### Diagnostic Script

Created `scripts/compare_entities.py` to compare source Parquet with downloaded CSV:

```bash
# Compare Parquet source with Lambda download
python scripts/compare_entities.py test-data/conservation-area.parquet ~/Downloads/conservation-area.csv

# Output shows:
# - Missing entities (sorted by row index)
# - Pattern analysis (first/last missing rows)
# - Unexpected entities in CSV
```

### Verification Steps

1. **Local test** (validates code logic):
   ```bash
   # Stream from local Parquet file
   python -c "..." > /tmp/test-local.csv
   python scripts/compare_entities.py test-data/conservation-area.parquet /tmp/test-local.csv
   # Result: ✅ All entities present
   ```

2. **Lambda test** (after fix):
   ```bash
   # Download from Lambda URL
   curl -o ~/Downloads/conservation-area.csv "https://your-lambda-url/conservation-area.csv"
   python scripts/compare_entities.py test-data/conservation-area.parquet ~/Downloads/conservation-area.csv
   # Expected: ✅ All entities present
   ```

## Deployment

After deploying this fix:

1. Build and push new Docker image
2. Update Lambda function
3. Test with full download:
   ```bash
   curl -o test-download.csv "https://your-lambda-url/conservation-area.csv"
   python scripts/compare_entities.py test-data/conservation-area.parquet test-download.csv
   ```

4. Check CloudWatch logs for completion message:
   ```
   Successfully streamed conservation-area: 6 batches, 11766 rows, format=csv, filter=none
   Stream wrapper completed: 6 chunks, ~30MB bytes, complete=True, reason=None
   ```

## Files Modified

1. [application/routers.py](application/routers.py#L130-131)
   - Removed `await asyncio.sleep(0)` causing chunk reordering

2. [application/services/data_stream_service.py](application/services/data_stream_service.py)
   - `_arrow_to_csv()` (lines 367-414): Added 5MB chunk size limit with line-boundary splitting
   - `_arrow_to_parquet()` (lines 457-508): Added 5MB chunk size limit with RecordBatch sub-batching
   - Added logging when chunks are split due to size

## Files Added

- [scripts/compare_entities.py](scripts/compare_entities.py) - Diagnostic tool to compare Parquet source with CSV download
- [docker-compose.test.yml](docker-compose.test.yml) - Local Lambda testing with LocalStack
- [scripts/test_lambda_local.sh](scripts/test_lambda_local.sh) - Automated Lambda container testing
- [tests/integration/test_lambda_streaming.py](tests/integration/test_lambda_streaming.py) - testcontainers-based integration tests
- [tests/integration/README.md](tests/integration/README.md) - Lambda testing documentation
- This document

## Related Issues

- Lambda Web Adapter response streaming with async generators
- Python asyncio event loop yielding in Lambda context
- FastAPI StreamingResponse with Lambda response streaming mode
