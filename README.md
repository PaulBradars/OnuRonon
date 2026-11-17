# BdSL video dataset manager

This repository contains the first dataset management component for OnuRonon. It registers original BdSL sign videos and their annotations. The starter vocabulary has provisional labels for `APNI` (আপনি), `CHA` (চা), and `KHAWA` (খাওয়া). A BdSL fluent reviewer should verify the labels and each recording. No example videos are included.

## Windows setup

From the repository directory in PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run dataset_tools/app.py
```

If PowerShell blocks activation, run `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` and `.\.venv\Scripts\python.exe -m streamlit run dataset_tools/app.py` directly. Use a current Python version supported by the pinned dependency ranges (Python 3.11–3.13 recommended).

## Record a sign

Use a front facing camera. Keep both hands, upper body, and face visible. Use consistent lighting; prefer 1080p at 30 FPS. Record a neutral pose before and after the sign. Obtain the signer's consent and a BdSL expert's validation before marking a recording verified.

## Upload and annotate

1. Open **Upload**, choose an MP4, MOV, or AVI, a gloss, variant, signer ID, and dominant hand. Preview the video and select **Register recording**. Registration checks that OpenCV can decode the file and rejects duplicate content. The original bytes are saved without recompression.
2. Open **Recordings & annotations**, select the recording, preview it, and enter start and end times in seconds. Both boundaries may be blank until annotation is ready. Save edits there later. Select `verified` only after linguistic review and enter a reviewer ID.
3. Open **Validation & export** to see technical and annotation warnings and download the CSV, vocabulary JSON, manifest JSON, or validation report JSON. The dashboard summarizes recording and warning counts even when the dataset is empty.

To add a gloss or variant, edit `config/gloss_vocabulary.json`: add a unique `gloss_id`, a Bangla `label_bn`, a `variants` array, and a `linguistic_status`. Restart or rerun the app. The app reads these choices from the file rather than hardcoding them.

## Validate and test

The Validation & export page runs the checks on demand. It reports missing or unreadable videos, bad FPS/frame counts/dimensions, inconsistent video metadata, duplicate SHA-256 content, unknown gloss IDs, missing signer IDs, and invalid or missing sign boundaries. A technical pass does not mean a sign is linguistically correct.

```powershell
python -m pytest tests/test_dataset_tools.py -q
```

## Data contract (schema 1.0)

`data/metadata/recordings.csv` is UTF-8 with one row per video. Its columns, in order, are:

| Column | Meaning |
| --- | --- |
| `recording_id` | Stable generated `rec_` UUID. |
| `gloss_id`, `variant_id`, `signer_id` | Vocabulary key, selected variant, and signer pseudonym. |
| `video_path` | Relative path from repository root to untouched source file. |
| `fps`, `frame_count`, `width`, `height`, `duration_seconds` | OpenCV properties at registration; duration is frame count / FPS. |
| `sign_start_seconds`, `sign_end_seconds` | Decimal seconds in the source video; both blank until annotated. Must satisfy 0 ≤ start < end ≤ duration. |
| `dominant_hand` | `unknown`, `left`, `right`, or `both`. |
| `review_status` | `unreviewed`, `needs_revision`, or `verified`; technical validation never sets this field. |
| `reviewer_id`, `notes` | Reviewer pseudonym and free text. `verified` requires a reviewer ID. |
| `created_at` | UTC ISO 8601 registration timestamp, unchanged on edits. |

`config/gloss_vocabulary.json` has `schema_version: "1.0"` and a `glosses` array. Each entry has `gloss_id`, `label_bn`, `variants`, and `linguistic_status`. `dataset_manifest.json` combines the vocabulary and recording rows under `schema_version: "1.0"`; `read_manifest` can parse this export for downstream tools. `validation_report.json` contains `schema_version`, `recording_count`, and `issues` (`recording_id`, `category`, `code`, `message`). Exported files contain metadata only. Keep the referenced source videos alongside them for the next processing stage.

The CSV is written atomically, but the prototype assumes one person edits it at a time. Video preview depends on browser codec support. MOV and AVI can pass OpenCV validation while some browsers cannot preview them. No landmark extraction, motion generation, or animation is implemented here.
