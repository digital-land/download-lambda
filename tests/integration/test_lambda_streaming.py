# """
# Integration tests for Lambda streaming with Web Adapter.

# These tests use testcontainers to spin up the actual Lambda container
# with the Web Adapter in front, simulating the real Lambda environment.

# Requirements:
#     pip install testcontainers pytest requests pyarrow

# Usage:
#     pytest tests/integration/test_lambda_streaming.py -v
# """

# import csv
# import time
# import pytest
# import requests
# from pathlib import Path
# from testcontainers.core.container import DockerContainer


# @pytest.fixture(scope="module")
# def localstack_container():
#     """Start LocalStack container for S3 emulation."""
#     with DockerContainer("localstack/localstack:latest") as container:
#         container.with_exposed_ports(4566)
#         container.with_env("SERVICES", "s3")
#         container.with_env("DEBUG", "1")
#         container.with_volume_mapping(
#             str(Path(__file__).parent.parent.parent / "test-data"),
#             "/test-data",
#             mode="ro"
#         )
#         container.start()

#         # Wait for LocalStack to be ready by polling health endpoint
#         endpoint_url = f"http://localhost:{container.get_exposed_port(4566)}"
#         for _ in range(30):
#             try:
#                 response = requests.get(f"{endpoint_url}/_localstack/health", timeout=1)
#                 if response.status_code == 200:
#                     break
#             except requests.exceptions.RequestException:
#                 pass
#             time.sleep(1)

#         time.sleep(2)  # Additional wait for S3 service

#         # Setup S3 bucket and upload test data
#         setup_s3(endpoint_url)

#         yield {
#             "endpoint_url": endpoint_url,
#             "container": container
#         }


# def setup_s3(endpoint_url):
#     """Create S3 bucket and upload test data."""
#     import boto3

#     s3_client = boto3.client(
#         's3',
#         endpoint_url=endpoint_url,
#         aws_access_key_id='test',
#         aws_secret_access_key='test',
#         region_name='us-east-1'
#     )

#     # Create bucket
#     s3_client.create_bucket(Bucket='test-bucket')

#     # Upload test Parquet file
#     test_data_dir = Path(__file__).parent.parent.parent / "test-data"
#     parquet_file = test_data_dir / "conservation-area.parquet"

#     if parquet_file.exists():
#         s3_client.upload_file(
#             str(parquet_file),
#             'test-bucket',
#             'dataset/conservation-area.parquet'
#         )
#         print(f"✅ Uploaded test data to S3: {parquet_file}")
#     else:
#         pytest.skip(f"Test data not found: {parquet_file}")


# @pytest.fixture(scope="module")
# def lambda_container(localstack_container):
#     """Start Lambda container with Web Adapter."""
#     # Build the Docker image if it doesn't exist
#     repo_root = Path(__file__).parent.parent.parent

#     import docker

#     try:
#         docker_client = docker.from_env()
#     except docker.errors.DockerException as e:
#         pytest.fail(f"Docker is not available: {e}")

#     # Check if image exists, if not build it
#     try:
#         docker_client.images.get("download-lambda:test")
#         print("✅ Using existing download-lambda:test image")
#     except docker.errors.ImageNotFound:
#         print("🐳 Building download-lambda:test image...")
#         try:
#             docker_client.images.build(
#                 path=str(repo_root),
#                 dockerfile="Dockerfile",
#                 tag="download-lambda:test",
#                 platform="linux/amd64",
#                 rm=True
#             )
#             print("✅ Image built successfully")
#         except docker.errors.BuildError as e:
#             # Print build logs for debugging
#             print("\n❌ Docker build failed!")
#             for log in e.build_log:
#                 if 'stream' in log:
#                     print(log['stream'].strip())
#             pytest.fail(f"Failed to build Docker image: {e}")
#         except Exception as e:
#             pytest.fail(f"Unexpected error building Docker image: {e}")

