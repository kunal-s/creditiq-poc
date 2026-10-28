"""The configuration writer — an administrative publish.

This is the ONLY code path that creates a new config version. It is a
separate package on purpose: pipeline, review and harness code must not be
able to import it (CLAUDE.md rule 4), enforced by the import-linter
contract in `.importlinter`. A publish is not a runtime event; it is
something an Administrator does, ledgered with author and diff, and it never
edits a prior version in place. Two ways in: `publish` from the configuration
files (the command line), and `publish_edited` from the settings an
Administrator edits on the screen (engine/admin_config.py, F-00.6).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml
from pydantic import BaseModel

from ..config import option_ids
from .schema import SECTION_MODELS, cross_check

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


INGESTION_SECTIONS = {
    "document_types": "document_types.json", "signals": "signals.yaml", "fields": "fields.yaml", "validators": "validators.yaml",
    "quality": "quality.yaml", "routing": "routing.yaml", "llm": "llm.yaml", "confidence": "confidence.yaml", "decision": "decision.yaml",
}


def load_ingestion_sections() -> dict[str, dict]:
    """The document-processing service's configuration (config/ingestion/), stored raw: the service
    validates it against its own models when it loads the version, and
    `python -m ingestion.cli config-validate config/ingestion` checks it before a publish."""
    out: dict[str, dict] = {}
    for name, fname in INGESTION_SECTIONS.items():
        path = CONFIG_DIR / "ingestion" / fname
        if not path.is_file():
            raise FileNotFoundError(f"missing ingestion config section: {path}")
        out[name] = json.loads(path.read_text(encoding="utf-8")) if path.suffix == ".json" else _load_yaml(path)
    return out


def _section_path(name: str, private_dir: Path | None) -> Path:
    """config/<name>.yaml, or <private_dir>/<name>.yaml when that file exists: RBL's own norms and
    matrix are published from a git-ignored directory (workflow/private/config), never committed."""
    if private_dir is not None and (Path(private_dir) / f"{name}.yaml").is_file():
        return Path(private_dir) / f"{name}.yaml"
    return CONFIG_DIR / f"{name}.yaml"


def private_sections(private_dir: Path | None) -> list[str]:
    return sorted(name for name in SECTION_MODELS if _section_path(name, private_dir).parent != CONFIG_DIR)


def load_authored_sections(private_dir: Path | None = None) -> dict[str, BaseModel]:
    """Validate every authored config file under config/ (or its private override) against its schema."""
    sections: dict[str, BaseModel] = {}

    for name, model in SECTION_MODELS.items():
        path = _section_path(name, private_dir)
        if not path.is_file():
            raise FileNotFoundError(f"missing authored config section: {path}")
        sections[name] = model.model_validate(_load_yaml(path))

    problems = cross_check(sections, load_ingestion_sections(), facilities=option_ids("facilities"))
    if problems:
        raise ValueError("config cross-check failed:\n  " + "\n  ".join(problems))
    return sections


def publish(*, data_root: Path, author: str, note: str = "", private_dir: Path | None = None) -> dict:
    """Validate every authored section, hash it, and — if the resulting
    version doesn't already exist — write it immutably and point
    published.json at it. Returns the version record."""
    sections = load_authored_sections(private_dir)
    section_dumps = {name: model.model_dump(mode="json") for name, model in sections.items()}
    section_dumps.update({f"ingestion.{name}": data for name, data in load_ingestion_sections().items()})
    return _write_version(data_root, section_dumps, author=author, note=note, origin="cli",
                          private=private_sections(private_dir))


# The sections an Administrator edits on the screen (F-00.6).
EDITABLE_SECTIONS = ("tolerances", "policy", "crosschecks", "approval_matrix", "statements")


def publish_edited(*, data_root: Path, author: str, note: str, sections: dict[str, BaseModel],
                   changes: list[dict]) -> dict:
    """Publish the settings an Administrator edited on the screen: every section of the version now
    published, with the edited ones replaced, validated as a file publish is. Recorded with
    origin "app" and the changes, so a later publish from the files cannot drop them unnoticed."""
    current = _published(data_root)
    if current is None:
        raise ValueError("no configuration is published yet")
    unknown = set(sections) - set(EDITABLE_SECTIONS)
    if unknown:
        raise ValueError(f"not editable on the screen: {', '.join(sorted(unknown))}")
    version_dir = Path(data_root) / "config_store" / "versions" / current["version"]
    dumps = {name: json.loads((version_dir / f"{name}.json").read_text(encoding="utf-8"))
             for name in current["section_hashes"]}
    models = {name: model.model_validate(dumps[name]) for name, model in SECTION_MODELS.items()}
    models.update(sections)
    ingestion = {name.removeprefix("ingestion."): data for name, data in dumps.items() if name.startswith("ingestion.")}
    problems = cross_check(models, ingestion, facilities=option_ids("facilities"))
    if problems:
        raise ValueError("config cross-check failed:\n  " + "\n  ".join(problems))
    dumps.update({name: model.model_dump(mode="json") for name, model in sections.items()})
    return _write_version(data_root, dumps, author=author, note=note, origin="app",
                          private=current.get("private_sections", []), changes=changes)


def _published(data_root: Path) -> dict | None:
    path = Path(data_root) / "config_store" / "published.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def app_edits_at_risk(*, data_root: Path, private_dir: Path | None = None) -> list[str]:
    """What a publish from the configuration files would undo: when the version now published was
    edited on the screen, each edited section whose files say otherwise. Empty otherwise."""
    current = _published(data_root)
    if current is None or current.get("origin") != "app":
        return []
    version_dir = Path(data_root) / "config_store" / "versions" / current["version"]
    files = load_authored_sections(private_dir)
    out = []
    for name in EDITABLE_SECTIONS:
        published = json.loads((version_dir / f"{name}.json").read_text(encoding="utf-8"))
        if section_hash(published) != section_hash(files[name].model_dump(mode="json")):
            out.append(name)
    return out


def _write_version(data_root: Path, section_dumps: dict[str, dict], *, author: str, note: str, origin: str,
                   private: list[str], changes: list[dict] | None = None) -> dict:
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
        "private_sections": private,
        "origin": origin,
    }
    if changes is not None:
        record["changes"] = changes
    store_dir.mkdir(parents=True, exist_ok=True)
    published_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    history_path = store_dir / "publish_log.jsonl"
    with history_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")

    return record
