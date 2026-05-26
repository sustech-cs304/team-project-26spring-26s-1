from __future__ import annotations

import pytest
from langchain_core.tools import StructuredTool

from agent.services.mcp_lifespan import _expose_mcp_tool, _mcp_tool_name


pytestmark = pytest.mark.unit


def _noop_tool() -> str:
    """No-op tool."""
    return "ok"


def test_mcp_tool_name_uses_safe_mcp_prefix():
    assert _mcp_tool_name("browser", "open_tab") == "mcp__browser__open_tab"
    assert _mcp_tool_name("my server", "file.read") == "mcp__my_server__file_read"


def test_expose_mcp_tool_marks_name_description_and_metadata():
    tool = StructuredTool.from_function(
        _noop_tool,
        name="open_tab",
        description="Open a browser tab.",
    )
    tool.metadata = {"existing": True}

    exposed = _expose_mcp_tool(tool, "browser")

    assert exposed is tool
    assert exposed.name == "mcp__browser__open_tab"
    assert exposed.description == "[MCP: browser] Open a browser tab."
    assert exposed.metadata == {
        "existing": True,
        "mcp_server": "browser",
        "mcp_original_name": "open_tab",
    }
