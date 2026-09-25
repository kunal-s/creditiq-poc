from pathlib import Path

import pytest

from engine.configstore import writer


@pytest.fixture()
def published_data_root(tmp_path: Path) -> Path:
    """A data root with the current authored config published into it."""
    writer.publish(data_root=tmp_path, author="test-fixture", note="test publish")
    return tmp_path
