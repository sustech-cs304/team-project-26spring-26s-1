from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from typing import Literal, cast

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
    transport: str
    url: str | None = None
    token: str | None = None
    command: str | None = None
    args: tuple[str, ...] = ()
    env: tuple[tuple[str, str], ...] = ()
    cwd: str | None = None


def _connection_signature(config: MCPConfig) -> _MCPConnectionSignature:
    if config.transport == "stdio":
        return _MCPConnectionSignature(
            transport="stdio",
            command=config.command,
            args=tuple(config.args),
            env=tuple(sorted(config.env.items())),
            cwd=config.cwd,
        )
    return _MCPConnectionSignature(
        transport="http",
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
        self._status: Literal["starting", "running", "failed"] = "starting"

        loop = asyncio.get_running_loop()
        ready: asyncio.Future[ClientSession] = loop.create_future()
        close_event = asyncio.Event()
        self._session_ready = ready
        self._session_close_event = close_event
        self._session_task = asyncio.create_task(
            self._run_persistent_session(ready, close_event),
            name=f"mcp-session:{self.name}",
        )

    @property
    def status(self) -> str:
        return self._status

    @staticmethod
    def _build_connection(config: MCPConfig) -> Connection:
        if config.transport == "stdio":
            connection: dict[str, object] = {
                "transport": "stdio",
                "command": config.command,
                "args": config.args,
            }
            if config.env:
                connection["env"] = config.env
            if config.cwd:
                connection["cwd"] = config.cwd
            return cast("Connection", connection)

        connection = {
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
                self._status = "running"
                if not ready.done():
                    ready.set_result(session)
                await close_event.wait()
        except asyncio.CancelledError:
            if not ready.done():
                ready.cancel()
            raise
        except Exception as exc:
            self._status = "failed"
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
                self._status = "starting"
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
        self._mcp_config: dict[str, MCPConfig] = dict(get_config_path(current_config, "mcp"))
        self._servers: dict[str, _ManagedMCPServer] = {}

    async def start(self) -> None:
        """Connect to all enabled MCP servers."""
        async with self._lock:
            for name, config in self._mcp_config.items():
                if not config.enabled:
                    continue
                if name in self._servers:
                    continue
                try:
                    require_mcp_config(config, f"mcp.{name}")
                except ConfigMissingError as exc:
                    log.warning("Skipping MCP server: %s", exc)
                    continue
                self._servers[name] = _ManagedMCPServer(name, config)

    def get_statuses(self) -> list[dict[str, str]]:
        """Return status of all configured MCP servers."""
        result: list[dict[str, str]] = []
        for name, config in self._mcp_config.items():
            if not config.enabled:
                result.append({"name": name, "status": "disabled"})
                continue
            server = self._servers.get(name)
            if server is None:
                result.append({"name": name, "status": "starting"})
            else:
                result.append({"name": name, "status": server.status})
        return result

    async def get_tools(self) -> list[BaseTool]:
        async with self._lock:
            server_names = list(self._servers.keys())
            servers = [self._servers[name] for name in server_names]

        if not servers:
            return []

        tools_by_server = await asyncio.gather(
            *(server.get_tools() for server in servers)
        )

        combined_tools: list[BaseTool] = []
        tool_owner: dict[str, str] = {}
        for name, tools in zip(server_names, tools_by_server, strict=False):
            for tool in tools:
                if tool.name in tool_owner:
                    owner = tool_owner[tool.name]
                    raise ValueError(
                        f"MCP tool name '{tool.name}' is duplicated across servers "
                        f"'{owner}' and '{name}'"
                    )
                tool_owner[tool.name] = name
                combined_tools.append(tool)

        return combined_tools

    async def get_tool(self, tool_name: str) -> BaseTool | None:
        for tool in await self.get_tools():
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
            next_mcp_config: dict[str, MCPConfig] = dict(get_config_path(new_config, "mcp"))
            self._mcp_config = next_mcp_config

            for server_name, server in list(self._servers.items()):
                config = next_mcp_config.get(server_name)
                should_remove = False
                if config is None:
                    should_remove = True
                elif not config.enabled:
                    should_remove = True
                else:
                    try:
                        config = require_mcp_config(config, f"mcp.{server_name}")
                    except ConfigMissingError:
                        should_remove = True
                    else:
                        if server.signature != _connection_signature(config):
                            should_remove = True
                if should_remove:
                    stale_servers.append(self._servers.pop(server_name))

            for server_name, config in next_mcp_config.items():
                if server_name in self._servers:
                    continue
                if not config.enabled:
                    continue
                try:
                    require_mcp_config(config, f"mcp.{server_name}")
                except ConfigMissingError:
                    continue
                self._servers[server_name] = _ManagedMCPServer(server_name, config)

        for server in stale_servers:
            await server.aclose()

    async def aclose(self) -> None:
        async with self._lock:
            servers = list(self._servers.values())
            self._servers.clear()

        for server in servers:
            await server.aclose()
