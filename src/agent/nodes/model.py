from collections.abc import Callable

from langchain.messages import SystemMessage
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_qwq import ChatQwen
from langchain.tools import BaseTool
from langgraph.runtime import Runtime

from agent.config import ApiEndpointConfig, AppConfig, jinja_env
from agent.core.state import AgentState
from agent.tools.core_memory import core_memory_get
from typing import Dict, Type

class Model:
    _models: Dict[str, Type["Model"]] = {}
    def __init_subclass__(cls, name, **kwargs):
        super().__init_subclass__(**kwargs)
        Model._models[name] = cls
    
    def __init__(self):
        pass
    
    @staticmethod
    def get(name : str, **kwargs) -> "Model":
        model_cls = Model._models.get(name)
        if not model_cls:
            raise ValueError(f"Model {name} not found")
        return model_cls(**kwargs)
    
    async def invoke_node(self, state: AgentState, runtime: Runtime) -> AgentState:
        raise NotImplementedError("invoke_node must be implemented by subclasses")

    @staticmethod
    def _make_chat_model(endpoint: ApiEndpointConfig, tools: list[BaseTool] | None):
        if endpoint.type == "OpenAI":
            m = ChatOpenAI(
                model=endpoint.model,
                api_key=endpoint.api_key,
                base_url=endpoint.base_url,
            )
        elif endpoint.type == "Qwen":
            m = ChatQwen(
                model=endpoint.model,
                api_key=endpoint.api_key,
                base_url=endpoint.base_url,
            )
        elif endpoint.type == "Anthropic":
            m = ChatAnthropic(
                model=endpoint.model,
                api_key=endpoint.api_key,
                base_url=endpoint.base_url,
            )
        else:
            raise ValueError(f"Unsupported agent model type: {endpoint.type}")
        if tools:
            m = m.bind_tools(tools)
        return m


class AgentModel(Model, name="Agent"):
    """Reads ``api.agent`` from ``get_config()`` each turn (hot-reload friendly)."""

    def __init__(
        self,
        get_config: Callable[[], AppConfig],
        tools: list[BaseTool] | None = None,
    ):
        self._get_config = get_config
        self._tools = tools
        self.system_prompt_template = jinja_env.get_template("system_prompt.j2")

    async def invoke_node(self, state: AgentState, runtime: Runtime) -> AgentState:
        endpoint = self._get_config().api.agent
        model = self._make_chat_model(endpoint, self._tools)

        store = runtime.store
        core_memory_entries: list[tuple[str, str]] = []
        if store:
            core_memory_entries = await core_memory_get(store)

        system_prompt = self.system_prompt_template.render(core_memory=core_memory_entries)
        system_prompt_message = SystemMessage(content=system_prompt)

        response = await model.ainvoke([system_prompt_message] + state["messages"])
        return {"messages": [response]} if response else state
