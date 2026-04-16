import logging
import re

from langchain.messages import AIMessage, HumanMessage, SystemMessage
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_qwq import ChatQwen

from agent.config import LLMEndpointConfig, get_config

log = logging.getLogger(__name__)
DEFAULT_CONVERSATION_TITLE = "New Conversation"


class ConversationTitleGenerator:
    def should_generate_title(self, title: str | None) -> bool:
        normalized = (title or "").strip()
        return not normalized or normalized == DEFAULT_CONVERSATION_TITLE

    def build_title_input(self, user_message: str) -> str:
        parts: list[str] = []
        normalized_user_message = user_message.strip()
        if normalized_user_message:
            parts.append(f"User message:\n{normalized_user_message}")
        return "\n\n".join(parts)

    def _build_model(self, endpoint: LLMEndpointConfig):
        if endpoint.type == "OpenAI":
            default_headers = None
            if endpoint == get_config().api.utility:
                default_headers = {
                    "User-Agent": "OpenCrab/1.0 utility-title-generator"
                }
            return ChatOpenAI(
                model=endpoint.model,
                api_key=endpoint.api_key,
                base_url=endpoint.base_url,
                default_headers=default_headers,
            )
        if endpoint.type == "Anthropic":
            return ChatAnthropic(
                model=endpoint.model,
                api_key=endpoint.api_key,
                base_url=endpoint.base_url,
            )
        if endpoint.type == "Qwen":
            return ChatQwen(
                model=endpoint.model,
                api_key=endpoint.api_key,
                base_url=endpoint.base_url,
            )
        raise ValueError(f"Unsupported title model type: {endpoint.type}")

    def _extract_text(self, message: AIMessage) -> str:
        content = message.content
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            return str(content)

        parts: list[str] = []
        for chunk in content:
            if isinstance(chunk, str):
                parts.append(chunk)
                continue
            if not isinstance(chunk, dict):
                continue
            text = chunk.get("text")
            if text:
                parts.append(str(text))
        return "".join(parts)

    def _normalize_title(self, title: str) -> str:
        normalized = title.strip().replace("\r", " ").replace("\n", " ")
        normalized = re.sub(r"\s+", " ", normalized)
        normalized = normalized.strip("\"'“”‘’`")
        normalized = re.sub(r"^(title|标题)\s*[:：]\s*", "", normalized, flags=re.IGNORECASE)
        normalized = normalized.strip()
        if len(normalized) > 60:
            normalized = normalized[:60].rstrip(" ,.;:!?，。；：！？、")
        return normalized

    async def _generate_with_endpoint(self, endpoint: LLMEndpointConfig, conversation_text: str) -> str | None:
        model = self._build_model(endpoint)
        response = await model.ainvoke([
            SystemMessage(
                content=(
                    "You generate concise, normalized conversation titles in Chinese.\n"
                    "Summarize the user's intent or topic instead of copying surface wording.\n"
                    "Return exactly one short title only.\n"
                    "Do not add quotes, prefixes, markdown, punctuation-only wrappers, or explanations.\n"
                    "Prefer a noun phrase or verb-object phrase, usually 4 to 8 Chinese characters.\n"
                    "Avoid repeating greetings, filler, or single-word paraphrases from the chat.\n"
                    "Examples:\n"
                    "User says: hi -> 打招呼\n"
                    "User says: hello -> 打招呼\n"
                    "User says: 帮我写周报 -> 撰写周报\n"
                    "User says: 解释一下 SSE 是什么 -> 了解SSE概念\n"
                    "User says: 帮我修复登录 bug -> 修复登录问题"
                )
            ),
            HumanMessage(
                content=(
                    "Generate one normalized Chinese title for this conversation.\n"
                    "Focus on the main task or intent, not on conversational wording.\n\n"
                    f"{conversation_text}"
                )
            ),
        ])
        if not isinstance(response, AIMessage):
            return None
        title = self._normalize_title(self._extract_text(response))
        return title or None

    async def generate(self, conversation_text: str) -> str | None:
        normalized_text = conversation_text.strip()
        if not normalized_text:
            return None

        endpoint = get_config().api.utility
        try:
            return await self._generate_with_endpoint(endpoint, normalized_text)
        except Exception as exc:
            log.warning(
                "Failed to generate conversation title with %s/%s: %s",
                endpoint.type,
                endpoint.model,
                exc,
            )
            return None
