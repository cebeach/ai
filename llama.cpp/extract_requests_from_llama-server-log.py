#!/usr/bin/env python3
"""
Extract OpenAI-compatible JSON request bodies from a llama-server log
and pretty-print them.

Assumption:
- Each request appears on a single log line containing:
    D srv  log_server_r: request:
- The JSON body begins immediately after 'request:' on that same line.

Usage:
    python extract_requests.py llama-server_openai_gpt-oss-20b-MXFP4_sample_log.txt

Optional:
    python extract_requests.py logfile.txt --index 2
    python extract_requests.py logfile.txt --compact
"""


import argparse
import json
import sys
from pathlib import Path

MARKER = "log_server_r: request:"


def extract_requests(path: Path) -> list[dict]:
    requests: list[dict] = []

    with path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            if MARKER not in line:
                continue

            body = line.split(MARKER, 1)[1].strip()
            if not body:
                print(
                    f"warning: line {lineno}: found marker but no body",
                    file=sys.stderr,
                )
                continue

            try:
                obj = json.loads(body)
            except json.JSONDecodeError as exc:
                print(
                    f"warning: line {lineno}: invalid JSON after marker: {exc}",
                    file=sys.stderr,
                )
                continue

            requests.append(obj)

    return requests


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract and pretty-print JSON requests from a llama-server log."
    )
    parser.add_argument("logfile", type=Path, help="Path to the log file")
    parser.add_argument(
        "--index",
        type=int,
        default=None,
        help="1-based request index to print (example: --index 2)",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Print compact JSON instead of pretty-printed JSON",
    )
    args = parser.parse_args()

    if not args.logfile.is_file():
        print(f"error: file not found: {args.logfile}", file=sys.stderr)
        return 1

    requests = extract_requests(args.logfile)

    if not requests:
        print("No request JSON objects found.", file=sys.stderr)
        return 1

    if args.index is not None:
        if args.index < 1 or args.index > len(requests):
            print(
                f"error: index out of range: {args.index} (found {len(requests)} requests)",
                file=sys.stderr,
            )
            return 1
        selected = [(args.index, requests[args.index - 1])]
    else:
        selected = list(enumerate(requests, start=1))

    for i, obj in selected:
        if len(selected) > 1:
            print(f"--- Request {i} ---")

        if args.compact:
            print(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))
        else:
            print(json.dumps(obj, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
