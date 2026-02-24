from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from json import JSONDecodeError
from typing import Any

from pydantic import ValidationError

from .schema import ResumeResponse


KNOWN_RESPONSE_KEYS = {"status", "clarifying_questions", "resume"}
KNOWN_RESUME_KEYS = {
    "header",
    "professional_summary",
    "technical_skills",
    "work_experience",
    "projects",
    "education_lines",
    "jd_match_map",
}
KNOWN_WORK_KEYS = {"thorogood_bullets", "gwu_gta_bullets"}
KNOWN_PROJECTS_KEYS = {"wtchtwr_bullets", "project2", "project3"}
KNOWN_PROJECT_ENTRY_KEYS = {"name", "bullets"}
ALLOWED_STATUS = {"final", "questions"}


@dataclass
class ValidationOutcome:
    is_valid: bool
    can_generate: bool
    status: str | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    payload: ResumeResponse | None = None
    normalized_json: dict[str, Any] | None = None
    extracted_json: bool = False
    additional_info: dict[str, Any] = field(default_factory=dict)


def _escape_control_chars_in_strings(text: str) -> str:
    out: list[str] = []
    in_string = False
    escaped = False

    for char in text:
        if in_string:
            if escaped:
                out.append(char)
                escaped = False
                continue
            if char == "\\":
                out.append(char)
                escaped = True
                continue
            if char == '"':
                out.append(char)
                in_string = False
                continue
            if char == "\n":
                out.append("\\n")
                continue
            if char == "\r":
                out.append("\\r")
                continue
            if char == "\t":
                out.append("\\t")
                continue
            out.append(char)
            continue

        out.append(char)
        if char == '"':
            in_string = True

    return "".join(out)


def _extract_status_value(text: str) -> str | None:
    match = re.search(r'"status"\s*:\s*"([^"]+)"', text)
    if not match:
        return None
    status = match.group(1).strip()
    if status in ALLOWED_STATUS:
        return status
    return None


def _extract_object_after_key(text: str, key: str) -> str | None:
    key_match = re.search(rf'"{re.escape(key)}"\s*:', text)
    if not key_match:
        return None

    idx = key_match.end()
    while idx < len(text) and text[idx].isspace():
        idx += 1
    if idx >= len(text) or text[idx] != "{":
        return None

    start = idx
    depth = 0
    in_string = False
    escaped = False

    for pos in range(start, len(text)):
        char = text[pos]
        if in_string:
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue
        if char == "{":
            depth += 1
            continue
        if char == "}":
            depth -= 1
            if depth == 0:
                return text[start : pos + 1]

    return None


def _looks_like_resume_content(candidate: Any) -> bool:
    if not isinstance(candidate, dict):
        return False
    required = {
        "header",
        "professional_summary",
        "technical_skills",
        "work_experience",
        "projects",
    }
    return required.issubset(candidate.keys())


def _find_nested_resume(candidate: Any) -> dict[str, Any] | None:
    if isinstance(candidate, dict):
        if _looks_like_resume_content(candidate):
            return candidate
        nested_resume = candidate.get("resume")
        if _looks_like_resume_content(nested_resume):
            return nested_resume
        for value in candidate.values():
            found = _find_nested_resume(value)
            if found is not None:
                return found
    elif isinstance(candidate, list):
        for value in candidate:
            found = _find_nested_resume(value)
            if found is not None:
                return found
    return None


def _score_candidate(candidate: dict[str, Any]) -> float:
    score = 0.0
    if isinstance(candidate.get("resume"), dict):
        score += 100.0
    if "status" in candidate:
        score += 40.0
    if _looks_like_resume_content(candidate):
        score += 80.0
    if _find_nested_resume(candidate) is not None:
        score += 20.0
    try:
        score += len(json.dumps(candidate, ensure_ascii=False)) / 1000.0
    except (TypeError, ValueError):
        pass
    return score


def _select_best_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    best = max(candidates, key=_score_candidate)
    return best


