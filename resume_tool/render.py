from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import shutil

from docx import Document
from docx.enum.text import WD_TAB_ALIGNMENT
from docx.shared import Inches
from docx.text.paragraph import Paragraph
from docxtpl import DocxTemplate

from .schema import ResumeDocument


AWARDS_LINE = (
    "MSBA Academic Excellence Award, GWU (2026) | "
    "Star Award, Thorogood Associates (2023)"
)


class LayoutValidationError(Exception):
    pass


@dataclass(frozen=True)
class RenderedResumePaths:
    docx_path: Path | None = None
    pdf_path: Path | None = None


@dataclass(frozen=True)
class LayoutOverflow:
    field_path: str
    display_name: str
    paragraph_index: int
    line_count: int
    text: str
    kind: str


@dataclass(frozen=True)
class ResumeLayoutReport:
    page_count: int
    bullet_overflows: tuple[LayoutOverflow, ...] = ()
    skill_overflows: tuple[LayoutOverflow, ...] = ()

    @property
    def passed(self) -> bool:
        return self.page_count == 1 and not self.bullet_overflows and not self.skill_overflows


def build_context(document: ResumeDocument) -> dict[str, str]:
    resume = document.resume
    project2 = resume.projects.project2
    context = {
        "summary": resume.professional_summary,
        "project1_name": resume.projects.project1.name.upper(),
        "project2_name": project2.name.upper() if project2 else "",
        "awards_line": AWARDS_LINE if document.metadata.include_awards else "",
    }
    for index, value in enumerate(resume.technical_skills, 1):
        context[f"skills_{index}"] = value
    for index, value in enumerate(resume.work_experience.ilink_bullets, 1):
        context[f"ilink_{index}"] = value
    for index, value in enumerate(resume.work_experience.gwu_gta_bullets, 1):
        context[f"gta_{index}"] = value
    for index, value in enumerate(resume.work_experience.thorogood_bullets, 1):
        context[f"thorogood_{index}"] = value
    for index, value in enumerate(resume.projects.project1.bullets, 1):
        context[f"project1_{index}"] = value
    if project2:
        for index, value in enumerate(project2.bullets, 1):
            context[f"project2_{index}"] = value
    return context


def render_resume_candidate(
    template_path: str | Path,
    document: ResumeDocument,
    candidate_path: str | Path,
) -> ResumeLayoutReport:
    template = Path(template_path)
    candidate = Path(candidate_path)
    if not template.is_file():
        raise FileNotFoundError(f"Selected resume template is missing: {template}")
    candidate.parent.mkdir(parents=True, exist_ok=True)
    if candidate.exists():
        candidate.unlink()
    docx = DocxTemplate(str(template))
    docx.render(build_context(document))
    docx.save(str(candidate))
    _apply_static_resume_format(candidate)
    _apply_skill_format(candidate, template, document)
    return inspect_resume_layout(candidate, template, document)


def inspect_resume_layout(
    docx_path: str | Path,
    template_path: str | Path,
    document: ResumeDocument,
) -> ResumeLayoutReport:
    placeholders = _load_placeholder_indices(Path(template_path))
    bullet_fields: dict[int, tuple[str, str]] = {}
    for prefix, count, path, label in (
        ("ilink", 6, "resume.work_experience.ilink_bullets", "iLink bullet"),
        ("gta", 3, "resume.work_experience.gwu_gta_bullets", "GTA bullet"),
        ("thorogood", 7, "resume.work_experience.thorogood_bullets", "Thorogood bullet"),
        ("project1", len(document.resume.projects.project1.bullets), "resume.projects.project1.bullets", "Project 1 bullet"),
        ("project2", 3 if document.resume.projects.project2 else 0, "resume.projects.project2.bullets", "Project 2 bullet"),
    ):
        bullet_fields.update(_indexed_fields(placeholders, prefix, count, path, label))
    skill_fields = _indexed_fields(
        placeholders, "skills", 6, "resume.technical_skills", "Skills line",
    )
    page_count, bullet_violations, skill_violations = _analyze_layout_with_word(
        Path(docx_path), list(bullet_fields), list(skill_fields),
    )
    return ResumeLayoutReport(
        page_count=page_count,
        bullet_overflows=tuple(
            _overflow(item, bullet_fields, "bullet") for item in bullet_violations
        ),
        skill_overflows=tuple(
            _overflow(item, skill_fields, "skill") for item in skill_violations
        ),
    )


def promote_resume_candidate(
    candidate_path: str | Path,
    output_docx_path: str | Path,
    *,
    export_docx: bool,
    export_pdf: bool,
) -> RenderedResumePaths:
    if not export_docx and not export_pdf:
        raise ValueError("At least one output format is required.")
    candidate = Path(candidate_path)
    output_docx = Path(output_docx_path)
    if not candidate.is_file():
        raise LayoutValidationError("Validated temporary resume candidate is missing.")
    output_docx.parent.mkdir(parents=True, exist_ok=True)
    docx_path: Path | None = None
    pdf_path: Path | None = None
    if export_docx:
        shutil.copy2(candidate, output_docx)
        docx_path = output_docx
    if export_pdf:
        pdf_path = _convert_docx_to_pdf(candidate, output_docx.with_suffix(".pdf"))
    return RenderedResumePaths(docx_path=docx_path, pdf_path=pdf_path)


