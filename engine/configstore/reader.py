"""Read-only access to the published config store.

Runtime code (the API, the checklist deriver, the future rule engine) reads
config through this module only. It never reads `config/*.yaml` directly and
never imports `writer` — see `.importlinter`. If no version has been
published yet, callers get a clear error, not a silent fall-through to the
authored source (that would defeat the point of publishing).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .schema import (
    AlignmentSection,
    CamSectionConfig,
    ChecklistTaxonomySection,
    CrossChecksSection,
    DocumentAgesSection,
    DocumentTypesSection,
    PolicySection,
    StatementsSection,
    TolerancesSection,
)


class NoPublishedConfig(RuntimeError):
    pass


def _store_dir(data_root: Path) -> Path:
    return Path(data_root) / "config_store"


def published_version(data_root: Path) -> dict:
    path = _store_dir(data_root) / "published.json"
    if not path.is_file():
        raise NoPublishedConfig(
            f"no published config version under {data_root} — run `creditiq config publish` first"
        )
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=32)
def _load_section_json(data_root_str: str, version: str, section: str) -> dict:
    path = Path(data_root_str) / "config_store" / "versions" / version / f"{section}.json"
    if not path.is_file():
        raise NoPublishedConfig(f"published version {version} has no section {section!r}")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_section(data_root: Path, section: str) -> dict:
    version = published_version(data_root)["version"]
    return _load_section_json(str(data_root), version, section)


def load_policy(data_root: Path) -> PolicySection:
    return PolicySection.model_validate(_load_section(data_root, "policy"))


def load_checklist_taxonomy(data_root: Path) -> ChecklistTaxonomySection:
    return ChecklistTaxonomySection.model_validate(_load_section(data_root, "checklist_taxonomy"))


def load_document_types(data_root: Path) -> DocumentTypesSection:
    return DocumentTypesSection.model_validate(_load_section(data_root, "document_types"))


def load_ingestion_section(data_root: Path, name: str) -> dict:
    """One section of the document-processing service's configuration, as published (raw JSON)."""
    return _load_section(data_root, f"ingestion.{name}")


def reason_codes(data_root: Path) -> dict[str, str]:
    """Reason code to plain-language re-scan request (F-07.4)."""
    return load_ingestion_section(data_root, "quality")["reason_codes"]


def manual_entry_cap(data_root: Path) -> float:
    return float(load_ingestion_section(data_root, "confidence")["manual_entry_cap"])


def load_document_ages(data_root: Path) -> DocumentAgesSection:
    return DocumentAgesSection.model_validate(_load_section(data_root, "document_ages"))


def load_tolerances(data_root: Path) -> TolerancesSection:
    return TolerancesSection.model_validate(_load_section(data_root, "tolerances"))


def load_alignment(data_root: Path) -> AlignmentSection:
    return AlignmentSection.model_validate(_load_section(data_root, "alignment"))


def load_statements(data_root: Path) -> StatementsSection:
    return StatementsSection.model_validate(_load_section(data_root, "statements"))


def load_cam(data_root: Path) -> CamSectionConfig:
    return CamSectionConfig.model_validate(_load_section(data_root, "cam"))


def load_crosschecks(data_root: Path) -> CrossChecksSection:
    return CrossChecksSection.model_validate(_load_section(data_root, "crosschecks"))


def section_path(data_root: Path, section: str) -> Path:
    """The published JSON file of a section, for services that read the
    published configuration directly (the ingest sidecar, AD-2)."""
    version = published_version(data_root)["version"]
    return _store_dir(data_root) / "versions" / version / f"{section}.json"
