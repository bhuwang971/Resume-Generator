from __future__ import annotations

import hashlib
import json
from pathlib import Path

import streamlit as st

from resume_tool.render import layout_failure_dicts
from resume_tool.schema import ResumeDocument
from resume_tool.template_selector import select_template
from resume_tool.validate import build_correction_prompt, format_json_text, validate_json_text
from resume_tool.workflow import (
    ResumePreflight, create_preflight, document_hash, promote_preflight,
)
from tracker import TrackerDatabase, TrackerService
from tracker.service import open_local_path

from .components import render_copy_button


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = PROJECT_ROOT / "resume_tool" / "templates"
TEMP_ROOT = PROJECT_ROOT / ".tmp" / "resume_render_checks"
OUTPUT_ROOT = PROJECT_ROOT / "outputs"
TRACKER_DB = PROJECT_ROOT / "data" / "tracker.db"
SAMPLE_JSON = PROJECT_ROOT / "examples" / "sample_output.json"


def render_generator() -> None:
    st.title("Generate Resume")
    st.caption("Paste JSON from your Custom GPT. Validation, Word preflight, rendering, and tracking are fully local.")
    if "pending_resume_json" in st.session_state:
        st.session_state["resume_json"] = st.session_state.pop("pending_resume_json")
    if "resume_json" not in st.session_state:
        st.session_state["resume_json"] = SAMPLE_JSON.read_text(encoding="utf-8") if SAMPLE_JSON.exists() else "{}"

    raw_tab, form_tab = st.tabs(("Raw JSON", "Friendly Form"))
    with raw_tab:
        raw_text = st.text_area("Paste Resume JSON", height=520, key="resume_json")
        format_column, validate_column = st.columns(2)
        if format_column.button("Format JSON", use_container_width=True):
            try:
                st.session_state["pending_resume_json"] = format_json_text(raw_text)
            except (ValueError, json.JSONDecodeError) as exc:
                st.error(f"Cannot format JSON: {exc}")
            else:
                st.rerun()
        validate_clicked = validate_column.button("Validate JSON", type="primary", use_container_width=True)

    validation = validate_json_text(raw_text)
    with form_tab:
        if validation.is_valid and validation.payload is not None:
            _friendly_form(validation.payload)
        else:
            st.info("Validate structurally correct JSON to enable the Friendly Form.")

    if validate_clicked or st.session_state.get("validated_json_hash") == _text_hash(raw_text):
        st.session_state["validated_json_hash"] = _text_hash(raw_text)
        _validation_result(raw_text, validation)

    if not validation.is_valid or validation.payload is None:
        return
    document = validation.payload
    selection = select_template(document.metadata, TEMPLATE_DIR)
    st.info(f"Selected Template: {selection.label}")
    if not selection.path.is_file():
        st.error(f"Fixed local template is missing: {selection.path}")
        return

    preflight = st.session_state.get("resume_preflight")
    if not isinstance(preflight, ResumePreflight) or preflight.content_hash != document_hash(document):
        preflight = None
    if st.button("Check Word Layout", type="primary"):
        try:
            preflight = create_preflight(
                document, template_dir=TEMPLATE_DIR, temp_root=TEMP_ROOT,
            )
        except Exception as exc:  # noqa: BLE001
            st.error(f"Word layout check failed: {exc}")
        else:
            st.session_state["resume_preflight"] = preflight
    if preflight is None:
        st.info("Run the Word layout check before generating permanent files.")
        return
    _preflight_result(raw_text, preflight)
    if not preflight.passed:
        return

    st.subheader("Generate permanent files")
    docx_col, pdf_col, both_col = st.columns(3)
    choice = None
    if docx_col.button("Generate DOCX", use_container_width=True):
        choice = (True, False)
    if pdf_col.button("Generate PDF", use_container_width=True):
        choice = (False, True)
    if both_col.button("Generate DOCX + PDF", type="primary", use_container_width=True):
        choice = (True, True)
    if choice:
        try:
            generated = promote_preflight(
                document, preflight, output_root=OUTPUT_ROOT,
                export_docx=choice[0], export_pdf=choice[1],
            )
            tracker = TrackerService(TrackerDatabase(TRACKER_DB))
            record, created = tracker.upsert_from_generation(
                document.metadata, generated.paths, generated.output.folder,
            )
        except Exception as exc:  # noqa: BLE001
            st.error(f"Generation failed: {exc}")
        else:
            st.session_state.pop("resume_preflight", None)
            st.session_state["last_generated"] = generated
            st.success(
                f"Generated resume_v{generated.output.version}; tracker record "
                f"{'created' if created else 'updated'} for {record.company or 'Unknown Company'}."
            )
    _generated_actions()


def _validation_result(raw_text, validation) -> None:
    if validation.is_valid:
        st.success("JSON structure and objective resume constraints passed.")
        return
    st.error("JSON validation failed.")
    for issue in validation.errors:
        st.error(f"{issue.path}: {issue.message}")
    correction = build_correction_prompt(raw_text, validation.errors)
    st.text_area("Structural correction prompt", correction, height=280)
    render_copy_button(correction, "Copy Correction Prompt", "structural-correction")


