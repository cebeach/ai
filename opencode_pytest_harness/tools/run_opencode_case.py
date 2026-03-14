#!/usr/bin/env python3

import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_OPENCODE_BIN = PROJECT_ROOT / "latest" / "packages/opencode/dist/opencode-linux-x64/bin/opencode"


def load_case(case_path: Path) -> dict:
    with case_path.open("r", encoding="utf-8") as handle:
        case = yaml.safe_load(handle)
    case.setdefault("expect", {})
    return case


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one OpenCode regression case manually.")
    parser.add_argument("case", type=Path, help="Path to YAML case file")
    parser.add_argument(
        "--opencode-bin",
        type=Path,
        default=DEFAULT_OPENCODE_BIN,
        help="Path to opencode binary",
    )
    args = parser.parse_args()

    case = load_case(args.case)
    repo_root = Path(__file__).resolve().parent.parent
    fixture_src = repo_root / "tests" / "fixtures" / case["fixture"]

    with tempfile.TemporaryDirectory(prefix=f"opencode-{case['name']}-") as tmp:
        workspace = Path(tmp) / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        shutil.copytree(fixture_src, workspace, dirs_exist_ok=True)

        proc = subprocess.run(
            [str(args.opencode_bin), "--prompt", case["prompt"]],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=int(case.get("timeout_seconds", 120)),
        )

        print("=== STDOUT ===")
        print(proc.stdout)
        print("=== STDERR ===", file=sys.stderr)
        print(proc.stderr, file=sys.stderr)
        print(f"=== RETURN CODE: {proc.returncode} ===")
        return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
