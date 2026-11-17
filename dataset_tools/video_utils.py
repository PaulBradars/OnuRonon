"""Preserve source videos and extract technical properties with OpenCV."""

import hashlib
import math
import os
from pathlib import Path
from uuid import uuid4

import cv2

SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".avi"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_video(path: Path) -> dict:
    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            raise ValueError("Video cannot be decoded")
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if not math.isfinite(fps) or fps <= 0:
            raise ValueError("Video has invalid FPS")
        if frame_count <= 0:
            raise ValueError("Video reports zero frames")
        if width <= 0 or height <= 0:
            raise ValueError("Video has invalid dimensions")
        decoded, frame = capture.read()
        if not decoded or frame is None:
            raise ValueError("Video has no decodable frames")
        return {"fps": fps, "frame_count": frame_count, "width": width,
                "height": height, "duration_seconds": frame_count / fps}
    finally:
        capture.release()


def stage_upload(upload, directory: Path, extension: str) -> Path:
    """Write upload bytes unchanged to a temporary file for validation."""
    if extension.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError("Use an MP4, MOV, or AVI file")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f".upload-{uuid4().hex}{extension.lower()}"
    try:
        with path.open("xb") as target:
            upload.seek(0)
            for chunk in iter(lambda: upload.read(1024 * 1024), b""):
                target.write(chunk)
        return path
    except Exception:
        path.unlink(missing_ok=True)
        raise


def commit_upload(staged: Path, destination: Path) -> None:
    if destination.exists():
        raise FileExistsError(destination)
    os.replace(staged, destination)
