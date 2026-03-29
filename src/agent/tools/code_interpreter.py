from langgraph.func import entrypoint, task
from enum import Enum
from langchain_core.language_models import BaseLanguageModel
from langchain_core.prompts import ChatPromptTemplate
from langgraph.types import interrupt, Overwrite
from langchain.tools import tool, ToolRuntime
from langchain_core.runnables import RunnableConfig
from typing import Annotated, Literal, TypedDict
from langgraph.graph import StateGraph, START, END
import operator

REVIEW_PROMPT_TEMPLATE = ChatPromptTemplate.from_messages([
    ("system", "You are a security expert. Review the following code for potential security vulnerabilities and provide feedback."),
    ("human", "{code}")
])

class ReviewOutput(TypedDict):
    review: str
    threat_level: Literal["Low", "Medium", "High"]
    
class CodeInterpreterGraph(TypedDict):
    code: str
    review_output: ReviewOutput
    user_feedback: Literal["Accept", "Reject"]
    execution_result: str
    
async def security_review_node(state: CodeInterpreterGraph, config: RunnableConfig):
    language_model = config["configurable"]["__utility_model"]
    chain = REVIEW_PROMPT_TEMPLATE | language_model.with_structured_output(ReviewOutput)
    review = await chain.ainvoke({"code": state["code"]})
    return {
        "review_output": review
    }
    
async def feedback_node(state: CodeInterpreterGraph, config: RunnableConfig):
    user_input = interrupt(f"Agent wants to execute the following code:\n{state['code']}\nRisk assessment: {state['review_output']['threat_level']}\n")
    feedback = "Accept" if user_input.lower() in {"accept", "yes", "y"} else "Reject"
    return {
        "user_feedback": feedback
    }
    
async def execution_node(state: CodeInterpreterGraph, config: RunnableConfig):
    if state["user_feedback"] == "Reject":
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
async def python_interpreter(code: str, config: RunnableConfig) -> str:
    """Interprets and executes python code"""
    state = {
        "code": code
    }
    result = await _graph.ainvoke(state, config=config)
    return result["execution_result"]