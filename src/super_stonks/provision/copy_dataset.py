"""Copy a dataset from the primary project to every other project in the org.

Projects are enumerated with the **bt CLI** (`bt projects list --json`, authenticated
via the profile — no API key needed). The rows are copied with the **Braintrust Python
SDK** (`init_dataset`), which reads `BRAINTRUST_API_KEY` from `.env`.

The `bt` CLI has no cross-project dataset copy, so the row copy is done via the SDK.

Run via:  make copy-dataset DATASET=<name>
          (or: uv run python -m super_stonks.provision.copy_dataset <name>)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

from dotenv import load_dotenv

load_dotenv()  # BRAINTRUST_API_KEY for the SDK; bt uses the profile, not this

from braintrust import init_dataset

# The source project every other project is seeded from.
PRIMARY_PROJECT = os.environ.get("PRIMARY_PROJECT", "super-stonks")

# Fields carried over per row (id preserved → re-runs upsert, i.e. idempotent).
_ROW_FIELDS = ("input", "expected", "output", "metadata", "tags", "id")


def list_org_projects() -> list[str]:
    """All project names in the active org, via the authenticated bt CLI."""
    result = subprocess.run(
        ["bt", "projects", "list", "--json"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [p["name"] for p in json.loads(result.stdout)]


def copy_dataset(name: str) -> None:
    source = init_dataset(project=PRIMARY_PROJECT, name=name)
    rows = list(source)
    if not rows:
        print(f"[copy-dataset] {PRIMARY_PROJECT}/{name} has 0 rows — nothing to copy.")
        return

    targets = [p for p in list_org_projects() if p != PRIMARY_PROJECT]
    if not targets:
        print(f"[copy-dataset] no projects other than {PRIMARY_PROJECT} in the org.")
        return

    print(
        f"[copy-dataset] copying {len(rows)} rows from {PRIMARY_PROJECT}/{name} "
        f"-> {len(targets)} project(s)"
    )
    for project in targets:
        target = init_dataset(project=project, name=name)
        for row in rows:
            target.insert(**{k: row[k] for k in _ROW_FIELDS if row.get(k) is not None})
        target.flush()
        print(f"  ✓ {project}/{name} ({len(rows)} rows)")


def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("DATASET", "").strip()
    if not name:
        print(
            "usage: python -m super_stonks.provision.copy_dataset <dataset-name>",
            file=sys.stderr,
        )
        raise SystemExit(2)
    copy_dataset(name)


if __name__ == "__main__":
    main()
