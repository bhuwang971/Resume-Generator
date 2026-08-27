from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re


WORD_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9'/-]*")


def word_count(text: str) -> int:
    return len(WORD_PATTERN.findall(text or ""))


def sanitize_path_part(value: str, fallback: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]', "", (value or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip(". ")
    return cleaned or fallback


@dataclass(frozen=True)
class VersionedOutput:
    folder: Path
    version: int
    docx_path: Path
    pdf_path: Path


def next_versioned_output(
    output_root: str | Path, company: str, role: str,
) -> VersionedOutput:
    folder = (
        Path(output_root)
        / sanitize_path_part(company, "Unknown Company")
        / sanitize_path_part(role, "Unknown Role")
    )
    folder.mkdir(parents=True, exist_ok=True)
    versions = {
        int(match.group(1))
        for path in folder.glob("resume_v*.*")
        if (match := re.fullmatch(r"resume_v(\d+)\.(?:docx|pdf)", path.name, re.I))
    }
    version = max(versions, default=0) + 1
    return VersionedOutput(
        folder=folder,
        version=version,
        docx_path=folder / f"resume_v{version}.docx",
        pdf_path=folder / f"resume_v{version}.pdf",
    )


def pretty_json(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def is_within(path: str | Path, root: str | Path) -> bool:
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
    except ValueError:
        return False
    return True
