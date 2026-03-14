# opencode_pytest_harness

Revision: r1 Timestamp: 2026-03-13 00:00:00

## 1. Purpose

This scaffold provides a minimal pytest-based black-box regression harness
for validating OpenCode CLI behavior against fixture workspaces.

## 2. Layout

- `tests/fixtures/basic_files/` contains the seed workspace.
- `tests/cases/*.yaml` contains declarative regression cases.
- `tests/test_opencode_cases.py` runs each case through the OpenCode CLI.
- `tests/conftest.py` provides shared configuration and binary override support.
- `tools/run_opencode_case.py` runs one case manually outside pytest.

## 3. Usage

Create and activate a virtual environment, then install the required packages:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install pytest pyyaml pexpect
```

Run the suite:

```bash
pytest -q
```

Override the OpenCode binary path when needed:

```bash
OPENCODE_BIN=/path/to/opencode pytest -q
```

Run a single case manually:

```bash
python tools/run_opencode_case.py tests/cases/read_basic.yaml
```

## 4. Notes

The scaffold intentionally stays black-box. It asserts only stdout, stderr,
and workspace side effects. Tool-trace validation and token accounting can be
added later without changing the basic harness model.
