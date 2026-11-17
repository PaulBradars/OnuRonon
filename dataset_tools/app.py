"""Run with: streamlit run dataset_tools/app.py"""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dataset_tools.export import export_bundle
from dataset_tools.metadata import create_recording, read_recordings, update_recording
from dataset_tools.validation import validate_dataset
from dataset_tools.video_utils import commit_upload, inspect_video, sha256_file, stage_upload
from dataset_tools.vocabulary import load_vocabulary

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "data/metadata/recordings.csv"
VOCAB = ROOT / "config/gloss_vocabulary.json"
RAW = ROOT / "data/raw_videos"


def labels():
    entries = load_vocabulary(VOCAB)["glosses"]
    return {entry["gloss_id"]: entry for entry in entries}


def register(upload, gloss_id, variant_id, signer_id, dominant_hand):
    staged = stage_upload(upload, RAW, Path(upload.name).suffix)
    destination = None
    try:
        properties = inspect_video(staged)
        incoming_hash = sha256_file(staged)
        for row in read_recordings(CSV).to_dict("records"):
            existing = ROOT / row["video_path"]
            if existing.is_file() and sha256_file(existing) == incoming_hash:
                raise ValueError(f"This video is already registered as {row['recording_id']}")
        from uuid import uuid4
        destination = RAW / f"{uuid4().hex}{Path(upload.name).suffix.lower()}"
        commit_upload(staged, destination)
        try:
            return create_recording(CSV, {
                "gloss_id": gloss_id, "variant_id": variant_id, "signer_id": signer_id.strip(),
                "video_path": destination.relative_to(ROOT).as_posix(), **properties,
                "sign_start_seconds": "", "sign_end_seconds": "",
                "dominant_hand": dominant_hand, "review_status": "unreviewed",
                "reviewer_id": "", "notes": "",
            })
        except Exception:
            destination.unlink(missing_ok=True)
            raise
    finally:
        staged.unlink(missing_ok=True)


st.set_page_config(page_title="BdSL dataset manager", layout="wide")
st.title("BdSL video dataset manager")
st.caption("Source recordings and technical checks. Gloss labels and linguistic review are provisional.")

try:
    vocab = labels()
    records = read_recordings(CSV)
except (ValueError, OSError, KeyError) as exc:
    st.error(str(exc))
    st.stop()

tabs = st.tabs(["Dashboard", "Upload", "Recordings & annotations", "Validation & export"])

with tabs[0]:
    total = len(records)
    verified = int((records.review_status == "verified").sum()) if total else 0
    a, b, c, d = st.columns(4)
    a.metric("Recordings", total)
    b.metric("Glosses represented", records.gloss_id.nunique() if total else 0)
    c.metric("Verified", verified)
    d.metric("Unverified", total - verified)
    st.subheader("Recordings per gloss")
    st.dataframe(records.groupby("gloss_id").size().rename("recordings").reset_index() if total else pd.DataFrame(columns=["gloss_id", "recordings"]), hide_index=True)
    report = validate_dataset(ROOT)
    annotations = [x for x in report["issues"] if x["category"] == "annotation"]
    technical = [x for x in report["issues"] if x["category"] == "technical"]
    st.metric("Annotation warnings", len(annotations))
    st.metric("Technical warnings", len(technical))

with tabs[1]:
    upload = st.file_uploader("Video", type=["mp4", "mov", "avi"])
    if upload is not None:
        st.video(upload)
    gloss_id = st.selectbox("Gloss ID", list(vocab), format_func=lambda x: f"{x} — {vocab[x].get('label_bn', '')}", key="upload_gloss")
    variants = vocab[gloss_id].get("variants", ["default"])
    with st.form("upload", clear_on_submit=True):
        variant_id = st.selectbox("Variant ID", variants)
        signer_id = st.text_input("Signer ID")
        hand = st.selectbox("Dominant hand", ["unknown", "right", "left", "both"])
        submitted = st.form_submit_button("Register recording")
    if submitted:
        if upload is None or not signer_id.strip():
            st.error("Choose a video and enter a signer ID.")
        else:
            try:
                row = register(upload, gloss_id, variant_id, signer_id, hand)
                st.success(f"Registered {row['recording_id']}. Add sign boundaries in Recordings & annotations.")
            except (ValueError, OSError) as exc:
                st.error(str(exc))

with tabs[2]:
    st.dataframe(records, hide_index=True, width="stretch")
    if not records.empty:
        rid = st.selectbox("Recording to edit", records.recording_id.tolist())
        row = records.loc[records.recording_id == rid].iloc[0].to_dict()
        video = ROOT / row["video_path"]
        if video.is_file():
            st.video(video.read_bytes())
        else:
            st.warning("Video file is missing")
        with st.form("annotation"):
            gloss_id = st.selectbox("Gloss ID", list(vocab), index=list(vocab).index(row["gloss_id"]) if row["gloss_id"] in vocab else 0)
            variants = vocab[gloss_id].get("variants", ["default"])
            variant_id = st.selectbox("Variant ID", variants, index=variants.index(row["variant_id"]) if row["variant_id"] in variants else 0)
            signer_id = st.text_input("Signer ID", row["signer_id"])
            hand_options = ["unknown", "right", "left", "both"]
            hand = st.selectbox("Dominant hand", hand_options, index=hand_options.index(row["dominant_hand"]) if row["dominant_hand"] in hand_options else 0)
            start = st.text_input("Sign start (seconds)", row["sign_start_seconds"])
            end = st.text_input("Sign end (seconds)", row["sign_end_seconds"])
            statuses = ["unreviewed", "needs_revision", "verified"]
            status = st.selectbox("Review status", statuses, index=statuses.index(row["review_status"]) if row["review_status"] in statuses else 0)
            reviewer = st.text_input("Reviewer ID", row["reviewer_id"])
            notes = st.text_area("Notes", row["notes"])
            saved = st.form_submit_button("Save annotations")
        if saved:
            try:
                update_recording(CSV, rid, {"gloss_id": gloss_id, "variant_id": variant_id,
                    "signer_id": signer_id, "dominant_hand": hand,
                    "sign_start_seconds": start.strip(), "sign_end_seconds": end.strip(),
                    "review_status": status, "reviewer_id": reviewer, "notes": notes})
                st.success("Annotations saved")
                st.rerun()
            except (ValueError, KeyError) as exc:
                st.error(str(exc))

with tabs[3]:
    report = validate_dataset(ROOT)
    st.write(f"Checked {report['recording_count']} recordings; {len(report['issues'])} warnings")
    st.dataframe(pd.DataFrame(report["issues"], columns=["recording_id", "category", "code", "message"]), hide_index=True, width="stretch")
    for name, content in export_bundle(ROOT).items():
        st.download_button(f"Download {name}", content, file_name=name,
                           mime="text/csv" if name.endswith(".csv") else "application/json")
