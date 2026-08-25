# Build Your Eval Foundations — Participant Guide

You will work in your own fresh project in the workshop Braintrust org. The presenter
will show Topics on a separate seeded project; you do not need access to that project.

## 1. Set up your project

Install `uv` and `bt`, clone the repository, then run:

```bash
make setup
```

Paste the issued keys into `.env`:

```bash
OPENAI_API_KEY=...
BRAINTRUST_API_KEY=...
```

Authenticate the CLI with the issued Braintrust credential, then give yourself an
isolated project name:

```bash
bt login
export BRAINTRUST_PROFILE="workshop-advanced-tracing"
export BRAINTRUST_DEFAULT_PROJECT="<your-name>-eval-foundations"
```

## 2. Create and inspect a trace

```bash
make agent
```

Ask: **“What is AAPL trading at right now?”** Stop the app after one response, then open
your Braintrust project in the UI. Inspect the trace: what did the user request, what did
the assistant say, and which tools were called?

The presenter will now demonstrate how Topics surfaces this pattern at scale. Your own
project starts fresh, so use its traces and Loop for the remaining exercises.

## 3. Make a small evaluation dataset

In the Braintrust UI, create a dataset named `price-gap-baseline`. Import
[`workshop_assets/price-gap-baseline.jsonl`](../workshop_assets/price-gap-baseline.jsonl),
then add your own observed bad trace as another case if time permits.

Ask Loop to summarize the failure pattern in your trace or dataset. A useful prompt is:

```text
What does the user request in these price questions, how does the assistant respond,
and what test cases should we retain to prevent this behavior from recurring?
```

### Optional CLI / coding-agent lane

If you prefer to curate your own traces in code, copy up to five root trace IDs from the
UI and run:

```bash
make curate-dataset TRACE_IDS=<id-1>,<id-2>
```

This writes metadata-rich JSONL and creates `price-gap-baseline` in your project. A
coding agent can help inspect the trace IDs, but is not required.

## 4. Write a quality criterion in the UI

Create an LLM-as-a-judge scorer named `price_response_quality`. Start with
[`workshop_assets/price-response-quality-template.md`](../workshop_assets/price-response-quality-template.md).
Before saving, change one criterion to reflect what matters for your agent, then test it
against one good and one bad response in the scorer UI.

This scorer measures response quality. It does **not** prove that an answer used a tool.

## 5. Establish a reliable baseline

Run the supplied evaluation against your dataset:

```bash
EVAL_DATASET=price-gap-baseline uv run bt eval src/super_stonks/evals/qa_eval.py
```

The experiment's `price_response_matches_tool_data` score is deliberately narrow and
reliable: it passes only when the final answer states the current price returned by the
traced price tool. With the tool off, it should score `0`.

## 6. Close the gap, then compare

The price tool is already implemented but intentionally disabled. Follow [GAP.md](GAP.md)
to re-enable its two marked blocks. Then rerun the same eval:

```bash
EVAL_DATASET=price-gap-baseline uv run bt eval src/super_stonks/evals/qa_eval.py
```

Compare the two experiments. Did the exact-price score improve? Inspect an individual
trace to confirm that `get_stock_performance` produced the data cited in the answer.

## 7. Online scoring demo

The presenter will show a live `price_response_completeness` online score. It is an
LLM-judge proxy for whether an answer is direct and complete; it is intentionally labeled
separately from the trace-based grounding score you used offline.
