from typing import Literal, TypedDict

from langchain.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolRuntime
from langgraph.types import interrupt

from agent.config import config

REVIEW_PROMPT_TEMPLATE = ChatPromptTemplate.from_messages([
    ("system", "You are a security expert. Review the following code for potential security vulnerabilities and provide feedback."),
    ("human", "{code}")
])

class ReviewOutput(TypedDict):
    review: str
    threat_level: Literal["Low", "Medium", "High"]
    
class CodeInterpreterGraph(TypedDict):
    code: str
    tool_call_id: str
    review_output: ReviewOutput
    user_feedback: Literal["Accept", "Reject"]
    execution_result: str
    
async def security_review_node(state: CodeInterpreterGraph):
    utility_config = config.api.utility
    language_model = ChatOpenAI(
        model=utility_config.model,
        api_key=utility_config.api_key,
        base_url=utility_config.base_url
    )
    structured_llm = REVIEW_PROMPT_TEMPLATE | language_model.with_structured_output(ReviewOutput)
    review = await structured_llm.ainvoke({"code": state["code"]})
    return {
        "review_output": review
    }
    
async def feedback_node(state: CodeInterpreterGraph):
    user_input = interrupt({
        "message": f"Agent wants to execute code. Risk assessment: {state['review_output']['threat_level']}\n",
        "tool_call_id": state["tool_call_id"]
    })
    feedback = "Accept" if user_input.lower() in {"accept", "yes", "y"} else "Reject"
    return {
        "user_feedback": feedback
    }
    
async def execution_node(state: CodeInterpreterGraph):
    if state["user_feedback"] == "reject":
        return {
            "execution_result": "Execution rejected by user."
        }
    
    
    
    return {
        "execution_result": "*placeholder*"
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

@tool
async def python_interpreter(code: str, config: RunnableConfig, runtime: ToolRuntime) -> str:
    """Interprets and executes python code"""
    state = {
        "code": code,
        "tool_call_id": runtime.tool_call_id
    }
    result = await _graph.ainvoke(state, config=config)
    return result["execution_result"]