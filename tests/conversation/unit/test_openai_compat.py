from agent.config import LLMEndpointConfig
from agent.nodes import model as model_module
from agent.nodes.model import ConfiguredModel
from agent.openai_compat import openai_default_headers


def test_openai_default_headers_include_component_name():
    assert openai_default_headers("agent-chat") == {
        "User-Agent": "OpenCrab/1.0 agent-chat"
    }


def test_configured_model_passes_user_agent_to_openai(monkeypatch):
    captured = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(model_module, "ChatOpenAI", FakeChatOpenAI)

    ConfiguredModel()._build_model(
        LLMEndpointConfig(
            type="OpenAI",
            model="test-model",
            api_key="test-key",
            base_url="http://localhost",
        )
    )

    assert captured["default_headers"] == {
        "User-Agent": "OpenCrab/1.0 agent-chat"
    }
