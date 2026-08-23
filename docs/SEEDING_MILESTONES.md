# Presenter Topics preflight

This document replaces the historical implementation checklist. It is only for the
presenter-only Topics demonstration; attendees do not depend on seeded traffic.

```bash
export BRAINTRUST_DEFAULT_PROJECT="<presenter-topics-project>"
make prepare
```

`make prepare` enables Topics, sends 10 smoke traces, then sends 990 additional traces
for 1,000 total. Before the workshop, confirm all of the following in the presenter
project:

- the price tool remains disabled;
- a current-price cluster is visible after Topics has processed the seed;
- representative traces show price questions without `get_stock_performance` spans;
- the presenter has one recorded baseline and one recorded fixed eval as a fallback.

The attendee flow intentionally uses separate fresh projects and the starter dataset in
`workshop_assets/price-gap-baseline.jsonl`.
