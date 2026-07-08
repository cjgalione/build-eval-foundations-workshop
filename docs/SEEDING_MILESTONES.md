# Seeding Milestones — provisioning the workshop project

The build plan for standing up a **live, pre-seeded Braintrust project** before the
workshop, then the **live workshop arc** that closes the gap. Pre-work leaves the
project with: the price tool **commented out**, Topics enabled, and ~1,000
production-like traces where realtime-price asks fail. The live arc then observes the
gap in Topics, builds a grounding scorer, proves it with two experiments, and promotes
it to an online score.

> **The agent already exists** (`src/super_stonks/agent/`, on `dev`/`main`). These milestones wire
> everything *around* it. The trace shape is now known, so scorer scope is **resolved
> below**.

**Status legend:** `[ ]` not started · `[~]` in progress · `[x]` done

---

## The workshop arc (the story these milestones serve)

1. **Comment out `get_stock_performance`** → the agent has no tool for realtime data.
2. **Seed ~1,000 traces** (M0–M3). Realtime-price asks get answered from parametric
   knowledge — ungrounded, often wrong.
3. **Observe Topics clusters** (§8) → a big "realtime stock info" cluster surfaces the
   demand the agent can't serve. *That's the gap.*
4. **Build a scorer** that measures whether the response is **grounded in tool data**
   (`response_grounded_in_data`, already skeletoned in `src/super_stonks/evals/scorers.py`).
5. **Experiment 1 — baseline** (tool still off): run it as a Braintrust experiment →
   the grounding score is **poor**.
6. **Uncomment the tool.**
7. **Experiment 2** (tool on): same dataset, same scorer → grounding score **jumps**.
8. **Push the scorer + add it as an online automation** so it scores live production.
9. **Generate new traffic** → the online score confirms the improved agent does better.

> ⚠️ **CLI limitation baked into the plan (step 8).** The `bt` CLI can push the scorer
> function but **cannot create the online-scoring automation** — see the callout below.
> That step uses the REST API (scriptable) or the UI.

---

## Where everything lives (verified against the code)

**Org:** always `workshop-advanced-tracing` — pinned by the `BRAINTRUST_PROFILE`
attendees set in `WORKSHOP.md §4.2`.

**Project:** resolved from **`BRAINTRUST_DEFAULT_PROJECT`** (the `bt`-native project
var, also set in §4.2). Every command, seed, eval, and automation reads it — attendees
each point it at their own project; the presenter points it at the seed project(s) when
seeding ahead of time. **No project name is hardcoded.**

> ✅ Code alignment (done): `src/super_stonks/agent/config.py::get_braintrust_project_name()` now
> reads **`BRAINTRUST_DEFAULT_PROJECT`** first (falls back to `BRAINTRUST_PROJECT_NAME`,
> then the default). Both `python -m super_stonks.agent` and the **Streamlit app** log through
> this resolver, so agent traffic lands in the same project the CLI uses. `.env.example`
> updated to match. Still to do when you write them: `seed.py`, `qa_eval.py`, and
> `configure.py` read `BRAINTRUST_DEFAULT_PROJECT` too (qa_eval scaffold already does).

**Stack:** LangGraph + OpenAI **gpt-4o-mini**, wrapped with `braintrust.wrap_openai`;
market data via **yfinance**; system prompt is the **hardcoded `STOCK_CHAT_SYSTEM`** —
no prompt registry, no `load_prompt`, nothing pushed. `exa` is **not used anywhere** —
verified across all files and git refs.

**Config & secrets split:**
- **`.env`** (loaded by Python via `load_dotenv()`): `OPENAI_API_KEY`, `BRAINTRUST_API_KEY` — the two secrets the agent / Streamlit / evals need.
- **Session exports** (`WORKSHOP.md §4.2`): `BRAINTRUST_PROFILE` (bt auth + org) and `BRAINTRUST_DEFAULT_PROJECT` (project, read by bt **and** Python). The `bt` CLI needs no `.env` / `--env-file` — it auths via the profile.

