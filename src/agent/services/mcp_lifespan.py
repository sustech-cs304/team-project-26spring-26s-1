from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from typing import Sequence, cast

from langchain.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.sessions import Connection
from langchain_mcp_adapters.tools import load_mcp_tools
from mcp.client.session import ClientSession

from agent.config import AppConfig, ConfigMissingError, MCPConfig, get_config, get_config_path, require_mcp_config

log = logging.getLogger(__name__)


def _normalize_token(token: str | None) -> str | None:
    if not token:
        return None
    return token


@dataclass(frozen=True)
class _MCPConnectionSignature:
    url: str
    token: str | None


def _connection_signature(config: MCPConfig) -> _MCPConnectionSignature:
    return _MCPConnectionSignature(
        url=config.url,
        token=_normalize_token(config.token),
    )


class _ManagedMCPServer:
    def __init__(self, name: str, config: MCPConfig):
        self.name = name
        self.signature = _connection_signature(config)
        self._client = MultiServerMCPClient(
            {name: self._build_connection(config)}
        )
        self._lock = asyncio.Lock()
        self._session: ClientSession | None = None
        self._tools: list[BaseTool] | None = None
        self._tools_task: asyncio.Task[list[BaseTool]] | None = None
        self._session_ready: asyncio.Future[ClientSession] | None = None
        self._session_task: asyncio.Task[None] | None = None
        self._session_close_event: asyncio.Event | None = None

    @staticmethod
    def _build_connection(config: MCPConfig) -> Connection:
        connection: dict[str, object] = {
            "transport": "http",
            "url": config.url,
        }
        token = _normalize_token(config.token)
        if token is not None:
            connection["headers"] = {
                "Authorization": f"Bearer {token}",
            }
        return cast("Connection", connection)

    async def _run_persistent_session(
        self,
        ready: asyncio.Future[ClientSession],
        close_event: asyncio.Event,
    ) -> None:
        try:
            async with self._client.session(self.name) as session:
                self._session = session
                if not ready.done():
                    ready.set_result(session)
                await close_event.wait()
        except asyncio.CancelledError:
            if not ready.done():
                ready.cancel()
            raise
        except Exception as exc:
            if not ready.done():
                ready.set_exception(exc)
            else:
                log.exception(
                    "Persistent MCP session failed: server=%s error=%s",
                    self.name,
                    exc,
                )
        finally:
            self._session = None
            async with self._lock:
                if self._session_ready is ready:
                    self._session_ready = None
                if self._session_close_event is close_event:
                    self._session_close_event = None
                if self._session_task is asyncio.current_task():
                    self._session_task = None

    async def _ensure_session(self) -> ClientSession:
        async with self._lock:
            if self._session is not None:
                return self._session

            if self._session_ready is None:
                loop = asyncio.get_running_loop()
                ready: asyncio.Future[ClientSession] = loop.create_future()
                close_event = asyncio.Event()
                self._session_ready = ready
                self._session_close_event = close_event
                self._session_task = asyncio.create_task(
                    self._run_persistent_session(ready, close_event),
                    name=f"mcp-session:{self.name}",
                )

            ready = self._session_ready

        if ready is None:
            raise RuntimeError(f"Failed to initialize MCP session for '{self.name}'")

        return await asyncio.shield(ready)

    async def _load_tools(self) -> list[BaseTool]:
        session = await self._ensure_session()
        return await load_mcp_tools(
            session,
            server_name=self.name,
        )

    async def get_tools(self) -> list[BaseTool]:
        async with self._lock:
            if self._tools is not None:
                return list(self._tools)

            if self._tools_task is None:
                self._tools_task = asyncio.create_task(
                    self._load_tools(),
                    name=f"mcp-tools:{self.name}",
                )
            tools_task = self._tools_task

        try:
            tools = await asyncio.shield(tools_task)
        except Exception:
            async with self._lock:
                if self._tools_task is tools_task:
                    self._tools_task = None
            await self.aclose()
            raise

        async with self._lock:
            if self._tools is None:
                self._tools = tools
            if self._tools_task is tools_task:
                self._tools_task = None
            return list(self._tools)

    def _close_locked(self) -> tuple[asyncio.Task[list[BaseTool]] | None, asyncio.Task[None] | None]:
        self._tools = None
        self._session = None
        tools_task = self._tools_task
        session_task = self._session_task
        self._tools_task = None
        close_event = self._session_close_event
        self._session_ready = None
        self._session_close_event = None
        self._session_task = None
        if close_event is not None:
            close_event.set()
        return tools_task, session_task

    async def aclose(self) -> None:
        async with self._lock:
            tools_task, session_task = self._close_locked()

        if tools_task is not None:
            try:
                await asyncio.shield(tools_task)
            except Exception:
                pass

        if session_task is not None:
            try:
                await asyncio.shield(session_task)
            except Exception:
                pass