def _preflight_result(raw_text: str, preflight: ResumePreflight) -> None:
    report = preflight.report
    if report.passed:
        st.success("Word layout passed: 1 page, no bullet overflow, no Skills overflow.")
    else:
        st.error(f"Word layout failed. Page count: {report.page_count}")
        for item in (*report.bullet_overflows, *report.skill_overflows):
            st.error(f"{item.field_path}: {item.line_count} lines")
            st.code(item.text)
        correction = build_correction_prompt(
            raw_text,
            layout_failures=layout_failure_dicts(report),
            page_count=report.page_count,
        )
        st.text_area("Layout correction prompt", correction, height=300)
        render_copy_button(correction, "Copy Layout Correction Prompt", "layout-correction")
    if preflight.candidate_path.is_file():
        st.download_button(
            "Download temporary diagnostic DOCX",
            data=preflight.candidate_path.read_bytes(),
            file_name="temporary_resume_layout_check.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )


def _friendly_form(document: ResumeDocument) -> None:
    payload = document.model_dump(mode="json")
    source_hash = _text_hash(json.dumps(payload, sort_keys=True))
    if st.session_state.get("friendly_source_hash") != source_hash:
        _load_form_state(payload)
        st.session_state["friendly_source_hash"] = source_hash
    st.subheader("Metadata")
    left, right = st.columns(2)
    for key, label in (("company", "Company"), ("location", "Location"), ("job_url", "Job URL"), ("project_count", "Project Count"), ("output_format", "Output Format")):
        with left:
            _metadata_widget(key, label)
    for key, label in (("role", "Role"), ("compensation", "Compensation"), ("source", "Source"), ("include_awards", "Include Awards")):
        with right:
            _metadata_widget(key, label)
    st.subheader("Resume")
    st.text_area("Professional Summary", key="form_summary", height=140)
    for index in range(6):
        st.text_input(f"Skills line {index + 1}", key=f"form_skill_{index}")
    _string_fields("iLink bullet", "form_ilink", 6)
    _string_fields("GTA bullet", "form_gta", 3)
    _string_fields("Thorogood bullet", "form_thorogood", 7)
    st.text_input("Project 1 name", key="form_project1_name")
    project_count = int(st.session_state.get("form_meta_project_count", 1))
    _string_fields("Project 1 bullet", "form_project1", 4 if project_count == 1 else 3)
    if project_count == 2:
        st.text_input("Project 2 name", key="form_project2_name")
        _string_fields("Project 2 bullet", "form_project2", 3)
    if st.button("Apply Friendly Form to Raw JSON", type="primary"):
        st.session_state["pending_resume_json"] = json.dumps(
            _form_payload(), ensure_ascii=False, indent=2,
        )
        st.rerun()


def _metadata_widget(key: str, label: str) -> None:
    state_key = f"form_meta_{key}"
    if key == "project_count":
        st.radio(label, (1, 2), horizontal=True, key=state_key)
    elif key == "include_awards":
        st.checkbox(label, key=state_key)
    elif key == "output_format":
        st.selectbox(label, ("docx", "pdf", "both"), key=state_key)
    else:
        st.text_input(label, key=state_key)


def _string_fields(label: str, prefix: str, count: int) -> None:
    st.markdown(f"**{label.replace(' bullet', '')}**")
    for index in range(count):
        st.text_input(f"{label} {index + 1}", key=f"{prefix}_{index}")


def _load_form_state(payload: dict) -> None:
    metadata = payload["metadata"]
    resume = payload["resume"]
    for key, value in metadata.items():
        st.session_state[f"form_meta_{key}"] = value
    st.session_state["form_summary"] = resume["professional_summary"]
    for index, value in enumerate(resume["technical_skills"]):
        st.session_state[f"form_skill_{index}"] = value
    for prefix, values in (
        ("form_ilink", resume["work_experience"]["ilink_bullets"]),
        ("form_gta", resume["work_experience"]["gwu_gta_bullets"]),
        ("form_thorogood", resume["work_experience"]["thorogood_bullets"]),
        ("form_project1", resume["projects"]["project1"]["bullets"]),
    ):
        for index, value in enumerate(values):
            st.session_state[f"{prefix}_{index}"] = value
    st.session_state["form_project1_name"] = resume["projects"]["project1"]["name"]
    project2 = resume["projects"].get("project2")
    st.session_state["form_project2_name"] = project2["name"] if project2 else ""
    for index in range(3):
        st.session_state[f"form_project2_{index}"] = project2["bullets"][index] if project2 else ""


def _form_payload() -> dict:
    count = int(st.session_state["form_meta_project_count"])
    metadata = {
        key: st.session_state[f"form_meta_{key}"]
        for key in (
            "company", "role", "location", "compensation", "job_url", "source",
            "project_count", "include_awards", "output_format",
        )
    }
    project1_count = 4 if count == 1 else 3
    return {
        "metadata": metadata,
        "resume": {
            "professional_summary": st.session_state["form_summary"],
            "technical_skills": [st.session_state[f"form_skill_{index}"] for index in range(6)],
            "work_experience": {
                "ilink_bullets": [st.session_state[f"form_ilink_{index}"] for index in range(6)],
                "gwu_gta_bullets": [st.session_state[f"form_gta_{index}"] for index in range(3)],
                "thorogood_bullets": [st.session_state[f"form_thorogood_{index}"] for index in range(7)],
            },
            "projects": {
                "project1": {
                    "name": st.session_state["form_project1_name"],
                    "bullets": [st.session_state[f"form_project1_{index}"] for index in range(project1_count)],
                },
                "project2": ({
                    "name": st.session_state["form_project2_name"],
                    "bullets": [st.session_state[f"form_project2_{index}"] for index in range(3)],
                } if count == 2 else None),
            },
        },
    }


def _generated_actions() -> None:
    generated = st.session_state.get("last_generated")
    if generated is None:
        return
    paths = generated.paths
    for label, path in (("Open DOCX", paths.docx_path), ("Open PDF", paths.pdf_path), ("Open Folder", generated.output.folder)):
        if path and st.button(label, key=f"generator_{label}_{path}"):
            try:
                open_local_path(path)
            except Exception as exc:  # noqa: BLE001
                st.error(f"Could not open {path}: {exc}")


def _text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