| Path | What it is |
|---|---|
| `src/super_stonks/agent/__main__.py` | CLI entry (`python -m super_stonks.agent`). `load_dotenv()`. Interactive multi-turn session. **Owns the manual span tree**: `stonks-sessions` (root) → `turn_{n}`, each `turn_span.log(input=…, output=…)`. |
| `src/super_stonks/agent/agent.py` | LangGraph: `agent` ⟷ `tools` nodes; compiled `graph`. **Hardcoded `STOCK_CHAT_SYSTEM`** (no registry call); honors `state["model"]` override (used by evals). `wrap_openai(OpenAI())` → LLM child spans. |
| `src/super_stonks/agent/tools.py` | `TOOLS_SPEC` + two `@traced` TOOL-span tools: `get_stock_performance` (yfinance: current price + day/week/year %) ← **commented out in M1**, `analyze_stock_buy` (RSI / MA cross / 52w / analyst → BUY·HOLD·SELL). |
| `src/super_stonks/agent/prompts.py` | `STOCK_CHAT_SYSTEM` — the agent's only system prompt (personal-finance scope). |
| `src/super_stonks/agent/config.py` | Project-name resolver + `init_braintrust_logger()`. |
| `src/super_stonks/agent/state.py` | `AgentState` TypedDict — `{messages, model}`. |
| `src/super_stonks/app.py` | Streamlit UI (`streamlit run src/super_stonks/app.py`) — live-demo front end for §5.1. |
| `src/super_stonks/evals/scorers.py` | **Scorer skeleton** — 7 handlers + `SpanParams`/`TraceParams` models. The workshop scorer `response_grounded_in_data` lives here. |

**Actual trace shape (drives all scope decisions):**

```
stonks-sessions          (root, span_attributes.type = task)   ← whole session
└─ turn_0                    (type = task)   logs input=user_input, output=reply
   ├─ chat.completions.create   (LLM span, via wrap_openai)
   └─ get_stock_performance / analyze_stock_buy   (TOOL span, via @traced)
└─ turn_1
   └─ …
```

With `get_stock_performance` commented out (M1), realtime-price turns have **no TOOL
span** — nothing for the grounding scorer to ground against.

> **Span names are shared across entrypoints.** Both the CLI (`__main__.py`) and the
> Streamlit app (`app.py`) now emit root `stonks-sessions` + `turn_{n}` (0-based). The
> **seed (M3) must emit the same wrapper** around `graph.invoke` — the graph itself does
> *not* create the session/turn spans, the entrypoint does. Keep the names identical or
> scorers / Topics / `btql_filter`s won't apply uniformly to seeded vs. live traffic.

---

## The gap — comment out the price tool

The gap is created deliberately: **comment out `get_stock_performance` in
`src/super_stonks/agent/tools.py`** (remove it from `TOOLS_SPEC` and from `_invoke_tool` routing in
`src/super_stonks/agent/agent.py`). With it gone, the agent has no way to fetch realtime prices, so
seeded realtime-price asks are answered from parametric knowledge — ungrounded and
often stale/wrong. `analyze_stock_buy` stays in (the workshop is about the *price*
grounding gap, not the research path).

The scorer that measures this — **`response_grounded_in_data`** — is already skeletoned
in `src/super_stonks/evals/scorers.py`: an LLM judge that checks the response cites specific
prices/percentages that appear in the tool data. With the tool commented out there are
no tool figures to ground on, so the score is low by construction. Uncommenting the
tool is the fix that moves it.

---

## ⚠️ CLI capability check — online scoring automations (verified `bt` v0.11.x)

**Question:** can `/braintrust` (the `bt` CLI) create the online-scoring automation for
step 8, or does that need the UI?

**Answer: the CLI cannot create an online-scoring automation.** Verified against the
full subcommand tree:

