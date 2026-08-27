# Development Rules

- Preserve the stabilized `resume_tool` JSON-to-DOCX/PDF renderer and template contract.
- Never fabricate applicant facts or infer facts from a job description.
- Only active, verified profile facts are evidence for scoring, answers, and tailoring.
- Preserve claim maturity; never promote POC, designed, evaluated, or mocked work.
- Keep Career Rules separate from applicant facts.
- Never scrape LinkedIn or bypass CAPTCHA, MFA, login, or access restrictions.
- Never automate final application submission, legal attestations, or demographic answers.
- Never commit personal documents, runtime databases, generated resumes, browser state, or secrets.
- Add tests for new behavior and run `python -m pytest -m "not word"` before completion.
