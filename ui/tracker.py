from __future__ import annotations

from pathlib import Path

import streamlit as st

from tracker import TRACKER_STATUSES, TrackerDatabase, TrackerService
from tracker.service import open_local_path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRACKER_DB = PROJECT_ROOT / "data" / "tracker.db"
OUTPUT_ROOT = PROJECT_ROOT / "outputs"


def render_tracker() -> None:
    st.title("Tracker")
    service = TrackerService(TrackerDatabase(TRACKER_DB))
    records = service.list()
    if not records:
        st.info("No applications yet. Successful resume generation creates the first tracker row.")
        return
    st.dataframe([
        {
            "Company": item.company,
            "Role": item.role,
            "Location": item.location,
            "Compensation": item.compensation,
            "Status": item.status,
            "Date Added": item.date_added,
            "DOCX": item.docx_path,
            "PDF": item.pdf_path,
            "Folder": item.folder_path,
            "Job URL": item.job_url,
        }
        for item in records
    ], hide_index=True, use_container_width=True)
    for record in records:
        st.markdown(f"### {record.company or 'Unknown Company'} — {record.role or 'Unknown Role'}")
        action_columns = st.columns(4)
        selected_status = action_columns[0].selectbox(
            "Status", TRACKER_STATUSES, index=TRACKER_STATUSES.index(record.status),
            key=f"status_{record.id}",
        )
        if selected_status != record.status:
            service.set_status(record.id, selected_status)
            st.rerun()
        _open_button(action_columns[1], "DOCX", record.docx_path, record.id)
        _open_button(action_columns[2], "PDF", record.pdf_path, record.id)
        _open_button(action_columns[3], "Folder", record.folder_path, record.id)
        with st.expander("Edit / Delete"):
            with st.form(f"edit_{record.id}"):
                company = st.text_input("Company", record.company)
                role = st.text_input("Role", record.role)
                location = st.text_input("Location", record.location)
                compensation = st.text_input("Compensation", record.compensation)
                job_url = st.text_input("Job URL", record.job_url)
                if st.form_submit_button("Save changes"):
                    try:
                        service.update(
                            record.id, company=company, role=role, location=location,
                            compensation=compensation, job_url=job_url,
                        )
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Could not update tracker row: {exc}")
                    else:
                        st.rerun()
            confirm = st.checkbox("Confirm deletion", key=f"confirm_delete_{record.id}")
            delete_files = st.checkbox(
                "Also delete generated files", value=False, key=f"delete_files_{record.id}",
            )
            if st.button("Delete", disabled=not confirm, key=f"delete_{record.id}"):
                try:
                    service.delete(
                        record.id, delete_files=delete_files, output_root=OUTPUT_ROOT,
                    )
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Could not delete tracker row: {exc}")
                else:
                    st.rerun()


def _open_button(column, label: str, value: str, record_id: str) -> None:
    if column.button(label, disabled=not value, key=f"open_{label}_{record_id}"):
        try:
            open_local_path(value)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Could not open {value}: {exc}")
