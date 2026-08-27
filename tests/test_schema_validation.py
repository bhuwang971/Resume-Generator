from __future__ import annotations

import json

import pytest

from resume_tool.schema import ResumeDocument
from resume_tool.validate import build_correction_prompt, format_json_text, validate_json_text


def _validate(payload: dict):
    return validate_json_text(json.dumps(payload))


def test_sample_json_is_valid(payload_factory):
    result = _validate(payload_factory())
    assert result.is_valid
    assert isinstance(result.payload, ResumeDocument)


@pytest.mark.parametrize("raw", ["", "[]", "{not json}"])
def test_invalid_json_is_rejected(raw):
    result = validate_json_text(raw)
    assert not result.is_valid
    assert result.errors


@pytest.mark.parametrize("words,valid", [(49, False), (50, True), (60, True), (61, False)])
def test_summary_word_boundaries(payload_factory, words, valid):
    payload = payload_factory()
    payload["resume"]["professional_summary"] = " ".join(f"word{index}" for index in range(words))
    assert _validate(payload).is_valid is valid


def test_requires_exactly_six_well_formed_skill_lines(payload_factory):
    payload = payload_factory()
    payload["resume"]["technical_skills"].pop()
    assert not _validate(payload).is_valid
    payload = payload_factory()
    payload["resume"]["technical_skills"][0] = "Missing category separator"
    assert not _validate(payload).is_valid
    payload["resume"]["technical_skills"][0] = "Category: one, two"
    assert not _validate(payload).is_valid


@pytest.mark.parametrize(
    "field,expected",
    [("ilink_bullets", 6), ("gwu_gta_bullets", 3), ("thorogood_bullets", 7)],
)
def test_experience_counts_are_exact(payload_factory, field, expected):
    payload = payload_factory()
    payload["resume"]["work_experience"][field] = ["Verified placeholder"] * (expected - 1)
    assert not _validate(payload).is_valid


def test_every_bullet_is_limited_to_seventeen_words(payload_factory):
    payload = payload_factory()
    payload["resume"]["work_experience"]["ilink_bullets"][0] = " ".join(["word"] * 18)
    result = _validate(payload)
    assert not result.is_valid
    assert any("17 words" in item.message for item in result.errors)


@pytest.mark.parametrize("include_awards", [False, True])
def test_awards_flag_is_structural_metadata(payload_factory, include_awards):
    assert _validate(payload_factory(include_awards=include_awards)).is_valid


def test_one_project_contract(payload_factory):
    payload = payload_factory(project_count=1)
    payload["resume"]["projects"]["project1"]["bullets"].pop()
    assert not _validate(payload).is_valid
    payload = payload_factory(project_count=1)
    payload["resume"]["projects"]["project2"] = {
        "name": "Unexpected Project",
        "bullets": ["One", "Two", "Three"],
    }
    assert not _validate(payload).is_valid


def test_two_project_contract(payload_factory):
    assert _validate(payload_factory(project_count=2)).is_valid
    payload = payload_factory(project_count=2)
    payload["resume"]["projects"]["project2"] = None
    assert not _validate(payload).is_valid
    payload = payload_factory(project_count=2)
    payload["resume"]["projects"]["project2"]["name"] = payload["resume"]["projects"]["project1"]["name"]
    assert not _validate(payload).is_valid


def test_unknown_legacy_fields_are_rejected(payload_factory):
    payload = payload_factory()
    payload["status"] = "final"
    result = _validate(payload)
    assert not result.is_valid
    assert any(item.path == "$.status" for item in result.errors)


def test_format_and_correction_prompt_are_deterministic(payload_factory):
    compact = json.dumps(payload_factory())
    formatted = format_json_text(compact)
    assert formatted.startswith("{\n  \"metadata\"")
    bad = payload_factory()
    bad["resume"]["professional_summary"] = "too short"
    raw = json.dumps(bad)
    result = validate_json_text(raw)
    prompt = build_correction_prompt(raw, result.errors, page_count=2)
    assert "CURRENT JSON" in prompt
    assert "FAILING FIELDS" in prompt
    assert "exactly 1 is required" in prompt
    assert raw in prompt
