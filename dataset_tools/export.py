"""Portable versioned metadata exports."""

import json
from pathlib import Path

from .metadata import FIELDS, read_recordings
from .validation import validate_dataset
from .vocabulary import load_vocabulary

SCHEMA_VERSION = "1.0"


def manifest(root: Path) -> dict:
    root = Path(root)
    vocabulary = load_vocabulary(root / "config/gloss_vocabulary.json")
    records = read_recordings(root / "data/metadata/recordings.csv")
    return {"schema_version": SCHEMA_VERSION, "vocabulary": vocabulary,
            "recordings": records[FIELDS].to_dict("records")}


def read_manifest(content: str | bytes) -> dict:
    data = json.loads(content)
    if data.get("schema_version") != SCHEMA_VERSION or not isinstance(data.get("recordings"), list):
        raise ValueError("Unsupported manifest schema")
    if any(set(row) != set(FIELDS) for row in data["recordings"]):
        raise ValueError("Manifest recording fields do not match schema")
    vocabulary = data.get("vocabulary", {})
    if vocabulary.get("schema_version") != SCHEMA_VERSION or not isinstance(vocabulary.get("glosses"), list):
        raise ValueError("Unsupported vocabulary schema")
    return data


def export_bundle(root: Path) -> dict[str, bytes]:
    root = Path(root)
    csv_path = root / "data/metadata/recordings.csv"
    csv_bytes = csv_path.read_bytes() if csv_path.exists() else (",".join(FIELDS) + "\n").encode("utf-8")
    vocabulary = load_vocabulary(root / "config/gloss_vocabulary.json")
    return {
        "recordings.csv": csv_bytes,
        "gloss_vocabulary.json": json.dumps(vocabulary, ensure_ascii=False, indent=2).encode("utf-8"),
        "dataset_manifest.json": json.dumps(manifest(root), ensure_ascii=False, indent=2).encode("utf-8"),
        "validation_report.json": json.dumps(validate_dataset(root), ensure_ascii=False, indent=2).encode("utf-8"),
    }
