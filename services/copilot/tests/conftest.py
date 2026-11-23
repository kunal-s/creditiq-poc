import pytest

from copilot import config as _config

# The tests run with the model settings their recordings were made under (golden_recordings.json,
# e2e_recordings.json), whatever provider the shipped config/llm.yaml names: every llm.yaml a test loads
# reads with these values, and no deployment. With the shipped OpenAI settings this changes nothing.
PINNED_MODEL = {"provider": "openai", "base_url": "https://api.openai.com/v1", "api_key_env": "OPENAI_API_KEY",
                "router_model": "gpt-5.4-nano", "runner_model": "gpt-5.4-nano"}
_read = _config._read


def _pinned_read(path):
    data = _read(path)
    if path.name == "llm.yaml" and isinstance(data, dict):
        data = {**{k: v for k, v in data.items() if k != "deployment"}, **PINNED_MODEL}
    return data


_config._read = _pinned_read


@pytest.fixture(autouse=True)
def _fresh_breakers():
    """Each test starts with every model server's breaker closed (they are kept per process)."""
    from copilot import model_errors

    model_errors.reset_breakers()
    yield
    model_errors.reset_breakers()
