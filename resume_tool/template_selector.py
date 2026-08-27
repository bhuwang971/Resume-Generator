from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from docx import Document
from docx.text.paragraph import Paragraph

from .schema import ResumeMetadata


TEMPLATE_FILENAMES = {
    (1, False): "resume_1project_no_awards.docx",
    (1, True): "resume_1project_awards.docx",
    (2, False): "resume_2projects_no_awards.docx",
    (2, True): "resume_2projects_awards.docx",
}


@dataclass(frozen=True)
class TemplateSelection:
    path: Path
    label: str


def select_template(metadata: ResumeMetadata, template_dir: str | Path) -> TemplateSelection:
    key = (metadata.project_count, metadata.include_awards)
    path = Path(template_dir) / TEMPLATE_FILENAMES[key]
    label = f"{metadata.project_count} Project{'s' if metadata.project_count == 2 else ''} + "
    label += "Awards" if metadata.include_awards else "No Awards"
    return TemplateSelection(path=path, label=label)


def create_fixed_templates(source_template: str | Path, template_dir: str | Path) -> tuple[Path, ...]:
    """Derive four fixed local templates from the approved private template."""
    source = Path(source_template)
    destination = Path(template_dir)
    if not source.is_file():
        raise FileNotFoundError(f"Approved source template is missing: {source}")
    destination.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    for (project_count, include_awards), filename in TEMPLATE_FILENAMES.items():
        document = Document(str(source))
        remove_tokens = set()
        if project_count == 1:
            remove_tokens.update({
                "{{project2_name}}", "{{project2_1}}", "{{project2_2}}", "{{project2_3}}",
            })
        else:
            remove_tokens.add("{{project1_4}}")
        if not include_awards:
            remove_tokens.add("{{awards_line}}")
        for paragraph in list(document.paragraphs):
            text = paragraph.text.strip()
            if text in remove_tokens or (not include_awards and text == "AWARDS"):
                _delete_paragraph(paragraph)
        output = destination / filename
        document.save(str(output))
        created.append(output)
    return tuple(created)


def _delete_paragraph(paragraph: Paragraph) -> None:
    element = paragraph._element
    element.getparent().remove(element)
    paragraph._p = paragraph._element = None
