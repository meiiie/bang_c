from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .config import HarnessConfig
from .schema import Problem


_QID_KEYS = ("qid", "id", "question_id", "index")
_QUESTION_KEYS = ("question", "prompt", "query", "text")
_CHOICE_KEYS = (
    "choices",
    "options",
    "answers",
    "candidates",
)
_LETTER_KEYS = tuple("ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def find_input_file(data_dir: Path, config: HarnessConfig) -> Path:
    for name in config.input_candidates:
        path = data_dir / name
        if path.exists():
            return path
    available = ", ".join(sorted(p.name for p in data_dir.iterdir())) if data_dir.exists() else ""
    raise FileNotFoundError(
        f"No contest input file found in {data_dir}. Available files: {available}"
    )


def load_problems(path: Path) -> list[Problem]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return _load_json(path)
    if suffix == ".csv":
        return _load_csv(path)
    raise ValueError(f"Unsupported input file type: {path}")


def _load_json(path: Path) -> list[Problem]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        rows = data.get("data") or data.get("questions") or data.get("items")
        if rows is None:
            rows = [data]
    elif isinstance(data, list):
        rows = data
    else:
        raise ValueError(f"JSON root must be an object or array: {path}")
    return [_problem_from_mapping(row, index) for index, row in enumerate(rows, start=1)]


def _load_csv(path: Path) -> list[Problem]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        return [_problem_from_mapping(row, index) for index, row in enumerate(reader, start=1)]


def _problem_from_mapping(row: Any, index: int) -> Problem:
    if not isinstance(row, dict):
        raise ValueError(f"Input row {index} must be an object")
    qid = _first_text(row, _QID_KEYS) or f"test_{index:04d}"
    question = _first_text(row, _QUESTION_KEYS)
    if not question:
        raise ValueError(f"Input row {index} is missing a question field")
    choices = _extract_choices(row)
    if not choices:
        raise ValueError(f"Input row {index} is missing choices/options")
    return Problem(qid=str(qid), question=str(question), choices=tuple(choices))


def _first_text(row: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    lowered = {str(key).lower(): value for key, value in row.items()}
    for key in keys:
        value = lowered.get(key.lower())
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _extract_choices(row: dict[str, Any]) -> list[str]:
    for key in _CHOICE_KEYS:
        value = _get_case_insensitive(row, key)
        parsed = _parse_choice_value(value)
        if parsed:
            return parsed

    lettered: list[str] = []
    for letter in _LETTER_KEYS:
        value = _get_case_insensitive(row, letter)
        if value is None:
            value = _get_case_insensitive(row, f"choice_{letter.lower()}")
        if value is None:
            value = _get_case_insensitive(row, f"option_{letter.lower()}")
        if value is None:
            break
        text = str(value).strip()
        if text:
            lettered.append(text)
    return lettered


def _get_case_insensitive(row: dict[str, Any], key: str) -> Any:
    for candidate, value in row.items():
        if str(candidate).lower() == key.lower():
            return value
    return None


def _parse_choice_value(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, dict):
        items = sorted(value.items(), key=lambda pair: str(pair[0]))
        return [str(item).strip() for _, item in items if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, (list, dict)):
        return _parse_choice_value(parsed)
    for separator in ("|||", "\t", "\n"):
        if separator in text:
            return [part.strip() for part in text.split(separator) if part.strip()]
    return []
