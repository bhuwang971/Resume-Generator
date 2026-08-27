from __future__ import annotations

from datetime import date
from pathlib import Path
import sqlite3

import pytest

from resume_tool.render import RenderedResumePaths
from resume_tool.schema import ResumeMetadata
from tracker import TRACKER_STATUSES, TrackerDatabase, TrackerService
from tracker.migration import migrate_legacy_career_database


@pytest.fixture
def tracker(tmp_path):
    return TrackerService(TrackerDatabase(tmp_path / "tracker.db"))


def test_generation_creates_then_updates_one_tracker_row(tracker, tmp_path):
    metadata = ResumeMetadata(
        company="Example Co", role="Data Role", location="Remote",
        compensation="$1", job_url="https://example.test/job/1",
    )
    first, created = tracker.upsert_from_generation(
        metadata, RenderedResumePaths(tmp_path / "v1.docx", None), tmp_path,
    )
    assert created
    second, created = tracker.upsert_from_generation(
        metadata, RenderedResumePaths(tmp_path / "v2.docx", tmp_path / "v2.pdf"), tmp_path,
    )
    assert not created
    assert second.id == first.id
    assert second.docx_path.endswith("v2.docx")
    assert second.pdf_path.endswith("v2.pdf")
    assert len(tracker.list()) == 1


def test_company_and_role_are_fallback_dedupe_key(tracker):
    first, _ = tracker.upsert(company=" Example  Co ", role="Data-Role")
    second, created = tracker.upsert(company="example co", role="data role")
    assert not created
    assert second.id == first.id


def test_status_edit_and_application_date_persist(tracker):
    record, _ = tracker.upsert(company="A", role="B")
    assert TRACKER_STATUSES == (
        "Saved", "Applied", "Interview", "Rejected", "Offer", "Withdrawn",
    )
    applied = tracker.set_status(record.id, "Applied")
    assert applied.status == "Applied"
    assert applied.application_date == date.today().isoformat()
    edited = tracker.update(
        record.id, company="Edited", role="Role", location="Chicago",
        compensation="$2", job_url="https://example.test/new",
    )
    assert edited.company == "Edited"
    assert edited.location == "Chicago"
    assert edited.application_date == applied.application_date


def test_delete_defaults_to_record_only(tracker, tmp_path):
    output_root = tmp_path / "outputs"
    folder = output_root / "Co" / "Role"
    folder.mkdir(parents=True)
    docx = folder / "resume_v1.docx"
    pdf = folder / "resume_v1.pdf"
    docx.write_bytes(b"docx")
    pdf.write_bytes(b"pdf")
    record, _ = tracker.upsert(
        company="Co", role="Role", docx_path=str(docx), pdf_path=str(pdf),
        folder_path=str(folder),
    )
    assert tracker.delete(record.id) == ()
    assert docx.exists() and pdf.exists()


def test_optional_file_delete_is_limited_to_outputs(tracker, tmp_path):
    output_root = tmp_path / "outputs"
    folder = output_root / "Co" / "Role"
    folder.mkdir(parents=True)
    docx = folder / "resume_v1.docx"
    docx.write_bytes(b"docx")
    record, _ = tracker.upsert(company="Co", role="Role", docx_path=str(docx))
    removed = tracker.delete(record.id, delete_files=True, output_root=output_root)
    assert removed == (str(docx.resolve()),)
    assert not docx.exists()

    outside = tmp_path / "private.docx"
    outside.write_bytes(b"private")
    record, _ = tracker.upsert(company="Other", role="Role", docx_path=str(outside))
    with pytest.raises(ValueError, match="outside outputs"):
        tracker.delete(record.id, delete_files=True, output_root=output_root)
    assert outside.exists()
    assert tracker.get(record.id) is not None


def test_missing_file_references_can_be_pruned_without_deleting_record(tracker, tmp_path):
    existing = tmp_path / "outputs" / "resume_v1.pdf"
    existing.parent.mkdir()
    existing.write_bytes(b"pdf")
    record, _ = tracker.upsert(
        company="Co", role="Role", docx_path=str(tmp_path / "missing.docx"),
        pdf_path=str(existing), folder_path=str(tmp_path / "missing-folder"),
    )
    assert tracker.prune_missing_paths() == 1
    updated = tracker.get(record.id)
    assert updated is not None
    assert updated.docx_path == ""
    assert updated.pdf_path == str(existing)
    assert updated.folder_path == str(existing.parent.resolve())


def test_legacy_migration_is_idempotent_and_keeps_only_valid_resume_paths(tmp_path):
    legacy = tmp_path / "career.db"
    valid_docx = tmp_path / "existing.docx"
    valid_docx.write_bytes(b"docx")
    connection = sqlite3.connect(legacy)
    connection.executescript(
        """
        CREATE TABLE jobs (
            id TEXT PRIMARY KEY, company TEXT, title TEXT, location TEXT,
            job_url TEXT, status TEXT, created_at TEXT
        );
        CREATE TABLE opportunity_metadata (
            job_id TEXT PRIMARY KEY, compensation TEXT, application_date TEXT
        );
        CREATE TABLE document_versions (
            job_id TEXT, material_type TEXT, docx_path TEXT, pdf_path TEXT,
            created_at TEXT
        );
        """
    )
    connection.execute(
        "INSERT INTO jobs VALUES (?,?,?,?,?,?,?)",
        ("job-1", "Legacy Co", "Legacy Role", "Remote", "https://example.test/legacy", "APPLIED", "2026-01-02T12:00:00"),
    )
    connection.execute(
        "INSERT INTO opportunity_metadata VALUES (?,?,?)",
        ("job-1", "$3", "2026-01-03"),
    )
    connection.execute(
        "INSERT INTO document_versions VALUES (?,?,?,?,?)",
        ("job-1", "resume", str(valid_docx), str(tmp_path / "missing.pdf"), "2026-01-04"),
    )
    connection.commit()
    connection.close()
    tracker = TrackerService(TrackerDatabase(tmp_path / "tracker.db"))
    first = migrate_legacy_career_database(legacy, tracker)
    second = migrate_legacy_career_database(legacy, tracker)
    assert (first.scanned, first.imported, first.updated, first.skipped) == (1, 1, 0, 0)
    assert (second.scanned, second.imported, second.updated, second.skipped) == (1, 0, 1, 0)
    record = tracker.list()[0]
    assert record.company == "Legacy Co"
    assert record.status == "Applied"
    assert record.docx_path == str(valid_docx.resolve())
    assert record.pdf_path == ""
