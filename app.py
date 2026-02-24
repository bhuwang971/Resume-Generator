from __future__ import annotations

import json
import os
from pathlib import Path

import streamlit as st

from resume_tool.render import render_resume_docx
from resume_tool.utils import build_resume_filename, ensure_directory
from resume_tool.validate import validate_json_text


PROJECT_ROOT = Path(__file__).resolve().parent
TEMPLATE_DIR = PROJECT_ROOT / "resume_tool" / "templates"
DEFAULT_BASE_TEMPLATE_PATH = TEMPLATE_DIR / "resume.base.docx"
DEFAULT_PREPPED_TEMPLATE_PATH = TEMPLATE_DIR / "resume.prepped.docx"
LEGACY_BASE_TEMPLATE_PATH = TEMPLATE_DIR / "Resume - Bhuwan Gupta.docx"
LEGACY_PREPPED_TEMPLATE_PATH = TEMPLATE_DIR / "Resume - Bhuwan Gupta.prepped.docx"
DEFAULT_OUTPUT_DIR = Path(r"C:\Users\bhuwa\Downloads\Applications US")


def _resolve_env_path(env_key: str, default_path: Path) -> Path:
    raw_value = os.getenv(env_key, "").strip()
    if not raw_value:
        return default_path
    candidate = Path(raw_value)
    if candidate.is_absolute():
        return candidate
    return PROJECT_ROOT / candidate


BASE_TEMPLATE_PATH = _resolve_env_path("RESUME_BASE_TEMPLATE_PATH", DEFAULT_BASE_TEMPLATE_PATH)
PREPPED_TEMPLATE_PATH = _resolve_env_path(
    "RESUME_PREPPED_TEMPLATE_PATH", DEFAULT_PREPPED_TEMPLATE_PATH
)
CONFIGURED_OUTPUT_DIR = _resolve_env_path("RESUME_OUTPUT_DIR", DEFAULT_OUTPUT_DIR)

if (
    PREPPED_TEMPLATE_PATH == DEFAULT_PREPPED_TEMPLATE_PATH
    and not PREPPED_TEMPLATE_PATH.exists()
    and LEGACY_PREPPED_TEMPLATE_PATH.exists()
):
    PREPPED_TEMPLATE_PATH = LEGACY_PREPPED_TEMPLATE_PATH

if (
    BASE_TEMPLATE_PATH == DEFAULT_BASE_TEMPLATE_PATH
    and not BASE_TEMPLATE_PATH.exists()
    and LEGACY_BASE_TEMPLATE_PATH.exists()
):
    BASE_TEMPLATE_PATH = LEGACY_BASE_TEMPLATE_PATH


def _open_path(path: Path) -> None:
    os.startfile(str(path.resolve()))


def _show_additional_json_info(additional_info: dict) -> None:
    if not additional_info:
        return

    st.subheader("Additional JSON Info")

    resume_text = additional_info.get("resume_text")
    if isinstance(resume_text, str) and resume_text.strip():
        st.text_area("resume_text", value=resume_text, height=320, key="additional_resume_text")

    other_fields = {k: v for k, v in additional_info.items() if k != "resume_text"}
    if other_fields:
        st.text_area(
            "additional_fields_json",
            value=json.dumps(other_fields, indent=2, ensure_ascii=False),
            height=260,
            key="additional_fields_json",
        )


@st.dialog("Role Name Warning")
def _role_name_warning_dialog() -> None:
    st.warning("Role name is empty. Continue without role name?")
    col_enter, col_continue = st.columns(2)
    with col_enter:
        if st.button("Enter role name", key="dialog_enter_role"):
            st.session_state["attempt_generate"] = False
            st.session_state["role_empty_confirmed"] = False
            st.rerun()
    with col_continue:
        if st.button("Continue", key="dialog_continue_without_role"):
            st.session_state["role_empty_confirmed"] = True
            st.rerun()


