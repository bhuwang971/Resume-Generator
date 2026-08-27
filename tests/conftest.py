from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def make_payload(*, project_count: int = 1, include_awards: bool = True) -> dict:
    payload = json.loads(
        (PROJECT_ROOT / "examples" / "sample_output.json").read_text(encoding="utf-8")
    )
    payload["metadata"]["project_count"] = project_count
    payload["metadata"]["include_awards"] = include_awards
    if project_count == 2:
        payload["resume"]["projects"]["project1"]["bullets"] = payload["resume"]["projects"]["project1"]["bullets"][:3]
        payload["resume"]["projects"]["project2"] = {
            "name": "Second Verified Project",
            "bullets": [
                "Replace with a verified second project accomplishment and scale.",
                "Replace with a verified second project delivery result and tools.",
                "Replace with a verified second project outcome and business value.",
            ],
        }
    return deepcopy(payload)


@pytest.fixture
def payload_factory():
    return make_payload
