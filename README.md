# Local Resume Generator and Tracker

This Windows application has two sections: **Generate Resume** and **Tracker**. It makes no AI or external-provider calls. A Custom GPT prepares factual resume JSON; the local application validates it, renders it through Microsoft Word, and records the generated files.

## Run it

From PowerShell in this repository:

```powershell
.\.venv\Scripts\Activate.ps1
python -m streamlit run app.py
```

If dependencies are not installed yet:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open the local URL printed by Streamlit, normally `http://localhost:8501`. Microsoft Word must be installed for physical layout checks and PDF export.

## Workflow

1. Ask the Custom GPT to produce JSON matching [the sample](examples/sample_output.json), using verified facts only.
2. Paste the JSON into **Generate Resume**. Use Raw JSON or Friendly Form.
3. Format and validate the JSON.
4. Run the Word layout check. Permanent files remain disabled until the resume is one page and its bullets and Skills lines pass physical-line validation.
5. Generate DOCX, PDF, or both. Files are versioned under `outputs/<Company>/<Role>/`.
6. Use **Tracker** to update application status, edit metadata, open local files, or delete a record.

## JSON contract

- Professional summary: 50-60 words.
- Technical Skills: exactly six `Category: item, item, item` strings.
- Experience bullets: exactly 6 iLink, 3 GTA, and 7 Thorogood bullets.
- Each experience and project bullet: no more than 17 words.
- One-project resumes: four Project 1 bullets and `project2: null`.
- Two-project resumes: three bullets per project and distinct project names.
- `project_count` and `include_awards` select one of four fixed local templates.

Applicant contact information, experience headings, exact Data & AI titles, education, and the optional Awards line are static template content. Project names are uppercased only in the rendered document.

## Local data

- Fixed templates: `resume_tool/templates/*.docx`
- Active tracker database: `data/tracker.db`
- Generated resumes: `outputs/`
- Word preflight candidates: `.tmp/resume_render_checks/`
- Archived legacy database: `data/backups/`

These locations are ignored by Git where they contain private or generated data. Deleting a tracker record does not delete generated files unless **Also delete generated files** is explicitly checked.

The one-time, idempotent legacy import can be rerun if needed:

```powershell
python -m tracker.migration --legacy data\backups\career-legacy-<timestamp>.db
```

It copies only useful application metadata and existing resume paths into `tracker.db`.

## Tests

```powershell
python -m pytest -m "not word"
$env:RUN_WORD_INTEGRATION="1"
python -m pytest -m word
git diff --check
```

Word integration tests require Windows, Microsoft Word, and the four private fixed templates.
