from __future__ import annotations

from datetime import date, datetime
import os
from pathlib import Path
import re
from uuid import uuid4

from resume_tool.schema import ResumeMetadata
from resume_tool.render import RenderedResumePaths
from resume_tool.utils import is_within

from .database import TrackerDatabase
from .models import TRACKER_STATUSES, TrackerRecord


class TrackerService:
    def __init__(self, database: TrackerDatabase):
        self.database = database
        self.database.initialize()

    def list(self) -> list[TrackerRecord]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM tracker_entries ORDER BY date_added DESC, updated_at DESC"
            ).fetchall()
        return [_record(row) for row in rows]

    def get(self, record_id: str) -> TrackerRecord | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM tracker_entries WHERE id=?", (record_id,),
            ).fetchone()
        return _record(row) if row else None

    def upsert_from_generation(
        self,
        metadata: ResumeMetadata,
        paths: RenderedResumePaths,
        folder_path: str | Path,
    ) -> tuple[TrackerRecord, bool]:
        return self.upsert(
            company=metadata.company,
            role=metadata.role,
            location=metadata.location,
            compensation=metadata.compensation,
            job_url=metadata.job_url,
            docx_path=str(paths.docx_path or ""),
            pdf_path=str(paths.pdf_path or ""),
            folder_path=str(Path(folder_path).resolve()),
        )

    def upsert(
        self,
        *,
        company: str,
        role: str,
        location: str = "",
        compensation: str = "",
        job_url: str = "",
        docx_path: str = "",
        pdf_path: str = "",
        folder_path: str = "",
        status: str = "Saved",
        date_added: str = "",
        application_date: str = "",
    ) -> tuple[TrackerRecord, bool]:
        normalized_status = _status(status)
        key = dedupe_key(company, role, job_url)
        now = _timestamp()
        added = date_added or date.today().isoformat()
        with self.database.connect() as connection:
            existing = connection.execute(
                "SELECT * FROM tracker_entries WHERE dedupe_key=?", (key,),
            ).fetchone()
            created = existing is None
            if existing is None:
                record_id = str(uuid4())
                connection.execute(
                    """INSERT INTO tracker_entries
                    (id,dedupe_key,company,role,location,compensation,status,date_added,
                     application_date,job_url,docx_path,pdf_path,folder_path,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        record_id, key, company.strip(), role.strip(), location.strip(),
                        compensation.strip(), normalized_status, added, application_date,
                        job_url.strip(), docx_path, pdf_path, folder_path, now, now,
                    ),
                )
            else:
                record_id = existing["id"]
                effective_status = existing["status"] if status == "Saved" else normalized_status
                effective_application = existing["application_date"] or application_date
                connection.execute(
                    """UPDATE tracker_entries SET company=?,role=?,location=?,compensation=?,
                    status=?,application_date=?,job_url=?,docx_path=?,pdf_path=?,folder_path=?,updated_at=?
                    WHERE id=?""",
                    (
                        company.strip() or existing["company"], role.strip() or existing["role"],
                        location.strip() or existing["location"],
                        compensation.strip() or existing["compensation"], effective_status,
                        effective_application, job_url.strip() or existing["job_url"],
                        docx_path or existing["docx_path"], pdf_path or existing["pdf_path"],
                        folder_path or existing["folder_path"], now, record_id,
                    ),
                )
        record = self.get(record_id)
        if record is None:
            raise RuntimeError("Tracker upsert did not produce a record.")
        return record, created

    def update(self, record_id: str, **values) -> TrackerRecord:
        current = self.get(record_id)
        if current is None:
            raise KeyError(record_id)
        status = _status(str(values.get("status", current.status)))
        application_date = current.application_date
        if status == "Applied" and not application_date:
            application_date = date.today().isoformat()
        company = str(values.get("company", current.company)).strip()
        role = str(values.get("role", current.role)).strip()
        job_url = str(values.get("job_url", current.job_url)).strip()
        with self.database.connect() as connection:
            connection.execute(
                """UPDATE tracker_entries SET dedupe_key=?,company=?,role=?,location=?,
                compensation=?,status=?,application_date=?,job_url=?,updated_at=? WHERE id=?""",
                (
                    dedupe_key(company, role, job_url), company, role,
                    str(values.get("location", current.location)).strip(),
                    str(values.get("compensation", current.compensation)).strip(),
                    status, application_date, job_url, _timestamp(), record_id,
                ),
            )
        updated = self.get(record_id)
        if updated is None:
            raise RuntimeError("Tracker update did not produce a record.")
        return updated

    def set_status(self, record_id: str, status: str) -> TrackerRecord:
        return self.update(record_id, status=status)

    def prune_missing_paths(self) -> int:
        """Clear stale local file references without removing tracker records."""
        changed = 0
        for record in self.list():
            docx = record.docx_path if _is_file(record.docx_path) else ""
            pdf = record.pdf_path if _is_file(record.pdf_path) else ""
            folder = record.folder_path if _is_directory(record.folder_path) else ""
            if not folder and (docx or pdf):
                folder = str(Path(docx or pdf).resolve().parent)
            if (docx, pdf, folder) == (
                record.docx_path, record.pdf_path, record.folder_path,
            ):
                continue
            with self.database.connect() as connection:
                connection.execute(
                    """UPDATE tracker_entries SET docx_path=?,pdf_path=?,folder_path=?,updated_at=?
                    WHERE id=?""",
                    (docx, pdf, folder, _timestamp(), record.id),
                )
            changed += 1
        return changed

    def delete(
        self,
        record_id: str,
        *,
        delete_files: bool = False,
        output_root: str | Path | None = None,
    ) -> tuple[str, ...]:
        current = self.get(record_id)
        if current is None:
            raise KeyError(record_id)
        removed: list[str] = []
        if delete_files:
            if output_root is None:
                raise ValueError("output_root is required when deleting generated files.")
            root = Path(output_root).resolve()
            file_paths: list[Path] = []
            for value in (current.docx_path, current.pdf_path):
                if not value:
                    continue
                path = Path(value).resolve()
                if not is_within(path, root):
                    raise ValueError(f"Refusing to delete a file outside outputs: {path}")
                file_paths.append(path)
            for path in file_paths:
                if path.is_file():
                    path.unlink()
                    removed.append(str(path))
        with self.database.connect() as connection:
            connection.execute("DELETE FROM tracker_entries WHERE id=?", (record_id,))
        return tuple(removed)


def dedupe_key(company: str, role: str, job_url: str) -> str:
    url = job_url.strip().casefold().rstrip("/")
    if url:
        return f"url:{url}"
    normalize = lambda value: re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()
    return f"role:{normalize(company)}|{normalize(role)}"


def open_local_path(path: str | Path) -> None:
    target = Path(path).resolve()
    if not target.exists():
        raise FileNotFoundError(target)
    os.startfile(str(target))


def _status(value: str) -> str:
    match = next((item for item in TRACKER_STATUSES if item.casefold() == value.casefold()), None)
    return match or "Saved"


def _timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _is_file(value: str) -> bool:
    return bool(value) and Path(value).is_file()


def _is_directory(value: str) -> bool:
    return bool(value) and Path(value).is_dir()


def _record(row) -> TrackerRecord:
    return TrackerRecord(**dict(row))
