import pytest


@pytest.fixture(autouse=True)
def _fresh_breakers():
    """Each test starts with every model server's breaker closed (they are kept per process)."""
    from copilot import model_errors

    model_errors.reset_breakers()
    yield
    model_errors.reset_breakers()
