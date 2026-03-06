from .config import Config
from .loop import AgentLoop, ReasoningEvent, TextDeltaEvent, ToolCallStartEvent, ToolResultEvent, DoneEvent
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
import asyncio


async def _run() -> None:
    config = Config.from_yaml()
    loop = await AgentLoop.create(config=config)
    messages = loop.new_context()
    session = PromptSession(history=InMemoryHistory())

    try:
        while True:
            while True:
                try:
                    user_input = await session.prompt_async("User: ")
                except KeyboardInterrupt:
                    # Ctrl-C mid-line: clear the line and let the user try again
                    print()
                    continue
                if user_input.lower() in ["exit", "reset"]:
                    break

                reasoning_started = False
                async for event in loop.step(messages, user_input):
                    if isinstance(event, ReasoningEvent):
                        if not reasoning_started:
                            print("--- Reasoning ---")
                            reasoning_started = True
                        print(event.delta, end="", flush=True)
                    elif isinstance(event, TextDeltaEvent):
                        if reasoning_started:
                            print("\n--- End Reasoning ---")
                            reasoning_started = False
                        print(event.delta, end="", flush=True)
                    elif isinstance(event, ToolCallStartEvent):
                        if reasoning_started:
                            print("\n--- End Reasoning ---")
                            reasoning_started = False
                        print(f"\nCalling tool: {event.name} with arguments {event.arguments}")
                    elif isinstance(event, ToolResultEvent):
                        print(f"Tool response: {event.result}")
                    elif isinstance(event, DoneEvent):
                        if reasoning_started:
                            print("\n--- End Reasoning ---")
                        messages = event.messages
                        print()  # newline after streamed text

            if user_input.lower() == "exit":
                print("Exiting.")
                await loop.save_memory(messages)
                break
            elif user_input.lower() == "reset":
                print("Resetting the conversation.")
                await loop.save_memory(messages)
                messages = loop.new_context()
                continue

    except KeyboardInterrupt:
        # Ctrl-C at the prompt: treat as a clean exit
        print("\nInterrupted. Exiting.")

    finally:
        await loop.shutdown()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
