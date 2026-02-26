from typing import Callable

class Tools:
    """
    A collection of tools that the agent can use.
    """
    def __init__(self):
        self.tools : dict[str, tuple[dict,Callable[[dict],str]]] = {}
        
    def add_tool(self, schema: dict, func: Callable[[dict], str]):
        """
        Add a tool to the collection.
        """
        self.tools[schema["name"]] = (schema, func)
        
    def openai_format(self) -> list[dict]:
        """
        Format the tools for OpenAI's API.
        """
        return [{
            "type": "function",
            "function": schema
        } for schema, _ in self.tools.values()]
        
    def run_tool(self, tool_name: str, params: dict) -> str:
        """
        Run a tool by name with the given parameters.
        """
        if tool_name not in self.tools:
            raise ValueError(f"Tool {tool_name} not found.")
        _, func = self.tools[tool_name]
        return func(params)