from __future__ import annotations

from pathlib import Path

import app


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_navigation_contains_exactly_two_normal_sections(monkeypatch):
    pages = []
    ran = []

    def page(path, **values):
        pages.append((path, values))
        return path

    class Navigation:
        def run(self):
            ran.append(True)

    monkeypatch.setattr(app.st, "Page", page)
    monkeypatch.setattr(app.st, "navigation", lambda values, **kwargs: Navigation())
    app.main()
    assert [item[1]["title"] for item in pages] == ["Generate Resume", "Tracker"]
    assert [item[0] for item in pages] == [
        "pages/1_Generate_Resume.py", "pages/2_Tracker.py",
    ]
    assert ran == [True]


def test_only_two_page_wrappers_exist():
    assert sorted(path.name for path in (PROJECT_ROOT / "pages").glob("*.py")) == [
        "1_Generate_Resume.py", "2_Tracker.py",
    ]


def test_active_runtime_has_no_external_generation_client():
    runtime_files = [PROJECT_ROOT / "app.py"]
    for folder in ("resume_tool", "tracker", "ui", "pages"):
        runtime_files.extend((PROJECT_ROOT / folder).glob("*.py"))
    forbidden = ("open" + "ai", "application" + "_pack", "maximum_resume" + "_retries")
    source = "\n".join(path.read_text(encoding="utf-8").casefold() for path in runtime_files)
    assert all(term not in source for term in forbidden)
