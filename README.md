# Resume DOCX Generator (Resume Only)

Local tool to generate a tailored resume DOCX from:
- a prepped DOCX template (Word formatting is preserved)
- JSON pasted from your Custom GPT

No OpenAI API calls are made by this app.
No cover letter features are included.

## What this project does

- Validates incoming JSON (schema + status flow)
- Accepts two JSON shapes (strict and nested variant)
- Renders DOCX with `docxtpl` using placeholders
- Enforces final layout checks:
  - resume must stay on 1 page
  - mapped bullet paragraphs must be 1 line each
- Overwrites existing output file if same name exists
- Opens generated DOCX directly from the UI
- Shows additional GPT fields (for example `resume_text`) in UI

## Who can use this

Anyone can use this with their own resume format. You are not restricted to Bhuwan's template.

You only need to provide your own prepped template DOCX with placeholders (details below).

## Tech stack

- Python 3.11+
- Streamlit UI
- `docxtpl` + `python-docx` for rendering
- `pywin32` + Microsoft Word for layout checks (page count and line count)

## Repository layout

```text
resume-docx-tailor/
  app.py
  requirements.txt
  README.md
  examples/
    sample_output.json
  resume_tool/
    __init__.py
    cli.py
    schema.py
    validate.py
    render.py
    template_prep.py
    preview.py
    utils.py
    templates/
      .gitkeep
```

## Prerequisites

1. Windows machine (required for Word automation checks).
2. Microsoft Word installed locally.
3. Python 3.11+ installed.

## Setup (new machine)

```powershell
git clone https://github.com/bhuwang971/Resume-Generator.git
cd Resume-Generator
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If activation is blocked:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## Files a new user must provide

At minimum:

1. `resume.prepped.docx` with placeholders, at:
   `resume_tool/templates/resume.prepped.docx`

Optional:

2. `resume.base.docx` (source before placeholders), at:
   `resume_tool/templates/resume.base.docx`
3. `mapping.json` if you use prep tooling/fallback indexing.

You can also keep templates anywhere and configure paths via environment variables.

## Configuration (no UI changes needed)

Set these env vars before launching app:

- `RESUME_PREPPED_TEMPLATE_PATH` (required if not using default path)
- `RESUME_BASE_TEMPLATE_PATH` (optional, informational)
- `RESUME_OUTPUT_DIR` (optional default output folder)

Example:

```powershell
$env:RESUME_PREPPED_TEMPLATE_PATH="C:\Templates\MyResume.prepped.docx"
$env:RESUME_BASE_TEMPLATE_PATH="C:\Templates\MyResume.base.docx"
$env:RESUME_OUTPUT_DIR="C:\Users\YourUser\Downloads"
streamlit run app.py
```

## Placeholder contract (required)

The prepped template must contain these placeholders exactly:

- Summary:
  - `{{summary}}`
- Skills:
  - `{{skills_1}}` to `{{skills_8}}`
- Work Experience:
  - `{{thorogood_1}}` to `{{thorogood_7}}`
  - `{{gta_1}}` to `{{gta_4}}`
- Projects:
  - `{{wtchtwr_1}}` to `{{wtchtwr_6}}`
  - `{{project2_name}}`
  - `{{project2_1}}` to `{{project2_3}}`
  - `{{project3_name}}`
  - `{{project3_1}}` to `{{project3_3}}`

Each placeholder should be the only text in that target paragraph.

## Run the app

```powershell
streamlit run app.py
```

UI fields:
- Output folder location
- Company name (required)
- Role name (optional with warning dialog)
- Paste JSON from GPT
- Validate and Generate Resume button

If role is empty, the app shows a dialog:
- `Enter role name`
- `Continue`

If continued with empty role, filename omits role segment:
- `Resume - Name - Company.docx`

## Output behavior

- Existing file with same output name is overwritten.
- Success message includes generated path.
- Button opens generated DOCX directly.
- Generation fails only when:
  - schema/status parsing fails
  - `status="questions"` flow blocks generation
  - final layout checks fail (more than 1 page or any mapped bullet wraps to 2+ lines)

## Expected JSON: supported formats

The validator supports both formats below.

### Format A (strict/internal)

```json
{
  "status": "final",
  "clarifying_questions": [],
  "resume": {
    "header": {
      "name": "Bhuwan Gupta",
      "phone": "(540) 877-8122",
      "email": "bhuwang2000@gmail.com",
      "linkedin": "linkedin.com/in/bhuwang6",
      "github": "github.com/bhuwang971"
    },
    "professional_summary": "....",
    "technical_skills": ["...", "...", "...", "...", "...", "...", "...", "..."],
    "work_experience": {
      "thorogood_bullets": ["...", "...", "...", "...", "...", "...", "..."],
      "gwu_gta_bullets": ["...", "...", "...", "..."]
    },
    "projects": {
      "wtchtwr_bullets": ["...", "...", "...", "...", "...", "..."],
      "project2": { "name": "...", "bullets": ["...", "...", "..."] },
      "project3": { "name": "...", "bullets": ["...", "...", "..."] }
    },
    "education_lines": ["...", "..."],
    "jd_match_map": ["...", "..."]
  }
}
```

### Format B (nested variant from some GPT prompts)

Also accepted:

- `work_experience.thorogood.bullets`
- `work_experience.gwu_gta.bullets`
- `projects.wtchtwr.bullets`

These are normalized internally into strict fields before rendering.

## JSON customization guide

You can customize safely:

- Header values
- Summary text
- Skills lines
- Bullet text
- Project 2 and Project 3 names
- `jd_match_map` size/content
- Additional fields (for example `resume_text`, `sources`) for UI viewing

Do not change unless you also update code:

- Core section key names (`header`, `work_experience`, `projects`, etc.)
- Placeholder naming scheme in template and renderer

If you want different section counts (for example 5 Thorogood bullets instead of 7):

1. Update placeholder counts in your prepped DOCX.
2. Update `build_context` in `resume_tool/render.py`.
3. Update mapping/placeholder expectations in render checks.
4. Update any schema assumptions in `resume_tool/schema.py` and normalization in `resume_tool/validate.py`.

## CLI usage

Generate from CLI:

```powershell
python -m resume_tool.cli --template "C:\path\resume.prepped.docx" --json "C:\path\output.json" --out "C:\path\Resume.docx"
```

Prep template from base:

```powershell
python -m resume_tool.cli --template "C:\path\resume.base.docx" --prep-template --prepped-out "C:\path\resume.prepped.docx" --mapping-out "C:\path\mapping.json"
```

## Cleanup policy for this repo

Not committed:

- `.venv/`
- `.tmp/`
- local streamlit/cache files
- user-specific templates (`resume_tool/templates/*.docx`)
- user-specific mapping (`resume_tool/templates/mapping.json`)

Committed:

- code
- sample JSON
- instructions

## Troubleshooting

### "Prepped template is missing"

Create or copy your prepped template to:
`resume_tool/templates/resume.prepped.docx`
or set `RESUME_PREPPED_TEMPLATE_PATH`.

### "Layout checks require Microsoft Word automation support"

Install dependencies and ensure Word is installed:

```powershell
pip install -r requirements.txt
```

### Resume fails with 2 pages or wrapped bullets

This is enforced intentionally. Shorten content in JSON or adjust template spacing.

