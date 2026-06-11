"""Build the labeled per-bucket dev sets for the router-vs-incumbent battery.

DEV-SIDE ONLY (network + pyarrow + gdown). Produces, per bucket, a harness-loadable
questions file (qid/question/choices) and a gold file (qid,answer):

- quant   : ViGEText test split, subjects mathematics/physics/chemistry (ungated).
- civics  : ViGEText test split, subject civic_education — the legal/admin RAG proxy.
- reading : ViMMRC 1.0 (passage-grounded MCQ; the public Google Drive file the
            SEACrowd loader uses). ViMMRC 2.0 is gated — fallback documented here
            on purpose (notes/lessons.md: datasets vanish, always have a fallback).

Sampling is seeded (fixed) so every battery re-run measures the SAME items.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import random
import re
import zipfile
from pathlib import Path

import requests

VIGETEXT_PARQUET_API = (
    "https://huggingface.co/api/datasets/uitnlp/ViGEText_17to23/parquet/default/test"
)
VIMMRC_DRIVE_ID = "14Rq-YANUv8qyi4Ze8ReEAEu_uxgcV_Yk"
SUBJECT_PATTERN = re.compile(r"^\d{4}_[a-z]+_(.+?)_\d+_\d+$")
OPTION_LINE = re.compile(r"^([A-Z])\.\s*(.*)$")
SEED = 42
SAMPLE_PER_BUCKET = 150

# Subject tokens exactly as they appear in ViGEText ids (note: "civic education"
# contains a SPACE). Verified 2026-06-11: mathematics=282, physics=248, chemistry=264,
# civic education=280 in the test split.
QUANT_SUBJECTS = {"mathematics", "physics", "chemistry"}
CIVICS_SUBJECTS = {"civic education"}


def parse_vigetext_input(text: str) -> tuple[str, list[str]] | None:
    """ViGEText `input` = question text with trailing 'A. ...' option lines."""
    lines = text.splitlines()
    first_option = None
    for index, line in enumerate(lines):
        if OPTION_LINE.match(line.strip()):
            first_option = index
            break
    if first_option is None or first_option == 0:
        return None
    question = "\n".join(lines[:first_option]).strip()
    choices: list[str] = []
    expected = "A"
    for line in lines[first_option:]:
        match = OPTION_LINE.match(line.strip())
        if match and match.group(1) == expected:
            choices.append(match.group(2).strip())
            expected = chr(ord(expected) + 1)
        elif choices:
            choices[-1] = f"{choices[-1]}\n{line.strip()}".strip()
    if not question or len(choices) < 2:
        return None
    return question, choices


def fetch_vigetext() -> list[dict]:
    import pyarrow.parquet as pq

    urls = requests.get(VIGETEXT_PARQUET_API, timeout=60).json()
    rows: list[dict] = []
    for url in urls:
        blob = requests.get(url, timeout=300).content
        table = pq.read_table(io.BytesIO(blob))
        rows.extend(table.to_pylist())
    return rows


def vigetext_bucket(rows: list[dict], subjects: set[str]) -> list[dict]:
    items = []
    for row in rows:
        match = SUBJECT_PATTERN.match(str(row["id"]))
        if not match or match.group(1) not in subjects:
            continue
        parsed = parse_vigetext_input(str(row["input"]))
        if parsed is None:
            continue
        question, choices = parsed
        target = str(row["target"]).strip().upper()
        if target not in "ABCDEFGHIJ"[: len(choices)]:
            continue
        items.append(
            {"qid": str(row["id"]), "question": question, "choices": choices, "answer": target}
        )
    return items


def fetch_vimmrc(work_dir: Path) -> list[dict]:
    """ViMMRC 1.0: one JSON per reading text {article, questions, options, answers}."""
    import gdown

    archive = work_dir / "vimmrc.zip"
    if not archive.exists():
        gdown.download(id=VIMMRC_DRIVE_ID, output=str(archive), quiet=False)
    items: list[dict] = []
    with zipfile.ZipFile(archive) as bundle:
        names = [
            n
            for n in bundle.namelist()
            if n.lower().endswith(".json")
            # macOS zips ship AppleDouble resource forks (__MACOSX/._foo.json):
            # binary files with a .json suffix — not data.
            and "__MACOSX" not in n
            and not Path(n).name.startswith("._")
        ]
        # Prefer the held-out split when present; otherwise take everything.
        test_names = [n for n in names if "test" in n.lower()] or names
        for name in sorted(test_names):
            data = json.loads(bundle.read(name).decode("utf-8-sig"))
            article = str(data.get("article", "")).strip()
            questions = data.get("questions", [])
            options = data.get("options", [])
            answers = data.get("answers", [])
            if not article or not questions:
                continue
            stem = Path(name).stem
            for index, (question, opts, answer) in enumerate(
                zip(questions, options, answers)
            ):
                choices = [re.sub(r"^[A-D]\.\s*", "", str(o)).strip() for o in opts]
                letter = str(answer).strip().upper()[:1]
                if len(choices) < 2 or letter not in "ABCDEFGHIJ"[: len(choices)]:
                    continue
                items.append(
                    {
                        "qid": f"vimmrc_{stem}_{index}",
                        "question": f"{article}\n\nCâu hỏi: {question}",
                        "choices": choices,
                        "answer": letter,
                    }
                )
    return items


def write_bucket(name: str, items: list[dict], out_dir: Path) -> None:
    rng = random.Random(SEED)
    sample = items if len(items) <= SAMPLE_PER_BUCKET else rng.sample(items, SAMPLE_PER_BUCKET)
    questions = [
        {"qid": item["qid"], "question": item["question"], "choices": item["choices"]}
        for item in sample
    ]
    (out_dir / f"{name}.json").write_text(
        json.dumps(questions, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    with (out_dir / f"{name}.gold.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["qid", "answer"])
        for item in sample:
            writer.writerow([item["qid"], item["answer"]])
    print(f"{name}: {len(sample)} items (from {len(items)} available)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="devsets")
    args = parser.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    vigetext = fetch_vigetext()
    write_bucket("quant", vigetext_bucket(vigetext, QUANT_SUBJECTS), out_dir)
    write_bucket("civics", vigetext_bucket(vigetext, CIVICS_SUBJECTS), out_dir)
    write_bucket("reading", fetch_vimmrc(out_dir), out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
