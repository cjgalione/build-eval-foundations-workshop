"""Turn selected traces from an attendee's own project into a small eval dataset.

This is the optional CLI lane. The default workshop lane uses the Braintrust UI/Loop,
but this command keeps data creation transparent and repeatable for attendees who want
to inspect the mechanics.

Example:
    uv run python -m super_stonks.provision.curate_dataset \
      --trace-ids <id-1>,<id-2> --output price-gap-baseline.jsonl --create
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any


DATASET = "price-gap-baseline"
MAX_ROWS = 5
FAILURE_DESCRIPTION = (
    "The user requested a current stock price, but the agent did not return the "
    "current price from the price tool."
)


def _bt_json(args: list[str]) -> Any:
    completed = subprocess.run(["bt", *args], capture_output=True, text=True, check=True)
    return json.loads(completed.stdout)


def _project_id(project: str) -> str:
    projects = _bt_json(["projects", "list", "--json"])
    match = next((item for item in projects if item.get("name") == project), None)
    if not match:
        raise SystemExit(f"project '{project}' was not found; generate a trace first.")
    return match["id"]


def _turn_for_trace(project_id: str, trace_id: str) -> dict[str, Any] | None:
    safe_trace_id = trace_id.replace("'", "''")
    query = (
        "SELECT input, output, span_attributes.name AS name "
        f"FROM project_logs('{project_id}') "
        f"WHERE root_span_id = '{safe_trace_id}' "
        "AND span_attributes.name = 'turn_0' ORDER BY created LIMIT 1"
    )
    response = _bt_json(["sql", query, "--json"])
    rows = response.get("data", [])
    return rows[0] if rows else None


def build_rows(trace_ids: list[str], turns: dict[str, dict[str, Any] | None]) -> list[dict[str, Any]]:
    """Build capped, portable dataset rows; kept pure for regression tests."""
    rows: list[dict[str, Any]] = []
    for trace_id in trace_ids:
        turn = turns.get(trace_id)
        if not turn or not turn.get("input"):
            continue
        rows.append({
            "input": turn["input"],
            "expected": None,
            "metadata": {
                "broken_output": turn.get("output"),
                "failure_category": "price_gap",
                "failure_description": FAILURE_DESCRIPTION,
                "source_trace_id": trace_id,
                "source_span_name": turn.get("name", "turn_0"),
            },
        })
        if len(rows) == MAX_ROWS:
            break
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _create_dataset(project: str, dataset: str, output: Path) -> None:
    subprocess.run(
        ["bt", "datasets", "create", dataset, "--file", str(output), "-p", project],
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a five-case price-gap dataset from selected traces.")
    parser.add_argument("--trace-ids", required=True, help="comma-separated root trace IDs from your own project")
    parser.add_argument("--output", required=True, type=Path, help="destination JSONL file")
    parser.add_argument("--dataset", default=DATASET)
    parser.add_argument("--create", action="store_true", help="create the dataset with bt after writing JSONL")
    args = parser.parse_args()

    project = os.environ.get("BRAINTRUST_DEFAULT_PROJECT", "").strip()
    if not project:
        raise SystemExit("Set BRAINTRUST_DEFAULT_PROJECT before curating traces.")
    trace_ids = list(dict.fromkeys(value.strip() for value in args.trace_ids.split(",") if value.strip()))
    if not trace_ids:
        raise SystemExit("Provide at least one trace ID.")

    project_id = _project_id(project)
    turns = {trace_id: _turn_for_trace(project_id, trace_id) for trace_id in trace_ids}
    rows = build_rows(trace_ids, turns)
    if not rows:
        raise SystemExit("No turn_0 spans found for the provided trace IDs.")

    _write_jsonl(args.output, rows)
    print(f"[curate] wrote {len(rows)} row(s) to {args.output}")
    if args.create:
        _create_dataset(project, args.dataset, args.output)
        print(f"[curate] created {project}/{args.dataset}")


if __name__ == "__main__":
    main()
