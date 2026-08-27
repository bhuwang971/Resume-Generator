from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path

from .render import (
    RenderedResumePaths, ResumeLayoutReport, promote_resume_candidate,
    render_resume_candidate,
)
from .schema import ResumeDocument
from .template_selector import TemplateSelection, select_template
from .utils import VersionedOutput, next_versioned_output


@dataclass(frozen=True)
class ResumePreflight:
    content_hash: str
    template: TemplateSelection
    candidate_path: Path
    report: ResumeLayoutReport

    @property
    def passed(self) -> bool:
        return self.report.passed


@dataclass(frozen=True)
class GeneratedResume:
    paths: RenderedResumePaths
    output: VersionedOutput


def document_hash(document: ResumeDocument) -> str:
    payload = document.model_dump_json(exclude_none=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def create_preflight(
    document: ResumeDocument,
    *,
    template_dir: str | Path,
    temp_root: str | Path,
) -> ResumePreflight:
    root = Path(temp_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    for prior in root.glob("resume_candidate_*.docx"):
        if prior.is_file() and prior.resolve().parent == root:
            prior.unlink()
    content_hash = document_hash(document)
    template = select_template(document.metadata, template_dir)
    candidate = root / f"resume_candidate_{content_hash[:12]}.docx"
    report = render_resume_candidate(template.path, document, candidate)
    return ResumePreflight(content_hash, template, candidate, report)


def promote_preflight(
    document: ResumeDocument,
    preflight: ResumePreflight,
    *,
    output_root: str | Path,
    export_docx: bool,
    export_pdf: bool,
) -> GeneratedResume:
    if document_hash(document) != preflight.content_hash:
        raise ValueError("Resume JSON changed after Word preflight; check the layout again.")
    if not preflight.passed:
        raise ValueError("Word preflight must pass before permanent generation.")
    expected_template = select_template(document.metadata, preflight.template.path.parent)
    if expected_template.path.resolve() != preflight.template.path.resolve():
        raise ValueError("Template selection changed after Word preflight.")
    output = next_versioned_output(
        output_root, document.metadata.company, document.metadata.role,
    )
    paths = promote_resume_candidate(
        preflight.candidate_path,
        output.docx_path,
        export_docx=export_docx,
        export_pdf=export_pdf,
    )
    preflight.candidate_path.unlink(missing_ok=True)
    return GeneratedResume(paths=paths, output=output)
