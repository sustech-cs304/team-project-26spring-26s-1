import asyncio
import logging
from pathlib import Path
import sys
import tempfile
from typing import Any, Literal, NotRequired, TypedDict, cast

from langchain.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolRuntime
from langgraph.types import interrupt

from agent.core.state import ResumePayload
from agent.config import get_config
from agent.tools import ToolArtifact

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
    ("human", "{code}")
])

WORKSPACE_DIR = Path("./workspace")
MAX_EXECUTION_OUTPUT_CHARS = 12000

class ReviewOutput(TypedDict):
    review: str
    threat_level: Literal["Low", "Medium", "High"]

class CodeInterpreterGraph(TypedDict):
    code: str
    tool_call_id: str
    review_output: ReviewOutput
    user_feedback: Literal["approve", "skip", "reject"]
    execution_result: str
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


async def _run_python_script(code: str) -> str:
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

    script_path = ""
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        dir=WORKSPACE_DIR,
        delete=False,
        encoding="utf-8",
    ) as script_file:
        script_file.write(code)
        script_path = script_file.name

    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            script_path,
            cwd=WORKSPACE_DIR,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await process.communicate()
    finally:
        Path(script_path).unlink(missing_ok=True)

    output = stdout.decode("utf-8", errors="replace") if stdout else ""
    if process.returncode != 0:
        output = f"Process exited with code {process.returncode}\n{output}"

    if not output:
        output = "(no output)"

    return _truncate_output(output)

async def security_review_node(state: CodeInterpreterGraph):
    utility_config = get_config().api.utility
    language_model = ChatOpenAI(
        model=utility_config.model,
        api_key=cast(Any, utility_config.api_key),
        base_url=utility_config.base_url
    )
    structured_llm = REVIEW_PROMPT_TEMPLATE | language_model.with_structured_output(ReviewOutput)
    review = await structured_llm.ainvoke({"code": state["code"]})
    return {
        "review_output": review
    }
    
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

    execution_result = await _run_python_script(state["code"])
    return {
        "execution_result": execution_result
    }

_workflow = StateGraph(CodeInterpreterGraph)
_workflow.add_node("security_review", security_review_node)
_workflow.add_node("feedback", feedback_node)
_workflow.add_node("execution", execution_node)

_workflow.add_edge(START, "security_review")
_workflow.add_edge("security_review", "feedback")
_workflow.add_edge("feedback", "execution")
_workflow.add_edge("execution", END)

_graph = _workflow.compile()

@tool(response_format="content_and_artifact")
async def python_interpreter(code: str, config: RunnableConfig, runtime: ToolRuntime) -> tuple[str, ToolArtifact]:
    """Interprets and executes python code"""
    state = cast(CodeInterpreterGraph, {
        "code": code,
        "tool_call_id": runtime.tool_call_id
    })
    result = await _graph.ainvoke(state, config=config)
    artifact: ToolArtifact = {
        "break_agent_loop": bool(result.get("break_agent_loop", False))
    }
    return result["execution_result"], artifact
