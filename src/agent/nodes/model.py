from langchain_qwq import ChatQwen
from langchain_openai import ChatOpenAI
from agent.core.state import AgentState
from langchain.messages import SystemMessage
from agent.config import jinja_env
from langgraph.runtime import Runtime
from agent.tools.core_memory import core_memory_get
from langchain.tools import BaseTool
from typing import Dict, Type

class Model:
    _models: Dict[str, Type["Model"]] = {}
    def __init_subclass__(cls, name, **kwargs):
        super().__init_subclass__(**kwargs)
        Model._models[name] = cls
    
    def __init__(self):
        pass
    
    @staticmethod
    def get(name : str, **kwargs) -> "Model":
        model_cls = Model._models.get(name)
        if not model_cls:
            raise ValueError(f"Model {name} not found")
        return model_cls(**kwargs)
    
    async def invoke_node(self, state: AgentState, runtime: Runtime) -> AgentState:
        raise NotImplementedError("invoke_node must be implemented by subclasses")

class OpenAIModel(Model, name="OpenAI"):
    def __init__(self, model: str, api_key: str, base_url: str, tools: list[BaseTool] | None = None):
        self.model = ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url
        )
        if tools:
            self.model = self.model.bind_tools(tools)
            
        self.system_prompt_template = jinja_env.get_template("system_prompt.j2")
        
    async def invoke_node(self, state: AgentState, runtime: Runtime) -> AgentState:    
        store = runtime.store
         
        core_memory_entries : list[tuple[str, str]]= []
        if store:
            core_memory_entries = await core_memory_get(store)
        
        system_prompt = self.system_prompt_template.render(core_memory=core_memory_entries)
        system_prompt_message = SystemMessage(content=system_prompt)
            
        response = await self.model.ainvoke([system_prompt_message] + state["messages"])
        return {"messages": [response]} if response else state

class QwenModel(Model, name="Qwen"):
    def __init__(self, model: str, api_key: str, base_url: str, tools: list[BaseTool] | None = None):
        self.model = ChatQwen(
            model=model,
            api_key=api_key,
            base_url=base_url
        )
        if tools:
            self.model = self.model.bind_tools(tools)
            
        self.system_prompt_template = jinja_env.get_template("system_prompt.j2")
        
    async def invoke_node(self, state: AgentState, runtime: Runtime) -> AgentState:    
        store = runtime.store
        
        core_memory_entries : list[tuple[str, str]]= []
        if store:
            core_memory_entries = await core_memory_get(store)
        
        system_prompt = self.system_prompt_template.render(core_memory=core_memory_entries)
        system_prompt_message = SystemMessage(content=system_prompt)
            
        response = await self.model.ainvoke([system_prompt_message] + state["messages"])
        return {"messages": [response]} if response else state
    