def main() -> None:
    st.set_page_config(page_title="Resume DOCX Tailor", layout="wide")
    st.title("Resume DOCX Tailor (Resume Only)")
    st.caption("No cover letter generation. No OpenAI API calls. Paste GPT JSON manually.")

    if "attempt_generate" not in st.session_state:
        st.session_state["attempt_generate"] = False
    if "role_empty_confirmed" not in st.session_state:
        st.session_state["role_empty_confirmed"] = False

    st.subheader("Template (Backend)")
    st.write(f"Base template: `{BASE_TEMPLATE_PATH}`")
    st.write(f"Prepped template: `{PREPPED_TEMPLATE_PATH}`")

    if not PREPPED_TEMPLATE_PATH.exists():
        st.error(
            "Prepped template is missing. Provide one file with placeholders and rerun.\n\n"
            f"Expected path: `{PREPPED_TEMPLATE_PATH}`\n"
            "Set a custom path via env var `RESUME_PREPPED_TEMPLATE_PATH`."
        )
        st.stop()

    output_dir_raw = st.text_input(
        "Output folder location",
        value=str(CONFIGURED_OUTPUT_DIR),
        help="Can also be preconfigured via RESUME_OUTPUT_DIR",
    )
    output_dir = ensure_directory(Path(output_dir_raw))

    col_company, col_role = st.columns(2)
    with col_company:
        company_name = st.text_input("Company name")
    with col_role:
        role_name = st.text_input("Role name")

    raw_json = st.text_area("Paste JSON from GPT", height=320)

    if st.button("Validate & Generate Resume"):
        st.session_state["attempt_generate"] = True
        st.session_state["last_output_file"] = st.session_state.get("last_output_file", "")

    if st.session_state["attempt_generate"]:
        missing_fields: list[str] = []
        if not company_name.strip():
            missing_fields.append("Company name")
        if missing_fields:
            st.error(f"Please input the field: {', '.join(missing_fields)}")
            st.session_state["attempt_generate"] = False
            st.stop()

        if not role_name.strip() and not st.session_state["role_empty_confirmed"]:
            _role_name_warning_dialog()
            st.stop()

        outcome = validate_json_text(raw_json)

        for warning in outcome.warnings:
            st.warning(warning)

        _show_additional_json_info(outcome.additional_info)

        if outcome.errors:
            st.error("Validation failed:")
            for err in outcome.errors:
                st.write(f"- {err}")
            st.session_state["attempt_generate"] = False
            st.session_state["role_empty_confirmed"] = False
            st.stop()

        if outcome.status == "questions" and outcome.payload is not None:
            st.info("GPT returned clarifying questions. Resume generation is blocked.")
            for question in outcome.payload.clarifying_questions or []:
                st.write(f"- {question}")
            st.session_state["attempt_generate"] = False
            st.session_state["role_empty_confirmed"] = False
            st.stop()

        if not outcome.can_generate or outcome.payload is None or outcome.payload.resume is None:
            st.error("Cannot generate resume from the current JSON payload.")
            st.session_state["attempt_generate"] = False
            st.session_state["role_empty_confirmed"] = False
            st.stop()

        resume = outcome.payload.resume
        filename = build_resume_filename(
            name=resume.header.name,
            company=company_name,
            role=role_name,
        )
        output_path = output_dir / filename
        if output_path.exists():
            st.info(f"Existing file will be overwritten: {output_path}")

        try:
            render_resume_docx(PREPPED_TEMPLATE_PATH, resume, output_path)
        except Exception as exc:  # noqa: BLE001
            st.error(f"DOCX generation failed: {exc}")
            st.session_state["attempt_generate"] = False
            st.session_state["role_empty_confirmed"] = False
            st.stop()

        st.success(f"Resume generated successfully: {output_path}")
        st.session_state["last_output_file"] = str(output_path)
        st.session_state["attempt_generate"] = False
        st.session_state["role_empty_confirmed"] = False

    last_output_file_raw = st.session_state.get("last_output_file", "")
    if last_output_file_raw:
        output_file_path = Path(last_output_file_raw)
        if st.button("Open generated resume"):
            try:
                _open_path(output_file_path)
            except Exception as exc:  # noqa: BLE001
                st.error(f"Could not open generated file automatically: {exc}")
                st.info(f"Open manually: {output_file_path}")


if __name__ == "__main__":
    main()
