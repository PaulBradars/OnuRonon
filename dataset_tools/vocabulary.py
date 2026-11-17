"""Versioned gloss vocabulary."""

import json
from pathlib import Path

SCHEMA_VERSION = "1.0"


def load_vocabulary(path: Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != SCHEMA_VERSION or not isinstance(data.get("glosses"), list):
        raise ValueError("Unsupported vocabulary schema")
    ids = [entry["gloss_id"] for entry in data["glosses"]]
    if len(ids) != len(set(ids)) or any(not item for item in ids):
        raise ValueError("Vocabulary has duplicate or empty gloss IDs")
    return data


def gloss_ids(path: Path) -> set[str]:
    return {entry["gloss_id"] for entry in load_vocabulary(path)["glosses"]}