| Task | CLI support |
|---|---|
| Push a scorer **function** | ✅ `bt functions push` (also `bt scorers list/view/invoke`) |
| Enable a **Topics** automation | ✅ `bt topics config enable` |
| Create an **online-scoring** automation (run a scorer on X% of prod logs) | ❌ **no command** — Topics is the *only* automation type the CLI exposes |

Online scores are `project_score` objects with `score_type: "online"`. They can only be
created via:
- **REST API / SDK** — `PUT /v1/project_score` with the `config.online` block (sampling
  rate, scorer function IDs, `apply_to_root_span`, `btql_filter`). This is what the
  reference `bt-cost-optimizer-demo/phase/complete/configure.ts` does. **Scriptable →
  wrap it in `make automations`.**
- **The UI** — Project → **Configuration → Online scoring** → add rule.

**Recommendation for the workshop:** push the scorer with `bt functions push` (a clean
CLI moment), then add the online automation with a one-line `make automations` that
hits the API. If you'd rather have a visual "flip the switch" beat on screen, do that
one step in the UI — but there is no `bt` command for it.

---

## Order of operations

Topics only cluster spans generated **after** it's enabled, so enable Topics before
seeding. The scorer and the online automation come **later**, in the live arc — they
are *not* part of pre-seed provisioning.

```
PRE-WORK:   comment out tool ─▶ enable Topics ─▶ SMOKE seed (10) ─▶ verify ─▶ FULL seed (1k)
                M1                 M2              M3-smoke           gate      M3-full

LIVE ARC:   observe Topics ─▶ finalize grounding scorer ─▶ exp1 (tool off, poor) ─▶ uncomment tool ─▶ exp2 (tool on, better)
                §8                 M4                          M5                        M5               M5
            ─▶ bt functions push scorer ─▶ make automations (API) ─▶ new traffic scored live
                    M6                          M6                        M6
```

`make provision` chains the pre-work (M2→M3-smoke) and stops at the smoke gate.

---

## Milestone 0 — Scaffold (uv + make)

Python project managed with **uv**; all workflows driven by **make**. The agent code
already exists — this milestone adds the packaging + operator entry points around it.

| Status | Task | Notes |
|---|---|---|
| [x] | `pyproject.toml` + `uv.lock` | **done** — package **`super-stonks`** (hatchling, src-layout, `packages = ["src/super_stonks"]`); deps: `braintrust`, `autoevals`, `openai`, `langgraph`, `yfinance`, `click`, `streamlit`, `python-dotenv`, `pydantic`; `requires-python >=3.10`. `uv sync` installs it editable → `import super_stonks…` works everywhere (verified) |
| [ ] | `make setup` → `uv sync` + copy `.env.example`→`.env` if missing | `.env` holds only secrets: `OPENAI_API_KEY`, `BRAINTRUST_API_KEY`. `BRAINTRUST_PROFILE` + `BRAINTRUST_DEFAULT_PROJECT` are session exports (§4.2) |
| [x] | `Makefile` with the target list (below) | **done** — `setup`, `agent`, `topics`, `push-scorer` (pushes `push_assets.py`) work now; `seed*` + `automations` guarded with a pointer to their milestone until `seed.py`/`configure.py` exist |
| [x] | `.gitignore` already present | keeps `.env` out (verified) |

**Actual + planned layout** (✎ = to create):

**src-layout — the importable package is `super_stonks` (installed editable by `uv sync`).**