def render_resume_outputs(
    template_path: str | Path,
    document: ResumeDocument,
    output_docx_path: str | Path,
    *,
    export_docx: bool = True,
    export_pdf: bool = True,
) -> RenderedResumePaths:
    output = Path(output_docx_path)
    temporary = output.with_name(f"{output.stem}.preflight.docx")
    report = render_resume_candidate(template_path, document, temporary)
    if not report.passed:
        raise LayoutValidationError(layout_error_message(report))
    try:
        return promote_resume_candidate(
            temporary, output, export_docx=export_docx, export_pdf=export_pdf,
        )
    finally:
        temporary.unlink(missing_ok=True)


def layout_error_message(report: ResumeLayoutReport) -> str:
    messages: list[str] = []
    if report.page_count != 1:
        messages.append(f"Resume has {report.page_count} pages; exactly 1 is required.")
    for item in (*report.bullet_overflows, *report.skill_overflows):
        messages.append(f"{item.field_path}: {item.line_count} physical lines -> {item.text}")
    return "\n".join(messages)


def layout_failure_dicts(report: ResumeLayoutReport) -> list[dict]:
    return [
        {
            "path": item.field_path,
            "message": f"{item.line_count} physical lines; one line required.",
            "current_text": item.text,
        }
        for item in (*report.bullet_overflows, *report.skill_overflows)
    ]


def _load_placeholder_indices(template_path: Path) -> dict[str, int]:
    result: dict[str, int] = {}
    for index, paragraph in enumerate(Document(str(template_path)).paragraphs):
        for token in re.findall(r"\{\{[A-Za-z0-9_]+\}\}", paragraph.text):
            result[token] = index
    return result


def _indexed_fields(
    placeholders: dict[str, int], prefix: str, count: int, path: str, label: str,
) -> dict[int, tuple[str, str]]:
    fields: dict[int, tuple[str, str]] = {}
    for index in range(count):
        token = f"{{{{{prefix}_{index + 1}}}}}"
        if token not in placeholders:
            raise LayoutValidationError(f"Selected template is missing placeholder {token}.")
        fields[placeholders[token]] = (f"{path}[{index}]", f"{label} {index + 1}")
    return fields


def _overflow(
    violation: tuple[int, int, str], fields: dict[int, tuple[str, str]], kind: str,
) -> LayoutOverflow:
    paragraph_index, line_count, text = violation
    path, label = fields.get(
        paragraph_index, (f"paragraphs[{paragraph_index}]", f"Paragraph {paragraph_index}"),
    )
    return LayoutOverflow(path, label, paragraph_index, line_count, text, kind)


def _apply_skill_format(
    output_path: Path, template_path: Path, document: ResumeDocument,
) -> None:
    placeholders = _load_placeholder_indices(template_path)
    rendered = Document(str(output_path))
    for index, skill in enumerate(document.resume.technical_skills, 1):
        paragraph_index = placeholders[f"{{{{skills_{index}}}}}"]
        paragraph = rendered.paragraphs[paragraph_index]
        category, _, items = skill.partition(":")
        _replace_paragraph_text(paragraph, f"{category.strip()}:")
        paragraph.runs[0].bold = True
        paragraph.runs[0].underline = False
        trailing = paragraph.add_run(f" {items.strip()}")
        trailing.bold = False
        trailing.underline = False
    rendered.save(str(output_path))


def _replace_paragraph_text(paragraph: Paragraph, text: str) -> None:
    if not paragraph.runs:
        paragraph.add_run(text)
        return
    for run in paragraph.runs:
        run.text = ""
    paragraph.runs[0].text = text


_RIGHT_EDGE = Inches(7.56)


def _format_left_right_row(
    paragraph: Paragraph, left: str, right: str, *, bold: bool, italic: bool,
) -> None:
    _replace_paragraph_text(paragraph, left)
    paragraph.runs[0].bold = bold
    paragraph.runs[0].italic = italic
    right_run = paragraph.add_run(f"\t{right}")
    right_run.bold = bold
    right_run.italic = italic
    paragraph.paragraph_format.tab_stops.clear_all()
    paragraph.paragraph_format.tab_stops.add_tab_stop(_RIGHT_EDGE, WD_TAB_ALIGNMENT.RIGHT)


