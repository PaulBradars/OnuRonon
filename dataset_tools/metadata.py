"""CSV recording store and annotation rules."""

import csv
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pandas as pd

FIELDS = [
    "recording_id", "gloss_id", "variant_id", "signer_id", "video_path",
    "fps", "frame_count", "width", "height", "duration_seconds",
    "sign_start_seconds", "sign_end_seconds", "dominant_hand", "review_status",
    "reviewer_id", "notes", "created_at",
]
DOMINANT_HANDS = {"unknown", "left", "right", "both"}
REVIEW_STATUSES = {"unreviewed", "needs_revision", "verified"}


def new_recording_id() -> str:
    return f"rec_{uuid4().hex}"


def read_recordings(path: Path) -> pd.DataFrame:
    if not Path(path).exists():
        return pd.DataFrame(columns=FIELDS, dtype=str)
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    if list(frame.columns) != FIELDS:
        raise ValueError("recordings.csv has an unsupported schema")
    if frame.recording_id.duplicated().any():
        raise ValueError("Duplicate recording IDs in metadata")
    return frame


def write_recordings(path: Path, frame: pd.DataFrame) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        frame[FIELDS].to_csv(temporary, index=False, quoting=csv.QUOTE_MINIMAL)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def annotation_errors(row: dict) -> list[str]:
    errors = []
    if not str(row.get("signer_id", "")).strip():
        errors.append("Signer ID is required")
    if not str(row.get("variant_id", "")).strip():
        errors.append("Variant ID is required")
    if row.get("dominant_hand") not in DOMINANT_HANDS:
        errors.append("Invalid dominant hand")
    if row.get("review_status") not in REVIEW_STATUSES:
        errors.append("Invalid review status")
    if row.get("review_status") == "verified" and not str(row.get("reviewer_id", "")).strip():
        errors.append("Verified recordings require a reviewer ID")
    start, end = row.get("sign_start_seconds", ""), row.get("sign_end_seconds", "")
    if (start == "") != (end == ""):
        errors.append("Set both sign boundaries or leave both empty")
    elif start != "":
        try:
            start_value, end_value = float(start), float(end)
            duration = float(row["duration_seconds"])
            if not all(math.isfinite(x) for x in (start_value, end_value, duration)) or not (0 <= start_value < end_value <= duration):
                errors.append("Sign boundaries must satisfy 0 ≤ start < end ≤ duration")
        except (ValueError, TypeError, KeyError):
            errors.append("Sign boundaries or duration are invalid")
    return errors


def create_recording(path: Path, values: dict) -> dict:
    frame = read_recordings(path)
    row = {field: str(values.get(field, "")) for field in FIELDS}
    row["recording_id"] = new_recording_id()
    row["created_at"] = datetime.now(timezone.utc).isoformat()
    errors = annotation_errors(row)
    if errors:
        raise ValueError("; ".join(errors))
    frame.loc[len(frame)] = row
    write_recordings(path, frame)
    return row


def update_recording(path: Path, recording_id: str, changes: dict) -> dict:
    allowed = {"gloss_id", "variant_id", "signer_id", "sign_start_seconds",
               "sign_end_seconds", "dominant_hand", "review_status", "reviewer_id", "notes"}
    if set(changes) - allowed:
        raise ValueError("Only annotation fields can be updated")
    frame = read_recordings(path)
    matches = frame.index[frame.recording_id == recording_id].tolist()
    if len(matches) != 1:
        raise KeyError(recording_id)
    index = matches[0]
    row = frame.loc[index].to_dict()
    row.update({key: str(value) for key, value in changes.items()})
    errors = annotation_errors(row)
    if errors:
        raise ValueError("; ".join(errors))
    for key in changes:
        frame.at[index, key] = row[key]
    write_recordings(path, frame)
    return row