```
pyproject.toml            # ✓ uv package "super-stonks" (hatchling, src-layout)
uv.lock                   # ✓ resolved lockfile
Makefile                  # ✓ operator entry points (setup/streamlit/topics live; rest guarded)
.env.example              # ✓ secrets only
src/super_stonks/
  __init__.py             # ✓ package init
  app.py                  # ✓ Streamlit UI (was app/streamlit.py)
  agent/
    __init__.py           # ✓
    __main__.py           # ✓ CLI entry + span tree (python -m super_stonks.agent)
    agent.py              # ✓ LangGraph graph
    tools.py              # ✓ get_stock_performance, analyze_stock_buy
    prompts.py            # ✓ STOCK_CHAT_SYSTEM (used as-is, not pushed)
    config.py  state.py   # ✓
  evals/
    __init__.py           # ✓
    judge_prompts.py      # ✓ shared LLM-judge prompts (online prompt scorer + offline LLMClassifier)
    scorers.py            # ✓ offline scorers (grounding scorer + skeleton) built from judge_prompts
    push_assets.py        # ✓ pushes ONLY the grounded scorer online (the reveal, M6)
    qa_eval.py            # ✎ experiment scaffold for the two eval runs (M5)
  provision/
    __init__.py           # ✓
    configure.py          # ✎ enable Topics (M2) + create online automation via API (M6)
    copy_dataset.py       # ✓ copy a dataset from super-stonks to all other org projects
  seed/
    __init__.py           # ✎
    scenarios.py          # ✎ use-case mix incl. the price-ask gap (M3)
    seed.py               # ✎ drives graph.invoke → traces (M3)
```

Because the package is installed, `import super_stonks…` works everywhere — including
under `streamlit run src/super_stonks/app.py` — with **no `PYTHONPATH` needed**.

**Make targets (contract for later milestones):**

```
make setup            # M0  uv sync + .env bootstrap
make agent            # run the agent's Streamlit app (live demo — §5.1)
make topics           # M2  enable Topics programmatically
make seed-smoke       # M3  seed 10 traces (tool OFF)
make seed             # M3  seed 1,000 traces (tool OFF) — the full workload
make provision        # M2 then SMOKE seed (10) and verify — stops at the gate
make copy-dataset DATASET=<name>   # fan a super-stonks dataset out to all other org projects
make push-scorer      # M6  bt functions push the grounding scorer
make automations      # M6  create the online-scoring automation via API (no bt cmd)
```

> **`make copy-dataset`** (`provision/copy_dataset.py`): the presenter curates a dataset
> in the primary **`super-stonks`** project, then fans it out to every other project in
> the org so each attendee starts from the same data. Projects are enumerated with the
> **bt CLI** (`bt projects list --json`, profile auth); rows are copied with the
> **SDK** (`init_dataset` — the CLI has no cross-project copy). Row `id`s are preserved,
> so re-running upserts (idempotent).

```makefile
# make agent — super_stonks is an installed package, so no PYTHONPATH needed
agent:
	uv run streamlit run src/super_stonks/app.py
```

---

## Milestone 1 — Comment out the price tool (create the gap)

Deliberately break the realtime-price path so the seed shows a real deficiency.

| Status | Task | Notes |
|---|---|---|
| [x] | Comment out `get_stock_performance` in `src/super_stonks/agent/tools.py` | **done** — its `TOOLS_SPEC` entry is a commented block behind a `THE GAP` marker; the `@traced` fn stays defined |
| [x] | Drop its route in `src/super_stonks/agent/agent.py::_invoke_tool` | **done** — route commented (same `THE GAP` marker); a stray/hallucinated call now returns `Unknown tool` |
| [x] | Leave `analyze_stock_buy` intact | the workshop is about the *price-grounding* gap, not research |
| [ ] | Sanity-run one price ask locally | `python -m super_stonks.agent` → confirm it answers ungrounded, no TOOL span |

> **The gap is active now.** Only `analyze_stock_buy` is exposed. To close it in M5,
> uncomment **two** clearly-marked blocks: the `get_stock_performance` entry in
> `tools.py::TOOLS_SPEC` and its route in `agent.py::_invoke_tool` (both flagged
> `THE GAP`).

---

## Milestone 2 — Enable Topics programmatically (`make topics`)

Turn Topics **on before seeding** so the ~1k traces cluster — the realtime-price cluster
is what §8 "discovers".

| Status | Task | Notes |
|---|---|---|
| [ ] | `src/super_stonks/provision/configure.py` enables Topics via `bt topics config enable` | shell out; idempotent (`delete --force` then `enable`) |
| [ ] | (optional) custom `intent` facet so a clean `realtime_price` topic forms | facet fn + topic-map classifier via API |
| [ ] | `make topics` runs it | |

