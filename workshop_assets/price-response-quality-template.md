# Price response quality — UI scorer template

Use this as the starting prompt for a Braintrust UI LLM-as-a-judge scorer named
`price_response_quality`. It measures response quality, not whether the value was
actually fetched.

```text
Judge whether the assistant directly and clearly answers this stock-price request.

User request:
{{input}}

Assistant answer:
{{output}}

Give a high score only when the answer is concise, states a concrete current price,
identifies the ticker, and clearly distinguishes a price from investment advice.
Give a low score for a refusal, generic commentary, or a buy/hold/sell verdict that
does not answer the price request.

Before saving, change one criterion to reflect what matters for your agent.
```
