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

## 90-minute flow

| Time | Segment | Audience action |
| --- | --- | --- |
| 0–10 min | Setup | Verify `uv`/`bt`, authenticate, and create an individual project |
| 10–24 min | I do: observe + Topics + advanced preview | Watch the seeded presenter project reveal the price gap, then briefly preview advanced Braintrust workflows participants can explore afterward |
| 24–37 min | We do: traces + dataset | Create a local trace, import starter cases, and inspect with Loop |
| 37–50 min | We do: criteria | Edit and test the UI scorer template |
| 50–69 min | Baseline + fix | Run the baseline, re-enable two tool blocks, rerun, and compare experiments |
| 69–79 min | I do: online score | Show the online completeness proxy and fresh scores |
| 79–90 min | You do + Q&A | Add a case or refine a rubric; use the optional code or coding-agent lane if desired |

Treat the installation steps in `docs/WELCOME.md` as pre-work so the setup block is a
verification and recovery window, not the first time attendees install dependencies.
Have the seeded Topics project, scorer editor, baseline/fixed experiments, and online
score open in separate tabs before the session. Keep transitions hard: each timebox
includes its UI navigation and explanation.

The advanced preview is intentionally presenter-led. Use it to show the ceiling — for
example, trace-level or multi-turn scoring, human review, or a broader production
monitoring workflow — without adding those concepts to the beginner hands-on path.
Point interested participants to follow-up material or office hours.

## Teaching notes

- Topics is discovery at scale; it is not a prerequisite for the attendee exercise.
- The workshop is a beginner foundations session. Advanced examples in the opening
  demonstration are previews, not participant requirements.
- Separate a **quality rubric** (subjective UI LLM judge) from a **grounding check**
  (deterministic, trace-scoped comparison against a tool result).
- Be precise about online scoring: `price_response_completeness` is useful monitoring,
  not proof that a number was sourced correctly.
- If Yahoo Finance is unavailable, use the pre-recorded baseline/fixed traces for the
  comparison and keep the lesson focused on the evaluation loop.