def _apply_static_resume_format(output_path: Path) -> None:
    rows = {
        "ILINK DIGITAL": ("ILINK DIGITAL", "Remote", True, False),
        "DATA AI CONTRACTOR": ("Data & AI Contractor", "July 2026 – Present", True, True),
        "THE GEORGE WASHINGTON UNIVERSITY, SCHOOL OF BUSINESS": (
            "THE GEORGE WASHINGTON UNIVERSITY, SCHOOL OF BUSINESS", "Washington, DC", True, False,
        ),
        "GRADUATE TEACHING ASSISTANT": (
            "Graduate Teaching Assistant", "August 2025 – December 2025", True, True,
        ),
        "THOROGOOD ASSOCIATES": ("THOROGOOD ASSOCIATES", "Bangalore, India", True, False),
        "DATA AI CONSULTANT": ("Data & AI Consultant", "July 2022 – July 2024", True, True),
        "GEORGE WASHINGTON UNIVERSITY, SCHOOL OF BUSINESS": (
            "GEORGE WASHINGTON UNIVERSITY, SCHOOL OF BUSINESS", "Washington, DC", True, False,
        ),
        "MASTER OF SCIENCE IN BUSINESS ANALYTICS": (
            "Master of Science in Business Analytics", "December 2025", False, True,
        ),
        "BIRLA INSTITUTE OF TECHNOLOGY AND SCIENCE, PILANI": (
            "BIRLA INSTITUTE OF TECHNOLOGY AND SCIENCE, PILANI", "Goa, India", True, False,
        ),
        "BACHELOR OF ENGINEERING IN MECHANICAL ENGINEERING": (
            "Bachelor of Engineering in Mechanical Engineering", "May 2022", False, True,
        ),
    }
    document = Document(str(output_path))
    for paragraph in document.paragraphs:
        normalized = " ".join(re.sub(r"[^A-Z0-9, ]", "", paragraph.text.upper()).split())
        for prefix, (left, right, bold, italic) in rows.items():
            if normalized.startswith(prefix):
                _format_left_right_row(paragraph, left, right, bold=bold, italic=italic)
                break
    document.save(str(output_path))


def _is_bullet_word_paragraph(word_paragraph) -> bool:
    text = str(word_paragraph.Range.Text).replace("\r", "").strip()
    if not text:
        return False
    try:
        if int(word_paragraph.Range.ListFormat.ListType) != 0:
            return True
    except Exception:  # noqa: BLE001
        pass
    return text.lstrip().startswith(("•", "-", "*"))


def _analyze_layout_with_word(
    docx_path: Path, bullet_indices: list[int], skill_indices: list[int],
) -> tuple[int, list[tuple[int, int, str]], list[tuple[int, int, str]]]:
    try:
        import pythoncom
        import win32com.client
    except ImportError as exc:
        raise LayoutValidationError("Word layout checks require pywin32 and Microsoft Word.") from exc
    wd_statistic_lines = 1
    wd_statistic_pages = 2
    bullet_failures: list[tuple[int, int, str]] = []
    skill_failures: list[tuple[int, int, str]] = []
    pythoncom.CoInitialize()
    word = None
    document = None
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        document = word.Documents.Open(
            str(docx_path.resolve()), ConfirmConversions=False, ReadOnly=True,
            AddToRecentFiles=False,
        )
        page_count = int(document.ComputeStatistics(wd_statistic_pages))
        paragraph_count = int(document.Paragraphs.Count)
        for index in sorted(set(bullet_indices)):
            if index + 1 > paragraph_count:
                continue
            paragraph = document.Paragraphs(index + 1)
            if not _is_bullet_word_paragraph(paragraph):
                continue
            text = str(paragraph.Range.Text).replace("\r", "").strip()
            lines = int(paragraph.Range.ComputeStatistics(wd_statistic_lines))
            if text and lines > 1:
                bullet_failures.append((index, lines, text))
        for index in sorted(set(skill_indices)):
            if index + 1 > paragraph_count:
                continue
            paragraph = document.Paragraphs(index + 1)
            text = str(paragraph.Range.Text).replace("\r", "").strip()
            lines = int(paragraph.Range.ComputeStatistics(wd_statistic_lines))
            if text and lines > 1:
                skill_failures.append((index, lines, text))
    except Exception as exc:  # noqa: BLE001
        raise LayoutValidationError("Microsoft Word could not inspect the temporary DOCX.") from exc
    finally:
        try:
            if document is not None:
                document.Close(False)
        except Exception:  # noqa: BLE001
            pass
        try:
            if word is not None:
                word.Quit()
        except Exception:  # noqa: BLE001
            pass
        pythoncom.CoUninitialize()
    return page_count, bullet_failures, skill_failures


def _convert_docx_to_pdf(docx_path: Path, pdf_path: Path) -> Path:
    try:
        import pythoncom
        import win32com.client
    except ImportError as exc:
        raise LayoutValidationError("PDF export requires pywin32 and Microsoft Word.") from exc
    pythoncom.CoInitialize()
    word = None
    document = None
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        document = word.Documents.Open(
            str(docx_path.resolve()), ConfirmConversions=False, ReadOnly=True,
            AddToRecentFiles=False,
        )
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        document.SaveAs(str(pdf_path.resolve()), FileFormat=17)
    except Exception as exc:  # noqa: BLE001
        raise LayoutValidationError("Microsoft Word could not export the PDF.") from exc
    finally:
        try:
            if document is not None:
                document.Close(False)
        except Exception:  # noqa: BLE001
            pass
        try:
            if word is not None:
                word.Quit()
        except Exception:  # noqa: BLE001
            pass
        pythoncom.CoUninitialize()
    return pdf_path