class MCPLifespanManager:
    def __init__(self, config: AppConfig | None = None):
        current_config = get_config() if config is None else config
        self._lock = asyncio.Lock()
        self._mcp_config = dict(get_config_path(current_config, "mcp"))
        self._servers: dict[str, _ManagedMCPServer] = {}

    async def _get_server(self, name: str) -> _ManagedMCPServer | None:
        stale_server: _ManagedMCPServer | None = None
        async with self._lock:
            config = self._mcp_config.get(name)
            if config is None:
                return None
            try:
                config = require_mcp_config(config, f"mcp.{name}")
            except ConfigMissingError as exc:
                log.warning("Skipping MCP server because config is incomplete: %s", exc)
                return None

            current_server = self._servers.get(name)
            if current_server is not None and current_server.signature == _connection_signature(config):
                return current_server

            if current_server is not None:
                stale_server = self._servers.pop(name)

            current_server = _ManagedMCPServer(name, config)
            self._servers[name] = current_server

        if stale_server is not None:
            await stale_server.aclose()

        return current_server

    async def get_tools(self, enabled_server_names: Sequence[str]) -> list[BaseTool]:
        unique_server_names = list(dict.fromkeys(enabled_server_names))
        server_entries = []
        for server_name in unique_server_names:
            server = await self._get_server(server_name)
            if server is not None:
                server_entries.append((server_name, server))
        if not server_entries:
            return []

        tools_by_server = await asyncio.gather(
            *(server.get_tools() for _, server in server_entries)
        )

        combined_tools: list[BaseTool] = []
        tool_owner: dict[str, str] = {}
        for (server_name, _), tools in zip(server_entries, tools_by_server, strict=False):
            for tool in tools:
                if tool.name in tool_owner:
                    owner = tool_owner[tool.name]
                    raise ValueError(
                        f"MCP tool name '{tool.name}' is duplicated across servers "
                        f"'{owner}' and '{server_name}'"
                    )
                tool_owner[tool.name] = server_name
                combined_tools.append(tool)

        return combined_tools

    async def get_tool(
        self,
        enabled_server_names: Sequence[str],
        tool_name: str,
    ) -> BaseTool | None:
        for tool in await self.get_tools(enabled_server_names):
            if tool.name == tool_name:
                return tool
        return None

    async def apply_config(
        self,
        _old_config: AppConfig,
        new_config: AppConfig,
    ) -> None:
        stale_servers: list[_ManagedMCPServer] = []
        async with self._lock:
            next_mcp_config = dict(get_config_path(new_config, "mcp"))
            self._mcp_config = next_mcp_config
            for server_name, server in list(self._servers.items()):
                config = next_mcp_config.get(server_name)
                if config is None:
                    stale_servers.append(self._servers.pop(server_name))
                    continue
                try:
                    config = require_mcp_config(config, f"mcp.{server_name}")
                except ConfigMissingError:
                    stale_servers.append(self._servers.pop(server_name))
                    continue
                if server.signature != _connection_signature(config):
                    stale_servers.append(self._servers.pop(server_name))

        for server in stale_servers:
            await server.aclose()

    async def aclose(self) -> None:
        async with self._lock:
            servers = list(self._servers.values())
            self._servers.clear()

        for server in servers:
            await server.aclose()
