"""LangGraph tool list and ToolNode for the compiled graph."""
from typing import TypedDict

from langgraph.prebuilt import ToolNode


class ToolArtifact(TypedDict):
    break_agent_loop: bool

from .bb import get_calendar_events
from .code_interpreter import python_interpreter
from .core_memory import core_memory_insert
from .tis import get_schedule, query_available_courses
from .routine_tools import (
    add_routine_event,
    delete_routine_events,
    get_my_routine_events,
    update_routine_event,
)
from .task_tools import (
    create_scheduled_task,
    delete_scheduled_task,
    read_scheduled_task_run_logs,
    read_scheduled_tasks,
    run_scheduled_task,
    update_scheduled_task,
)

from .core_memory import core_memory_insert
from .web_tools import webfetch, websearch
from .code_interpreter import python_interpreter

tools = [
    get_calendar_events,
    get_schedule,
    query_available_courses,
    get_my_routine_events,
    add_routine_event,
    update_routine_event,
    delete_routine_events,
    create_scheduled_task,
    read_scheduled_tasks,
    read_scheduled_task_run_logs,
    run_scheduled_task,
    update_scheduled_task,
    delete_scheduled_task,
    core_memory_insert,
    python_interpreter,
    webfetch,
    websearch,
]

tool_node = ToolNode(tools=tools)
