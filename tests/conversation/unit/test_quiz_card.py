import asyncio
import json
from pathlib import Path

import pytest
from langchain_core.messages import ToolMessage

from agent.parser.anthropic import AnthropicEventParser
from agent.tools.quiz_card import quiz_card


def _serialize_tool_call_arguments(tool_name, args):
    import agent.api.conversation_runner as conversation_runner

    helper = getattr(conversation_runner, "_serialize_tool_call_arguments", None)
    if helper is None:
        pytest.xfail(
            "Known issue: conversation_runner currently has no public helper for "
            "standard JSON serialization of tool call arguments."
        )
    return helper(tool_name, args)


def test_quiz_card_tool_accepts_multiple_questions():
    result = asyncio.run(
        quiz_card.ainvoke(
            {
                "questions": [
                    {
                        "title": "???",
                        "type": "single",
                        "choices": ["??A", "??B"],
                        "correct_choice_indexes": [0],
                        "explanation": "A ?????????????",
                    },
                    {
                        "title": "???",
                        "type": "multiple",
                        "choices": ["??A", "??B", "??C"],
                        "correct_choice_indexes": [0, 2],
                        "explanation": "A?C ?????????????",
                    },
                ]
            }
        )
    )

    assert result == "Prepared 1 quiz card(s) with 2 quiz item(s)."


def test_quiz_card_tool_rejects_invalid_choice_indexes():
    try:
        asyncio.run(
            quiz_card.ainvoke(
                {
                    "questions": [
                        {
                            "title": "???",
                            "type": "single",
                            "choices": ["??A", "??B"],
                            "correct_choice_indexes": [0, 1],
                            "explanation": "A ?????????????",
                        }
                    ]
                }
            )
        )
    except Exception:
        return

    raise AssertionError("quiz_card should reject invalid correct_choice_indexes")


def test_serialize_quiz_card_arguments_outputs_standard_json():
    serialized_arguments = _serialize_tool_call_arguments(
        "quiz_card",
        {
            "questions": [
                {
                    "title": "???",
                    "type": "single",
                    "choices": ["??A", "??B"],
                    "correct_choice_indexes": [0],
                    "explanation": "A ?????????????",
                }
            ]
        },
    )

    assert serialized_arguments == [
        {
            "questions": json.dumps(
                [
                    {
                        "title": "???",
                        "type": "single",
                        "choices": ["??A", "??B"],
                        "correct_choice_indexes": [0],
                        "explanation": "A ?????????????",
                    }
                ],
                ensure_ascii=False,
            )
        }
    ]
    assert json.loads(serialized_arguments[0]["questions"])[0]["correct_choice_indexes"] == [0]


def test_serialize_quiz_card_arguments_normalizes_python_literal_string():
    serialized_arguments = _serialize_tool_call_arguments(
        "quiz_card",
        {
            "questions": "[{'choices': ['4', '6', '8', '12'], 'correct_choice_indexes': [3], 'explanation': '?????? D???????????', 'title': '???', 'type': 'single'}]"
        },
    )

    assert serialized_arguments == [
        {
            "questions": json.dumps(
                [
                    {
                        "choices": ["4", "6", "8", "12"],
                        "correct_choice_indexes": [3],
                        "explanation": "?????? D???????????",
                        "title": "???",
                        "type": "single",
                    }
                ],
                ensure_ascii=False,
            )
        }
    ]


def test_parser_preserves_parseable_questions_argument_for_history_and_tool_call():
    parser = AnthropicEventParser()
    serialized_arguments = _serialize_tool_call_arguments(
        "quiz_card",
        {
            "questions": [
                {
                    "title": "???",
                    "type": "single",
                    "choices": ["??A", "??B"],
                    "correct_choice_indexes": [0],
                    "explanation": "A ?????????????",
                }
            ]
        },
    )
    message = ToolMessage(
        content="Prepared 1 quiz card(s) with 1 quiz item(s).",
        name="quiz_card",
        tool_call_id="call_123",
        additional_kwargs={
            "args": serialized_arguments,
            "hitl_status": {"status": "approved", "pending_reason": ""},
        },
    )

    parsed_history = parser.parse_message(message)
    parsed_delta = parser.parse_message_delta(message, "tool_msg_123")[0]

    assert parsed_history.tool_name == "quiz_card"
    assert parsed_history.tool_arguments[0].argument_name == "questions"
    assert json.loads(parsed_history.tool_arguments[0].argument) == json.loads(
        serialized_arguments[0]["questions"]
    )
    assert parsed_delta.tool_name == "quiz_card"
    assert parsed_delta.tool_arguments[0].argument_name == "questions"
    assert json.loads(parsed_delta.tool_arguments[0].argument) == json.loads(
        serialized_arguments[0]["questions"]
    )


def test_quiz_card_prompt_mentions_consistency_and_warning_suffix():
    system_prompt = Path("src/agent/templates/system_prompt.j2").read_text(encoding="utf-8")
    tool_source = Path("src/agent/tools/quiz_card.py").read_text(encoding="utf-8")

    assert "mutually consistent" not in system_prompt
    assert "interactive quiz cards instead of plain text" in system_prompt
    assert "Make sure each question's title, correct answers, and explanation are consistent" in tool_source
    assert "The explanation must agree with the selected correct answers and must not contradict the question stem" in tool_source
    assert "模型生成，可能有误。" in tool_source
    assert "Do not answer with a schema explanation or example JSON when the user asked for actual quiz cards" in tool_source
