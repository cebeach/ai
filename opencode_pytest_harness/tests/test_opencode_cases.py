import filecmp
import json
import os
import pexpect
import re
import shutil
import subprocess
import time
from pathlib import Path
import pexpect
import pytest

ROOT = Path(__file__).resolve().parent.parent
CASES_DIR = ROOT / "tests" / "cases"
FIXTURES_DIR = ROOT / "tests" / "fixtures"


class CaseResult(dict):
    @property
    def stdout(self) -> str:
        return self["stdout"]

    @property
    def stderr(self) -> str:
        return self["stderr"]

    @property
    def returncode(self) -> int:
        return self["returncode"]


def load_case(case_path: Path) -> dict:
    import yaml

    with case_path.open("r", encoding="utf-8") as handle:
        case = yaml.safe_load(handle)
    case["case_path"] = case_path
    case.setdefault("expect", {})
    return case


def iter_case_paths() -> list[Path]:
    return sorted(CASES_DIR.glob("*.yaml"))


def copy_fixture_tree(src: Path, dest: Path) -> None:
    shutil.copytree(src, dest, dirs_exist_ok=True)


def snapshot_text_files(root: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        try:
            snapshot[rel] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            snapshot[rel] = "<binary>"
    return snapshot


def write_snapshot_json(path: Path, data: dict[str, str]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


ANSI_RE = re.compile(
    r"""
    \x1B[@-_][0-?]*[ -/]*[@-~]      |  # ESC / CSI sequences
    \x1B\][^\x07]*(?:\x07|\x1B\\)   |  # OSC ... BEL or ST
    [\x00-\x08\x0b-\x1f\x7f]        # control chars except \t \n \r
    """,
    re.VERBOSE,
)

READY_RE = r"Ask anything\.\.\."
PERMISSION_RE = r"Permission required|Allow once|Allow always|Reject"


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def run_opencode_tui(
    opencode_bin: Path,
    prompt: str,
    workspace: Path,
    timeout: int = 120,
    quiet_timeout: int = 2,
    ready_timeout: int = 20,
    exit_timeout: int = 10,
    max_permission_approvals: int = 5,
) -> dict:

    transcript_parts: list[str] = []

    project_root = Path(__file__).resolve().parents[1]

    tools_dir = project_root / "tools" / "opencode"
    test_opencode_json = project_root / "tools" / "opencode" / "opencode.json"
    prompts_src = tools_dir / "prompts"

    if not test_opencode_json.exists():
        raise FileNotFoundError(f"Missing harness config: {test_opencode_json}")

    config_home = workspace / ".xdg_config"
    state_home = workspace / ".xdg_state"
    cache_home = workspace / ".xdg_cache"

    config_home.mkdir(parents=True, exist_ok=True)
    state_home.mkdir(parents=True, exist_ok=True)
    cache_home.mkdir(parents=True, exist_ok=True)

    opencode_config_dir = config_home / "opencode"
    opencode_config_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Log key paths for debugging
    # ------------------------------------------------------------------

    transcript_parts.append("\n[HARNESS PATH INFO]\n")
    transcript_parts.append(f"project_root={project_root}\n")
    transcript_parts.append(f"workspace={workspace}\n")
    transcript_parts.append(f"tools_dir={tools_dir}\n")
    transcript_parts.append(f"opencode_bin={opencode_bin}\n")
    transcript_parts.append(f"config_home={config_home}\n")
    transcript_parts.append(f"state_home={state_home}\n")
    transcript_parts.append(f"cache_home={cache_home}\n")
    transcript_parts.append(f"opencode_config_dir={opencode_config_dir}\n\n")

    # ------------------------------------------------------------------
    # Copy opencode.json
    # ------------------------------------------------------------------

    shutil.copy2(
        test_opencode_json,
        opencode_config_dir / "opencode.json",
    )

    # ------------------------------------------------------------------
    # Copy prompts directory if present
    # ------------------------------------------------------------------

    if prompts_src.exists():
        prompts_dst = opencode_config_dir / "prompts"

        if prompts_dst.exists():
            shutil.rmtree(prompts_dst)

        shutil.copytree(prompts_src, prompts_dst)

    # ------------------------------------------------------------------
    # Environment variables
    # ------------------------------------------------------------------

    env = {
        **os.environ,
        "TERM": "xterm-256color",
        "CI": "1",
        "NO_COLOR": "1",
        "XDG_CONFIG_HOME": str(config_home),
        "XDG_STATE_HOME": str(state_home),
        "XDG_CACHE_HOME": str(cache_home),
    }

    child = pexpect.spawn(
        str(opencode_bin),
        cwd=str(workspace),
        env=env,
        encoding="utf-8",
        timeout=quiet_timeout,
    )

    timed_out = False
    permission_approvals = 0

    try:
        child.expect(READY_RE, timeout=ready_timeout)
        transcript_parts.append(child.before or "")
        transcript_parts.append(child.after or "")

        child.send(prompt)
        child.send("\r")

        deadline = time.monotonic() + timeout
        saw_post_submit_output = False

        while True:
            if time.monotonic() >= deadline:
                transcript_parts.append("\n[HARNESS TIMEOUT waiting for response completion]\n")
                timed_out = True
                break

            remaining = max(0.1, min(quiet_timeout, deadline - time.monotonic()))

            try:
                idx = child.expect(
                    [PERMISSION_RE, READY_RE, r".+"],
                    timeout=remaining,
                )

                transcript_parts.append(child.before or "")
                transcript_parts.append(child.after or "")
                saw_post_submit_output = True

                if idx == 0:
                    permission_approvals += 1

                    if permission_approvals > max_permission_approvals:
                        transcript_parts.append("\n[HARNESS ABORT: too many permission prompts]\n")
                        timed_out = True
                        break

                    transcript_parts.append("\n[HARNESS: approving permission dialog with Enter]\n")
                    child.send("\r")

                    # Let the TUI settle after the approval redraw.
                    try:
                        child.expect(r".+", timeout=0.5)
                        transcript_parts.append(child.before or "")
                        transcript_parts.append(child.after or "")
                    except pexpect.TIMEOUT:
                        pass

                    continue

                if idx == 1 and saw_post_submit_output:
                    break

            except pexpect.TIMEOUT:
                if saw_post_submit_output:
                    break

        child.send("\x1b")
        child.send("/exit")
        child.send("\r")

        try:
            child.expect(pexpect.EOF, timeout=exit_timeout)
            transcript_parts.append(child.before or "")
        except pexpect.TIMEOUT:
            transcript_parts.append(child.before or "")
            child.close(force=True)
        else:
            child.close()

    finally:
        if child.isalive():
            child.close(force=True)

    raw_output = "".join(transcript_parts)
    cleaned_output = strip_ansi(raw_output)

    return {
        "returncode": 124 if timed_out else (child.exitstatus if child.exitstatus is not None else 0),
        "stdout": cleaned_output,
        "stderr": "",
        "raw_stdout": raw_output,
    }


def assert_contains_all(haystack: str, needles: list[str], label: str) -> None:
    for needle in needles:
        assert needle in haystack, f"{label} missing expected text: {needle!r}"


def assert_not_contains_any(haystack: str, needles: list[str], label: str) -> None:
    for needle in needles:
        assert needle not in haystack, f"{label} unexpectedly contained: {needle!r}"


def assert_file_contains(workspace: Path, entries: list[dict]) -> None:
    for entry in entries:
        path = workspace / entry["path"]
        content = path.read_text(encoding="utf-8")
        assert entry["contains"] in content, f"{entry['path']} missing expected text"


def assert_file_not_contains(workspace: Path, entries: list[dict]) -> None:
    for entry in entries:
        path = workspace / entry["path"]
        content = path.read_text(encoding="utf-8")
        assert entry["contains"] not in content, f"{entry['path']} still contains forbidden text"


def assert_files_exist(workspace: Path, paths: list[str]) -> None:
    for rel_path in paths:
        assert (workspace / rel_path).exists(), f"Expected file to exist: {rel_path}"


def assert_files_unchanged(before: dict[str, str], after: dict[str, str]) -> None:
    assert before == after, "Workspace changed unexpectedly"


@pytest.mark.parametrize("case_path", iter_case_paths(), ids=lambda path: path.stem)
def test_opencode_case(case_path: Path, tmp_path: Path, artifacts_root: Path, opencode_bin: Path) -> None:
    case = load_case(case_path)
    fixture_src = FIXTURES_DIR / case["fixture"]
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    copy_fixture_tree(fixture_src, workspace)

    before_snapshot = snapshot_text_files(workspace)

    case_artifact_dir = artifacts_root / case["name"]
    if case_artifact_dir.exists():
        shutil.rmtree(case_artifact_dir)
    case_artifact_dir.mkdir(parents=True, exist_ok=True)
    write_snapshot_json(case_artifact_dir / "workspace_before.json", before_snapshot)

    timeout = int(case.get("timeout_seconds", 120))
    result = run_opencode_tui(opencode_bin, case["prompt"], workspace, timeout)

    (case_artifact_dir / "stdout_raw.txt").write_text(result["raw_stdout"], encoding="utf-8")
    (case_artifact_dir / "stdout.txt").write_text(result["stdout"], encoding="utf-8")
    (case_artifact_dir / "stderr.txt").write_text(result["stderr"], encoding="utf-8")

    after_snapshot = snapshot_text_files(workspace)
    write_snapshot_json(case_artifact_dir / "workspace_after.json", after_snapshot)

    expect = case["expect"]
    expected_returncode = int(expect.get("returncode", 0))
    assert result["returncode"] == expected_returncode, (
        f"Unexpected return code for {case['name']}: {result['returncode']}\n"
        f"STDOUT:\n{result['stdout']}\n\nSTDERR:\n{result['stderr']}"
    )

    assert_contains_all(result["stdout"], expect.get("stdout_contains", []), "stdout")
    assert_not_contains_any(result["stdout"], expect.get("stdout_not_contains", []), "stdout")
    assert_contains_all(result["stderr"], expect.get("stderr_contains", []), "stderr")
    assert_not_contains_any(result["stderr"], expect.get("stderr_not_contains", []), "stderr")
    assert_file_contains(workspace, expect.get("file_contains", []))
    assert_file_not_contains(workspace, expect.get("file_not_contains", []))
    assert_files_exist(workspace, expect.get("files_exist", []))

    if expect.get("files_unchanged", False):
        assert_files_unchanged(before_snapshot, after_snapshot)
