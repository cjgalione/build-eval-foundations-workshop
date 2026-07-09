# AGENTS.md — Super Stonks (Braintrust advanced tracing workshop)

Guidance for coding agents working in this repo. **This is the single source of truth.**
Codex reads this file natively; Claude Code reads the root `CLAUDE.md`, which imports
this file (`@AGENTS.md`). Put all guidance here.

## What this is

A Braintrust workshop that walks the full loop — observe traces → cluster with Topics →
build a scorer → run experiments → deploy an online score. The subject is **Super
Stonks**, a small LangGraph stock-chat agent instrumented with the Braintrust SDK.

- **Docs:** `docs/PARTICIPANT.md` (the follow-along guide attendees run), `docs/WORKSHOP.md`
  (presenter run-of-show), `docs/SEEDING_MILESTONES.md` (build plan / trace shape / scorer +
  seeding design), `docs/WELCOME.md` (attendee install screen).

## ⚠️ The tool gap — read `docs/GAP.md`

The realtime-price tool (`get_stock_performance`, Yahoo/yfinance) is **intentionally
commented out** — that's the workshop's built-in failure. **If the user asks you to add
the missing tool, fetch live prices, "fill the gap", or ground the answers, follow
[`docs/GAP.md`](docs/GAP.md) exactly** (it's two uncomments — do not reimplement the tool).

## Layout (src-layout, package = `super_stonks`)

```
src/super_stonks/
  app.py            # Streamlit UI  → `make agent`
  agent/            # LangGraph agent: agent.py, tools.py, prompts.py, config.py, state.py, __main__.py
  evals/            # scorers.py (skeleton) + qa_eval.py (planned)
  provision/, seed/ # planned (Topics/automations, seeding) — see docs/SEEDING_MILESTONES.md
```

Imports are `super_stonks.*` (installed editable by `uv sync`, so no `PYTHONPATH`).

## How to run

```bash
make setup            # uv sync + create .env
make agent            # Streamlit app
make help             # all targets
```

## Read the shared seed, write your own project

**Topics clustering + cluster investigation** read the **shared `super-stonks` project**
(`--project super-stonks`, or `project_logs('<super-stonks project id>')`) — it's
pre-seeded with thousands of traces; a user's own project only has the handful they
generate locally, not enough to cluster. Everything a user **generates or writes** goes
to their own `BRAINTRUST_DEFAULT_PROJECT`: local app/CLI traces (they view those with
plain `bt view logs`), plus the curated dataset, experiments, and online score. So:
Topics/clusters ⇒ `super-stonks`; my own traces + dataset + evals ⇒ the user's project.

## Investigating a Topics cluster (by name)

When asked "how are traces performing in the '<cluster>' cluster" (or to investigate a
Topics cluster by name), use the `bt` CLI **against the shared `super-stonks` project**
(that's where the seeded traffic + Topics are — not the user's own project):

1. **Find the topic-map function id** — from `bt topics config --json --project super-stonks`
   (`.automations[0].topic_map_functions[]` → built-in `Task`/`Sentiment`/`Issues` + ids).
   Bare `bt topics`/`status` only shows automation status, **not** the ids. A cluster about
   what the user is *trying to do* is under **`Task`**:
   ```
   TASK=$(bt topics config --json --project super-stonks \
     | jq -r '.automations[0].topic_map_functions[] | select(.name=="Task").id')
   ```
2. **Download the report** — `bt topics report <topic-map-fn-id> --json --project super-stonks`. Shape:
   `clusters[]` (each: `name`, `description`, `count`, `keywords`, `sample_texts`) and
   `embedding_points[]` (each: `cluster`, `trace_id`, `text`).
3. **Match the cluster** by `name`; its `description` / `keywords` / `sample_texts` give
   the intent. **Gotcha:** the cluster's stable key is `.cluster_id` (an **integer**), not
   `.id` (which is `null`). Grab it: `jq -r '.clusters[] | select(.name=="<cluster>") | .cluster_id'`.
4. **Collect member traces** — `embedding_points` where `.cluster == <cluster_id>` (that
   integer; `-1` is the noise/unclustered bucket) → the `trace_id`s (these are
   **root_span_id**s):
   ```
   jq -r --argjson c <cluster_id> '.embedding_points[] | select(.cluster==$c) | .trace_id' report.json
   ```
5. **Inspect a sample** — compare user input vs. agent output vs. tools used. Use `bt sql`
   against the **super-stonks** id (not list-mode — it truncates long values). **Always
   pass `--json` and parse with jq — the default table is unusably wide (hundreds of KB for
   one trace).** Two shape gotchas: `bt sql --json` wraps rows in `{"data": [...]}` (use
   `.data[]`, not a bare array), and the turn-level user text + agent reply live on the
   `turn_{n}` spans (`.input` = user string, `.output` = agent reply); the root
   `stonks-sessions` span carries the same input/output too. `analyze_stock_buy` is the only
   TOOL span you'll see — its absence of a price tool is the failure. Example:
   ```
   bt sql "SELECT span_attributes.name AS name, input, output
           FROM project_logs('<super-stonks project id>')
           WHERE root_span_id = '<trace_id>' ORDER BY created" --json \
     | jq -r '.data[] | select(.name|startswith("turn_")) | "USER: \(.input)\nAGENT: \(.output)"'
   ```
   The SQL linter requires a range/id filter, so **always scope by `root_span_id`** (or add
   a `created >= '<date>'` range). Get the id from `bt projects list --json`.
6. **Report the failure mode from the evidence** — e.g. inputs ask for X but the agent has
   no tool for X, so it deflects. (For this repo that's the price gap — see `docs/GAP.md`.)

The curated dataset from this cluster is then created in the **user's own**
`BRAINTRUST_DEFAULT_PROJECT` (write), not in `super-stonks`.

### Creating the dataset — use the `bt` CLI, not the SDK

**Always create datasets with `bt datasets create --file <rows.jsonl>`** (the `braintrust`
skill's mechanics), **not** the Python `braintrust` SDK or a TS `DatasetPipeline` — even
when invoked via `agent-auto-improvement` (its examples point at the pipeline/SDK; override
that here). Build the rows from `bt sql --json` piped through `jq` into JSONL, one row per
line: `{"input": ..., "expected": ..., "metadata": {...}}` (metadata carries the baseline
`broken_output`, failure category, and `source_trace_id`).

Example row (first row of the `current-price-gap-offline` dataset in the user's project):

```json
{
  "input": "How much is TSLA stock today?",
  "expected": null,
  "metadata": {
    "broken_output": "I'm not able to provide the real-time price of TSLA stock directly. However, I can share some analysis regarding its performance.\n\nThe current investment analysis for Tesla (TSLA) indicates a **BUY** recommendation based on several signals:\n- **RSI (14)**: 47.7, which suggests it’s nearing the neutral range.\n- **50-day Moving Average vs 200-day Moving Average**: The 50-day moving average is currently below the 200-day moving average, indicating a potential downward trend.\n- **52-week Position**: TSLA is positioned at 53% of its 52-week range, implying it's performing moderately compared to its highest and lowest prices over the past year.\n- **Analyst Recommendation Mean**: 2.34 (on a scale where 1 is a strong buy and 5 is a strong sell), suggesting analysts tend to view it positively.\n\nOverall, while it's recommended as a buy, do consider the noted risks, including market volatility and further technical trends. For the latest price, I recommend checking a financial news site or stock market app.",
    "failure_category": "price_gap",
    "failure_description": "User asked for a current/live price or recent performance; agent has no price tool (get_stock_performance is disabled) so it either deflects (\"no real-time access\") or substitutes an analyze_stock_buy verdict — never returns the requested price.",
    "source_project": "super-stonks",
    "source_span_name": "turn_0",
    "source_trace_id": "3a10c2bf07135888680b95ff82357f26",
    "topic_cluster": "Current stock price analysis"
  }
}
```

Then:

```
BRAINTRUST_PROFILE=workshop-advanced-tracing bt datasets create <name> \
  --description "..." --file rows.jsonl -p "$BRAINTRUST_DEFAULT_PROJECT"
```

Use `bt datasets update/add <name> --file …` to upsert more rows, and
`bt datasets view <name> -p <project> --json` to verify. Never write the dataset to
`super-stonks` — always the user's own project.

## Conventions (keep these stable — scorers/Topics/seed depend on them)

- **Stack:** LangGraph + OpenAI `gpt-4o-mini`, `braintrust.wrap_openai`; market data via
  yfinance. System prompt is the hardcoded `STOCK_CHAT_SYSTEM` — **no prompt registry,
  nothing pushed.**
- **Trace shape / span names:** root `stonks-sessions` → `turn_{n}` (0-based) →
  `{ LLM span, TOOL span }`. Both the CLI (`agent/__main__.py`) and Streamlit (`app.py`)
  emit this; any seed script must too.
- **Config:** `.env` holds only secrets (`OPENAI_API_KEY`, `BRAINTRUST_API_KEY`).
  `BRAINTRUST_PROFILE` + `BRAINTRUST_DEFAULT_PROJECT` are shell exports (see
  `docs/WORKSHOP.md §4.2`); the `bt` CLI and the Python code both read the project from
  `BRAINTRUST_DEFAULT_PROJECT`. Org is always `workshop-advanced-tracing`.
- **`bt` CLI auth:** the CLI is authenticated with an API token via `bt auth login`
  (stored in the profile / keychain), so it does **not** read `BRAINTRUST_API_KEY` from
  `.env`. That `.env` value exists only for the **Python Braintrust SDK** (agent,
  Streamlit, evals). Don't add `--env-file` to `bt` commands.
- **Package management:** uv. Add deps to `pyproject.toml`; run via `uv run`.
- **Env in bash (coding agents):** a human exports the vars once per session
  (`docs/WORKSHOP.md §4.2`), but a coding agent's shell usually **resets between commands** —
  exports don't persist. So pass what each command needs **inline**:
  - `bt` / `make` targets need the project: `BRAINTRUST_DEFAULT_PROJECT=super-stonks make seed-smoke`
    (and `BRAINTRUST_PROFILE=workshop-advanced-tracing` if the profile isn't already the active one).
  - Ad-hoc Python that imports the agent/scorers (they build OpenAI clients at import)
    needs the keys: `OPENAI_API_KEY=… BRAINTRUST_API_KEY=… uv run python …`. The CLI/Streamlit/eval
    entrypoints already call `load_dotenv()`, so `make agent` etc. pick them up from `.env` on their own.

## Don't

- Don't rename spans, restructure the package, or change `analyze_stock_buy`.
- Don't push prompts to Braintrust.
- Don't hardcode a project name — read `BRAINTRUST_DEFAULT_PROJECT`.
