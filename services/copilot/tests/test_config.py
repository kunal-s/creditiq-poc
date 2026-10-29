import shutil
from pathlib import Path

import pytest
import yaml

from copilot.cli import main
from copilot.config import ConfigError, load_dir

CONFIG = Path(__file__).resolve().parent.parent / "config"


@pytest.fixture
def cfgdir(tmp_path):
    d = tmp_path / "c"
    shutil.copytree(CONFIG, d)
    return d


def edit(d, name, fn):
    p = d / name
    data = yaml.safe_load(p.read_text())
    fn(data)
    p.write_text(yaml.safe_dump(data))


def test_shipped_config_loads_and_hash_is_stable():
    a, b = load_dir(CONFIG), load_dir(CONFIG)
    assert a.hash == b.hash and len(a.hash) == 64
    assert a.use_case("explain_rejections").tools == ["get_rejection_reasons"]


def test_hash_changes_with_prompt(cfgdir):
    before = load_dir(cfgdir).hash
    (cfgdir / "prompts" / "router.md").write_text("changed")
    assert load_dir(cfgdir).hash != before


def test_unknown_tool_refused(cfgdir):
    edit(cfgdir, "registry.yaml", lambda d: d["use_cases"][0]["tools"].append("nope"))
    with pytest.raises(ConfigError, match="unknown tool"):
        load_dir(cfgdir)


def test_read_use_case_cannot_use_act_tool(cfgdir):
    edit(cfgdir, "tools.yaml", lambda d: d["tools"][0].update(kind="act"))
    with pytest.raises(ConfigError, match="read use case cannot use"):
        load_dir(cfgdir)


def test_context_key_must_be_allowed(cfgdir):
    edit(cfgdir, "host.yaml", lambda d: d.update(context_keys=[]))
    with pytest.raises(ConfigError, match="context_keys"):
        load_dir(cfgdir)


def test_missing_prompt_and_extra_field_refused(cfgdir):
    (cfgdir / "prompts" / "explain_rejections.md").unlink()
    with pytest.raises(ConfigError, match="not found in prompts"):
        load_dir(cfgdir)
    edit(cfgdir, "llm.yaml", lambda d: d.update(top_p=0.5))
    with pytest.raises(ConfigError):
        load_dir(cfgdir)


def test_path_placeholder_needs_param(cfgdir):
    edit(cfgdir, "tools.yaml", lambda d: d["tools"][0].update(path="/x/{other}"))
    with pytest.raises(ConfigError, match="placeholders"):
        load_dir(cfgdir)


def test_cli(capsys, cfgdir):
    assert main(["config-validate", str(cfgdir)]) == 0
    assert "3 use cases, 2 tools" in capsys.readouterr().out
    (cfgdir / "llm.yaml").unlink()
    assert main(["config-validate", str(cfgdir)]) == 1
