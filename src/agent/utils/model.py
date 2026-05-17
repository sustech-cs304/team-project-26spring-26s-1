from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_qwq import ChatQwen

from agent.config import LLMEndpointConfig


def build_model(endpoint: LLMEndpointConfig):
    headers = endpoint.get_headers()
    if endpoint.type == "OpenAI":
        return ChatOpenAI(
            model=endpoint.model,
            api_key=endpoint.api_key,
            base_url=endpoint.base_url,
            default_headers=headers,
        )
    if endpoint.type == "Qwen":
        return ChatQwen(
            model=endpoint.model,
            api_key=endpoint.api_key,
            base_url=endpoint.base_url,
            default_headers=headers,
        )
    if endpoint.type == "Anthropic":
        return ChatAnthropic(
            model=endpoint.model,
            api_key=endpoint.api_key,
            base_url=endpoint.base_url,
            max_tokens_to_sample=100_000,
            default_headers=headers,
        )
    raise ValueError(f"Model type {endpoint.type} not supported")
