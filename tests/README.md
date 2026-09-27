# CapEcon Test Suite

This directory contains the test suite for CapEcon (agentic decision analytics + legacy simulator modules).

## Directory Structure

```
tests/
├── __init__.py
├── conftest.py              # Pytest configuration and hypothesis profiles
├── README.md                # This file
├── unit/                    # Unit tests / narrow behaviour checks
├── property/               # Hypothesis property-based correctness tests
└── integration/             # Lightweight smoke drills across generator ↔ analytics stacks
```

## Test Types

### Unit Tests (`tests/unit/`)
Unit tests verify specific examples and edge cases:
- Specific calculation examples (e.g., typical e-commerce CVR of 3%, 10% MDE)
- Boundary conditions (minimum/maximum valid inputs)
- Error message content and formatting
- Integration points with existing functions

### Property-Based Tests (`tests/property/`)
Property-based tests verify universal properties across all inputs using Hypothesis:
- Mathematical properties (idempotence, monotonicity, inverse relationships)
- Input validation across the entire valid range
- Calculation correctness for randomly generated valid inputs
- Threshold-based warning generation
- Arithmetic relationships (totals, splits, proportions)

**Configuration**: Minimum 100 iterations per property test (configured in `conftest.py`)

### Integration Tests (`tests/integration/`)
Targeted drills that hydrate `generate_all_data()` and traverse a handful of analytics modules (`churn`,
`conversion`, `product_metrics`, etc.).
They are intentionally **narrow** smoke checks rather than full UI regressions—the Streamlit surfaces still
demand exploratory QA locally.

## Running Tests

### Run All Tests
```bash
pytest tests/ -v
```

### Run Unit Tests Only
```bash
pytest tests/unit/ -v
```

### Run Property Tests Only
```bash
pytest tests/property/ -v --hypothesis-show-statistics
```

### Run Integration Tests Only
```bash
pytest tests/integration/ -v
```

### Run with Coverage
```bash
pytest tests/ -v --cov=analytics.conversion --cov-report=html
```

### Run Specific Test File
```bash
pytest tests/unit/test_data_models.py -v
```

### Run Specific Test
```bash
pytest tests/unit/test_data_models.py::TestTestConfiguration::test_validate_valid_configuration -v
```

## Hypothesis Configuration

The test suite uses Hypothesis for property-based testing with the following profiles:

- **default**: 100 iterations per test (used by default)
- **ci**: 200 iterations per test (for CI/CD pipelines)
- **dev**: 50 iterations per test (for faster feedback during development)

To use a different profile:
```bash
pytest tests/property/ --hypothesis-profile=ci
```

## Test Markers

Tests are organized using pytest markers:

- `@pytest.mark.unit`: Unit tests
- `@pytest.mark.property`: Property-based tests
- `@pytest.mark.integration`: Integration tests
- `@pytest.mark.slow`: Tests that take longer to run

Run tests by marker:
```bash
pytest -m unit -v
pytest -m property -v
pytest -m integration -v
```

## Coverage Goals

- **Calculation Functions**: 100% line coverage, 100% branch coverage
- **Validation Logic**: 100% line coverage, 100% branch coverage
- **Property Tests**: All 25 correctness properties implemented
- **Integration Points**: Key scenarios covered

## Performance Requirements

All calculation functions must complete in <100ms:
- Sample size calculation: <10ms
- MDE calculation: <10ms
- Power calculation: <10ms
- Test validation: <50ms
- Segment analysis: <100ms

## Writing New Tests

### Unit Test Template
```python
def test_feature_description():
    """Test that feature behaves correctly."""
    # Arrange
    input_data = ...
    
    # Act
    result = function_under_test(input_data)
    
    # Assert
    assert result == expected_value
```

### Property Test Template
```python
from hypothesis import given, strategies as st

# Feature: cro-analytics-enhancement, Property X: Property Description
@given(
    param=st.floats(min_value=0.001, max_value=1.0)
)
def test_property_description(param):
    """Property X: Description of universal property."""
    result = function_under_test(param)
    assert property_holds(result)
```

## Dependencies

- `pytest>=7.4.0`: Test framework
- `hypothesis>=6.92.0`: Property-based testing library
- `pytest-cov` (optional): Coverage reporting

## References

- Methodology: [`docs/methodology.md`](../docs/methodology.md)
- Honesty & limits: [`docs/honesty.md`](../docs/honesty.md)
- Ontology package: [`ontology/README.md`](../ontology/README.md)