```bash
# project comes from $BRAINTRUST_DEFAULT_PROJECT — no --project needed
bt topics config enable \
  --name "Workshop Topics" \
  --topic-window 1d \
  --generation-cadence 1h \
  --no-input
```

> **Custom facet (optional).** For a crisp `realtime_price` intent: create a facet
> extraction fn (`function_type: "facet"`) + a topic-map classifier (`function_type:
> "classifier"`, `function_data.type: "topic_map"`), then `POST
> /api/project_automation/patch_id` with the **full** config (patch is a replace, not a
> merge). Built-in facets (Task/Sentiment/Issues) are enough for a first pass.

---

## Milestone 3 — Seed the project (tool OFF): smoke 10 → full 1,000

Drive the (now toolless) agent over a realistic mix so the realtime-price gap is a
visible, dense Topics cluster. **Smoke 10 first, verify, then full 1,000.** No online
scoring yet — that comes in M6; here we just need traces + clusters.

| Status | Task | Notes |
|---|---|---|
| [ ] | `seed/scenarios.py` defines the use-case mix (below) | ~20% realtime-price asks (the gap) |
| [ ] | `src/super_stonks/seed/seed.py` runs sessions through `super_stonks.agent.agent.graph` | reuse the real graph so the span tree matches prod |
| [ ] | `make seed-smoke` → 10 traces; verify | see gate below |
| [ ] | `make seed` → ~1,000 traces | resumable / safe to re-run |
| [ ] | Confirm the realtime-price traces cluster in Topics | this is the §8 "aha" |

**Suggested use-case mix (tool OFF):**

| Use case | Share | With tool commented out |
|---|---|---|
| **Realtime stock price** ("what's TSLA at right now", "current AAPL price") | **~20% (the gap)** | ❌ no tool → ungrounded, fabricated/stale numbers |
| Buy/hold/sell research ("should I buy MSFT") | ~20% | ✅ `analyze_stock_buy` still works |
| Stock performance ("how has NVDA done this year") | ~15% | ⚠️ degraded — was `get_stock_performance` |
| Compare two tickers | ~10% | ⚠️ degraded |
| Retirement / account concept Qs (IRA, 401k, RMD, Roth) | ~15% | n/a (parametric, in-scope) |
| Budgeting / debt / taxes concept Qs | ~10% | n/a (parametric) |
| Explain an investing concept (P/E, ETFs, dividends) | ~10% | n/a (parametric) |

**Smoke gate (after `make seed-smoke`):**

```bash
make seed-smoke
bt view logs --list-mode spans --json | jq '.'   # project from $BRAINTRUST_DEFAULT_PROJECT
```
- [ ] traces landed · [ ] span tree `stonks-sessions → turn_n → llm` (no tool span on price asks) · [ ] Topics starts clustering

Don't run `make seed` until the smoke gate passes. `make provision` runs M2→M3-smoke and stops here.

> The `SAMPLE_PROMPTS` in `src/super_stonks/app.py` seed the in-scope buckets. For the gap
> bucket, vary tickers + phrasings so the cluster is dense but not identical.

---

## Milestone 4 — Finalize the grounding scorer (`src/super_stonks/evals/scorers.py`)

The scorer the workshop builds is already skeletoned: **`response_grounded_in_data`** —
an LLM judge (gpt-4o, `autoevals.LLMClassifier`, `{{thread}}`, CoT, 11-level A+→F) that
checks the response cites specific prices/percentages present in the tool data. With the
tool off, there's nothing to ground on → low score.

| Status | Task | Notes |
|---|---|---|
| [ ] | Finalize `response_grounded_in_data` handler | returns `{"name","score","metadata"}`; reads `output` + `trace` |
| [ ] | Confirm it's **trace-scoped** | it needs `{{thread}}` + tool spans → register with `TraceParams`, `apply_to_root_span` |
| [ ] | (optional) also finalize `tool_returned_data` | code scorer, trace-scoped — 0 when no tool span exists; a nice free companion signal |

