"""C1 (plan.md): an administrative publish is not a runtime event. These
tests are the "store-hash-unchanged after a full run" half of that contract
— the other half (after reviews) has nothing to exercise yet, since reviews
don't exist before Stage E."""

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
