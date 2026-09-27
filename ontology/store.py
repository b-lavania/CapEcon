"""Durable GrowthDecisionRecord store — SQLite plus JSONL export."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STORE_DIR = Path(__file__).resolve().parent.parent / "data" / "records"
DB_PATH = STORE_DIR / "capecon.sqlite"


def _ensure_dir(store_dir: Path) -> Path:
    store_dir.mkdir(parents=True, exist_ok=True)
    return store_dir


def db_path(store_dir: Path | None = None) -> Path:
    d = _ensure_dir(store_dir or STORE_DIR)
    return d / "capecon.sqlite"


def connect(store_dir: Path | None = None) -> sqlite3.Connection:
    path = db_path(store_dir)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS decisions (
            record_id TEXT PRIMARY KEY,
            vertical TEXT,
            entity_type TEXT,
            payload TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS triage (
            record_id TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'pending',
            assignee TEXT,
            owner_role TEXT,
            notes TEXT,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS hook_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hook TEXT NOT NULL,
            record_id TEXT,
            detail TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def upsert_record(record: dict[str, Any], store_dir: Path | None = None) -> Path:
    """Write GDR to SQLite and append JSONL (audit)."""
    store_dir = _ensure_dir(store_dir or STORE_DIR)
    record_id = str(record.get("record_id") or "")
    if not record_id:
        raise ValueError("record_id required")
    entity_type = (record.get("subject") or {}).get("entity_type", "")
    vertical = str(record.get("vertical", "unknown"))
    payload = json.dumps(record)
    with connect(store_dir) as conn:
        conn.execute(
            """
            INSERT INTO decisions (record_id, vertical, entity_type, payload, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(record_id) DO UPDATE SET
                vertical=excluded.vertical,
                entity_type=excluded.entity_type,
                payload=excluded.payload,
                updated_at=excluded.updated_at
            """,
            (record_id, vertical, entity_type, payload, _now()),
        )
        conn.commit()
    jsonl = store_dir / f"{vertical}.jsonl"
    with open(jsonl, "a", encoding="utf-8") as f:
        f.write(payload + "\n")
    return jsonl


def append_record(record: dict[str, Any], store_dir: Path | None = None) -> Path:
    """Backward-compatible alias used by Radar / Flywheel."""
    return upsert_record(record, store_dir=store_dir)


def read_records(vertical: str | None = None, store_dir: Path | None = None) -> list[dict[str, Any]]:
    """Prefer SQLite; fall back to JSONL if the DB is empty."""
    store_dir = store_dir or STORE_DIR
    records: list[dict[str, Any]] = []
    db = db_path(store_dir)
    if db.exists():
        with connect(store_dir) as conn:
            if vertical:
                rows = conn.execute(
                    "SELECT payload FROM decisions WHERE vertical = ? ORDER BY updated_at",
                    (vertical,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT payload FROM decisions ORDER BY updated_at").fetchall()
            records = [json.loads(r["payload"]) for r in rows]
        if records:
            return records
    if not store_dir.exists():
        return []
    paths = list(store_dir.glob("*.jsonl"))
    if vertical:
        paths = [p for p in paths if p.stem == vertical]
    for p in paths:
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
    return records


def set_triage(
    record_id: str,
    *,
    status: str,
    assignee: str | None = None,
    owner_role: str | None = None,
    notes: str | None = None,
    store_dir: Path | None = None,
) -> None:
    with connect(store_dir) as conn:
        conn.execute(
            """
            INSERT INTO triage (record_id, status, assignee, owner_role, notes, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(record_id) DO UPDATE SET
                status=excluded.status,
                assignee=COALESCE(excluded.assignee, triage.assignee),
                owner_role=COALESCE(excluded.owner_role, triage.owner_role),
                notes=COALESCE(excluded.notes, triage.notes),
                updated_at=excluded.updated_at
            """,
            (record_id, status, assignee, owner_role, notes, _now()),
        )
        conn.commit()


def get_triage(record_id: str, store_dir: Path | None = None) -> dict[str, Any] | None:
    with connect(store_dir) as conn:
        row = conn.execute("SELECT * FROM triage WHERE record_id = ?", (record_id,)).fetchone()
    return dict(row) if row else None


def list_triage(store_dir: Path | None = None) -> dict[str, dict[str, Any]]:
    with connect(store_dir) as conn:
        rows = conn.execute("SELECT * FROM triage").fetchall()
    return {r["record_id"]: dict(r) for r in rows}


def log_hook(hook: str, *, record_id: str | None = None, detail: dict[str, Any] | None = None, store_dir: Path | None = None) -> None:
    with connect(store_dir) as conn:
        conn.execute(
            "INSERT INTO hook_audit (hook, record_id, detail, created_at) VALUES (?, ?, ?, ?)",
            (hook, record_id, json.dumps(detail or {}), _now()),
        )
        conn.commit()


def list_hooks(store_dir: Path | None = None, limit: int = 50) -> list[dict[str, Any]]:
    with connect(store_dir) as conn:
        rows = conn.execute(
            "SELECT hook, record_id, detail, created_at FROM hook_audit ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    out = []
    for r in rows:
        item = dict(r)
        try:
            item["detail"] = json.loads(item["detail"]) if item.get("detail") else {}
        except json.JSONDecodeError:
            pass
        out.append(item)
    return out
