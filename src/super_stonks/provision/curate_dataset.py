"""Curate a Topics cluster from the shared seed into a dataset in YOUR project (§9).

READ: the cluster's member traces from **super-stonks** (bt CLI, profile auth).
WRITE: a dataset in your own **BRAINTRUST_DEFAULT_PROJECT** (Braintrust SDK).

    make curate-dataset
    CLUSTER="Current stock price analysis" DATASET=realtime-price make curate-dataset
"""

from __future__ import annotations

import json
import os
import subprocess

from dotenv import load_dotenv

load_dotenv()  # BRAINTRUST_API_KEY for the SDK write

from braintrust import init_dataset

SHARED_PROJECT = "super-stonks"
CLUSTER = os.environ.get("CLUSTER", "Current stock price analysis")
DATASET = os.environ.get("DATASET", "realtime-price")


def _bt_json(args: list[str]):
    out = subprocess.run(["bt", *args], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def _shared_project_id() -> str:
    for p in _bt_json(["projects", "list", "--json"]):
        if p["name"] == SHARED_PROJECT:
            return p["id"]
    raise SystemExit(f"project '{SHARED_PROJECT}' not found")


def _task_topic_map_id() -> str:
    cfg = _bt_json(["topics", "config", "--json", "--project", SHARED_PROJECT])
    for tm in (cfg.get("automations") or [{}])[0].get("topic_map_functions", []):
        if tm.get("name") == "Task":
            return tm["id"]
    raise SystemExit("Task topic map not found")


def _cluster_trace_ids(task_id: str) -> list[str]:
    rep = _bt_json(["topics", "report", task_id, "--project", SHARED_PROJECT, "--json"])
    cluster = next((c for c in rep["clusters"] if c["name"] == CLUSTER), None)
    if not cluster:
        raise SystemExit(f"cluster '{CLUSTER}' not found in the Task facet")
    cid = cluster["cluster_id"]
    tids = [p["trace_id"] for p in rep["embedding_points"] if p.get("cluster") == cid and p.get("trace_id")]
    return list(dict.fromkeys(tids))  # dedupe, preserve order


def _question(pid: str, trace_id: str):
    q = _bt_json([
        "sql",
        f"SELECT input FROM project_logs('{pid}') "
        f"WHERE root_span_id = '{trace_id}' AND span_attributes.name = 'turn_0'",
        "--json",
    ])
    rows = q.get("data") or []
    return rows[0].get("input") if rows else None


def main() -> None:
    project = os.environ["BRAINTRUST_DEFAULT_PROJECT"]  # write target = your project
    pid = _shared_project_id()
    trace_ids = _cluster_trace_ids(_task_topic_map_id())
    print(f"[curate] '{CLUSTER}': {len(trace_ids)} member traces → dataset '{DATASET}' in '{project}'")

    dataset = init_dataset(project, DATASET)
    n = 0
    for tid in trace_ids:
        question = _question(pid, tid)
        if not question:
            continue
        dataset.insert(
            input=question,
            metadata={"source": SHARED_PROJECT, "cluster": CLUSTER, "trace_id": tid},
            id=tid,  # preserve → re-running upserts
        )
        n += 1
    dataset.flush()
    print(f"[curate] wrote {n} rows to {project}/{DATASET}")


if __name__ == "__main__":
    main()
