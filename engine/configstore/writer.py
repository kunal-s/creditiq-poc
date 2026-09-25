"""The configuration writer — an administrative publish (plan.md C1).

This is the ONLY code path that creates a new config version. It is a
separate package on purpose: pipeline, review, copilot and harness code must
not be able to import it (CLAUDE.md rule 4), enforced by the import-linter
contract in `importlinter.cfg`. A publish is not a runtime event; it is
something an Administrator does, ledgered with author and diff, and it never
edits a prior version in place.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml
from pydantic import BaseModel

from .schema import SECTION_MODELS, DictionarySection

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"


def _canonical_json(data: dict) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")


def section_hash(data: dict) -> str:
    return hashlib.sha256(_canonical_json(data)).hexdigest()


def _merkle_root(section_hashes: dict[str, str]) -> str:
    """Hash of the sorted (section, hash) pairs — the version id."""
    joined = "".join(f"{name}:{h}" for name, h in sorted(section_hashes.items()))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_authored_sections() -> dict[str, BaseModel]:
    """Validate every authored config file under config/ against its schema."""
    sections: dict[str, BaseModel] = {}

    for name, model in SECTION_MODELS.items():
        path = CONFIG_DIR / f"{name}.yaml"
        if not path.is_file():
            raise FileNotFoundError(f"missing authored config section: {path}")
        sections[name] = model.model_validate(_load_yaml(path))

    dict_dir = CONFIG_DIR / "dictionaries"
    if dict_dir.is_dir():
        for path in sorted(dict_dir.glob("*.yaml")):
            data = DictionarySection.model_validate(_load_yaml(path))
            sections[f"dictionary.{data.case_id}"] = data

    return sections


def publish(*, data_root: Path, author: str, note: str = "") -> dict:
    """Validate every authored section, hash it, and — if the resulting
    version doesn't already exist — write it immutably and point
    published.json at it. Returns the version record."""
    sections = load_authored_sections()
    section_dumps = {name: model.model_dump(mode="json") for name, model in sections.items()}
    section_hashes = {name: section_hash(dump) for name, dump in section_dumps.items()}
    version = _merkle_root(section_hashes)

    store_dir = Path(data_root) / "config_store"
    version_dir = store_dir / "versions" / version
    published_path = store_dir / "published.json"

    is_new = not version_dir.is_dir()
    if is_new:
        version_dir.mkdir(parents=True)
        for name, dump in section_dumps.items():
            (version_dir / f"{name}.json").write_text(
                json.dumps(dump, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        (version_dir / "_manifest.json").write_text(
            json.dumps({"section_hashes": section_hashes, "version": version}, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )

    prior = None
    if published_path.is_file():
        prior = json.loads(published_path.read_text(encoding="utf-8"))

    record = {
        "version": version,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "author": author,
        "note": note,
        "section_hashes": section_hashes,
        "prior_version": prior["version"] if prior else None,
    }
    store_dir.mkdir(parents=True, exist_ok=True)
    published_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    history_path = store_dir / "publish_log.jsonl"
    with history_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")

    return record
