"""An administrative publish is not a runtime event (CLAUDE.md rule 4; FRD
principle 3). These tests cover the "store unchanged after a full run of
reads" half of that contract; the other half (review decisions never change
configuration) is added with FRD F-17."""

from pathlib import Path

from engine.checklist import CaseAttributes, derive_checklist
from engine.configstore import reader, writer


def _published_json_snapshot(data_root: Path) -> dict:
    version = reader.published_version(data_root)
    versions_dir = data_root / "config_store" / "versions"
    return {
        p.name: p.read_text(encoding="utf-8")
        for p in sorted((versions_dir / version["version"]).glob("*.json"))
    }


def test_reading_config_never_changes_the_store(published_data_root: Path):
    before = _published_json_snapshot(published_data_root)

    # Simulate a full run's worth of config reads.
    reader.load_policy(published_data_root)
    reader.load_checklist_taxonomy(published_data_root)
    attrs = CaseAttributes.from_request(
        facility_types=["cash_credit", "term_loan"], collateral_present=True, mpbf_applicable=True
    )
    derive_checklist(published_data_root, "private_limited", attrs)
    derive_checklist(published_data_root, "proprietorship", attrs)
    derive_checklist(published_data_root, "partnership", attrs)

    after = _published_json_snapshot(published_data_root)
    assert before == after


def test_republishing_unchanged_config_reuses_the_same_version(published_data_root: Path):
    first = reader.published_version(published_data_root)
    second = writer.publish(data_root=published_data_root, author="someone-else", note="no-op republish")
    assert first["version"] == second["version"]
    assert first["section_hashes"] == second["section_hashes"]


def test_published_version_is_immutable_on_disk(published_data_root: Path):
    version = reader.published_version(published_data_root)["version"]
    version_dir = published_data_root / "config_store" / "versions" / version
    mtimes_before = {p: p.stat().st_mtime_ns for p in version_dir.glob("*.json")}

    writer.publish(data_root=published_data_root, author="someone-else", note="no-op republish")

    mtimes_after = {p: p.stat().st_mtime_ns for p in version_dir.glob("*.json")}
    assert mtimes_before == mtimes_after


def test_republishing_with_the_matrix_unchanged_reuses_the_version(published_data_root: Path):
    first = reader.published_version(published_data_root)
    assert "approval_matrix" in first["section_hashes"]
    assert writer.publish(data_root=published_data_root, author="someone-else")["version"] == first["version"]


def test_changing_one_band_changes_the_version(tmp_path: Path, monkeypatch):
    import shutil

    config = tmp_path / "config"
    shutil.copytree(writer.CONFIG_DIR, config)
    path = config / "approval_matrix.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace("up_to_inr: 20000000", "up_to_inr: 25000000", 1),
                    encoding="utf-8")
    default = writer.publish(data_root=tmp_path / "a", author="t")
    monkeypatch.setattr(writer, "CONFIG_DIR", config)
    changed = writer.publish(data_root=tmp_path / "b", author="t")
    assert changed["version"] != default["version"]
    assert changed["section_hashes"]["approval_matrix"] != default["section_hashes"]["approval_matrix"]
    assert reader.load_approval_matrix(tmp_path / "b").bands["working_capital"][0].up_to_inr == 25_000_000


def test_reading_the_matrix_never_changes_the_store(published_data_root: Path):
    before = _published_json_snapshot(published_data_root)
    reader.load_approval_matrix(published_data_root)
    assert _published_json_snapshot(published_data_root) == before
