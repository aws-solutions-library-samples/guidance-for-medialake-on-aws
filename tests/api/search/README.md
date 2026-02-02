# Assets Page Bugs - Test Suite

This directory contains comprehensive tests for the assets-page-bugs specification, including property-based tests and unit tests for sorting, pagination, and URL state management.

## Overview

The test suite validates critical bug fixes in the Assets Page:

- **Sorting functionality**: Parameter extraction, validation, and query construction
- **Pagination**: URL state persistence, page range validation, and calculations
- **Storage identifier**: Bucket filtering query construction
- **Parameter forwarding**: Unified search orchestrator parameter handling

## Test Files

### Property-Based Tests (Hypothesis)

Property-based tests use Hypothesis to generate hundreds of test cases automatically, ensuring properties hold across all valid inputs.

- **test_sort_parameter_extraction_properties.py**: Sort parameter parsing
- **test_sort_parameter_validation_properties.py**: Sort field and direction validation
- **test_sort_clause_construction_properties.py**: OpenSearch query construction
- **test_parameter_forwarding_properties.py**: Orchestrator parameter forwarding
- **test_page_validation_properties.py**: Page range and size validation
- **test_storage_identifier_properties.py**: Bucket filtering queries

### Unit Tests

Unit tests verify specific examples and edge cases.

- **test_sort_field_mappings.py**: Frontend field → OpenSearch path mappings
- **test_default_sort_behavior.py**: Default sort handling

## Running Tests

### Prerequisites

```bash
# Install dependencies
pip install -r requirements-dev.txt

# Ensure you're in the project root
cd /path/to/medialake
```

### Run All Tests

```bash
# Run all search API tests
pytest tests/api/search/

# Run with verbose output
pytest tests/api/search/ -v

# Run with coverage report
pytest tests/api/search/ --cov=lambdas/api/search/get_search --cov-report=html
```

### Run Specific Test Files

```bash
# Run sort parameter extraction tests
pytest tests/api/search/test_sort_parameter_extraction_properties.py

# Run sort validation tests
pytest tests/api/search/test_sort_parameter_validation_properties.py

# Run sort clause construction tests
pytest tests/api/search/test_sort_clause_construction_properties.py

# Run parameter forwarding tests
pytest tests/api/search/test_parameter_forwarding_properties.py

# Run page validation tests
pytest tests/api/search/test_page_validation_properties.py

# Run storage identifier tests
pytest tests/api/search/test_storage_identifier_properties.py

# Run field mapping tests
pytest tests/api/search/test_sort_field_mappings.py

# Run default sort behavior tests
pytest tests/api/search/test_default_sort_behavior.py
```

### Run Specific Test Classes or Methods

```bash
# Run a specific test class
pytest tests/api/search/test_sort_parameter_extraction_properties.py::TestSortParameterExtractionProperty

# Run a specific test method
pytest tests/api/search/test_sort_parameter_extraction_properties.py::TestSortParameterExtractionProperty::test_descending_sort_extraction

# Run tests matching a pattern
pytest tests/api/search/ -k "sort_parameter"
```

### Hypothesis Options

```bash
# Show Hypothesis statistics
pytest tests/api/search/ --hypothesis-show-statistics

# Run more examples (default is 100)
pytest tests/api/search/ --hypothesis-max-examples=1000

# Run with specific seed for reproducibility
pytest tests/api/search/ --hypothesis-seed=12345

# Show Hypothesis output
pytest tests/api/search/ --hypothesis-verbosity=verbose
```

### Coverage Reports

```bash
# Generate HTML coverage report
pytest tests/api/search/ --cov=lambdas/api/search/get_search --cov-report=html

# Open coverage report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows

# Generate terminal coverage report
pytest tests/api/search/ --cov=lambdas/api/search/get_search --cov-report=term-missing
```

## Test Structure

### Property-Based Test Pattern

