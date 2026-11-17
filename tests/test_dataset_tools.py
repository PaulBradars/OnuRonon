import json
import io
from pathlib import Path

import cv2
import numpy as np
import pytest

from dataset_tools.export import export_bundle, manifest, read_manifest
from dataset_tools.metadata import create_recording, read_recordings, update_recording
from dataset_tools.validation import validate_dataset
from dataset_tools.video_utils import commit_upload, inspect_video, sha256_file, stage_upload


@pytest.fixture
def dataset(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "data/raw_videos").mkdir(parents=True)
    (tmp_path / "config/gloss_vocabulary.json").write_text(json.dumps({
        "schema_version": "1.0", "glosses": [{"gloss_id": "APNI", "label_bn": "আপনি", "variants": ["default"]}]
    }), encoding="utf-8")
    return tmp_path


def video(path):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (32, 24))
    assert writer.isOpened()
    for _ in range(5):
        writer.write(np.zeros((24, 32, 3), dtype=np.uint8))
    writer.release()
    return inspect_video(path)


def add(dataset, filename="a.avi", gloss="APNI"):
    path = dataset / "data/raw_videos" / filename
    properties = video(path)
    return create_recording(dataset / "data/metadata/recordings.csv", {
        "gloss_id": gloss, "variant_id": "default", "signer_id": "signer_1",
        "video_path": f"data/raw_videos/{filename}", **properties,
        "dominant_hand": "unknown", "review_status": "unreviewed",
        "sign_start_seconds": "", "sign_end_seconds": "",
    })


def test_create_update_and_unique_ids(dataset):
    first = add(dataset)
    second = add(dataset, "b.avi")
    assert first["recording_id"] != second["recording_id"]
    changed = update_recording(dataset / "data/metadata/recordings.csv", first["recording_id"], {
        "sign_start_seconds": "0.1", "sign_end_seconds": "0.4", "notes": "review later"})
    assert changed["recording_id"] == first["recording_id"]
    assert changed["created_at"] == first["created_at"]
    assert len(read_recordings(dataset / "data/metadata/recordings.csv")) == 2


def test_invalid_annotations(dataset):
    first = add(dataset)
    path = dataset / "data/metadata/recordings.csv"
    for changes in ({"sign_start_seconds": "0.2"},
                    {"sign_start_seconds": "0.4", "sign_end_seconds": "0.1"},
                    {"review_status": "verified"}, {"signer_id": " "}):
        with pytest.raises(ValueError):
            update_recording(path, first["recording_id"], changes)


def test_video_validation_and_missing_video(dataset):
    first = add(dataset)
    report = validate_dataset(dataset)
    assert not [x for x in report["issues"] if x["category"] == "technical"]
    (dataset / first["video_path"]).unlink()
    assert "missing_video" in {x["code"] for x in validate_dataset(dataset)["issues"]}
    (dataset / first["video_path"]).write_bytes(b"not video")
    assert "unreadable_video" in {x["code"] for x in validate_dataset(dataset)["issues"]}


def test_duplicate_content_and_unknown_gloss(dataset):
    add(dataset)
    add(dataset, "b.avi", "UNKNOWN")
    codes = [x["code"] for x in validate_dataset(dataset)["issues"]]
    assert codes.count("duplicate_content") == 2
    assert "unknown_gloss" in codes


def test_export_import_round_trip(dataset):
    add(dataset)
    bundle = export_bundle(dataset)
    loaded = read_manifest(bundle["dataset_manifest.json"])
    assert loaded == manifest(dataset)
    assert len(loaded["recordings"]) == 1
    assert set(bundle) == {"recordings.csv", "gloss_vocabulary.json", "dataset_manifest.json", "validation_report.json"}
    with pytest.raises(ValueError):
        read_manifest('{"schema_version":"2.0","recordings":[]}')


def test_upload_preserves_bytes_and_rejects_fake_video(dataset):
    source = dataset / "sample.avi"
    video(source)
    original = source.read_bytes()
    staged = stage_upload(io.BytesIO(original), dataset / "data/raw_videos", ".avi")
    assert sha256_file(staged) == sha256_file(source)
    destination = dataset / "data/raw_videos/copy.avi"
    commit_upload(staged, destination)
    assert destination.read_bytes() == original
    invalid = dataset / "data/raw_videos/invalid.mp4"
    invalid.write_bytes(b"fake video")
    with pytest.raises(ValueError):
        inspect_video(invalid)
