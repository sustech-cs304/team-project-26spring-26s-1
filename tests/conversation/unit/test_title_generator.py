from langchain.messages import AIMessage

from agent.api.title_generator import ConversationTitleGenerator


def test_title_generator_extracts_bare_ai_message_content():
    generator = ConversationTitleGenerator()

    assert generator._extract_text(AIMessage(content=" Weekly Report ")) == " Weekly Report "


def test_title_generator_extracts_text_chunks_from_ai_message_content():
    generator = ConversationTitleGenerator()
    response = AIMessage(content=[{"type": "text", "text": "Fix Login Issue"}])

    assert generator._extract_text(response) == "Fix Login Issue"
