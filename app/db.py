"""SQLite-backed job history. One file, no server."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    job_uuid     TEXT UNIQUE NOT NULL,
    source_path  TEXT NOT NULL,
    source_stem  TEXT NOT NULL,
    src_lang     TEXT,
    transcript   TEXT,
    translations TEXT,            -- JSON: {lang: text}
    engines      TEXT,            -- JSON: list of engine ids
    languages    TEXT,            -- JSON: list of lang codes
    status       TEXT NOT NULL,   -- queued | asr | translating | synthesizing | done | error
    error        TEXT,
    created_at   REAL NOT NULL,
    updated_at   REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS artifacts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    job_uuid     TEXT NOT NULL,
    engine       TEXT NOT NULL,
    language     TEXT NOT NULL,
    output_path  TEXT NOT NULL,
    duration_s   REAL,
    created_at   REAL NOT NULL,
    FOREIGN KEY (job_uuid) REFERENCES jobs(job_uuid)
);

CREATE INDEX IF NOT EXISTS idx_artifacts_job ON artifacts(job_uuid);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC);
"""


class Database:
    """Thin wrapper. Thread-safe via a single shared connection + lock."""

    def __init__(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    @contextmanager
    def _cur(self):
        with self._lock:
            cur = self._conn.cursor()
            try:
                yield cur
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
            finally:
                cur.close()

    # ---- jobs ---------------------------------------------------------
    def create_job(self, job_uuid: str, source_path: str, source_stem: str) -> None:
        now = time.time()
        with self._cur() as cur:
            cur.execute(
                "INSERT INTO jobs (job_uuid, source_path, source_stem, status, created_at, updated_at)"
                " VALUES (?, ?, ?, 'queued', ?, ?)",
                (job_uuid, source_path, source_stem, now, now),
            )

    def update_job(
        self,
        job_uuid: str,
        *,
        status: Optional[str] = None,
        src_lang: Optional[str] = None,
        transcript: Optional[str] = None,
        translations: Optional[Dict[str, str]] = None,
        engines: Optional[List[str]] = None,
        languages: Optional[List[str]] = None,
        error: Optional[str] = None,
    ) -> None:
        sets: List[str] = []
        vals: List[Any] = []
        if status is not None:
            sets.append("status = ?"); vals.append(status)
        if src_lang is not None:
            sets.append("src_lang = ?"); vals.append(src_lang)
        if transcript is not None:
            sets.append("transcript = ?"); vals.append(transcript)
        if translations is not None:
            sets.append("translations = ?"); vals.append(json.dumps(translations, ensure_ascii=False))
        if engines is not None:
            sets.append("engines = ?"); vals.append(json.dumps(engines))
        if languages is not None:
            sets.append("languages = ?"); vals.append(json.dumps(languages))
        if error is not None:
            sets.append("error = ?"); vals.append(error)
        if not sets:
            return
        sets.append("updated_at = ?"); vals.append(time.time())
        vals.append(job_uuid)
        with self._cur() as cur:
            cur.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE job_uuid = ?", vals)

    def get_job(self, job_uuid: str) -> Optional[Dict[str, Any]]:
        with self._cur() as cur:
            cur.execute("SELECT * FROM jobs WHERE job_uuid = ?", (job_uuid,))
            row = cur.fetchone()
            if not row:
                return None
            job = dict(row)
            cur.execute("SELECT * FROM artifacts WHERE job_uuid = ? ORDER BY id", (job_uuid,))
            job["artifacts"] = [dict(r) for r in cur.fetchall()]
            return job

    def list_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._cur() as cur:
            cur.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,))
            jobs = []
            for row in cur.fetchall():
                j = dict(row)
                cur.execute("SELECT engine, language, output_path, duration_s FROM artifacts WHERE job_uuid = ?", (j["job_uuid"],))
                j["artifacts"] = [dict(r) for r in cur.fetchall()]
                jobs.append(j)
            return jobs

    # ---- artifacts ----------------------------------------------------
    def add_artifact(
        self,
        job_uuid: str,
        engine: str,
        language: str,
        output_path: str,
        duration_s: Optional[float] = None,
    ) -> None:
        with self._cur() as cur:
            cur.execute(
                "INSERT INTO artifacts (job_uuid, engine, language, output_path, duration_s, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (job_uuid, engine, language, output_path, duration_s, time.time()),
            )

    def list_artifacts_for_playback(self, limit: int = 200) -> List[Dict[str, Any]]:
        with self._cur() as cur:
            cur.execute(
                "SELECT a.id, a.job_uuid, a.engine, a.language, a.output_path, a.duration_s, j.source_stem"
                " FROM artifacts a JOIN jobs j ON a.job_uuid = j.job_uuid"
                " ORDER BY a.id DESC LIMIT ?",
                (limit,),
            )
            return [dict(r) for r in cur.fetchall()]


_db_singleton: Database | None = None


def get_db() -> Database:
    global _db_singleton
    if _db_singleton is None:
        from .config import get_config
        path = get_config().get("paths.db_path", "./jobs.db")
        _db_singleton = Database(path)
    return _db_singleton
