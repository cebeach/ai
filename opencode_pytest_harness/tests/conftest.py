from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

DEFAULT_OPENCODE_BIN = (
    Path.home()
    / "build/opencode_pytest_harness/latest_build/packages/opencode/dist/opencode-linux-x64/bin/opencode"
)


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def fixtures_dir(repo_root: Path) -> Path:
    return repo_root / "tests" / "fixtures"


@pytest.fixture(scope="session")
def cases_dir(repo_root: Path) -> Path:
    return repo_root / "tests" / "cases"


@pytest.fixture(scope="session")
def artifacts_root(repo_root: Path) -> Path:
    path = repo_root / "tests" / "artifacts"
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture(scope="session")
def opencode_bin() -> Path:
    override = os.environ.get("OPENCODE_BIN")
    return Path(override).expanduser() if override else DEFAULT_OPENCODE_BIN


@pytest.fixture(scope="session")
def case_definitions(cases_dir: Path) -> list[dict]:
    definitions: list[dict] = []
    for case_path in sorted(cases_dir.glob("*.yaml")):
        with case_path.open("r", encoding="utf-8") as handle:
            case = yaml.safe_load(handle)
        case["case_path"] = case_path
        case.setdefault("expect", {})
        definitions.append(case)
    return definitions
