from __future__ import annotations

from dataclasses import dataclass
import argparse
from pathlib import Path
import sqlite3

from .database import TrackerDatabase
from .service import TrackerService


@dataclass(frozen=True)
class MigrationResult:
    scanned: int
    imported: int
    updated: int
    skipped: int


def migrate_legacy_career_database(
    legacy_database: str | Path, tracker: TrackerService,
) -> MigrationResult:
    source = Path(legacy_database)
    if not source.is_file():
        return MigrationResult(0, 0, 0, 0)
    connection = sqlite3.connect(source)
    connection.row_factory = sqlite3.Row
    try:
        tables = {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if "jobs" not in tables:
            return MigrationResult(0, 0, 0, 0)
        opportunity_join = (
            "LEFT JOIN opportunity_metadata o ON o.job_id=j.id"
            if "opportunity_metadata" in tables else ""
        )
        compensation = "COALESCE(o.compensation, '')" if opportunity_join else "''"
        application_date = "COALESCE(o.application_date, '')" if opportunity_join else "''"
        rows = connection.execute(
            f"""SELECT j.id,j.company,j.title,j.location,j.job_url,j.status,j.created_at,
            {compensation} AS compensation,{application_date} AS application_date
            FROM jobs j {opportunity_join} ORDER BY j.created_at"""
        ).fetchall()
        files = _latest_resume_files(connection, tables)
        imported = updated = skipped = 0
        for row in rows:
            company = str(row["company"] or "").strip()
            role = str(row["title"] or "").strip()
            if not company and not role:
                skipped += 1
                continue
            docx, pdf = files.get(str(row["id"]), ("", ""))
            folder = str(Path(docx or pdf).resolve().parent) if docx or pdf else ""
            _, created = tracker.upsert(
                company=company, role=role, location=str(row["location"] or ""),
                compensation=str(row["compensation"] or ""),
                status=str(row["status"] or "Saved"), job_url=str(row["job_url"] or ""),
                date_added=str(row["created_at"] or "")[:10],
                application_date=str(row["application_date"] or ""),
                docx_path=docx, pdf_path=pdf, folder_path=folder,
            )
            if created:
                imported += 1
            else:
                updated += 1
        return MigrationResult(len(rows), imported, updated, skipped)
    finally:
        connection.close()


def _latest_resume_files(
    connection: sqlite3.Connection, tables: set[str],
) -> dict[str, tuple[str, str]]:
    rows: list[sqlite3.Row] = []
    if "document_versions" in tables:
        rows.extend(connection.execute(
            """SELECT job_id,docx_path,pdf_path,created_at FROM document_versions
            WHERE material_type='resume' ORDER BY created_at"""
        ).fetchall())
    if "resume_versions" in tables:
        rows.extend(connection.execute(
            """SELECT job_id,COALESCE(docx_path,'') docx_path,
            COALESCE(pdf_path,'') pdf_path,created_at FROM resume_versions ORDER BY created_at"""
        ).fetchall())
    result: dict[str, tuple[str, str]] = {}
    for row in sorted(rows, key=lambda item: str(item["created_at"] or "")):
        docx = _valid_file(str(row["docx_path"] or ""), ".docx")
        pdf = _valid_file(str(row["pdf_path"] or ""), ".pdf")
        prior_docx, prior_pdf = result.get(str(row["job_id"]), ("", ""))
        result[str(row["job_id"])] = (docx or prior_docx, pdf or prior_pdf)
    return result


def _valid_file(value: str, suffix: str) -> str:
    path = Path(value) if value else None
    return str(path.resolve()) if path and path.suffix.casefold() == suffix and path.is_file() else ""


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Copy useful application rows from legacy career.db into tracker.db."
    )
    parser.add_argument(
        "--legacy", type=Path, default=_default_legacy_database(project_root),
    )
    parser.add_argument(
        "--tracker", type=Path, default=project_root / "data" / "tracker.db",
    )
    arguments = parser.parse_args()
    result = migrate_legacy_career_database(
        arguments.legacy,
        TrackerService(TrackerDatabase(arguments.tracker)),
    )
    print(
        f"scanned={result.scanned} imported={result.imported} "
        f"updated={result.updated} skipped={result.skipped}"
    )


def _default_legacy_database(project_root: Path) -> Path:
    active = project_root / "data" / "career.db"
    if active.is_file():
        return active
    archives = sorted(
        (project_root / "data" / "backups").glob("career-legacy-*.db"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return archives[0] if archives else active


if __name__ == "__main__":
    main()
