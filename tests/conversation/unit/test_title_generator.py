from agent.api.title_generator import ConversationTitleGenerator


def test_title_generator_extracts_bare_string_response():
    generator = ConversationTitleGenerator()

    assert generator._extract_openai_response_text(" 撰写周报 ") == " 撰写周报 "


def test_title_generator_extracts_chat_completion_response():
    generator = ConversationTitleGenerator()
    response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "修复登录问题"}],
                }
            }
        ]
    }

    assert generator._extract_openai_response_text(response) == "修复登录问题"
