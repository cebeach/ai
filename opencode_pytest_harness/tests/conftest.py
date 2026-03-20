import os
from pathlib import Path
import pytest
import requests
import warnings
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_OPENCODE_BIN = Path.home() / ".opencode/bin/opencode"

# llama-server base URL, overridable via environment variable
DEFAULT_LLAMA_SERVER_URL = "http://127.0.0.1:8001"


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


@pytest.fixture(autouse=True)
def flush_llama_kv_cache() -> None:
    """Erase all llama-server KV cache slots before each test.

    Without this, the model's KV cache accumulates context from prior tests
    within the same pytest session, causing stale workspace paths and file
    content from earlier tests to bleed into subsequent ones.

    Requires llama-server to be started with --slot-save-path (any writable
    directory will do; the flag gates the /slots POST endpoint regardless of
    whether save/restore is actually used).

    The action and id_slot are passed as query parameters, not JSON body
    fields, per the llama-server API:
        POST /slots/{id}?action=erase&id_slot={id}

    If the server is unreachable or the endpoint is unavailable, a warning
    is issued but the test is not failed -- the flush is best-effort.
    """
    llama_url = os.environ.get("LLAMA_SERVER_URL", DEFAULT_LLAMA_SERVER_URL)
    try:
        slots_resp = requests.get(f"{llama_url}/slots", timeout=5)
        slots_resp.raise_for_status()
        slot_ids = [slot["id"] for slot in slots_resp.json()]
        for slot_id in slot_ids:
            requests.post(
                f"{llama_url}/slots/{slot_id}",
                params={"action": "erase", "id_slot": slot_id},
                timeout=5,
            )
    except Exception as exc:
        warnings.warn(
            f"Could not flush llama-server KV cache: {exc}. "
            "Tests may be affected by stale context from prior runs.",
            UserWarning,
            stacklevel=2,
        )
