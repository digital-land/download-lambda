#!/usr/bin/env python3
"""
Helper script to count rows in CSV, JSON, or Parquet files.

Usage:
    python scripts/count_rows.py path/to/file.csv
    python scripts/count_rows.py path/to/file.json
    python scripts/count_rows.py path/to/file.parquet
"""

import sys
import json
from pathlib import Path


def count_csv_rows(filepath):
    """Count rows in CSV file (excluding header)."""
    with open(filepath, "r") as f:
        lines = f.readlines()

    # Filter out empty lines
    non_empty_lines = [line for line in lines if line.strip()]

    print("CSV Analysis:")
    print(f"  Total lines: {len(non_empty_lines)}")
    print("  Header line: 1")
    print(f"  Data rows: {len(non_empty_lines) - 1}")
    return len(non_empty_lines) - 1


def count_json_rows(filepath):
    """Count rows in JSON file."""
    with open(filepath, "r") as f:
        data = json.load(f)

    if isinstance(data, list):
        print("JSON Analysis:")
        print(f"  Array length: {len(data)}")
        print(f"  Data rows: {len(data)}")
        return len(data)
    else:
        print("JSON file is not an array - cannot count rows")
        return 0


def count_parquet_rows(filepath):
    """Count rows in Parquet file."""
    try:
        import pyarrow.parquet as pq
    except ImportError:
        print("Error: pyarrow not installed. Run: pip install pyarrow")
        return 0

    table = pq.read_table(filepath)
    print("Parquet Analysis:")
    print(f"  Total rows: {len(table)}")
    print(f"  Columns: {len(table.schema)}")
    return len(table)


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    filepath = Path(sys.argv[1])

    if not filepath.exists():
        print(f"Error: File not found: {filepath}")
        sys.exit(1)

    print(f"File: {filepath}")
    print(
        f"Size: {filepath.stat().st_size:,} bytes ({filepath.stat().st_size / 1024 / 1024:.2f} MB)"
    )
    print()

    suffix = filepath.suffix.lower()

    if suffix == ".csv":
        row_count = count_csv_rows(filepath)
    elif suffix == ".json":
        row_count = count_json_rows(filepath)
    elif suffix == ".parquet":
        row_count = count_parquet_rows(filepath)
    else:
        print(f"Error: Unsupported file type: {suffix}")
        sys.exit(1)

    print(f"\n✅ Total data rows: {row_count:,}")


if __name__ == "__main__":
    main()
