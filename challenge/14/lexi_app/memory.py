from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from .config import MEMORY_DB_PATH
from .state import MemoryRecord, UTC, VocabularyEntry


def initialize_memory_db(db_path: Path = MEMORY_DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS study_memory (
                word TEXT PRIMARY KEY,
                lemma TEXT NOT NULL,
                meaning_in_context TEXT NOT NULL,
                source_sentence TEXT NOT NULL,
                context_note TEXT NOT NULL,
                why_it_matters TEXT NOT NULL DEFAULT '',
                study_priority TEXT NOT NULL DEFAULT 'medium',
                created_at TEXT NOT NULL,
                review_count INTEGER NOT NULL DEFAULT 0,
                last_reviewed_at TEXT,
                last_review_result TEXT
            )
            """
        )
        conn.commit()
    _migrate_schema(db_path)


def _migrate_schema(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(study_memory)").fetchall()}
        if "why_it_matters" not in columns:
            conn.execute("ALTER TABLE study_memory ADD COLUMN why_it_matters TEXT NOT NULL DEFAULT ''")
        if "study_priority" not in columns:
            conn.execute("ALTER TABLE study_memory ADD COLUMN study_priority TEXT NOT NULL DEFAULT 'medium'")
        conn.commit()


def load_memory_records(db_path: Path = MEMORY_DB_PATH) -> list[MemoryRecord]:
    if not db_path.exists():
        return []

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT
                word,
                lemma,
                meaning_in_context,
                source_sentence,
                context_note,
                why_it_matters,
                study_priority,
                created_at,
                review_count,
                last_reviewed_at,
                last_review_result
            FROM study_memory
            ORDER BY created_at ASC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def upsert_memory_record(entry: VocabularyEntry, db_path: Path = MEMORY_DB_PATH) -> None:
    initialize_memory_db(db_path)
    with sqlite3.connect(db_path) as conn:
        existing = conn.execute(
            "SELECT created_at, review_count, last_reviewed_at, last_review_result FROM study_memory WHERE word = ?",
            (entry["word"],),
        ).fetchone()

        created_at = existing[0] if existing else datetime.now(UTC).isoformat()
        review_count = existing[1] if existing else 0
        last_reviewed_at = existing[2] if existing else None
        last_review_result = existing[3] if existing else None

        conn.execute(
            """
            INSERT INTO study_memory (
                word,
                lemma,
                meaning_in_context,
                source_sentence,
                context_note,
                why_it_matters,
                study_priority,
                created_at,
                review_count,
                last_reviewed_at,
                last_review_result
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(word) DO UPDATE SET
                lemma = excluded.lemma,
                meaning_in_context = excluded.meaning_in_context,
                source_sentence = excluded.source_sentence,
                context_note = excluded.context_note,
                why_it_matters = excluded.why_it_matters,
                study_priority = excluded.study_priority,
                created_at = excluded.created_at,
                review_count = excluded.review_count,
                last_reviewed_at = excluded.last_reviewed_at,
                last_review_result = excluded.last_review_result
            """,
            (
                entry["word"],
                entry["lemma"],
                entry["meaning_in_context"],
                entry["source_sentence"],
                entry["context_note"],
                entry.get("why_it_matters", ""),
                entry.get("study_priority", "medium"),
                created_at,
                review_count,
                last_reviewed_at,
                last_review_result,
            ),
        )
        conn.commit()


def record_review_result(word: str, judgment: str, db_path: Path = MEMORY_DB_PATH) -> None:
    initialize_memory_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE study_memory
            SET review_count = review_count + 1,
                last_reviewed_at = ?,
                last_review_result = ?
            WHERE word = ?
            """,
            (datetime.now(UTC).isoformat(), judgment, word),
        )
        conn.commit()
