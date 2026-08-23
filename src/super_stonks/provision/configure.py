"""Turn on the presenter-only online response-quality automation (`make automations`).

The bt CLI can't create online-scoring automations, so this hits the REST API
(`PUT /v1/project_score`). Push the scorer first (`make push-scorer`), which registers
`price_response_completeness` as a prompt scorer in your project.

The automation scores **turn spans** (where input = the user question, output = the
reply) at 100% in the presenter project. It is a response-quality proxy, not a
trace-level proof of tool grounding.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from dotenv import load_dotenv

load_dotenv()

API = os.environ.get("BRAINTRUST_API_URL", "https://api.braintrust.dev").rstrip("/")
KEY = os.environ["BRAINTRUST_API_KEY"]
PROJECT = os.environ["BRAINTRUST_DEFAULT_PROJECT"]
SCORER_SLUG = "price_response_completeness"
_HEADERS = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}


def _req(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, headers=_HEADERS, method=method)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read() or "{}")


def _project_id() -> str:
    objs = _req("GET", f"/v1/project?project_name={urllib.parse.quote(PROJECT)}").get("objects", [])
    if not objs:
        raise SystemExit(f"project '{PROJECT}' not found")
    return objs[0]["id"]


def _scorer_function_id(project_id: str, retries: int = 6, delay: float = 3.0) -> str:
    for i in range(retries):
        objs = _req("GET", f"/v1/function?project_id={project_id}&slug={SCORER_SLUG}").get("objects", [])
        if objs:
            return objs[0]["id"]
        if i < retries - 1:
            print(f"  … waiting for '{SCORER_SLUG}' to index ({i + 1}/{retries})")
            time.sleep(delay)
    raise SystemExit(f"scorer '{SCORER_SLUG}' not found — run `make push-scorer` first")


def main() -> None:
    project_id = _project_id()
    fn_id = _scorer_function_id(project_id)
    _req("PUT", "/v1/project_score", {
        "project_id": project_id,
        "name": "price-response-completeness",
        "description": "Online response-quality proxy on turn spans (presenter demo).",
        "score_type": "online",
        "config": {
            "online": {
                "sampling_rate": 1.0,
                "scorers": [{"type": "function", "id": fn_id}],
                "btql_filter": "span_attributes.name ilike 'turn_%'",
            }
        },
    })
    print(f"[automations] online score 'price-response-completeness' enabled on '{PROJECT}' (turn spans, 100%).")


if __name__ == "__main__":
    main()