**Full scorer skeleton for reference** (`src/super_stonks/evals/scorers.py`; scope resolved from the trace shape):

| Scorer | Type | Reads | Scope |
|---|---|---|---|
| `response_grounded_in_data` | **LLM judge** | `output`, `trace` | **trace** — *the workshop scorer* |
| `tool_returned_data` | code | `output`, `trace` | trace |
| `tool_ticker_valid` | code | `output` | span |
| `has_citations_header` | code | `output` | span |
| `research_verdict_sound` | LLM judge | `input`, `output` | span/row |
| `scope_adherence` | LLM judge | `output`, `trace` | trace |
| `conversation_quality` | LLM judge | `output`, `trace` | trace |

> You only need `response_grounded_in_data` for the core arc. The rest are available if
> you want a richer scorecard, but keep the on-screen story to the one scorer that moves.

---

## Milestone 5 — Two experiments: prove the gap, then the fix

Run the grounding scorer as **Braintrust experiments** (offline evals) — first with the
tool off (poor), then uncomment and re-run (better). Same dataset, same scorer, changed
agent → a clean before/after.

| Status | Task | Notes |
|---|---|---|
| [ ] | Curate a dataset from the realtime-price Topics cluster (§9) | e.g. `init_dataset(project, "realtime-price")` |
| [ ] | `src/super_stonks/evals/qa_eval.py` — `Eval()` wrapping `graph`, scored by `response_grounded_in_data` | `state["model"]` override available if you also want to A/B models |
| [ ] | **Experiment 1 (tool OFF):** `bt eval src/super_stonks/evals/qa_eval.py` | grounding score is **low** — the baseline |
| [ ] | **Uncomment `get_stock_performance`** (revert M1) | the live fix |
| [ ] | **Experiment 2 (tool ON):** `bt eval src/super_stonks/evals/qa_eval.py` | grounding score **jumps** — compare in the UI (§15) |

```python
# src/super_stonks/evals/qa_eval.py — scaffold
import os
from dotenv import load_dotenv
load_dotenv()                                          # OPENAI_API_KEY + BRAINTRUST_API_KEY from .env

from braintrust import Eval, init_dataset
from super_stonks.agent.agent import graph
from super_stonks.evals.scorers import response_grounded_in_data   # the workshop scorer

PROJECT = os.environ["BRAINTRUST_DEFAULT_PROJECT"]     # each attendee's own project (session export)

def run(user_input: str) -> str:
    result = graph.invoke({"messages": [{"role": "user", "content": user_input}]})
    msgs = result["messages"]
    return next(
        (m["content"] for m in reversed(msgs)
         if m.get("role") == "assistant" and m.get("content")),
        "",
    )

Eval(
    PROJECT,
    data=init_dataset(PROJECT, "realtime-price"),      # curated in §9
    task=run,
    scores=[response_grounded_in_data],
)
```

> **Import order matters:** `agent.py` and `src/super_stonks/evals/scorers.py` both build their OpenAI
> clients at *import* time, so `load_dotenv()` must run **before** those imports (as
> above) or `bt eval` won't have `OPENAI_API_KEY` / `BRAINTRUST_API_KEY`.

> Run 1 and Run 2 land as two experiments in the same project → the §15 comparison view
> shows the grounding-score delta driven purely by uncommenting the tool.

---

## Milestone 6 — Promote the scorer to an online score

Push the scorer, then attach it as an **online automation** so it scores live
production traffic — and watch the improved (tool-on) agent score better on new traffic.

> **Only the grounded scorer is ever pushed.** No scorers are pushed during
> provisioning — attendees' fresh projects stay clean, and the single online score is
> the one the story is about. It's pushed as an **LLM-judge prompt scorer**
> (`push_assets.py` → `project.scorers.create(messages=…, model=…, choice_scores=…)`),
> sharing `judge_prompts.GROUNDED_PROMPT` with the offline `LLMClassifier` in
> `scorers.py` — same rubric online and offline.

