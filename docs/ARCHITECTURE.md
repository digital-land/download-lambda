# Architecture Documentation

## Overview

This Lambda function provides a scalable, secure solution for streaming filtered dataset downloads from S3 Parquet files. It's designed to work with CloudFront CDN or Lambda Function URLs for optimal performance.

## Architecture Diagram

```
┌─────────────┐
│   Client    │
│  (Browser)  │
└──────┬──────┘
       │ HTTPS GET /{dataset}.{ext}?organisation-entity={value}
       ▼
┌─────────────────┐
│   CloudFront    │◄──── Optional: CDN caching, custom domain
│  Distribution   │      Benefits: Global edge locations, DDoS protection
└────────┬────────┘
         │
         ▼
┌──────────────────────┐
│  Lambda Function URL │◄──── AWS_IAM authentication
│  or Lambda@Edge      │      Response streaming support
└──────────┬───────────┘
           │
    ┌──────┴──────┐
    │             │
    ▼             ▼
┌─────────┐   ┌────────────────┐
│ Lambda  │   │  CloudWatch    │
│Function │──►│     Logs       │
└────┬────┘   └────────────────┘
     │
     │ Read Parquet
     ▼
┌──────────────┐
│  S3 Bucket   │
│   Parquet    │
│   Datasets   │
└──────────────┘
```

## Component Details

### 1. Client Request

**Supported Formats:**
```
GET /{dataset}.csv                                    # Full dataset
GET /{dataset}.json?organisation-entity=acme-corp    # Filtered JSON
GET /{dataset}.parquet?organisation-entity=org-1     # Filtered Parquet
```

**Request Flow:**
1. Client makes HTTPS GET request
2. Path and query parameters are extracted
3. Parameters validated using Pydantic models
4. Request routed to Lambda function

### 2. CloudFront Distribution (Optional)

**Purpose:**
- Global content delivery
- Caching for repeated requests
- Custom domain names
- SSL/TLS termination
- DDoS protection

**Cache Behavior:**
- Cache based on query string parameters
- Different cache policies per file format
- Origin request policies for headers

**Configuration:**
```yaml
Origin: Lambda Function URL
Protocol: HTTPS only
Cache Policy: Custom (based on query strings)
Origin Request Policy: Include query strings
TTL: 3600 seconds (adjustable)
```

### 3. Lambda Function

**Runtime:** Python 3.11

**Memory:** 512MB (configurable)

**Timeout:** 60 seconds (configurable)

**Layers:**
- Core Python libraries (boto3, pandas, pyarrow)
- Pydantic for validation

**Environment Variables:**
- `DATASET_BUCKET`: S3 bucket name (required)

**Execution Flow:**

```python
1. Receive event (CloudFront or Function URL)
   ↓
2. Parse request using utils.parse_cloudfront_request()
   ↓
3. Validate parameters with Pydantic models
   ↓
4. Initialize DataProcessor with S3 bucket
   ↓
5. Stream data in chunks:
   - Read Parquet file from S3
   - Apply filters (if specified)
   - Convert to requested format
   - Yield chunks to client
   ↓
6. Return streaming or buffered response
```

### 4. S3 Bucket

**Structure:**
```
s3://datasets-bucket/
├── dataset1.parquet
├── dataset2.parquet
├── customers.parquet
└── transactions.parquet
```

**Security:**
- Server-side encryption (AES256)
- Versioning enabled
- Public access blocked
- Lambda read-only access via IAM role

**Lifecycle Policies:**
- Delete old versions after 90 days
- Transition to Glacier for archival (optional)

## Data Flow

### CSV Export Flow

```
S3 Parquet File
    ↓
PyArrow reads in batches (10,000 rows)
    ↓
Convert to Pandas DataFrame
    ↓
Apply filter: df[df['organisation-entity'] == value]
    ↓
Convert to CSV string
    ↓
Yield as bytes chunk
    ↓
Stream to client
```

### JSON Export Flow

```
S3 Parquet File
    ↓
PyArrow reads in batches
    ↓
Convert to Pandas DataFrame
    ↓
Apply filter
    ↓
Convert to dict records
    ↓
Serialize to JSON (with proper array formatting)
    ↓
Stream to client
```

### Parquet Export Flow

```
S3 Parquet File
    ↓
PyArrow reads in batches
    ↓
Convert to Pandas DataFrame
    ↓
Apply filter
    ↓
Write filtered data as Parquet
    ↓
Stream binary data to client
```

## Security Architecture

### Authentication & Authorization

**Lambda Function URL:**
- AWS_IAM authentication required
- IAM policy controls access
- SigV4 signed requests

**CloudFront:**
- Origin Access Identity (OAI) for Lambda@Edge
- AWS WAF for request filtering (optional)
- Geo-restriction capabilities

### Input Validation

**Path Parameters:**
```python
dataset: str
- Length: 1-100 characters
- No path traversal: ../, /, \
- Alphanumeric and hyphens only

extension: Literal["csv", "json", "parquet"]
- Validated against allowed formats only
```

**Query Parameters:**
```python
organisation-entity: Optional[str]
- Validated for SQL injection patterns
- Sanitized before filtering
```

