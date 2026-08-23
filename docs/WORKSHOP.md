# Build Your Eval Foundations — Presenter run-of-show

## Preflight (complete before attendees arrive)

1. Fork this repository to `cjgalione/build-eval-foundations-workshop` and verify the
   HTTPS clone URL in `docs/WELCOME.md`.
2. Confirm issued Braintrust credentials can create isolated attendee projects in the
   workshop org and that issued OpenAI credentials have sufficient capped capacity.
3. In a separate presenter project, keep the price tool disabled, run `make prepare`,
   and confirm Topics has a visible current-price cluster.
4. Run the attendee path in a second, empty project: setup, one Streamlit trace, UI
   dataset import, baseline eval, two-line fix, second eval.
5. In the presenter project only, run `make push-scorer` and `make automations`, then
   create fresh traffic and confirm `price_response_completeness` appears.

## Three-hour flow

| Time | Segment | Audience action |
| --- | --- | --- |
| 0–20 min | Setup | Install `uv`/`bt`, authenticate, create individual project |
| 20–40 min | I do: observe + Topics | Watch seeded presenter project reveal the price gap |
| 40–70 min | We do: traces + dataset | Create a local trace, import starter cases, inspect with Loop |
| 70–100 min | We do: criteria | Edit/test the UI scorer template |
| 100–130 min | Baseline + fix | Run baseline, re-enable two tool blocks, compare evals |
| 130–150 min | I do: online score | Show the online completeness proxy and fresh scores |
| 150–180 min | You do + Q&A | Add a case/refine a rubric; optional code or coding-agent lane |

## Teaching notes

- Topics is discovery at scale; it is not a prerequisite for the attendee exercise.
- Separate a **quality rubric** (subjective UI LLM judge) from a **grounding check**
  (deterministic, trace-scoped comparison against a tool result).
- Be precise about online scoring: `price_response_completeness` is useful monitoring,
  not proof that a number was sourced correctly.
- If Yahoo Finance is unavailable, use the pre-recorded baseline/fixed traces for the
  comparison and keep the lesson focused on the evaluation loop.
