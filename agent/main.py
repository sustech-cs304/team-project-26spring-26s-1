from .loop import AgentLoop
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory


def main() -> None:
    loop = AgentLoop()
    messages = loop.new_context()
    session = PromptSession(history=InMemoryHistory())

    try:
        while True:
            while True:
                try:
                    user_input = session.prompt("User: ")
                except KeyboardInterrupt:
                    # Ctrl-C mid-line: clear the line and let the user try again
                    print()
                    continue
                if user_input.lower() in ["exit", "reset"]:
                    break

                result = loop.step(messages, user_input)
                messages = result.messages

                for tc in result.tool_calls:
                    print(f"Calling tool: {tc.name} with arguments {tc.arguments}")
                    print(f"Tool response: {tc.result}")

                print(f"Assistant: {result.response}")

            if user_input.lower() == "exit":
                print("Exiting.")
                loop.save_memory(messages)
                break
            elif user_input.lower() == "reset":
                print("Resetting the conversation.")
                loop.save_memory(messages)
                messages = loop.new_context()
                continue

    except KeyboardInterrupt:
        # Ctrl-C at the prompt: treat as a clean exit
        print("\nInterrupted. Exiting.")

    finally:
        loop.shutdown()


if __name__ == "__main__":
    main()
