from __future__ import annotations

from dataclasses import dataclass


TRACKER_STATUSES = (
    "Saved", "Applied", "Interview", "Rejected", "Offer", "Withdrawn",
)


@dataclass(frozen=True)
class TrackerRecord:
    id: str
    dedupe_key: str
    company: str
    role: str
    location: str
    compensation: str
    status: str
    date_added: str
    application_date: str
    job_url: str
    docx_path: str
    pdf_path: str
    folder_path: str
    created_at: str
    updated_at: str
