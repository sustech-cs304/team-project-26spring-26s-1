import asyncio
import logging
from pathlib import Path
import sys
import tempfile
from typing import Any, Literal, NotRequired, TypedDict, cast

from langchain.tools import tool
from langchain_core.runnables import RunnableConfig
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolRuntime
from langgraph.types import interrupt
from pydantic import BaseModel, Field

from agent.core.state import ResumePayload
from agent.core.runnable_config import runnable_config_bool
from agent.config import (
    ConfigMissingError,
    get_config,
    get_config_path,
    require_config_fields,
    require_llm_endpoint_config,
)
from agent.tools import ToolArtifact
from agent.utils.model import build_model

log = logging.getLogger(__name__)
REVIEW_PROMPT_TEMPLATE = ChatPromptTemplate.from_messages([
    ("system", """
You are a security expert. Review the following code for potential security vulnerabilities and provide a concise feedback.
Provide JSON output like this:
{{
    "review": "Your review text here",
    "threat_level": "Low"  // or "Medium", or "High"    
}}
     """.strip()),
    ("human", "Language: {language}\n\nCode:\n{code}")
])

WORKSPACE_DIR = Path("./workspace")
MAX_EXECUTION_OUTPUT_CHARS = 12000
SUPPORTED_LANGUAGE_ALIASES = {
    "py": "python",
    "python": "python",
    "python3": "python",
    "bash": "bash",
    "sh": "bash",
    "shell": "bash",
    "js": "javascript",
    "javascript": "javascript",
    "node": "javascript",
    "nodejs": "javascript",
}
LANGUAGE_FILE_SUFFIXES = {
    "python": ".py",
    "bash": ".sh",
    "javascript": ".js",
}
SUPPORTED_LANGUAGES = tuple(LANGUAGE_FILE_SUFFIXES)
RISK_LEVEL_VALUES = {
    "Low": 0,
    "Medium": 1,
    "High": 2,
}
RiskLevel = Literal["Low", "Medium", "High"]


class CodeInterpreterInput(BaseModel):
    code: str = Field(min_length=1, description="Code to execute.")
    language: str | None = Field(
        default=None,
        min_length=1,
        description="Execution language. Supported values: python, bash, javascript. Defaults to python when omitted.",
    )
    timeout_s: float | None = Field(
        default=None,
        gt=0,
        description="Optional per-call timeout override in seconds. Defaults to config when omitted.",
    )


class ReviewOutput(TypedDict):
    review: str
    threat_level: RiskLevel


class CodeInterpreterGraph(TypedDict):
    code: str
    language: str
    timeout_s: float
    tool_call_id: str
    review_output: NotRequired[ReviewOutput]
    user_feedback: NotRequired[Literal["approve", "skip", "reject"]]
    execution_result: NotRequired[str]
    break_agent_loop: NotRequired[bool]


def _truncate_output(output: str) -> str:
    if len(output) <= MAX_EXECUTION_OUTPUT_CHARS:
        return output

    head_size = MAX_EXECUTION_OUTPUT_CHARS // 2
    tail_size = MAX_EXECUTION_OUTPUT_CHARS - head_size
    truncated_count = len(output) - MAX_EXECUTION_OUTPUT_CHARS
    return (
        output[:head_size]
        + f"\n\n...[output truncated: {truncated_count} chars omitted]...\n\n"
        + output[-tail_size:]
    )


def _normalize_language(language: str) -> str | None:
    return SUPPORTED_LANGUAGE_ALIASES.get(language.strip().lower())


def _build_command(language: str, script_path: str) -> list[str]:
    if language == "python":
        return [sys.executable, script_path]
    if language == "bash":
        return ["bash", script_path]
    if language == "javascript":
        return ["node", script_path]
    raise ValueError(f"Unsupported language: {language}")


def _is_risk_level_allowed(threat_level: RiskLevel, max_risk_level: RiskLevel) -> bool:
    return RISK_LEVEL_VALUES[threat_level] <= RISK_LEVEL_VALUES[max_risk_level]


async def _read_output(stream: asyncio.StreamReader | None) -> bytes:
    if stream is None:
        return b""
    chunks: list[bytes] = []
    while True:
        chunk = await stream.read(4096)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


async def _settle_returncode(
    process: asyncio.subprocess.Process,
    *,
    attempts: int = 5,
    delay_s: float = 0.01,
) -> int | None:
    for _ in range(attempts):
        if process.returncode is not None:
            return process.returncode
        await asyncio.sleep(delay_s)
    return process.returncode


