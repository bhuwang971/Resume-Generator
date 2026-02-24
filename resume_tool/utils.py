from __future__ import annotations

import json
import re
from pathlib import Path


WINDOWS_INVALID_CHARS = r'[<>:"/\\|?*]'


def word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'/-]*", text or ""))


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def sanitize_filename_part(value: str, fallback: str) -> str:
    cleaned = re.sub(WINDOWS_INVALID_CHARS, "", (value or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.strip(". ")
    return cleaned or fallback


def build_resume_filename(name: str, company: str, role: str) -> str:
    safe_name = sanitize_filename_part(name, "Candidate")
    safe_company = sanitize_filename_part(company, "Company")
    safe_role = sanitize_filename_part(role, "")

    parts = ["Resume", safe_name, safe_company]
    if safe_role:
        parts.append(safe_role)
    return f"{' - '.join(parts)}.docx"


def pretty_json(data: dict) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


def load_text_file(path: Path, fallback: str = "") -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return fallback
