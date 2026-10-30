"""Append-only audit trail: output/audit_trail.json (a JSON array; runs are never wiped)."""
from __future__ import annotations

import json
import threading
from datetime import datetime
from typing import Any

from backend.models import AuditRecord, TeamDeps
from core.config import AUDIT_TRAIL, MODEL

_lock = threading.Lock()
MAX_FIELD_CHARS = 4000


def _clip(value: Any) -> Any:
    """Keep huge tool results readable while leaving the record valid JSON."""
    text = json.dumps(value, default=str)
    if len(text) <= MAX_FIELD_CHARS:
        return json.loads(text)
    return {"truncated": True, "preview": text[:MAX_FIELD_CHARS]}


def _append(record: AuditRecord) -> None:
    with _lock:
        AUDIT_TRAIL.parent.mkdir(parents=True, exist_ok=True)
        try:
            records = json.loads(AUDIT_TRAIL.read_text(encoding="utf-8")) if AUDIT_TRAIL.exists() else []
            if not isinstance(records, list):
                records = [records]
        except json.JSONDecodeError:
            # Never lose the old trail: keep the unreadable file and start a new one.
            AUDIT_TRAIL.rename(AUDIT_TRAIL.with_suffix(f".corrupt-{datetime.now():%Y%m%d%H%M%S}.json"))
            records = []
        records.append(record.model_dump())
        tmp = AUDIT_TRAIL.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(records, indent=1, default=str), encoding="utf-8")
        tmp.replace(AUDIT_TRAIL)


def log(deps: TeamDeps, kind: str, data: Any = None, usage: dict | None = None) -> None:
    _append(AuditRecord(
        ts=datetime.now().isoformat(timespec="milliseconds"), run_id=deps.work.run_id,
        ticket_id=deps.work.ticket_id, step=deps.work.next_step(), agent=deps.agent,
        chain=list(deps.chain), depth=deps.depth, kind=kind, model=MODEL, data=_clip(data), usage=usage))
