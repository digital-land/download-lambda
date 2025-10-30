# Testing Guide

This project follows the [Digital Land testing guidance](https://digital-land.github.io/technical-documentation/development/testing-guidance/) with a clear separation between unit, integration, and acceptance tests.

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── unit/                    # Fast, isolated tests with no external dependencies
│   ├── test_models.py       # Pydantic model validation
│   ├── test_utils.py        # Utility function tests
│   └── test_data_processor.py  # Data processing logic
├── integration/             # Tests with mocked AWS dependencies
│   └── test_lambda_handler.py  # Lambda handler with S3 integration
└── acceptance/              # End-to-end user scenarios
    └── test_user_download_scenarios.py  # User stories and acceptance criteria
```

## Test Types

### Unit Tests
**Purpose:** Test the smallest piece of code in isolation

**Characteristics:**
- Fast execution (< 1 second per test)
- No external dependencies (no S3, no network)
- Mock all external interactions
- Focus on logic and validation

**Example:**
```python
def test_path_params_with_valid_csv_extension():
    """Test creating PathParams with valid CSV extension."""
    params = PathParams(dataset="customers", extension="csv")
    assert params.dataset == "customers"
    assert params.extension == "csv"
```

**Run unit tests only:**
```bash
pytest tests/unit/ -v
```

### Integration Tests
**Purpose:** Test components working together with mocked AWS services

**Characteristics:**
- Test complete workflows
- Use moto to mock AWS services (S3)
- Verify component interactions
- Slower than unit tests (1-5 seconds per test)

**Example:**
```python
def test_handler_returns_csv_data(mock_env_vars, s3_bucket_with_data):
    """Test handler returns CSV data for Function URL event."""
    event = lambda_function_url_event_factory(path="/test-dataset.csv")
    response = lambda_handler(event, None)

    assert response["statusCode"] == 200
    assert "text/csv" in response["headers"]["Content-Type"]
```

**Run integration tests only:**
```bash
pytest tests/integration/ -v
```

### Acceptance Tests
**Purpose:** Verify end-to-end user stories and acceptance criteria

**Characteristics:**
- Test from user perspective
- Verify complete user workflows
- Include user story documentation
- Test acceptance criteria explicitly

**Example:**
```python
def test_user_downloads_dataset_in_csv_format():
    """
    User Story: Download dataset as CSV

    AS A data analyst
    I WANT TO download a dataset as CSV
    SO THAT I can open it in Excel

    GIVEN a dataset exists in S3
    WHEN a user requests it in CSV format
    THEN they receive a valid CSV file
    """
```

**Run acceptance tests only:**
```bash
pytest tests/acceptance/ -v
```

## Running Tests

### Run All Tests
```bash
make test
```

Or directly with pytest:
```bash
pytest
```

### Run Specific Test Types
```bash
# Unit tests only (fast)
pytest tests/unit/

# Integration tests
pytest tests/integration/

# Acceptance tests
pytest tests/acceptance/
```

### Run Specific Test File
```bash
pytest tests/unit/test_models.py -v
```

### Run Specific Test
```bash
pytest tests/unit/test_models.py::TestPathParams::test_valid_path_params_csv -v
```

### Run Tests Matching Pattern
```bash
# All tests with "filter" in the name
pytest -k filter

# All tests for CSV functionality
pytest -k csv
```

### Run with Coverage
```bash
pytest --cov=src --cov-report=html
```

View coverage report:
```bash
open htmlcov/index.html
```

## Test Markers

Tests can be marked for categorization:

```python
@pytest.mark.unit
def test_something():
    pass

@pytest.mark.integration
def test_with_s3():
    pass

@pytest.mark.slow
def test_large_dataset():
    pass

@pytest.mark.security
def test_path_traversal_blocked():
    pass
```

Run tests by marker:
```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Skip slow tests
pytest -m "not slow"

# Run security tests
pytest -m security
```

## Fixtures

### Shared Fixtures (conftest.py)

**Data Fixtures:**
- `sample_dataframe` - DataFrame with test data
- `sample_parquet_bytes` - Parquet file as bytes

**AWS Fixtures:**
- `aws_credentials` - Mock AWS credentials
- `s3_mock` - Mocked S3 client using moto
- `s3_bucket_with_data` - S3 bucket with sample datasets

**Event Fixtures:**
- `lambda_function_url_event` - Sample Function URL event
- `cloudfront_event` - Sample CloudFront event
- `lambda_function_url_event_factory` - Factory for custom events

**Environment Fixtures:**
- `mock_env_vars` - Mock environment variables

### Using Fixtures

```python
def test_with_s3_data(s3_bucket_with_data, lambda_function_url_event_factory):
    """Test using S3 bucket and event factory fixtures."""
    event = lambda_function_url_event_factory(path="/test-dataset.csv")
    # S3 bucket already contains test data
    response = lambda_handler(event, None)
    assert response["statusCode"] == 200
```

## Writing Tests

### Test Naming Convention

Follow the pattern: `test_<function_name>_<behavior>`

**Good examples:**
- `test_parse_path_with_csv_extension`
- `test_handler_returns_404_for_nonexistent_dataset`
- `test_user_filters_dataset_and_receives_only_matching_records`

**Bad examples:**
- `test_1` (not descriptive)
- `test_parse_path` (missing behavior)
- `testParsePathCSV` (not snake_case)

### Test Structure

Use the AAA pattern: Arrange, Act, Assert

```python
def test_parse_path_with_csv_extension():
    """Test parsing path with CSV extension."""
    # Arrange
    path = "/test-dataset.csv"

    # Act
    dataset, extension = _parse_path(path)

    # Assert
    assert dataset == "test-dataset"
    assert extension == "csv"
```

For acceptance tests, use Given/When/Then:

```python
def test_user_downloads_csv():
    """
    GIVEN a dataset exists in S3
    WHEN a user requests it as CSV
    THEN they receive a valid CSV file
    """
    # Given
    event = lambda_function_url_event_factory(path="/test.csv")

    # When
    response = lambda_handler(event, None)

    # Then
    assert response["statusCode"] == 200
    assert "text/csv" in response["headers"]["Content-Type"]
```

### Docstrings

Every test should have a clear docstring:

```python
def test_path_traversal_blocked():
    """Test that path traversal attempts with .. are blocked."""
    # Test code here
```

For acceptance tests, include the user story:

```python
def test_user_filters_data():
    """
    User Story: Filter dataset by organisation

    AS A data analyst
    I WANT TO filter a dataset by organisation
    SO THAT I only download relevant data

    GIVEN a dataset with multiple organisations
    WHEN I filter by one organisation
    THEN I receive only matching records
    """
    # Test code here
```

## Coverage Requirements

- **Minimum coverage:** 80% (enforced by pytest.ini)
- **Target coverage:** 90%+

Check current coverage:
```bash
pytest --cov=src --cov-report=term-missing
```

### Excluded from Coverage

Lines excluded from coverage (see pytest.ini):
- `pragma: no cover` comments
- `def __repr__` methods
- Defensive assertions (`raise AssertionError`, `raise NotImplementedError`)
- `if __name__ == "__main__":` blocks
- Type checking blocks (`if TYPE_CHECKING:`)

## Continuous Integration

Tests run automatically on:
- Every pull request
- Every push to main branch

GitHub Actions workflow (`.github/workflows/deploy.yml`) runs:
1. Linting (ruff, black)
2. Type checking (mypy)
3. Unit tests
4. Integration tests
5. Acceptance tests
6. Coverage report

## Best Practices

### 1. Keep Tests Isolated
```python
# Good - uses fixture with function scope
def test_with_s3(s3_mock):
    # Clean S3 for each test
    pass

# Bad - shared state between tests
global_state = []
def test_appends_to_global():
    global_state.append("test")
```

### 2. Use Descriptive Assertions
```python
# Good
assert response["statusCode"] == 200, f"Expected 200, got {response['statusCode']}"

# Better - pytest shows detailed diff
assert response["statusCode"] == 200

# Bad
assert response["statusCode"]  # Not clear what's being tested
```

### 3. Test Edge Cases
```python
def test_parse_path_with_various_inputs():
    """Test path parsing with edge cases."""
    # Normal case
    assert _parse_path("/test.csv") == ("test", "csv")

    # Edge cases
    assert _parse_path("/test.CSV") == ("test", "csv")  # Uppercase
    assert _parse_path("test.csv") == ("test", "csv")   # No leading slash

    # Error cases
    with pytest.raises(ValueError):
        _parse_path("")  # Empty path
```

### 4. Use Parametrize for Similar Tests
```python
@pytest.mark.parametrize("extension,content_type", [
    ("csv", "text/csv"),
    ("json", "application/json"),
    ("parquet", "application/octet-stream"),
])
def test_content_type_for_extension(extension, content_type):
    """Test content type mapping for each extension."""
    assert get_content_type(extension) == content_type
```

### 5. Mock External Dependencies in Unit Tests
```python
# Good - mocks S3
def test_data_processor_with_mocked_s3(s3_mock):
    processor = DataProcessor("test-bucket")
    # Test proceeds with mocked S3

# Bad - tries to connect to real S3
def test_data_processor():
    processor = DataProcessor("real-production-bucket")  # Don't do this!
```

## Debugging Tests

### Run with verbose output
```bash
pytest -vv
```

### Show local variables on failure
```bash
pytest --showlocals
```

### Stop on first failure
```bash
pytest -x
```

### Drop into debugger on failure
```bash
pytest --pdb
```

### Run specific failing test
```bash
pytest tests/unit/test_models.py::TestPathParams::test_valid_path_params_csv -vv
```

## Test Performance

Monitor test execution time:
```bash
pytest --durations=10
```

This shows the 10 slowest tests.

### Performance Guidelines
- Unit tests: < 1 second each
- Integration tests: < 5 seconds each
- Acceptance tests: < 10 seconds each
- Total test suite: < 2 minutes

## Common Issues

### Issue: Import errors
```bash
ModuleNotFoundError: No module named 'src'
```

**Solution:** Tests add src to path in each file:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
```

### Issue: Moto S3 not working
```bash
AttributeError: 'S3' object has no attribute 'create_bucket'
```

**Solution:** Use the `s3_mock` fixture which sets up moto correctly.

### Issue: Tests pass locally but fail in CI
**Possible causes:**
- Missing environment variables
- Timing issues
- File path differences

**Solution:** Check `.github/workflows/deploy.yml` for environment setup.

## Resources

- [Digital Land Testing Guidance](https://digital-land.github.io/technical-documentation/development/testing-guidance/)
- [Pytest Documentation](https://docs.pytest.org/)
- [Moto Documentation](https://docs.getmoto.org/)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)

## Contributing

When adding new features:
1. Write tests first (TDD approach)
2. Add unit tests for new functions
3. Add integration tests for new workflows
4. Update acceptance tests for user-facing changes
5. Ensure coverage remains above 80%
6. Run full test suite before submitting PR

```bash
# Full test workflow before PR
make lint
make test
```
