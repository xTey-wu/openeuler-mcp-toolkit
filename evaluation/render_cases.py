"""Render evaluation cases with the PID of a caller-created controlled process."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import psutil

PID_TOKEN = "__CONTROLLED_PID__"


def replace_pid(value: Any, pid: int) -> Any:
    if isinstance(value, dict):
        return {key: replace_pid(item, pid) for key, item in value.items()}
    if isinstance(value, list):
        return [replace_pid(item, pid) for item in value]
    if value == PID_TOKEN:
        return pid
    if isinstance(value, str):
        return value.replace(PID_TOKEN, str(pid))
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--controlled-pid", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--template",
        type=Path,
        default=Path(__file__).with_name("cases.jsonl"),
    )
    args = parser.parse_args()

    if args.controlled_pid <= 0 or not psutil.pid_exists(args.controlled_pid):
        raise SystemExit("controlled PID must identify a currently running process")
    rows = [
        json.loads(line)
        for line in args.template.read_text(encoding="utf-8").splitlines()
        if line
    ]
    rendered = [replace_pid(row, args.controlled_pid) for row in rows]
    args.output.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rendered),
        encoding="utf-8",
    )
    print(f"rendered {len(rendered)} cases for controlled PID {args.controlled_pid}")


if __name__ == "__main__":
    main()
