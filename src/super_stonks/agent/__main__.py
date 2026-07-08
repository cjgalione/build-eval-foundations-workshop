import click
import braintrust
from dotenv import load_dotenv

load_dotenv()

from .config import init_braintrust_logger

bt_logger = init_braintrust_logger()

from .agent import graph

@click.command()
def main() -> None:
    """Interactive stock chat agent powered by GPT-4o and real market data."""
    click.echo("Stock Chat Agent — ask me about any stock! (type 'quit' to exit)")
    click.echo("-" * 60)

    # One span wraps the entire multiturn session
    with braintrust.start_span(name="stonks-sessions", span_attributes={"type": "task"}) as session:
        history: list[dict] = []
        turns = 0

        while True:
            try:
                user_input = input("\nYou: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if user_input.lower() in ("quit", "exit", "q"):
                break
            if not user_input:
                continue

            history.append({"role": "user", "content": user_input})

            with braintrust.start_span(name=f"turn_{turns}", span_attributes={"type": "task"}) as turn_span:
                result = graph.invoke({"messages": history})
                history = result["messages"]
                reply = next(
                    (m["content"] for m in reversed(history) if m.get("role") == "assistant" and m.get("content")),
                    "(no response)",
                )
                turn_span.log(input=user_input, output=reply)
                braintrust.flush()
            turns += 1

            print(f"\nAssistant: {reply}")

        session.log(
            input={"session": "stock-chat"},
            output={"turns": turns},
            metadata={"total_messages": len(history)},
        )


if __name__ == "__main__":
    main()
