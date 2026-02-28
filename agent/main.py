from .mem0 import Mem0
from .core_memory import CoreMemory
from .tools import Tools
from .context_manager import ContextManager
from .rag import KnowledgeBase
from .skills import SkillsStore
from .code_runner import CodeRunner
from .config import (
    AGENT_MODEL,
    AGENT_API_BASE_URL, AGENT_API_KEY,
    UTILITY_MODEL, UTILITY_API_BASE_URL, UTILITY_API_KEY,
    EMBED_API_BASE_URL, EMBED_API_KEY,
    AGENT_QDRANT_PATH,
    USER_ID,
)
import openai
import json
from qdrant_client import QdrantClient
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory


def _shutdown(
    longterm_memory: Mem0,
    messages: list,
    code_runner: CodeRunner,
    agent_qdrant: QdrantClient,
) -> None:
    """Explicit teardown: flush memory then close all qdrant handles.

    Called from the finally block so it always runs, even on KeyboardInterrupt
    or an unexpected exception. Closing the qdrant clients here — while all
    library modules are still alive — avoids the crash that occurs when Python's
    GC triggers QdrantClient.__del__ during interpreter teardown after modules
    have already been nulled out.
    """
    try:
        longterm_memory.insert_memory(messages)
    except Exception as exc:
        print(f"[Shutdown] Warning: could not save session memory: {exc}")
    try:
        code_runner.cleanup()
    except Exception:
        pass
    try:
        agent_qdrant.close()
    except Exception:
        pass


def main() -> None:
    tools = Tools()
    core_memory = CoreMemory()
    core_memory.register_tools(tools)

    agent_client   = openai.OpenAI(base_url=AGENT_API_BASE_URL,   api_key=AGENT_API_KEY)
    utility_client = openai.OpenAI(base_url=UTILITY_API_BASE_URL, api_key=UTILITY_API_KEY)
    embed_client   = openai.OpenAI(base_url=EMBED_API_BASE_URL,   api_key=EMBED_API_KEY)

    longterm_memory = Mem0(user_id=USER_ID, client=utility_client, model=UTILITY_MODEL)
    longterm_memory.register_tools(tools)
    core_memory.register_archive_tool(tools, longterm_memory)

    AGENT_QDRANT_PATH.mkdir(parents=True, exist_ok=True)
    agent_qdrant = QdrantClient(path=str(AGENT_QDRANT_PATH))

    knowledge_base = KnowledgeBase(client=embed_client, qdrant=agent_qdrant)
    knowledge_base.register_tools(tools)

    skills_store = SkillsStore(client=embed_client, qdrant=agent_qdrant)
    skills_store.register_tools(tools)

    code_runner = CodeRunner(client=utility_client)
    code_runner.register_tools(tools)

    ctx = ContextManager(core_memory=core_memory, tools=tools, client=agent_client, model=AGENT_MODEL)

    messages = [{"role": "system", "content": ctx.build_system_message()}]
    session = PromptSession(history=InMemoryHistory())

    def call_openai_api(msgs: list[dict]):
        return agent_client.chat.completions.create(
            model=AGENT_MODEL,
            messages=msgs,
            tools=tools.openai_format(),
        )

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
                messages.append({"role": "user", "content": user_input})

                while True:
                    messages[0]["content"] = ctx.build_system_message()
                    response = call_openai_api(messages)
                    if response.choices[0].message.tool_calls:
                        print(f"Assistant: {response.choices[0].message.content}")
                        messages.append(response.choices[0].message.model_dump())
                        for tool_call in response.choices[0].message.tool_calls:
                            tool_arguments = json.loads(tool_call.function.arguments)
                            tool_call_str = f"Calling tool: {tool_call.function.name} with arguments {tool_arguments}"
                            print(tool_call_str)
                            tool_response = tools.run_tool(tool_call.function.name, tool_arguments)
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": tool_call_str + ": " + tool_response
                            })
                            print(f"Tool response: {tool_response}")
                    else:
                        assistant_response = response.choices[0].message.content or ""
                        print(f"Assistant: {assistant_response}")
                        messages.append(response.choices[0].message.model_dump())
                        break

                ctx.run_eviction()
                ctx.run_fold(messages)

            if user_input.lower() == "exit":
                print("Exiting.")
                longterm_memory.insert_memory(messages)
                break
            elif user_input.lower() == "reset":
                print("Resetting the conversation.")
                longterm_memory.insert_memory(messages)
                messages = [{"role": "system", "content": ctx.build_system_message()}]
                continue

    except KeyboardInterrupt:
        # Ctrl-C at the prompt: treat as a clean exit
        print("\nInterrupted. Exiting.")

    finally:
        # Always runs — whether we exited normally, via Ctrl-C, or due to an
        # unexpected exception. Flushes memory and closes qdrant clients while
        # the interpreter is still in a fully valid state.
        _shutdown(longterm_memory, messages, code_runner, agent_qdrant)


if __name__ == "__main__":
    main()
