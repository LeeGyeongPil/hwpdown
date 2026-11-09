import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "samples"


@pytest.fixture(scope="session")
def samples() -> Path:
    return SAMPLES


@pytest.fixture(scope="session")
def truth() -> dict:
    return json.loads((SAMPLES / "questions.json").read_text(encoding="utf-8"))["documents"]
