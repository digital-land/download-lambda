#!/usr/bin/env python3
"""
Compare entities between Parquet source and CSV download to find missing rows.

Usage:
    python scripts/compare_entities.py test-data/conservation-area.parquet ~/Downloads/conservation-area.csv
"""

import sys
import csv
from pathlib import Path


def get_parquet_entities(parquet_path):
    """Get all entity values from Parquet file."""
    try:
        import pyarrow.parquet as pq
    except ImportError:
        print("Error: pyarrow not installed. Run: pip install pyarrow")
        sys.exit(1)

    table = pq.read_table(parquet_path)
    entities = table.column("entity").to_pylist()
    return entities


def get_csv_entities(csv_path):
    """Get all entity values from CSV file."""
    entities = []

    # Increase field size limit for large geometry fields
    csv.field_size_limit(10 * 1024 * 1024)  # 10MB

    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entities.append(int(row["entity"]))

    return entities


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)

    parquet_path = Path(sys.argv[1])
    csv_path = Path(sys.argv[2])

    if not parquet_path.exists():
        print(f"Error: Parquet file not found: {parquet_path}")
        sys.exit(1)

    if not csv_path.exists():
        print(f"Error: CSV file not found: {csv_path}")
        sys.exit(1)

    print("Comparing:")
    print(f"  Parquet: {parquet_path}")
    print(f"  CSV:     {csv_path}")
    print()

    # Get entities from both files
    print("Reading Parquet entities...")
    parquet_entities = get_parquet_entities(parquet_path)
    print(f"  Found {len(parquet_entities)} entities")

    print("Reading CSV entities...")
    csv_entities = get_csv_entities(csv_path)
    print(f"  Found {len(csv_entities)} entities")
    print()

    # Find missing entities
    parquet_set = set(parquet_entities)
    csv_set = set(csv_entities)
    missing = parquet_set - csv_set

    if missing:
        print(f"❌ {len(missing)} unique entities missing from CSV:")
        missing_with_indices = []
        for entity in missing:
            # Find all indices where this entity appears in parquet
            indices = [i for i, e in enumerate(parquet_entities) if e == entity]
            for idx in indices:
                missing_with_indices.append((idx, entity))

        # Sort by index
        missing_with_indices.sort()

        print("\nMissing entities (sorted by row index):")
        for idx, entity in missing_with_indices[:20]:  # Show first 20
            print(f"  Row {idx}: entity={entity}")

        if len(missing_with_indices) > 20:
            print(f"  ... and {len(missing_with_indices) - 20} more")

        # Analyze pattern
        print("\nPattern analysis:")
        print(f"  First missing row: {missing_with_indices[0][0]}")
        print(f"  Last missing row:  {missing_with_indices[-1][0]}")
        print(f"  Total parquet rows: {len(parquet_entities)}")
        print(f"  Total CSV rows: {len(csv_entities)}")
        print(f"  Missing rows: {len(parquet_entities) - len(csv_entities)}")

    else:
        print("✅ All entities present in CSV")

    # Check for extra entities in CSV (shouldn't happen)
    extra = csv_set - parquet_set
    if extra:
        print(f"\n⚠️  {len(extra)} unexpected entities in CSV (not in Parquet):")
        for entity in list(extra)[:10]:
            print(f"  {entity}")


if __name__ == "__main__":
    main()
