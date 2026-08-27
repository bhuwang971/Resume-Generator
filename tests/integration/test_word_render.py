from __future__ import annotations

import os
from pathlib import Path

from docx import Document
from pypdf import PdfReader
import pytest

from resume_tool.schema import ResumeDocument
from resume_tool.template_selector import select_template
from resume_tool.render import AWARDS_LINE, render_resume_candidate
from resume_tool.workflow import create_preflight, promote_preflight
from tracker import TrackerDatabase, TrackerService


pytestmark = pytest.mark.word
PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = PROJECT_ROOT / "resume_tool" / "templates"


def _require_word_integration():
    if os.environ.get("RUN_WORD_INTEGRATION") != "1":
        pytest.skip("Set RUN_WORD_INTEGRATION=1 to run Microsoft Word tests.")


@pytest.mark.parametrize("project_count", [1, 2])
@pytest.mark.parametrize("include_awards", [False, True])
def test_all_fixed_templates_are_ats_safe_one_page(
    tmp_path, payload_factory, project_count, include_awards,
):
    _require_word_integration()
    document = ResumeDocument.model_validate(
        payload_factory(project_count=project_count, include_awards=include_awards)
    )
    selection = select_template(document.metadata, TEMPLATE_DIR)
    output = tmp_path / selection.path.name
    report = render_resume_candidate(selection.path, document, output)
    assert report.passed
    extracted = "\n".join(paragraph.text for paragraph in Document(output).paragraphs)
    assert "Data & AI Contractor" in extracted
    assert "Data & AI Consultant" in extracted
    assert "Master of Science in Business Analytics" in extracted
    assert "Bachelor of Engineering in Mechanical Engineering" in extracted
    assert document.resume.projects.project1.name.upper() in extracted
    assert (AWARDS_LINE in extracted) is include_awards


@pytest.mark.parametrize(
    "project_count,include_awards",
    [(1, True), (2, False)],
    ids=["demo-a-one-project-awards", "demo-b-two-projects-no-awards"],
)
def test_end_to_end_generation_and_tracker_demo(
    tmp_path, payload_factory, project_count, include_awards,
):
    _require_word_integration()
    document = ResumeDocument.model_validate(
        payload_factory(project_count=project_count, include_awards=include_awards)
    )
    preflight = create_preflight(
        document, template_dir=TEMPLATE_DIR, temp_root=tmp_path / "preflight",
    )
    assert preflight.passed
    generated = promote_preflight(
        document, preflight, output_root=tmp_path / "outputs",
        export_docx=True, export_pdf=True,
    )
    assert generated.paths.docx_path.is_file()
    assert generated.paths.pdf_path.is_file()
    pdf = PdfReader(generated.paths.pdf_path)
    assert len(pdf.pages) == 1
    ats_text = pdf.pages[0].extract_text()
    assert "Data & AI Contractor" in ats_text
    assert "Data & AI Consultant" in ats_text
    assert document.resume.projects.project1.name.upper() in ats_text
    tracker = TrackerService(TrackerDatabase(tmp_path / "tracker.db"))
    record, created = tracker.upsert_from_generation(
        document.metadata, generated.paths, generated.output.folder,
    )
    assert created
    assert record.docx_path == str(generated.paths.docx_path)
    assert record.pdf_path == str(generated.paths.pdf_path)