```python
@given(field_name=valid_sort_field)
@settings(max_examples=100)
def test_property_name(self, field_name: str):
    """
    Property X: Property Name

    *For any* valid input, the system SHALL behave correctly.

    **Validates: Requirements X.Y**
    """
    # Arrange
    params = SearchParams(q="test", sort=field_name)

    # Act
    result = function_under_test(params)

    # Assert
    assert expected_property_holds(result)
```

### Unit Test Pattern

```python
def test_specific_behavior(self):
    """
    Test that specific input produces specific output.

    **Validates: Requirement X.Y**
    """
    # Arrange
    input_data = create_test_data()

    # Act
    result = function_under_test(input_data)

    # Assert
    assert result == expected_output
```

## Understanding Test Output

### Successful Test Run

```
tests/api/search/test_sort_parameter_extraction_properties.py::TestSortParameterExtractionProperty::test_descending_sort_extraction PASSED [100%]

====== 1 passed in 0.50s ======
```

### Failed Property Test

When a property test fails, Hypothesis will show:

1. The failing example
2. A simplified (shrunk) example
3. The assertion that failed

```
Falsifying example: test_property(
    field_name='createdAt'
)
AssertionError: sort_by should be 'createdAt', got 'None'
```

### Hypothesis Statistics

```
- test_descending_sort_extraction: 100 examples, 0 failing
- test_ascending_sort_extraction: 100 examples, 0 failing
```

## Debugging Tests

### Run with Print Statements

```bash
# Show print output
pytest tests/api/search/ -s

# Show print output with verbose
pytest tests/api/search/ -sv
```

### Run with Debugger

```bash
# Drop into debugger on failure
pytest tests/api/search/ --pdb

# Drop into debugger on first failure
pytest tests/api/search/ -x --pdb
```

### Reproduce Failing Test

```bash
# Use the seed from the failure output
pytest tests/api/search/ --hypothesis-seed=12345
```

## Common Issues

### Import Errors

**Problem**: `ModuleNotFoundError: No module named 'lambdas'`

**Solution**: Ensure you're running from the project root and PYTHONPATH is set:

```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest tests/api/search/
```

### Hypothesis Timeout

**Problem**: Tests take too long with many examples

**Solution**: Reduce examples for development:

```bash
pytest tests/api/search/ --hypothesis-max-examples=10
```

### Mocking Issues

**Problem**: Tests fail due to missing AWS resources

**Solution**: Tests should mock external dependencies. Check that mocks are properly configured.

## Best Practices

### Writing New Tests

1. **Use descriptive names**: Test names should explain what is being tested
2. **Document requirements**: Include `**Validates: Requirement X.Y**` in docstrings
3. **Use appropriate test type**:
   - Property-based: For universal properties across many inputs
   - Unit: For specific examples and edge cases
4. **Keep tests independent**: No shared state between tests
5. **Use fixtures**: For common test setup

### Property-Based Testing Tips

1. **Start with simple properties**: Build up to complex ones
2. **Use appropriate strategies**: Choose generators that match your domain
3. **Add assumptions**: Use `assume()` to filter invalid combinations
4. **Check shrinking**: Verify that failing examples shrink to minimal cases
5. **Document properties**: Explain what property is being tested

### Test Maintenance

1. **Run tests frequently**: Catch regressions early
2. **Update tests with requirements**: Keep tests in sync with specs
3. **Review coverage**: Ensure all code paths are tested
4. **Refactor tests**: Keep tests clean and maintainable

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Test Assets Page Bugs

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: pip install -r requirements-dev.txt
      - name: Run tests
        run: pytest tests/api/search/ --cov=lambdas/api/search/get_search --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

## Resources

- **Hypothesis Documentation**: https://hypothesis.readthedocs.io/
- **pytest Documentation**: https://docs.pytest.org/
- **Property-Based Testing Guide**: https://hypothesis.works/articles/what-is-property-based-testing/
- **Specification**: `.kiro/specs/assets-page-bugs/`

## Support

For questions or issues:

1. Check the test output for error messages
2. Review the specification documents
3. Check existing tests for examples
4. Consult the TEST_SUMMARY.md for coverage details
