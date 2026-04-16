from langchain.messages import SystemMessage
from langchain.tools import BaseTool
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_qwq import ChatQwen
from langgraph.runtime import Runtime
from typing import Any

from agent.config import LLMEndpointConfig, get_config, jinja_env
from agent.core.state import AgentState
from agent.tools.core_memory import core_memory_get


class ConfiguredModel:
    def __init__(self, tools: list[BaseTool] | None = None):
        self._tools = tools
        self._system_prompt_template = jinja_env.get_template("system_prompt.j2")
        self._model: Any | None = None
        self._model_signature: tuple[str, str, str, str] | None = None

    def _build_model(self, endpoint: LLMEndpointConfig):
        if endpoint.type == "OpenAI":
            model = ChatOpenAI(
                model=endpoint.model,
                api_key=endpoint.api_key,
                base_url=endpoint.base_url,
            )
        elif endpoint.type == "Qwen":
            model = ChatQwen(
                model=endpoint.model,
                api_key=endpoint.api_key,
                base_url=endpoint.base_url,
            )
        elif endpoint.type == "Anthropic":
            model = ChatAnthropic(
                model=endpoint.model,
                api_key=endpoint.api_key,
                base_url=endpoint.base_url,
            )
        else:
            raise ValueError(f"Model type {endpoint.type} not supported")

        if self._tools:
            model = model.bind_tools(self._tools)
        return model

    def _get_model(self):
        endpoint = get_config().api.agent
        signature = (
            endpoint.type,
            endpoint.model,
            endpoint.api_key,
            endpoint.base_url,
        )
        if self._model is None or self._model_signature != signature:
            self._model = self._build_model(endpoint)
            self._model_signature = signature
        return self._model

    async def invoke_node(self, state: AgentState, runtime: Runtime) -> AgentState:
        store = runtime.store

        core_memory_entries: list[tuple[str, str]] = []
        if store:
            core_memory_entries = await core_memory_get(store)

        endpoint = get_config().api.agent
        system_prompt = self._system_prompt_template.render(
            core_memory=core_memory_entries,
            token_limit=endpoint.max_token_count,
        )
        system_prompt_message = SystemMessage(content=system_prompt)

        model = self._get_model()
        response = await model.ainvoke([system_prompt_message] + state["messages"])
        return {"messages": [response]} if response else state
