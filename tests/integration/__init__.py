"""
Integration test package for feedspine.

Integration tests verify that components work together correctly.
These tests may be slower and are marked appropriately:

- @pytest.mark.slow - Slower tests, skip with -m "not slow"
- @pytest.mark.integration - Integration tests
- @pytest.mark.network - Tests requiring network access

Run all tests:
    pytest tests/integration/

Run fast tests only:
    pytest tests/integration/ -m "not slow"

Run with coverage:
    pytest tests/integration/ --cov=feedspine
"""