**⚠️ The online automation is NOT a `bt` command** (see the CLI callout above). Push is
CLI; the automation is API (scriptable) or UI.

| Status | Task | Notes |
|---|---|---|
| [ ] | `bt functions push` the grounding scorer → `make push-scorer` | registers it as a project function; resolve its function ID |
| [ ] | Create the online automation via API → `make automations` | `src/super_stonks/provision/configure.py`: `PUT /v1/project_score`, `score_type:"online"` (no CLI equivalent) |
| [ ] | **`make automations` sets the scope automatically** | derive trace-vs-span from the scorer (M4) and set the online config accordingly — see below |
| [ ] | *(or)* add it in the UI | Project → Configuration → Online scoring → add rule |
| [ ] | Generate fresh traffic (Streamlit or `python -m super_stonks.agent`) | agent now has the tool back |
| [ ] | Confirm the online score attaches and is **higher** than the baseline traces | §17 "validate new coverage" |

**Scope is not hardcoded — `configure.py` derives it from the scorer.** Each scorer
declares its scope via its param model in `src/super_stonks/evals/scorers.py` (`TraceParams` → trace,
`SpanParams` → span). `make automations` reads that and writes the matching
`config.online`:

- **trace-scoped** (e.g. `response_grounded_in_data`) → `apply_to_root_span: True`
  (score the root `stonks-sessions`/`turn` span, with the full thread + tool spans).
- **span-scoped** (e.g. `tool_ticker_valid`) → `apply_to_root_span: False` + a
  `btql_filter` that targets the specific span (e.g. `span_attributes.name ilike 'turn_%'`).

```python
# src/super_stonks/provision/configure.py — the step bt CAN'T do; see reference configure.ts
# PROJECT_ID resolved from the env project: GET /v1/project?project_name=$BRAINTRUST_DEFAULT_PROJECT
# One source of truth: map each scorer to its scope, then build the config.
SCOPES = {"response_grounded_in_data": "trace", "tool_ticker_valid": "span"}  # from scorers.py param models

def online_config(fn_id: str, slug: str) -> dict:
    trace_scoped = SCOPES[slug] == "trace"
    online = {
        "sampling_rate": 1.0,                              # generous for the demo
        "scorers": [{"type": "function", "id": fn_id}],
        "apply_to_root_span": trace_scoped,               # ← scope-driven, not hardcoded
    }
    if not trace_scoped:
        online["btql_filter"] = "span_attributes.name ilike 'turn_%'"  # target the span
    return {"online": online}

PUT /v1/project_score
{
  "project_id": PROJECT_ID,
  "name": "grounded-in-tool-data",
  "score_type": "online",
  "config": online_config(GROUNDED_FN_ID, "grounded-in-tool-data"),   # → apply_to_root_span=True
}
```

```bash
make push-scorer     # bt functions push  → function ID
make automations     # API call → online score live
# then drive new traffic and watch the score in bt view logs / the UI
```

---

## Day-of checklist

```bash
# --- pre-work (tool commented out) ---
make setup                 # uv sync + .env
make provision             # topics + 10-trace smoke  ← STOP & verify
make seed                  # ~1,000 traces, tool OFF (the gap is now in the data)

# --- live arc ---
# §8  observe Topics → realtime-price cluster
# §9  curate that cluster into a dataset
bt eval src/super_stonks/evals/qa_eval.py   # Experiment 1 (tool OFF) → low grounding score
#     uncomment get_stock_performance
bt eval src/super_stonks/evals/qa_eval.py   # Experiment 2 (tool ON)  → grounding score jumps (§15)
make push-scorer           # bt functions push the scorer
make automations           # API → online score (NOT a bt command)
# §17 drive new traffic → online grounding score confirms the improvement
```

Reference for Topics + online-automation API calls (the non-CLI bits):
`/Users/spencerseale/bt-repos/bt-cost-optimizer-demo/phase/complete/configure.ts`.
