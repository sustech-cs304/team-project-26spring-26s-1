from .mem0 import Mem0
from .core_memory import CoreMemory
from .tools import Tools
from .context_manager import ContextManager
from .rag import KnowledgeBase
from .config import AGENT_MODEL, API_BASE_URL, USER_ID
import openai
import json
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory

def main() -> None:
    tools = Tools()
    core_memory = CoreMemory()
    core_memory.register_tools(tools)

    client = openai.OpenAI(base_url=API_BASE_URL)

    longterm_memory = Mem0(user_id=USER_ID, client=client, model=AGENT_MODEL)
    longterm_memory.register_tools(tools)
    core_memory.register_archive_tool(tools, longterm_memory)

    knowledge_base = KnowledgeBase(client=client)
    knowledge_base.register_tools(tools)

    ctx = ContextManager(core_memory=core_memory, tools=tools, client=client, model=AGENT_MODEL)

    messages = [{"role": "system", "content": ctx.build_system_message()}]
    session = PromptSession(history=InMemoryHistory())

    def call_openai_api(msgs: list[dict]):
        return client.chat.completions.create(
            model=AGENT_MODEL,
            messages=msgs,
            tools=tools.openai_format(),
        )

    while True:
        while True:
            user_input = session.prompt("User: ")
            if user_input.lower() in ["exit", "reset"]:
                break
            messages.append({"role": "user", "content": user_input})

            while True:
                messages[0]["content"] = ctx.build_system_message()
                response = call_openai_api(messages)
                if response.choices[0].message.tool_calls:
                    print(f"Assistant decision: {response.choices[0].message.content}")
                    for tool_call in response.choices[0].message.tool_calls:
                        tool_arguments = json.loads(tool_call.function.arguments)
                        tool_call_str = f"Calling tool: {tool_call.function.name} with arguments {tool_arguments}"
                        tool_response = tools.run_tool(tool_call.function.name, tool_arguments)
                        messages.append({"role": "tool", "content": tool_call_str + ": " + tool_response})
                        print(tool_call_str + ": " + tool_response)
                else:
                    assistant_response = response.choices[0].message.content or ""
                    print(f"Assistant: {assistant_response}")
                    messages.append({"role": "assistant", "content": assistant_response})
                    break

            ctx.run_eviction()
            ctx.run_fold(messages)

        if user_input.lower() == "exit":
            print("Exiting the program.")
            break
        elif user_input.lower() == "reset":
            print("Resetting the conversation.")
            longterm_memory.insert_memory(messages)
            messages = [{"role": "system", "content": ctx.build_system_message()}]
            continue

if __name__ == "__main__":
    main()
