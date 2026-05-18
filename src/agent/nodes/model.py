from collections.abc import Mapping

from langchain.messages import SystemMessage
from langchain.tools import BaseTool
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from typing import Any

from agent.config import LLMEndpointConfig, get_config, get_config_path, jinja_env, require_llm_endpoint_config
from agent.utils.model import build_model as _build_chat_model
from agent.core.runnable_config import runnable_config_bool
from agent.core.state import AgentState
from agent.services.mcp_lifespan import MCPLifespanManager
from agent.tools import internal_tool_names
from agent.tools.core_memory import core_memory_get
from agent.tools.skills_tools import get_installed_skill_summaries


class ConfiguredModel:
    def __init__(
        self,
        tools: list[BaseTool] | None = None,
        mcp_manager: MCPLifespanManager | None = None,
    ):
        self._tools = list(tools or [])
        self._mcp_manager = mcp_manager
        self._system_prompt_template = jinja_env.get_template("system_prompt.j2")
        self._model: Any | None = None
        self._model_signature: tuple[str, str, str, str] | None = None

    def _build_model(self, endpoint: LLMEndpointConfig):
        return _build_chat_model(endpoint)

    def _get_model(self, endpoint: LLMEndpointConfig | None = None):
        if endpoint is None:
            endpoint = require_llm_endpoint_config(get_config_path(get_config(), "api.agent"), "api.agent")
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

    def _hide_from_subagent(self, tool: BaseTool) -> bool:
        metadata = getattr(tool, "metadata", None)
        if isinstance(metadata, Mapping) and metadata.get("hide_from_subagent") is True:
            return True

        extras = getattr(tool, "extras", None)
        if isinstance(extras, Mapping) and extras.get("hide_from_subagent") is True:
            return True

        return False

    async def invoke_node(
        self,
        state: AgentState,
        runtime: Runtime,
        config: RunnableConfig,
    ) -> AgentState:
        store = runtime.store

        core_memory_entries: list[tuple[str, str]] = []
        if store:
            core_memory_entries = await core_memory_get(store)

        endpoint = require_llm_endpoint_config(get_config_path(get_config(), "api.agent"), "api.agent")
        installed_skills = get_installed_skill_summaries()

        system_prompt = self._system_prompt_template.render(
            core_memory=core_memory_entries,
            installed_skills=installed_skills,
            token_limit=endpoint.max_token_count,
        )
        system_prompt_message = SystemMessage(content=system_prompt)

        model = self._get_model(endpoint)
        mcp_tools: list[BaseTool] = []
        if self._mcp_manager is not None:
            mcp_tools = await self._mcp_manager.get_tools()
        for tool in mcp_tools:
            if tool.name in internal_tool_names:
                raise ValueError(
                    f"MCP tool '{tool.name}' conflicts with an internal tool name"
                )
        tools = self._tools
        if runnable_config_bool(config, "subagent"):
            tools = [
                tool
                for tool in tools
                if not self._hide_from_subagent(tool)
            ]
            mcp_tools = [
                tool
                for tool in mcp_tools
                if not self._hide_from_subagent(tool)
            ]
        if tools or mcp_tools:
            model = model.bind_tools(tools + mcp_tools)
        response = await model.ainvoke([system_prompt_message] + state["messages"])
        return {"messages": [response]} if response else state