#     with DockerContainer("download-lambda:test") as container:
#         # Get the LocalStack container's network info
#         # Use the container's internal IP instead of host.docker.internal
#         localstack_docker_container = localstack_container['container']

#         # Connect to the same network
#         import docker
#         docker_client = docker.from_env()
#         localstack_info = docker_client.api.inspect_container(localstack_docker_container.get_wrapped_container().id)
#         localstack_ip = localstack_info['NetworkSettings']['IPAddress']

#         print(f"🔗 Connecting Lambda container to LocalStack at {localstack_ip}:4566")

#         # Set container to use the built image
#         container.with_env("DATASET_BUCKET", "test-bucket")
#         container.with_env("AWS_REGION", "us-east-1")
#         container.with_env("S3_ENDPOINT_URL", f"http://{localstack_ip}:4566")
#         container.with_env("S3_USE_SSL", "false")
#         container.with_env("AWS_ACCESS_KEY_ID", "test")
#         container.with_env("AWS_SECRET_ACCESS_KEY", "test")
#         container.with_env("DUCKDB_MEMORY_LIMIT", "256MB")

#         # Lambda Web Adapter is already configured in Dockerfile
#         container.with_exposed_ports(8000)  # Application port
#         container.with_command("/lambda-entrypoint.sh")

#         container.start()

#         # Wait for container to be ready
#         time.sleep(5)

#         base_url = f"http://localhost:{container.get_exposed_port(8000)}"

#         # Wait for health endpoint
#         for _ in range(30):
#             try:
#                 response = requests.get(f"{base_url}/health", timeout=5)
#                 if response.status_code == 200:
#                     break
#             except requests.exceptions.RequestException:
#                 pass
#             time.sleep(1)

#         yield {
#             "base_url": base_url,
#             "container": container
#         }


# def get_parquet_entities(parquet_path):
#     """Get all entity values from Parquet file."""
#     import pyarrow.parquet as pq

#     table = pq.read_table(parquet_path)
#     return table.column('entity').to_pylist()


# def get_csv_entities(csv_path):
#     """Get all entity values from CSV file."""
#     entities = []

#     # Increase field size limit for large geometry fields
#     csv.field_size_limit(10 * 1024 * 1024)

#     with open(csv_path, 'r') as f:
#         reader = csv.DictReader(f)
#         for row in reader:
#             entities.append(int(row['entity']))

#     return entities


# @pytest.mark.integration
# def test_lambda_csv_streaming_completeness(lambda_container, tmp_path):
#     """Test that Lambda streaming returns all rows without corruption."""
#     # Download CSV from Lambda
#     response = requests.get(
#         f"{lambda_container['base_url']}/conservation-area.csv",
#         stream=True,
#         timeout=60
#     )

#     assert response.status_code == 200, f"Expected 200, got {response.status_code}"

#     # Save to temporary file
#     output_file = tmp_path / "lambda-download.csv"
#     with open(output_file, 'wb') as f:
#         for chunk in response.iter_content(chunk_size=8192):
#             f.write(chunk)

#     # Compare entities with source Parquet
#     parquet_path = Path(__file__).parent.parent.parent / "test-data" / "conservation-area.parquet"

#     parquet_entities = get_parquet_entities(parquet_path)
#     csv_entities = get_csv_entities(output_file)

#     # Check counts
#     assert len(csv_entities) == len(parquet_entities), \
#         f"Row count mismatch: CSV has {len(csv_entities)}, Parquet has {len(parquet_entities)}"

#     # Check for missing entities
#     parquet_set = set(parquet_entities)
#     csv_set = set(csv_entities)
#     missing = parquet_set - csv_set

#     assert len(missing) == 0, \
#         f"Missing {len(missing)} entities from CSV. First 10: {list(missing)[:10]}"

#     # Check for unexpected entities
#     extra = csv_set - parquet_set
#     assert len(extra) == 0, \
#         f"Found {len(extra)} unexpected entities in CSV. First 10: {list(extra)[:10]}"

