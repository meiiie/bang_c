from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal


EventStatus = Literal["started", "completed", "warning", "failed", "skipped"]


@dataclass(frozen=True)
class RunEvent:
    schema_version: str
    created_at_utc: str
    event_type: str
    status: EventStatus
    message: str
    qid: str | None
    payload: dict[str, Any]


def build_event(
    event_type: str,
    status: EventStatus,
    message: str,
    *,
    qid: str | None = None,
    payload: dict[str, Any] | None = None,
) -> RunEvent:
    return RunEvent(
        schema_version="neko_core.run_event.v1",
        created_at_utc=datetime.now(UTC).isoformat(timespec="seconds"),
        event_type=event_type,
        status=status,
        message=message,
        qid=qid,
        payload=payload or {},
    )


def write_events(path: Path, events: tuple[RunEvent, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(asdict(event), ensure_ascii=False) for event in events]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def load_events(target: Path) -> tuple[RunEvent, ...]:
    path = target / "events.jsonl" if target.is_dir() else target
    if not path.exists():
        return ()

    events: list[RunEvent] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"Expected object JSONL row in {path}")
        if row.get("schema_version") != "neko_core.run_event.v1":
            raise ValueError(f"Unsupported event schema in {path}")
        payload = row.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}
        events.append(
            RunEvent(
                schema_version=str(row["schema_version"]),
                created_at_utc=str(row["created_at_utc"]),
                event_type=str(row["event_type"]),
                status=_event_status(row.get("status")),
                message=str(row["message"]),
                qid=_string_or_none(row.get("qid")),
                payload=payload,
            )
        )
    return tuple(events)


def render_events(events: tuple[RunEvent, ...], *, source: Path) -> str:
    lines = [
        "Neko Core Events",
        f"Source: {source}",
        f"Events: {len(events)}",
        "",
    ]
    if not events:
        lines.append("- none")
        return "\n".join(lines)

    for event in events:
        qid = f" [{event.qid}]" if event.qid else ""
        lines.append(
            f"- {event.created_at_utc} {event.status.upper()} "
            f"{event.event_type}{qid}: {event.message}"
        )
    return "\n".join(lines)


def _event_status(value: Any) -> EventStatus:
    status = str(value)
    if status in {"started", "completed", "warning", "failed", "skipped"}:
        return status  # type: ignore[return-value]
    return "warning"


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
