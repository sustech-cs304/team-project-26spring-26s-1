import asyncio
import logging
import os
from pathlib import Path
import shutil
import sys
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
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
from agent.credentials_store import EnvVaultAccessError, read_credential_values
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
_ENV_VAR_CREDENTIAL_TYPE = "env_var"
RISK_LEVEL_VALUES = {
    "Low": 0,
    "Medium": 1,
    "High": 2,
}
RiskLevel = Literal["Low", "Medium", "High"]


@dataclass(frozen=True)
class CodeInterpreterLanguage:
    name: str
    aliases: tuple[str, ...]
    file_suffix: str
    test: Callable[[], bool]
    run: Callable[[str], Sequence[str]]


def _python_available() -> bool:
    return bool(sys.executable)


def _python_command(script_path: str) -> Sequence[str]:
    return [sys.executable, script_path]


def _bash_available() -> bool:
    return shutil.which("bash") is not None


def _bash_command(script_path: str) -> Sequence[str]:
    return ["bash", script_path]


def _javascript_available() -> bool:
    return shutil.which("node") is not None


def _javascript_command(script_path: str) -> Sequence[str]:
    return ["node", script_path]


def _powershell_executable() -> str | None:
    return shutil.which("pwsh") or shutil.which("powershell")


def _powershell_available() -> bool:
    return _powershell_executable() is not None


def _powershell_command(script_path: str) -> Sequence[str]:
    executable = _powershell_executable() or "pwsh"
    return [
        executable,
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        script_path,
    ]


CODE_INTERPRETER_LANGUAGES: tuple[CodeInterpreterLanguage, ...] = (
    CodeInterpreterLanguage(
        name="python",
        aliases=("python", "python3", "py"),
        file_suffix=".py",
        test=_python_available,
        run=_python_command,
    ),
    CodeInterpreterLanguage(
        name="bash",
        aliases=("bash", "sh", "shell"),
        file_suffix=".sh",
        test=_bash_available,
        run=_bash_command,
    ),
    CodeInterpreterLanguage(
        name="javascript",
        aliases=("javascript", "js", "node", "nodejs"),
        file_suffix=".js",
        test=_javascript_available,
        run=_javascript_command,
    ),
    CodeInterpreterLanguage(
        name="powershell",
        aliases=("powershell", "pwsh", "ps", "ps1"),
        file_suffix=".ps1",
        test=_powershell_available,
        run=_powershell_command,
    ),
)
SUPPORTED_LANGUAGE_ALIASES = {
    alias: language.name
    for language in CODE_INTERPRETER_LANGUAGES
    for alias in language.aliases
}
LANGUAGE_FILE_SUFFIXES = {
    language.name: language.file_suffix
    for language in CODE_INTERPRETER_LANGUAGES
}
SUPPORTED_LANGUAGES = tuple(language.name for language in CODE_INTERPRETER_LANGUAGES)


class CodeInterpreterInput(BaseModel):
    code: str = Field(min_length=1, description="Code to execute.")
    language: str | None = Field(
        default=None,
        min_length=1,
        description=(
            "Execution language. Defaults to python when omitted."
        ),
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


def _language_by_alias() -> dict[str, CodeInterpreterLanguage]:
    languages: dict[str, CodeInterpreterLanguage] = {}
    for language in CODE_INTERPRETER_LANGUAGES:
        languages[language.name.lower()] = language
        for alias in language.aliases:
            languages[alias.lower()] = language
    return languages


def _resolve_language(language: str) -> CodeInterpreterLanguage | None:
    return _language_by_alias().get(language.strip().lower())


def _normalize_language(language: str) -> str | None:
    resolved = _resolve_language(language)
    return resolved.name if resolved is not None else None


def _build_command(language: str, script_path: str) -> list[str]:
    resolved = _resolve_language(language)
    if resolved is None:
        raise ValueError(f"Unsupported language: {language}")
    return list(resolved.run(script_path))


def _is_language_available(language: CodeInterpreterLanguage) -> bool:
    try:
        return language.test()
    except OSError:
        log.debug("Language availability check failed for %s", language.name, exc_info=True)
        return False


def discover_available_languages() -> tuple[CodeInterpreterLanguage, ...]:
    return tuple(
        language
        for language in CODE_INTERPRETER_LANGUAGES
        if _is_language_available(language)
    )


def _format_language(language: CodeInterpreterLanguage) -> str:
    aliases = ", ".join(language.aliases)
    return f"{language.name} (aliases: {aliases})"


def _format_languages(languages: Sequence[CodeInterpreterLanguage]) -> str:
    if not languages:
        return "none detected"
    return "; ".join(_format_language(language) for language in languages)


def _build_language_field_description(languages: Sequence[CodeInterpreterLanguage]) -> str:
    return (
        "Execution language. "
        f"Available values on this platform: {_format_languages(languages)}. "
        "Defaults to python when omitted."
    )


def _build_tool_description(languages: Sequence[CodeInterpreterLanguage]) -> str:
    return (
        "Execute code in a supported interpreter after a security review. "
        f"Available languages on this platform: {_format_languages(languages)}. "
        "Defaults to python when language is omitted."
    )


def discover_languages_and_update_tool_description() -> tuple[CodeInterpreterLanguage, ...]:
    languages = discover_available_languages()
    description = _build_tool_description(languages)
    code_interpreter.description = description
    CodeInterpreterInput.model_fields["language"].description = _build_language_field_description(languages)
    return languages


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


async def _build_execution_env() -> dict[str, str]:
    global_vars = await read_credential_values(_ENV_VAR_CREDENTIAL_TYPE)
    env = dict(os.environ)
    env.update(global_vars)
    return env


async def _run_script(code: str, language: str, timeout_s: float) -> str:
    language_runtime = _resolve_language(language)
    if language_runtime is None:
        return _truncate_output(f"Unable to execute unsupported language: {language}")
    if not _is_language_available(language_runtime):
        return _truncate_output(
            f"Unable to execute {language_runtime.name} code because no interpreter is available on this platform."
        )

    workspace_dir = WORKSPACE_DIR.resolve()
    workspace_dir.mkdir(parents=True, exist_ok=True)

    script_path = ""
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=language_runtime.file_suffix,
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
        try:
            env = await _build_execution_env()
        except EnvVaultAccessError as exc:
            return _truncate_output(f"Unable to execute {language} code because the credential store is unavailable: {exc}")

        command = list(language_runtime.run(str(script_path_obj)))
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(workspace_dir),
                env=env,
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
    resolved_language = _resolve_language(selected_language)
    if resolved_language is None:
        supported = _format_languages(discover_available_languages())
        return (
            f"Error: Unsupported language '{selected_language}'. Available languages: {supported}.",
            {"break_agent_loop": False},
        )
    if not _is_language_available(resolved_language):
        available = _format_languages(discover_available_languages())
        return (
            f"Error: Language '{resolved_language.name}' is supported but not available on this platform. "
            f"Available languages: {available}.",
            {"break_agent_loop": False},
        )

    resolved_timeout_s = timeout_s if timeout_s is not None else interpreter_config.default_timeout_s
    state = cast(CodeInterpreterGraph, {
        "code": code,
        "language": resolved_language.name,
        "timeout_s": resolved_timeout_s,
        "tool_call_id": runtime.tool_call_id or "",
    })
    result = await _graph.ainvoke(state, config=runtime.config)
    artifact: ToolArtifact = {
        "break_agent_loop": bool(result.get("break_agent_loop", False))
    }
    return result["execution_result"], artifact


discover_languages_and_update_tool_description()
