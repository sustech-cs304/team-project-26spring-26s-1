import asyncio
from types import SimpleNamespace
from typing import Any, cast

import pytest
from langchain.messages import AIMessage, HumanMessage

import agent.nodes.model as model_module
from agent.api.onebot.hub import OneBotHub
from agent.config import config, get_config, patch_config
from agent.nodes.model import ConfiguredModel


@pytest.fixture(autouse=True)
def restore_runtime_config():
    snapshot = get_config().model_dump()
    yield
    patch_config(snapshot)


def test_patch_config_replaces_live_config_object():
    original_config = get_config()
    original_onebot = original_config.onebot
    original_notification = original_config.notification

    patched = patch_config(
        {
            "onebot": {"command_name": "#patched"},
            "notification": {"app_name": "Patched App"},
        }
    )

    current_config = get_config()
    assert patched is current_config
    assert current_config is not original_config
    assert current_config.onebot is not original_onebot
    assert current_config.notification is not original_notification
    assert current_config.onebot.command_name == "#patched"
    assert current_config.notification.app_name == "Patched App"
    assert original_onebot.command_name != "#patched"
    assert original_notification.app_name != "Patched App"


def test_config_proxy_tracks_latest_runtime_config():
    patch_config({"onebot": {"command_name": "#proxy-test"}})

    assert config.onebot.command_name == "#proxy-test"


def test_onebot_hub_reads_live_runtime_config():
    hub = OneBotHub(cast(Any, None), None, cast(Any, None))

    patch_config(
        {
            "onebot": {
                "command_name": "#first",
                "superuser_id": "7",
                "access_token": "token-a",
            }
        }
    )
    assert hub.command_name == "first"
    assert hub._command_usage("help") == "#first help"
    assert hub._is_superuser({"user_id": 7}) is True
    assert hub._is_authorized(SimpleNamespace(headers={"authorization": "Bearer token-a"})) is True

    patch_config(
        {
            "onebot": {
                "command_name": "#second",
                "superuser_id": "11",
                "access_token": "token-b",
            }
        }
    )
    assert hub.command_name == "second"
    assert hub._command_usage("help") == "#second help"
    assert hub._is_superuser({"user_id": 11}) is True
    assert hub._is_authorized(SimpleNamespace(headers={"authorization": "Bearer token-b"})) is True
    assert hub._is_authorized(SimpleNamespace(headers={"authorization": "Bearer token-a"})) is False


class _FakeChatClient:
    def __init__(self, backend: str, calls: list[dict[str, Any]], **kwargs: Any):
        self._entry = {"backend": backend, **kwargs}
        calls.append(self._entry)

    def bind_tools(self, tools):
        self._entry["tools"] = list(tools)
        return self

    async def ainvoke(self, messages):
        self._entry["messages"] = messages
        return AIMessage(content=f"{self._entry['backend']}:{self._entry['model']}")


def _fake_chat_factory(backend: str, calls: list[dict[str, Any]]):
    def factory(**kwargs: Any):
        return _FakeChatClient(backend, calls, **kwargs)

    return factory


def test_configured_model_uses_latest_agent_config(monkeypatch: pytest.MonkeyPatch):
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(model_module, "ChatAnthropic", _fake_chat_factory("Anthropic", calls))
    monkeypatch.setattr(model_module, "ChatOpenAI", _fake_chat_factory("OpenAI", calls))
    monkeypatch.setattr(model_module, "ChatQwen", _fake_chat_factory("Qwen", calls))

    model = ConfiguredModel()
    runtime = SimpleNamespace(store=None)
    state = {"messages": [HumanMessage(content="hello")]}

    patch_config(
        {
            "api": {
                "agent": {
                    "type": "Anthropic",
                    "model": "anthropic-model",
                    "base_url": "https://anthropic.example",
                    "api_key": "anthropic-key",
                }
            }
        }
    )
    asyncio.run(model.invoke_node(state, runtime))
    assert calls[-1]["backend"] == "Anthropic"
    assert calls[-1]["model"] == "anthropic-model"
    assert calls[-1]["base_url"] == "https://anthropic.example"
    assert calls[-1]["api_key"] == "anthropic-key"

    patch_config(
        {
            "api": {
                "agent": {
                    "type": "OpenAI",
                    "model": "openai-model",
                    "base_url": "https://openai.example",
                    "api_key": "openai-key",
                }
            }
        }
    )
    asyncio.run(model.invoke_node(state, runtime))
    assert calls[-1]["backend"] == "OpenAI"
    assert calls[-1]["model"] == "openai-model"
    assert calls[-1]["base_url"] == "https://openai.example"
    assert calls[-1]["api_key"] == "openai-key"