#     print(f"✅ All {len(csv_entities)} entities present and correct")


# @pytest.mark.integration
# def test_lambda_csv_specific_entity(lambda_container):
#     """Test that specific problematic entity (44008914) is present."""
#     # Download CSV from Lambda
#     response = requests.get(
#         f"{lambda_container['base_url']}/conservation-area.csv",
#         stream=True,
#         timeout=60
#     )

#     assert response.status_code == 200

#     # Stream and check for entity 44008914
#     found = False
#     for line in response.iter_lines(decode_unicode=True):
#         if '44008914' in line:
#             found = True
#             print(f"✅ Found entity 44008914 in response")
#             break

#     assert found, "Entity 44008914 not found in Lambda response"


# @pytest.mark.integration
# def test_lambda_json_streaming(lambda_container, tmp_path):
#     """Test JSON streaming returns complete data."""
#     response = requests.get(
#         f"{lambda_container['base_url']}/conservation-area.json",
#         stream=True,
#         timeout=60
#     )

#     assert response.status_code == 200
#     assert response.headers['Content-Type'] == 'application/json'

#     # Save to file
#     output_file = tmp_path / "lambda-download.json"
#     with open(output_file, 'wb') as f:
#         for chunk in response.iter_content(chunk_size=8192):
#             f.write(chunk)

#     # Parse JSON and check count
#     import json
#     with open(output_file, 'r') as f:
#         data = json.load(f)

#     assert isinstance(data, list), "JSON should be an array"

#     # Compare with Parquet
#     parquet_path = Path(__file__).parent.parent.parent / "test-data" / "conservation-area.parquet"
#     parquet_entities = get_parquet_entities(parquet_path)

#     assert len(data) == len(parquet_entities), \
#         f"Row count mismatch: JSON has {len(data)}, Parquet has {len(parquet_entities)}"

#     print(f"✅ JSON streaming returned all {len(data)} rows")


# @pytest.mark.integration
# def test_lambda_response_headers(lambda_container):
#     """Test that response headers are correct."""
#     response = requests.get(
#         f"{lambda_container['base_url']}/conservation-area.csv",
#         stream=True,
#         timeout=60
#     )

#     assert response.status_code == 200
#     assert 'Content-Disposition' in response.headers
#     assert 'conservation-area.csv' in response.headers['Content-Disposition']
#     assert response.headers.get('X-Dataset') == 'conservation-area'
#     assert response.headers.get('X-Format') == 'csv'

#     print("✅ Response headers correct")


# @pytest.mark.integration
# def test_lambda_filtered_streaming(lambda_container):
#     """Test streaming with organisation-entity filter."""
#     # First, get a valid organisation entity from the data
#     parquet_path = Path(__file__).parent.parent.parent / "test-data" / "conservation-area.parquet"
#     import pyarrow.parquet as pq
#     table = pq.read_table(parquet_path)

#     # Get first non-null organisation-entity
#     org_entities = table.column('organisation-entity').to_pylist()
#     test_org = next((org for org in org_entities if org is not None), None)

#     if test_org is None:
#         pytest.skip("No organisation-entity values in test data")

#     # Request with filter
#     response = requests.get(
#         f"{lambda_container['base_url']}/conservation-area.csv",
#         params={"organisation-entity": test_org},
#         stream=True,
#         timeout=60
#     )

#     assert response.status_code == 200

#     # Count rows (should be less than total)
#     row_count = sum(1 for _ in response.iter_lines(decode_unicode=True)) - 1  # Exclude header

#     total_rows = len(org_entities)
#     assert row_count < total_rows, "Filtered result should have fewer rows"
#     assert row_count > 0, "Filtered result should have at least one row"

#     print(f"✅ Filtered streaming returned {row_count} rows (total: {total_rows})")


# if __name__ == "__main__":
#     # Allow running directly with: python -m pytest tests/integration/test_lambda_streaming.py -v
#     pytest.main([__file__, "-v", "-s"])