def _canonicalize_resume(resume: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    canonical: dict[str, Any] = {}
    extras: dict[str, Any] = {}

    for key, value in resume.items():
        if key in KNOWN_RESUME_KEYS:
            canonical[key] = value
        else:
            extras[key] = value

    work = canonical.get("work_experience")
    if isinstance(work, dict):
        normalized_work: dict[str, Any] = {}
        work_extras: dict[str, Any] = {}

        thorogood_bullets = work.get("thorogood_bullets")
        if isinstance(thorogood_bullets, list):
            normalized_work["thorogood_bullets"] = thorogood_bullets
        else:
            thorogood_obj = work.get("thorogood")
            if isinstance(thorogood_obj, dict):
                nested_bullets = thorogood_obj.get("bullets")
                if isinstance(nested_bullets, list):
                    normalized_work["thorogood_bullets"] = nested_bullets
                thorogood_meta = {
                    k: v for k, v in thorogood_obj.items() if k != "bullets"
                }
                if thorogood_meta:
                    work_extras["thorogood_meta"] = thorogood_meta

        gwu_gta_bullets = work.get("gwu_gta_bullets")
        if isinstance(gwu_gta_bullets, list):
            normalized_work["gwu_gta_bullets"] = gwu_gta_bullets
        else:
            gwu_gta_obj = work.get("gwu_gta")
            if isinstance(gwu_gta_obj, dict):
                nested_bullets = gwu_gta_obj.get("bullets")
                if isinstance(nested_bullets, list):
                    normalized_work["gwu_gta_bullets"] = nested_bullets
                gwu_gta_meta = {k: v for k, v in gwu_gta_obj.items() if k != "bullets"}
                if gwu_gta_meta:
                    work_extras["gwu_gta_meta"] = gwu_gta_meta

        passthrough_work_extras = {
            k: v
            for k, v in work.items()
            if k not in {"thorogood_bullets", "gwu_gta_bullets", "thorogood", "gwu_gta"}
        }
        if passthrough_work_extras:
            work_extras["unmapped_fields"] = passthrough_work_extras

        if work_extras:
            extras["work_experience_extra_fields"] = work_extras
        canonical["work_experience"] = normalized_work

    projects = canonical.get("projects")
    if isinstance(projects, dict):
        normalized_projects: dict[str, Any] = {}
        projects_extras: dict[str, Any] = {}

        wtchtwr_bullets = projects.get("wtchtwr_bullets")
        if isinstance(wtchtwr_bullets, list):
            normalized_projects["wtchtwr_bullets"] = wtchtwr_bullets
        else:
            wtchtwr_obj = projects.get("wtchtwr")
            if isinstance(wtchtwr_obj, dict):
                nested_bullets = wtchtwr_obj.get("bullets")
                if isinstance(nested_bullets, list):
                    normalized_projects["wtchtwr_bullets"] = nested_bullets
                wtchtwr_meta = {k: v for k, v in wtchtwr_obj.items() if k != "bullets"}
                if wtchtwr_meta:
                    projects_extras["wtchtwr_meta"] = wtchtwr_meta

        for entry_key in ("project2", "project3"):
            entry_val = projects.get(entry_key)
            if isinstance(entry_val, dict):
                entry_extras = {
                    k: v for k, v in entry_val.items() if k not in KNOWN_PROJECT_ENTRY_KEYS
                }
                if entry_extras:
                    projects_extras[f"{entry_key}_extra_fields"] = entry_extras
                normalized_projects[entry_key] = {
                    k: entry_val.get(k) for k in KNOWN_PROJECT_ENTRY_KEYS if k in entry_val
                }
            elif entry_val is not None:
                projects_extras[f"{entry_key}_raw"] = entry_val

        passthrough_project_extras = {
            k: v
            for k, v in projects.items()
            if k not in {"wtchtwr_bullets", "wtchtwr", "project2", "project3"}
        }
        if passthrough_project_extras:
            projects_extras["unmapped_fields"] = passthrough_project_extras

        if projects_extras:
            extras["projects_extra_fields"] = projects_extras

        canonical["projects"] = normalized_projects

    return canonical, extras


def _normalize_payload(
    parsed: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    warnings: list[str] = []
    additional_info: dict[str, Any] = {}

    status = parsed.get("status")
    if not isinstance(status, str) or status not in ALLOWED_STATUS:
        status = "final"
        warnings.append("Missing or invalid status; defaulted to 'final'.")

    clarifying_questions = parsed.get("clarifying_questions")
    if clarifying_questions is not None and not isinstance(clarifying_questions, list):
        clarifying_questions = None
        warnings.append("clarifying_questions was not a list and was ignored.")

    resume_obj: dict[str, Any] | None = None
    if _looks_like_resume_content(parsed.get("resume")):
        resume_obj = parsed["resume"]
    elif _looks_like_resume_content(parsed):
        resume_obj = parsed
        warnings.append("Input looked like a resume object and was wrapped automatically.")
    else:
        resume_obj = _find_nested_resume(parsed)
        if resume_obj is not None:
            warnings.append("Found a nested resume object and used it for validation.")

    if status == "final" and resume_obj is None:
        raise ValueError(
            "JSON does not contain a valid resume object with required fields."
        )

    top_level_extras = {k: v for k, v in parsed.items() if k not in KNOWN_RESPONSE_KEYS}
    if top_level_extras:
        additional_info.update(top_level_extras)

    normalized: dict[str, Any] = {
        "status": status,
        "clarifying_questions": clarifying_questions,
        "resume": None,
    }

    if resume_obj is not None:
        canonical_resume, resume_extras = _canonicalize_resume(resume_obj)
        normalized["resume"] = canonical_resume
        resume_text = resume_extras.get("resume_text")
        if isinstance(resume_text, str):
            additional_info["resume_text"] = resume_text
        if resume_extras:
            additional_info["resume_extra_fields"] = resume_extras

    return normalized, additional_info, warnings


def _parse_json_with_salvage(raw_text: str) -> tuple[dict[str, Any], bool, list[str]]:
    text = (raw_text or "").strip()
    if not text:
        raise ValueError("No JSON provided.")

    notes: list[str] = []
    sanitized = _escape_control_chars_in_strings(text)

    variants: list[tuple[str, str, bool]] = [("original", text, False)]
    if sanitized != text:
        variants.append(("sanitized-control-chars", sanitized, True))

    for label, variant, salvaged in variants:
        try:
            parsed = json.loads(variant)
        except JSONDecodeError:
            continue
        if not isinstance(parsed, dict):
            raise ValueError("Top-level JSON must be an object.")
        if salvaged:
            notes.append(f"Parsed JSON after {label} salvage.")
        return parsed, salvaged, notes

    for variant in (sanitized, text):
        resume_object = _extract_object_after_key(variant, "resume")
        if not resume_object:
            continue
        try:
            resume_dict = json.loads(_escape_control_chars_in_strings(resume_object))
        except JSONDecodeError:
            continue
        status = _extract_status_value(variant) or "final"
        notes.append(
            "Parsed resume block even though the full payload was malformed."
        )
        return {
            "status": status,
            "clarifying_questions": [],
            "resume": resume_dict,
        }, True, notes

    decoder = json.JSONDecoder()
    candidates: list[dict[str, Any]] = []
    for idx, char in enumerate(sanitized):
        if char != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(sanitized[idx:])
        except JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            candidates.append(parsed)

    if candidates:
        notes.append(
            "Detected extra or malformed text and salvaged the strongest JSON object."
        )
        return _select_best_candidate(candidates), True, notes

    raise ValueError(
        "Unable to parse JSON. Paste valid JSON or include one valid JSON object block."
    )


def _validate_constraints(payload: ResumeResponse) -> list[str]:
    # JSON validation now checks structural/schema correctness only.
    # Layout constraints (single page + single-line bullet rendering)
    # are enforced during DOCX generation in render.py.
    if payload.status == "questions":
        return []

    if payload.resume is None:
        return ["resume is required when status='final'."]

    return []


def validate_json_text(raw_text: str) -> ValidationOutcome:
    try:
        parsed, salvaged, parse_notes = _parse_json_with_salvage(raw_text)
        normalized, additional_info, normalize_notes = _normalize_payload(parsed)
    except ValueError as exc:
        return ValidationOutcome(
            is_valid=False,
            can_generate=False,
            errors=[str(exc)],
        )

    warnings = [*parse_notes, *normalize_notes]

    try:
        payload = ResumeResponse.model_validate(normalized)
    except ValidationError as exc:
        formatted_errors: list[str] = []
        for err in exc.errors():
            path = ".".join(str(item) for item in err["loc"])
            formatted_errors.append(f"{path}: {err['msg']}")
        return ValidationOutcome(
            is_valid=False,
            can_generate=False,
            errors=formatted_errors,
            warnings=warnings,
            extracted_json=salvaged,
            additional_info=additional_info,
        )

    errors = _validate_constraints(payload)

    return ValidationOutcome(
        is_valid=len(errors) == 0,
        can_generate=(len(errors) == 0 and payload.status == "final"),
        status=payload.status,
        errors=errors,
        warnings=warnings,
        payload=payload,
        normalized_json=payload.model_dump(mode="json"),
        extracted_json=salvaged,
        additional_info=additional_info,
    )
