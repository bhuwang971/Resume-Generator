from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Iterator


class TrackerDatabase:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS tracker_entries (
                    id TEXT PRIMARY KEY,
                    dedupe_key TEXT NOT NULL UNIQUE,
                    company TEXT NOT NULL DEFAULT '',
                    role TEXT NOT NULL DEFAULT '',
                    location TEXT NOT NULL DEFAULT '',
                    compensation TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'Saved',
                    date_added TEXT NOT NULL,
                    application_date TEXT NOT NULL DEFAULT '',
                    job_url TEXT NOT NULL DEFAULT '',
                    docx_path TEXT NOT NULL DEFAULT '',
                    pdf_path TEXT NOT NULL DEFAULT '',
                    folder_path TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_tracker_status
                    ON tracker_entries(status);
                CREATE INDEX IF NOT EXISTS idx_tracker_date_added
                    ON tracker_entries(date_added DESC);
                """
            )
