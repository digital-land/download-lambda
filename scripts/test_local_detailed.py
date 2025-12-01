#!/usr/bin/env python3
"""Test local streaming with detailed logging."""
from application.services.s3_service import S3Service
from application.services.data_stream_service import DataStreamService


# Override S3 service to use local file
class LocalS3Service(S3Service):
    def get_s3_uri(self, dataset):
        return "test-data/conservation-area.parquet"

    def dataset_exists(self, dataset):
        return True

    def get_credentials(self):
        return None


s3_service = LocalS3Service("test-bucket", "local")
stream_service = DataStreamService(s3_service)

# Count chunks and bytes
print("Starting local streaming test...")
chunk_count = 0
total_bytes = 0
lines = 0

with open("/tmp/test-local-detailed.csv", "wb") as f:
    for chunk in stream_service.stream_data("conservation-area", "csv"):
        chunk_count += 1
        total_bytes += len(chunk)
        lines += chunk.count(b"\n")
        f.write(chunk)

print("\nSummary:")
print(f"  Total chunks: {chunk_count}")
print(f"  Total bytes: {total_bytes}")
print(f"  Total lines (including header): {lines}")
print(f"  Data rows: {lines - 1}")
print("\nFile written to: /tmp/test-local-detailed.csv")