### Data Security

1. **Encryption in Transit:**
   - TLS 1.2+ for all connections
   - CloudFront to Lambda: HTTPS
   - Lambda to S3: HTTPS

2. **Encryption at Rest:**
   - S3 server-side encryption
   - CloudWatch Logs encryption

3. **IAM Permissions:**
```json
{
  "Effect": "Allow",
  "Action": [
    "s3:GetObject",
    "s3:ListBucket"
  ],
  "Resource": [
    "arn:aws:s3:::datasets-bucket",
    "arn:aws:s3:::datasets-bucket/*"
  ]
}
```

## Performance Optimization

### Memory Management

**Chunk Processing:**
- Default: 10,000 rows per chunk
- Adjustable based on dataset size
- Prevents memory exhaustion

**Stream Processing:**
```python
# Generator pattern for memory efficiency
for batch in parquet_file.iter_batches(batch_size=10000):
    df = batch.to_pandas()
    # Process and yield
```

### Response Streaming

**Benefits:**
- Lower latency for first byte
- Reduced Lambda memory usage
- Support for large files (>6MB)

**Implementation:**
```python
# Lambda Function URL with RESPONSE_STREAM
InvokeMode: RESPONSE_STREAM
```

### Caching Strategy

**CloudFront Cache:**
- Static datasets: Long TTL (3600s+)
- Dynamic filtered results: Short TTL (300s)
- Cache key includes query parameters

**Lambda Performance:**
- Global DataProcessor initialization
- Reuse S3 client connections
- PyArrow for efficient Parquet reading

## Scalability

### Horizontal Scaling

**Lambda Concurrency:**
- Default: 1,000 concurrent executions
- Reserved concurrency (optional)
- Auto-scales based on demand

**CloudFront:**
- Automatic edge location scaling
- No capacity planning needed

### Vertical Scaling

**Lambda Memory:**
```yaml
512MB:  Good for datasets < 100MB
1024MB: Good for datasets < 500MB
2048MB: Good for datasets < 2GB
```

**Processing Optimization:**
- Parallel batch processing
- Columnar filtering with PyArrow
- Predicate pushdown (future enhancement)

## Monitoring & Observability

### CloudWatch Metrics

**Lambda Metrics:**
- Invocations
- Duration
- Errors
- Throttles
- Concurrent Executions

**Custom Metrics:**
```python
logger.info(f"Processing {dataset} format={format} filter={filter}")
logger.info(f"Dataset {dataset} rows_processed={count}")
```

### CloudWatch Logs

**Log Groups:**
```
/aws/lambda/download-lambda-stack-DownloadFunction
```

**Log Format:**
```
[INFO] Received event: {...}
[INFO] Parsed request: dataset=customers, format=csv, filter=org-1
[INFO] Streaming customers.parquet from datasets-bucket as csv
[INFO] Successfully streamed customers.parquet
```

### Alarms

**Recommended CloudWatch Alarms:**
1. Error rate > 5%
2. Duration > 50 seconds
3. Throttles > 0
4. 5xx errors from CloudFront

## Cost Optimization

### Lambda Costs

**Factors:**
- Execution time
- Memory allocation
- Number of requests

**Optimization:**
- Right-size memory (512MB vs 1024MB)
- Enable response streaming
- Cache frequently accessed datasets

### S3 Costs

**Factors:**
- Storage (per GB)
- GET requests
- Data transfer out

**Optimization:**
- Use S3 Intelligent-Tiering
- Enable versioning with lifecycle rules
- Compress Parquet files

### CloudFront Costs

**Factors:**
- Data transfer out
- HTTPS requests

**Benefits:**
- Reduces Lambda invocations
- Reduces S3 GET requests
- Lower cost per request than Lambda

**Cost Example:**
```
1 million requests/month:
- Without CloudFront: $X Lambda + $Y S3
- With CloudFront (80% cache hit): $Z CloudFront + $0.2X Lambda + $0.2Y S3
- Savings: ~60-70%
```

## Deployment Strategies

### Blue/Green Deployment

```yaml
AutoPublishAlias: live
DeploymentPreference:
  Type: Canary10Percent5Minutes
  Alarms:
    - !Ref ErrorAlarm
```

### Multi-Region

Deploy to multiple regions for disaster recovery:

```bash
sam deploy --region us-east-1
sam deploy --region eu-west-1
```

Configure Route 53 for failover.

### Environment Separation

```
dev-download-lambda-stack
staging-download-lambda-stack
prod-download-lambda-stack
```

Each with separate S3 buckets and configurations.

## Future Enhancements

1. **Query Language Support**
   - SQL-like filtering
   - Complex predicates
   - Column selection

2. **Authentication**
   - API Gateway with Cognito
   - Custom authorizers
   - Rate limiting

3. **Format Extensions**
   - Excel (XLSX)
   - XML
   - Avro

4. **Performance**
   - DuckDB for SQL queries
   - Parquet metadata for stats
   - Predicate pushdown

5. **Features**
   - Pagination
   - Sorting
   - Aggregations
   - Multiple filters
