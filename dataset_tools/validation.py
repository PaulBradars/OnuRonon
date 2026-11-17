"""Technical checks; linguistic review remains a separate annotation."""

import math
from collections import defaultdict
from pathlib import Path

from .metadata import annotation_errors, read_recordings
from .video_utils import inspect_video, sha256_file
from .vocabulary import gloss_ids


def validate_dataset(root: Path) -> dict:
    root = Path(root)
    records = read_recordings(root / "data/metadata/recordings.csv")
    known = gloss_ids(root / "config/gloss_vocabulary.json")
    issues = []
    hashes = defaultdict(list)
    for row in records.to_dict("records"):
        rid = row["recording_id"]

        def issue(code, message, category="technical"):
            issues.append({"recording_id": rid, "category": category,
                           "code": code, "message": message})

        if row["gloss_id"] not in known:
            issue("unknown_gloss", f"Unknown gloss ID: {row['gloss_id']}", "annotation")
        for error in annotation_errors(row):
            issue("invalid_annotation", error, "annotation")
        if not row["sign_start_seconds"] and not row["sign_end_seconds"]:
            issue("missing_boundaries", "Sign boundaries are missing", "annotation")
        relative = Path(row["video_path"])
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            issue("invalid_path", "Video path must stay inside the dataset")
            continue
        video = root / relative
        if not video.is_file():
            issue("missing_video", "Video file is missing")
            continue
        hashes[sha256_file(video)].append(rid)
        try:
            observed = inspect_video(video)
        except ValueError as exc:
            issue("unreadable_video", str(exc))
            continue
        for field in ("fps", "frame_count", "width", "height", "duration_seconds"):
            try:
                recorded = float(row[field])
                if not math.isfinite(recorded) or recorded <= 0:
                    issue("invalid_video_metadata", f"Invalid {field} metadata")
                elif abs(recorded - observed[field]) > (0.01 if field in {"fps", "duration_seconds"} else 0):
                    issue("video_metadata_mismatch", f"{field} differs from the video")
            except (TypeError, ValueError):
                issue("invalid_video_metadata", f"Invalid {field} metadata")
    for ids in hashes.values():
        if len(ids) > 1:
            for rid in ids:
                issues.append({"recording_id": rid, "category": "technical",
                               "code": "duplicate_content", "message": "Same video content as " + ", ".join(x for x in ids if x != rid)})
    return {"schema_version": "1.0", "recording_count": len(records), "issues": issues}
