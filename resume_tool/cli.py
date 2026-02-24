from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .preview import build_resume_preview
from .render import render_resume_docx
from .template_prep import TemplatePrepError, prepare_template
from .utils import build_resume_filename, pretty_json
from .validate import validate_json_text


DEFAULT_OUTPUT_DIR = Path(r"C:\Users\bhuwa\Downloads\Applications US")


def _read_json_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m resume_tool.cli",
        description="Validate GPT JSON and render tailored resume DOCX from a prepped template.",
    )
    parser.add_argument("--template", required=True, help="Path to source or prepped template DOCX")
    parser.add_argument("--json", help="Path to JSON payload from your GPT")
    parser.add_argument("--out", help="Output DOCX path")
    parser.add_argument("--prep-template", action="store_true", help="Create a prepped placeholder template")
    parser.add_argument("--prepped-out", help="Path for prepped template output")
    parser.add_argument("--mapping-json", help="Optional mapping.json for manual paragraph indices")
    parser.add_argument("--mapping-out", help="Where to write mapping.json during prep")
    parser.add_argument("--out-json", help="Write validated normalized JSON")
    parser.add_argument("--out-txt", help="Write resume preview as .txt")
    parser.add_argument("--company", default="Company", help="Company name for default output filename")
    parser.add_argument("--role", default="Role", help="Role name for default output filename")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Default output directory used when --out is omitted",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    template_path = Path(args.template)
    if not template_path.exists():
        print(f"Template not found: {template_path}")
        return 1

    template_for_render = template_path

    if args.prep_template:
        prepped_out = (
            Path(args.prepped_out)
            if args.prepped_out
            else template_path.with_name(f"{template_path.stem}.prepped.docx")
        )

        mapping = None
        if args.mapping_json:
            mapping_path = Path(args.mapping_json)
            mapping = json.loads(mapping_path.read_text(encoding="utf-8"))

        try:
            prepare_template(
                template_path=template_path,
                output_path=prepped_out,
                mapping_output_path=args.mapping_out,
                mapping=mapping,
            )
        except TemplatePrepError as exc:
            print(f"Template prep failed: {exc}")
            return 1

        print(f"Prepped template created: {prepped_out}")
        template_for_render = prepped_out

        if not args.json:
            return 0

    if not args.json:
        print("--json is required unless only running --prep-template.")
        return 1

    json_path = Path(args.json)
    if not json_path.exists():
        print(f"JSON file not found: {json_path}")
        return 1

    outcome = validate_json_text(_read_json_file(json_path))

    for warning in outcome.warnings:
        print(f"Warning: {warning}")

    if outcome.errors:
        print("Validation errors:")
        for error in outcome.errors:
            print(f"- {error}")
        return 1

    if outcome.status == "questions":
        print("GPT returned clarifying questions. Resolve these before generating a resume:")
        for question in (outcome.payload.clarifying_questions or []):
            print(f"- {question}")
        return 2

    payload = outcome.payload
    if payload is None or payload.resume is None:
        print("Validated payload missing resume content.")
        return 1

    resume = payload.resume
    preview_text = build_resume_preview(resume)

    output_path: Path
    if args.out:
        output_path = Path(args.out)
    else:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / build_resume_filename(
            name=resume.header.name,
            company=args.company,
            role=args.role,
        )

    try:
        render_resume_docx(template_for_render, resume, output_path)
    except Exception as exc:  # noqa: BLE001
        print(f"DOCX render failed: {exc}")
        return 1

    print(f"Resume generated: {output_path}")

    if args.out_json and outcome.normalized_json is not None:
        out_json_path = Path(args.out_json)
        out_json_path.parent.mkdir(parents=True, exist_ok=True)
        out_json_path.write_text(pretty_json(outcome.normalized_json), encoding="utf-8")
        print(f"Validated JSON written: {out_json_path}")

    if args.out_txt:
        out_txt_path = Path(args.out_txt)
        out_txt_path.parent.mkdir(parents=True, exist_ok=True)
        out_txt_path.write_text(preview_text, encoding="utf-8")
        print(f"Resume preview written: {out_txt_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
