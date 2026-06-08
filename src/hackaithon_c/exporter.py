from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

from .schema import Prediction


def write_predictions(path: Path, predictions: list[Prediction]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["qid", "answer"])
        writer.writeheader()
        for prediction in predictions:
            writer.writerow({"qid": prediction.qid, "answer": prediction.answer})


def write_trace(trace_dir: Path, predictions: list[Prediction]) -> None:
    trace_dir.mkdir(parents=True, exist_ok=True)
    path = trace_dir / "predictions.trace.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for prediction in predictions:
            handle.write(json.dumps(asdict(prediction), ensure_ascii=False) + "\n")
