from __future__ import annotations

from pathlib import Path

from docx import Document
import pytest

from resume_tool.render import AWARDS_LINE, build_context
from resume_tool.schema import ResumeDocument, ResumeMetadata
from resume_tool.template_selector import TEMPLATE_FILENAMES, select_template


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "resume_tool" / "templates"


@pytest.mark.parametrize(
    "projects,awards,filename,label",
    [
        (1, False, "resume_1project_no_awards.docx", "1 Project + No Awards"),
        (1, True, "resume_1project_awards.docx", "1 Project + Awards"),
        (2, False, "resume_2projects_no_awards.docx", "2 Projects + No Awards"),
        (2, True, "resume_2projects_awards.docx", "2 Projects + Awards"),
    ],
)
def test_all_four_templates_are_selected(projects, awards, filename, label):
    selection = select_template(
        ResumeMetadata(project_count=projects, include_awards=awards), TEMPLATE_DIR,
    )
    assert selection.path.name == filename
    assert selection.label == label


@pytest.mark.template
@pytest.mark.parametrize("key,filename", list(TEMPLATE_FILENAMES.items()))
def test_fixed_template_has_exact_variant_structure(key, filename):
    project_count, awards = key
    path = TEMPLATE_DIR / filename
    if not path.is_file():
        pytest.skip(f"Private template unavailable: {path}")
    text = "\n".join(paragraph.text for paragraph in Document(path).paragraphs)
    assert "{{project1_name}}" in text
    assert ("{{project1_4}}" in text) is (project_count == 1)
    assert ("{{project2_name}}" in text) is (project_count == 2)
    assert ("{{project2_3}}" in text) is (project_count == 2)
    assert ("{{awards_line}}" in text) is awards
    assert ("AWARDS" in text) is awards
    assert "Data & AI Contractor" in text
    assert "Data & AI Consultant" in text
    assert "Master of Science in Business Analytics" in text
    assert "Bachelor of Engineering in Mechanical Engineering" in text
    folded = text.casefold()
    for required in (
        "bhuwan gupta", "linkedin", "github", "ilink digital", "remote",
        "july 2026", "the george washington university, school of business",
        "august 2025", "december 2025", "thorogood associates", "bangalore, india",
        "july 2022", "july 2024", "birla institute of technology and science, pilani",
        "goa, india", "may 2022",
    ):
        assert required in folded
    assert "@" in text
    assert "gpa" not in folded


@pytest.mark.parametrize("project_count", [1, 2])
@pytest.mark.parametrize("include_awards", [False, True])
def test_render_context_uses_json_only_for_dynamic_content(
    payload_factory, project_count, include_awards,
):
    document = ResumeDocument.model_validate(
        payload_factory(project_count=project_count, include_awards=include_awards)
    )
    original_name = document.resume.projects.project1.name
    context = build_context(document)
    assert context["project1_name"] == original_name.upper()
    assert document.resume.projects.project1.name == original_name
    assert context["awards_line"] == (AWARDS_LINE if include_awards else "")
    assert context["ilink_6"]
    assert context["gta_3"]
    assert context["thorogood_7"]
    assert context["skills_6"]
    assert ("project2_3" in context) is (project_count == 2)