async def _run_script(code: str, language: str, timeout_s: float) -> str:
    workspace_dir = WORKSPACE_DIR.resolve()
    workspace_dir.mkdir(parents=True, exist_ok=True)

    script_path = ""
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=LANGUAGE_FILE_SUFFIXES[language],
        dir=workspace_dir,
        delete=False,
        encoding="utf-8",
    ) as script_file:
        script_file.write(code)
        script_path = script_file.name

    script_path_obj = Path(script_path).resolve()
    process: asyncio.subprocess.Process | None = None
    stdout: bytes | None = None
    timed_out = False
    try:
        command = _build_command(language, str(script_path_obj))
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(workspace_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
        except FileNotFoundError:
            return _truncate_output(
                f"Unable to execute {language} code because interpreter '{command[0]}' was not found."
            )
        except OSError as exc:
            return _truncate_output(f"Unable to execute {language} code: {exc}")

        output_task = asyncio.create_task(_read_output(process.stdout))
        done, _ = await asyncio.wait({output_task}, timeout=timeout_s)
        if output_task in done:
            stdout = output_task.result()
        else:
            timed_out = True
            if process.returncode is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
            stdout = await output_task

        returncode = process.returncode if timed_out else await _settle_returncode(process)
    finally:
        script_path_obj.unlink(missing_ok=True)

    output = stdout.decode("utf-8", errors="replace") if stdout else ""
    if timed_out:
        if output and not output.endswith("\n"):
            output += "\n"
        output += f"Process killed after exceeding timeout of {timeout_s:g}s."
    elif returncode not in (None, 0):
        output = f"Process exited with code {returncode}\n{output}"

    if not output:
        output = "(no output)"

    return _truncate_output(output)


async def security_review_node(state: CodeInterpreterGraph, config: RunnableConfig):
    app_config = get_config()
    utility_config = require_llm_endpoint_config(
        get_config_path(app_config, "api.utility"),
        "api.utility",
    )
    interpreter_config = require_config_fields(
        get_config_path(app_config, "code_interpreter"),
        "code_interpreter",
        ("auto_approve_max_risk_level",),
    )
    language_model = build_model(utility_config)
    structured_llm = REVIEW_PROMPT_TEMPLATE | language_model.with_structured_output(ReviewOutput, method="json_schema")
    review = await structured_llm.ainvoke({"language": state["language"], "code": state["code"]})
    result: dict[str, Any] = {
        "review_output": review
    }
    if _is_risk_level_allowed(
        review["threat_level"],
        interpreter_config.auto_approve_max_risk_level,
    ):
        result["user_feedback"] = "approve"
    elif runnable_config_bool(config, "non_interactive"):
        result["user_feedback"] = "skip"
    return result


def auto_approval_route(state: CodeInterpreterGraph) -> Literal["feedback", "execution"]:
    if state.get("user_feedback") in {"approve", "skip", "reject"}:
        return "execution"
    return "feedback"


async def feedback_node(state: CodeInterpreterGraph):
    resume_payload: ResumePayload = interrupt({
        "message": f"Agent wants to execute code. Risk assessment: {state['review_output']['threat_level']}.",
        "options": ["approve", "skip", "reject"],
        "tool_call_id": state["tool_call_id"]
    })
    user_input = resume_payload["user_input"]

    normalized = ""
    if isinstance(user_input, dict):
        normalized = str(user_input.get("action", "")).strip().lower()
    else:
        normalized = str(user_input).strip().lower()
        
    log.info("User feedback received: %s", normalized)

    if normalized in {"approve", "approved", "accept", "yes", "y"}:
        feedback: Literal["approve", "skip", "reject"] = "approve"
    elif normalized in {"reject", "r"}:
        feedback = "reject"
    else:
        feedback = "skip"

    return {
        "user_feedback": feedback
    }
    
async def execution_node(state: CodeInterpreterGraph):
    if state["user_feedback"] == "skip":
        return {
            "execution_result": "Execution rejected by user."
        }

    if state["user_feedback"] == "reject":
        return {
            "execution_result": "Execution rejected by user.",
            "break_agent_loop": True,
        }

    execution_result = await _run_script(
        state["code"],
        language=state["language"],
        timeout_s=state["timeout_s"],
    )
    return {
        "execution_result": execution_result
    }

_workflow = StateGraph(CodeInterpreterGraph)
_workflow.add_node("security_review", security_review_node)
_workflow.add_node("feedback", feedback_node)
_workflow.add_node("execution", execution_node)

_workflow.add_edge(START, "security_review")
_workflow.add_conditional_edges(
    "security_review",
    auto_approval_route,
    {
        "feedback": "feedback",
        "execution": "execution",
    },
)
_workflow.add_edge("feedback", "execution")
_workflow.add_edge("execution", END)

_graph = _workflow.compile()

@tool("code_interpreter", args_schema=CodeInterpreterInput, response_format="content_and_artifact")
async def code_interpreter(
    runtime: ToolRuntime,
    code: str,
    language: str | None = None,
    timeout_s: float | None = None,
) -> tuple[str, ToolArtifact]:
    """Execute code in a supported interpreter after a security review."""
    app_config = get_config()
    try:
        require_llm_endpoint_config(
            get_config_path(app_config, "api.utility"),
            "api.utility",
        )
        interpreter_config = require_config_fields(
            get_config_path(app_config, "code_interpreter"),
            "code_interpreter",
            ("default_timeout_s",),
        )
    except ConfigMissingError as exc:
        return f"Error: {exc}", {"break_agent_loop": False}

    selected_language = language or "python"
    resolved_language = _normalize_language(selected_language)
    if resolved_language is None:
        supported = ", ".join(SUPPORTED_LANGUAGES)
        return (
            f"Error: Unsupported language '{selected_language}'. Supported languages: {supported}.",
            {"break_agent_loop": False},
        )

    resolved_timeout_s = timeout_s if timeout_s is not None else interpreter_config.default_timeout_s
    state = cast(CodeInterpreterGraph, {
        "code": code,
        "language": resolved_language,
        "timeout_s": resolved_timeout_s,
        "tool_call_id": runtime.tool_call_id or "",
    })
    result = await _graph.ainvoke(state, config=runtime.config)
    artifact: ToolArtifact = {
        "break_agent_loop": bool(result.get("break_agent_loop", False))
    }
    return result["execution_result"], artifact
