from __future__ import annotations

from pathlib import Path
import shutil

import pytest

from resume_tool.render import RenderedResumePaths, ResumeLayoutReport
from resume_tool.schema import ResumeDocument
from resume_tool.template_selector import select_template
from resume_tool.utils import is_within, next_versioned_output, sanitize_path_part
from resume_tool.workflow import ResumePreflight, document_hash, promote_preflight


def test_output_names_are_sanitized_and_incremented(tmp_path):
    first = next_versioned_output(tmp_path, 'A:/Company?', 'Role*Name')
    first.docx_path.write_bytes(b"docx")
    second = next_versioned_output(tmp_path, 'A:/Company?', 'Role*Name')
    assert first.folder.name == "RoleName"
    assert first.folder.parent.name == "ACompany"
    assert second.version == 2
    assert second.docx_path.name == "resume_v2.docx"
    assert sanitize_path_part("...", "fallback") == "fallback"
    assert is_within(second.docx_path, tmp_path)
    assert not is_within(tmp_path.parent / "outside.docx", tmp_path)


def test_only_passing_unchanged_preflight_can_be_promoted(
    tmp_path, monkeypatch, payload_factory,
):
    document = ResumeDocument.model_validate(payload_factory())
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    selection = select_template(document.metadata, template_dir)
    selection.path.write_bytes(b"template")
    candidate = tmp_path / "candidate.docx"
    candidate.write_bytes(b"validated candidate")
    preflight = ResumePreflight(
        document_hash(document), selection, candidate, ResumeLayoutReport(page_count=1),
    )

    def fake_promote(source, output, *, export_docx, export_pdf):
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        docx = output if export_docx else None
        pdf = output.with_suffix(".pdf") if export_pdf else None
        if docx:
            shutil.copy2(source, docx)
        if pdf:
            pdf.write_bytes(b"pdf")
        return RenderedResumePaths(docx, pdf)

    monkeypatch.setattr("resume_tool.workflow.promote_resume_candidate", fake_promote)
    generated = promote_preflight(
        document, preflight, output_root=tmp_path / "outputs",
        export_docx=True, export_pdf=True,
    )
    assert generated.paths.docx_path.is_file()
    assert generated.paths.pdf_path.is_file()
    assert not candidate.exists()


def test_changed_or_failed_preflight_is_rejected(tmp_path, payload_factory):
    document = ResumeDocument.model_validate(payload_factory())
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    selection = select_template(document.metadata, template_dir)
    selection.path.write_bytes(b"template")
    candidate = tmp_path / "candidate.docx"
    candidate.write_bytes(b"candidate")
    failed = ResumePreflight(
        document_hash(document), selection, candidate, ResumeLayoutReport(page_count=2),
    )
    with pytest.raises(ValueError, match="must pass"):
        promote_preflight(
            document, failed, output_root=tmp_path / "outputs",
            export_docx=True, export_pdf=False,
        )
    changed_payload = payload_factory()
    changed_payload["metadata"]["company"] = "Changed"
    changed = ResumeDocument.model_validate(changed_payload)
    passing = ResumePreflight(
        document_hash(document), selection, candidate, ResumeLayoutReport(page_count=1),
    )
    with pytest.raises(ValueError, match="changed"):
        promote_preflight(
            changed, passing, output_root=tmp_path / "outputs",
            export_docx=True, export_pdf=False,
        )
