"""Load a configuration directory, or a published version, into one frozen IngestionConfig."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import yaml

from ..util import hash_of
from .models import (
    ConfidenceConfig, DecisionConfig, DocumentTypesConfig, FieldsConfig, IngestionConfig, LlmConfig,
    QualityConfig, RoutingConfig, SignalsConfig, ValidatorsConfig,
)

FILES = {
    "document_types": "document_types.json",
    "signals": "signals.yaml",
    "fields": "fields.yaml",
    "validators": "validators.yaml",
    "quality": "quality.yaml",
    "routing": "routing.yaml",
    "llm": "llm.yaml",
    "confidence": "confidence.yaml",
    "decision": "decision.yaml",
}


class ConfigError(ValueError):
    pass


def _read(path: Path):
    text = path.read_text(encoding="utf-8")
    return json.loads(text) if path.suffix == ".json" else yaml.safe_load(text)


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load_dir(path: Path | str, *, version: str = "dev", overlay: Path | str | None = None) -> IngestionConfig:
    """Read every section from `path`. An `overlay` directory may hold partial sections that are
    deep-merged on top (lists replace); tests use it for fixture-specific noise patterns."""
    path = Path(path)
    raw: dict[str, object] = {}
    for key, fname in FILES.items():
        f = path / fname
        if not f.exists():
            raise ConfigError(f"missing configuration file {fname} in {path}")
        data = _read(f)
        if overlay and (Path(overlay) / fname).exists():
            data = _merge(data, _read(Path(overlay) / fname))
        raw[key] = data
    return _build(raw, version)


def _build(raw: dict, version: str) -> IngestionConfig:
    h = hash_of(raw)
    try:
        cfg = IngestionConfig(
            version=version, hash=h,
            document_types=DocumentTypesConfig.model_validate(raw["document_types"]),
            signals=SignalsConfig.model_validate(raw["signals"]),
            fields=FieldsConfig.model_validate(raw["fields"]),
            validators=ValidatorsConfig.model_validate(raw["validators"]),
            quality=QualityConfig.model_validate(raw["quality"]),
            routing=RoutingConfig.model_validate(raw["routing"]),
            llm=LlmConfig.model_validate(raw["llm"]),
            confidence=ConfidenceConfig.model_validate(raw["confidence"]),
            decision=DecisionConfig.model_validate(raw["decision"]),
        )
    except Exception as e:  # pydantic's message already names the section and key
        raise ConfigError(str(e)) from e
    problems = cfg.check_consistency()
    if problems:
        raise ConfigError("configuration is inconsistent:\n  " + "\n  ".join(problems))
    return cfg


def _engine_hash(data) -> str:
    """The engine's section hash (engine/configstore/writer.py section_hash): sha256 of canonical JSON."""
    import hashlib

    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


class ConfigStore:
    """Read access to the configuration the engine published (FRD principle 3). One version holds the
    engine's sections and ours: <root>/config_store/versions/<version>/ingestion.<section>.json, with
    each section's hash in _manifest.json. A section changed on disk after publishing is refused.
    The service has no way to write configuration (CLAUDE.md rule 4): publishing is the engine's."""

    def __init__(self, data_root: Path | str):
        self.base = Path(data_root) / "config_store" / "versions"

    def versions(self) -> list[str]:
        return sorted(p.name for p in self.base.iterdir() if p.is_dir()) if self.base.exists() else []

    def load(self, version: str) -> IngestionConfig:
        return _load_published(str(self.base), version)


@lru_cache(maxsize=16)
def _load_published(base: str, version: str) -> IngestionConfig:
    d = Path(base) / version
    if not d.is_dir():
        raise ConfigError(f"unknown configuration version {version}")
    manifest = json.loads((d / "_manifest.json").read_text(encoding="utf-8"))
    raw: dict[str, object] = {}
    for key in FILES:
        f = d / f"ingestion.{key}.json"
        if not f.is_file():
            raise ConfigError(f"version {version} has no ingestion section {key}")
        data = json.loads(f.read_text(encoding="utf-8"))
        if manifest["section_hashes"].get(f"ingestion.{key}") != _engine_hash(data):
            raise ConfigError(f"published version {version} was modified on disk (section ingestion.{key})")
        raw[key] = data
    return _build(raw, version)
