# Build Your Eval Foundations — Super Stonks

A hands-on Braintrust workshop for turning agent behavior into measurable improvement.
The exercise uses **Super Stonks**, a small LangGraph stock assistant with an
intentional current-price gap.

## The workshop loop

1. Observe a traced agent interaction.
2. Turn a failure into a small dataset.
3. Define quality criteria and run a baseline experiment.
4. Close the gap and compare results.
5. See an online score monitor new production traffic.

The default attendee path is UI-first. Loop and a coding agent are optional advanced
paths, not prerequisites. Topics is a presenter-only demonstration on a seeded project;
each attendee creates and owns an isolated project in the workshop org.

## Start here

- Attendees: [Participant guide](docs/PARTICIPANT.md)
- Presenters: [Run-of-show and preflight](docs/WORKSHOP.md)
- Room/setup screen: [Welcome](docs/WELCOME.md)
- Optional code assets: [`workshop_assets/`](workshop_assets)

## Local commands

```bash
make setup
make agent
make help
```

`BRAINTRUST_DEFAULT_PROJECT` is required and should be unique per attendee, for example
`<your-name>-eval-foundations`.

The hidden exercise answer is in [docs/GAP.md](docs/GAP.md): enable the already-written
price tool by uncommenting its two marked blocks. Do not reveal it before the baseline.

## Presenter pre-work

Use a separate presenter project for seeded Topics traffic. `make prepare` enables Topics
and generates 1,000 total traces (10 smoke traces plus 990 full traces). Do not use that
project as an attendee workspace.
