#!/usr/bin/env python3
"""
Generate test Parquet data for local development.

Creates realistic test datasets that can be used to test the FastAPI application
with various filtering and output format options.

Run this script locally (not in Docker) to generate test data:
  python docker/localstack/generate_test_data.py
"""

import os
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime, timedelta
import random

# Output directory for test data
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "../test-data")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def generate_test_dataset():
    """Generate a basic test dataset with organisation filtering."""
    print("  Generating test-dataset.parquet...")

    # Generate data
    ids = list(range(1, 101))
    org_entities = [f"org-{(i % 5) + 1}" for i in range(100)]
    names = [f"Record {i}" for i in range(1, 101)]
    statuses = [random.choice(["active", "inactive", "pending"]) for _ in range(100)]
    values = [round(random.uniform(100, 10000), 2) for _ in range(100)]
    created_ats = [
        (datetime.now() - timedelta(days=random.randint(0, 365))).isoformat()
        for _ in range(100)
    ]

    # Create PyArrow table
    table = pa.table(
        {
            "id": pa.array(ids, type=pa.int64()),
            "organisation-entity": pa.array(org_entities, type=pa.string()),
            "name": pa.array(names, type=pa.string()),
            "status": pa.array(statuses, type=pa.string()),
            "value": pa.array(values, type=pa.float64()),
            "created_at": pa.array(created_ats, type=pa.string()),
        }
    )

    output_path = os.path.join(OUTPUT_DIR, "test-dataset.parquet")
    pq.write_table(table, output_path)

    print(f"    Created {len(table)} rows")
    print(f"    Organisations: {sorted(set(org_entities))}")
    print(f"    Saved to: {output_path}")


def generate_sales_data():
    """Generate sales data with multiple organisations."""
    print("  Generating sales-data.parquet...")

    products = ["Widget A", "Widget B", "Widget C", "Gadget X", "Gadget Y"]
    regions = ["North", "South", "East", "West"]

    # Generate data
    sale_ids = list(range(1, 201))
    org_entities = [f"org-{(i % 10) + 1}" for i in range(200)]
    product_list = [random.choice(products) for _ in range(200)]
    region_list = [random.choice(regions) for _ in range(200)]
    quantities = [random.randint(1, 100) for _ in range(200)]
    unit_prices = [round(random.uniform(10, 500), 2) for _ in range(200)]
    total_amounts = [
        round(qty * price, 2) for qty, price in zip(quantities, unit_prices)
    ]
    sale_dates = [
        (datetime.now() - timedelta(days=random.randint(0, 90))).isoformat()
        for _ in range(200)
    ]

    # Create PyArrow table
    table = pa.table(
        {
            "sale_id": pa.array(sale_ids, type=pa.int64()),
            "organisation-entity": pa.array(org_entities, type=pa.string()),
            "product": pa.array(product_list, type=pa.string()),
            "region": pa.array(region_list, type=pa.string()),
            "quantity": pa.array(quantities, type=pa.int64()),
            "unit_price": pa.array(unit_prices, type=pa.float64()),
            "total_amount": pa.array(total_amounts, type=pa.float64()),
            "sale_date": pa.array(sale_dates, type=pa.string()),
        }
    )

    output_path = os.path.join(OUTPUT_DIR, "sales-data.parquet")
    pq.write_table(table, output_path)

    print(f"    Created {len(table)} rows")
    print(f"    Organisations: {sorted(set(org_entities))}")
    print(f"    Total sales value: ${sum(total_amounts):,.2f}")
    print(f"    Saved to: {output_path}")


if __name__ == "__main__":
    print("Generating test Parquet files...")
    print()

    generate_test_dataset()
    print()
    generate_sales_data()
    print()

    print("✓ All test data generated successfully")
    print()
    print("Next steps:")
    print("  1. Restart LocalStack: make dev-restart")
    print("  2. The data will be automatically uploaded to S3")
