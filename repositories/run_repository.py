import json
import sqlite3
from contextlib import closing
from datetime import timezone
from pathlib import Path
from typing import get_args

from pydantic import ValidationError

from models.errors import ERRORS, ApplicationError
from models.run import MAX_SQLITE_INTEGER, RunPage, RunRecord
from models.detection import DetectorName, FallbackReason

_LEGACY_COLUMNS = {"id", "created_at", "status", "duration_ms", "error_code"}
_COLUMNS = _LEGACY_COLUMNS | {"detector_used", "fallback_reason"}


class RunRepository:
    def __init__(self, path: Path) -> None:
        self._path = path
        codes = ", ".join(f"'{code}'" for code in ERRORS)
        detectors = ", ".join(f"'{value}'" for value in get_args(DetectorName))
        reasons = ", ".join(f"'{value}'" for value in get_args(FallbackReason))
        try:
            with closing(sqlite3.connect(self._path, timeout=5)) as conn, conn:
                conn.execute("BEGIN IMMEDIATE")
                tables = {row[0] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )}
                if tables - {"runs"}:
                    raise ApplicationError("database_unavailable")
                conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS runs (
                        id TEXT PRIMARY KEY NOT NULL,
                        created_at TEXT NOT NULL,
                        status TEXT NOT NULL CHECK (status IN ('success', 'failure')),
                        duration_ms INTEGER NOT NULL CHECK (duration_ms >= 0),
                        error_code TEXT CHECK (error_code IN ({codes})),
                        detector_used TEXT CHECK (detector_used IN ({detectors})),
                        fallback_reason TEXT CHECK (fallback_reason IS NULL OR
                            (fallback_reason IN ({reasons}) AND detector_used IS NOT NULL
                            AND detector_used = 'presidio')),
                        CHECK ((status = 'success' AND error_code IS NULL)
                            OR (status = 'failure' AND error_code IS NOT NULL))
                    )
                """)
                columns = {row[1] for row in conn.execute("PRAGMA table_info(runs)")}
                if columns == _LEGACY_COLUMNS:
                    conn.execute(
                        f"ALTER TABLE runs ADD COLUMN detector_used TEXT CHECK (detector_used IN ({detectors}))"
                    )
                    conn.execute(
                        f"ALTER TABLE runs ADD COLUMN fallback_reason TEXT CHECK "
                        f"(fallback_reason IS NULL OR (fallback_reason IN ({reasons}) "
                        f"AND detector_used IS NOT NULL AND detector_used = 'presidio'))"
                    )
                elif columns != _COLUMNS:
                    raise ApplicationError("database_unavailable")
        except sqlite3.Error:
            raise ApplicationError("database_unavailable") from None

    def add(self, run: RunRecord) -> None:
        try:
            with closing(sqlite3.connect(self._path, timeout=5)) as conn, conn:
                conn.execute(
                    "INSERT INTO runs (id, created_at, status, duration_ms, error_code, "
                    "detector_used, fallback_reason) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(run.id), run.created_at.astimezone(timezone.utc).isoformat(),
                        run.status, run.duration_ms, run.error_code, run.detector_used, run.fallback_reason,
                    ),
                )
        except sqlite3.Error:
            raise ApplicationError("database_unavailable") from None

    def list_runs(self, limit: int = 50, offset: int = 0) -> RunPage:
        if not 1 <= limit <= 100 or not 0 <= offset <= MAX_SQLITE_INTEGER:
            raise ApplicationError("invalid_request")
        try:
            with closing(sqlite3.connect(self._path, timeout=5)) as conn, conn:
                conn.row_factory = sqlite3.Row
                conn.execute("BEGIN")
                total = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
                rows = conn.execute(
                    "SELECT id, created_at, status, duration_ms, error_code, detector_used, fallback_reason FROM runs "
                    "ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
                items = [RunRecord.model_validate_json(json.dumps(dict(row))) for row in rows]
                return RunPage(items=items, total=total, limit=limit, offset=offset)
        except (sqlite3.Error, ValidationError, TypeError):
            raise ApplicationError("database_unavailable") from None
