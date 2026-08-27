from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Iterable

from pydantic import ValidationError

from .schema import ResumeDocument


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    message: str


@dataclass(frozen=True)
class ValidationResult:
    payload: ResumeDocument | None
    errors: tuple[ValidationIssue, ...] = ()

    @property
    def is_valid(self) -> bool:
        return self.payload is not None and not self.errors


def validate_json_text(raw_text: str) -> ValidationResult:
    text = (raw_text or "").strip()
    if not text:
        return ValidationResult(None, (ValidationIssue("$", "Paste Resume JSON first."),))
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        return ValidationResult(None, (
            ValidationIssue("$", f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}."),
        ))
    if not isinstance(parsed, dict):
        return ValidationResult(None, (ValidationIssue("$", "Top-level JSON must be an object."),))
    try:
        payload = ResumeDocument.model_validate(parsed)
    except ValidationError as exc:
        issues = tuple(
            ValidationIssue(_error_path(item.get("loc", ())), _clean_message(str(item["msg"])))
            for item in exc.errors()
        )
        return ValidationResult(None, issues)
    return ValidationResult(payload)


def format_json_text(raw_text: str) -> str:
    parsed = json.loads((raw_text or "").strip())
    if not isinstance(parsed, dict):
        raise ValueError("Top-level JSON must be an object.")
    return json.dumps(parsed, ensure_ascii=False, indent=2)


def build_correction_prompt(
    raw_text: str,
    validation_errors: Iterable[ValidationIssue] = (),
    layout_failures: Iterable[dict] = (),
    *,
    page_count: int | None = None,
) -> str:
    failures = [
        {"path": issue.path, "message": issue.message}
        for issue in validation_errors
    ]
    failures.extend(dict(item) for item in layout_failures)
    if page_count is not None and page_count != 1:
        failures.append({"path": "resume", "message": f"Rendered resume has {page_count} pages; exactly 1 is required."})
    constraints = (
        "Summary: 50-60 words; Skills: exactly six 'Category: item, item, item' strings; "
        "iLink/GTA/Thorogood bullets: exactly 6/3/7; one project: four bullets and project2=null; "
        "two projects: three bullets each; every bullet: at most 17 words; physical output: one page "
        "with one-line bullets and no unacceptable Skills overflow."
    )
    return (
        "Correct only the failing structural or layout fields. Return the complete JSON object only.\n\n"
        f"REQUIRED CONSTRAINTS\n{constraints}\n\n"
        f"FAILING FIELDS\n{json.dumps(failures, ensure_ascii=False, indent=2)}\n\n"
        f"CURRENT JSON\n{raw_text.strip()}"
    )


def _error_path(location) -> str:
    if not location:
        return "$"
    path = "$"
    for part in location:
        path += f"[{part}]" if isinstance(part, int) else f".{part}"
    return path


def _clean_message(message: str) -> str:
    prefix = "Value error, "
    return message[len(prefix):] if message.startswith(prefix) else message
