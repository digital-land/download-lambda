# Test Data

This directory contains test Parquet files for development and testing.

## Files

- `conservation-area.parquet` - Real dataset from planning.data.gov.uk (11,766 rows)
  - Source: https://files.planning.data.gov.uk/dataset/conservation-area.parquet
  - Used for testing CSV/JSON/Parquet conversion accuracy

## Usage

Test row count accuracy:
```bash
python scripts/count_rows.py test-data/conservation-area.parquet
```

Expected output: **11,766 rows**
