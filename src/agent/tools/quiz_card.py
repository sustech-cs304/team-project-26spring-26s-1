from __future__ import annotations

from typing import Literal, TypedDict

from langchain.tools import tool
from pydantic import BaseModel, Field, model_validator


class ToolArtifact(TypedDict):
    break_agent_loop: bool


class QuizQuestion(BaseModel):
    title: str = Field(min_length=1)
    type: Literal["single", "multiple"]
    choices: list[str] = Field(min_length=2)
    correct_choice_indexes: list[int] = Field(min_length=1)
    explanation: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_question(self) -> "QuizQuestion":
        if any(not choice.strip() for choice in self.choices):
            raise ValueError("choices must be non-empty strings")

        if len(set(self.correct_choice_indexes)) != len(self.correct_choice_indexes):
            raise ValueError("correct_choice_indexes must not contain duplicates")

        if any(index < 0 or index >= len(self.choices) for index in self.correct_choice_indexes):
            raise ValueError("correct_choice_indexes must be valid choice indexes")

        if self.type == "single" and len(self.correct_choice_indexes) != 1:
            raise ValueError("single questions must have exactly one correct choice index")

        return self


class QuizCardInput(BaseModel):
    questions: list[QuizQuestion] = Field(min_length=1)


def _build_result(questions: list[QuizQuestion]) -> tuple[str, ToolArtifact]:
    return (
        f"Prepared 1 quiz card(s) with {len(questions)} quiz item(s).",
        {"break_agent_loop": True},
    )


@tool(args_schema=QuizCardInput, response_format="content_and_artifact")
async def quiz_card(questions: list[QuizQuestion]) -> tuple[str, ToolArtifact]:
    """Render a quiz card for the frontend.

    Call this tool directly when the user wants interactive quiz cards,
    quiz questions, or a quiz-card-style response. If the user provides
    constraints about `card_id`, `cards`, `options`, or `answers`, treat
    those as output requirements and still call this tool instead of
    explaining the schema.

    Input schema:
    - Use a single top-level field named `questions`
    - `questions` must be an array
    - Each question item must include:
      - `title`
      - `type`: `single` or `multiple`
      - `choices`: array of option text strings
      - `correct_choice_indexes`: array of correct option indexes
      - `explanation`: explanation string

    Important:
    - Do not generate `card_id`, `options`, or `answers`
    - Provide `questions` as plain JSON-compatible values, not as a manually serialized string
    - Do not wrap `questions` in Python-style object literals or single-quoted pseudo-JSON
    - Make sure each question's title, correct answers, and explanation are consistent
    - The explanation must match the correct answers and must end with `模型生成，可能有误。`
    - Do not output normal explanatory text before or after calling this tool
    """
    return _build_result(questions)
