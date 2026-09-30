"""裁判模型：只接收隐藏 emoji 和当前问题，只返回 yes 或 no，不带任何解释。"""
from __future__ import annotations

from typing import Any

from .config import ModelInfo
from .emojis import name_of
from .llm import LLMError, structured_call

JUDGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "answer": {"type": "string", "enum": ["yes", "no"]},
    },
    "required": ["answer"],
    "additionalProperties": False,
}

SYSTEM = """You are the impartial answerer in a game of Emoji Twenty Questions.
You know the secret emoji. A guesser (who cannot see it) asks yes/no questions.

You may ONLY answer "yes" or "no". No explanation, no hints, no other words.
Answer based on the common, everyday understanding of what the emoji depicts.
- "yes" if the statement is true of the secret emoji.
- "no" if it is false.
If the question is unclear or not strictly a yes/no question, still pick whichever of yes/no is closer to the truth."""


async def judge_question(judge_model: ModelInfo, secret_emoji: str, question: str) -> tuple[str, dict[str, Any]]:
    """返回 ("yes" | "no", 用量)。"""
    user = (
        f"Secret emoji: {secret_emoji} ({name_of(secret_emoji) or 'no name'})\n"
        f"Question from the guesser: \"{question}\"\n\n"
        "Answer yes or no."
    )
    raw, usage = await structured_call(judge_model, SYSTEM, user, JUDGE_SCHEMA, tool_name="answer_question", max_tokens=1024)
    answer = str(raw.get("answer", "")).strip().lower()
    if answer not in ("yes", "no"):
        raise LLMError(f"裁判返回了无效答案: {raw}")
    return answer, usage
