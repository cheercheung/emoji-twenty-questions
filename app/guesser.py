"""猜测模型：只看规则 + 候选集 + 历史，绝不接触隐藏答案。"""
from __future__ import annotations

from typing import Any

from . import config
from .config import ModelInfo
from .emojis import candidate_list_text, is_candidate, normalize
from .llm import LLMError, structured_call

GUESS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["ask", "guess"]},
        "question": {
            "type": "string",
            "description": "The yes/no question when action=ask; empty string otherwise.",
        },
        "guess": {
            "type": "string",
            "description": "A single emoji from the candidate list when action=guess; empty string otherwise.",
        },
    },
    "required": ["action", "question", "guess"],
    "additionalProperties": False,
}

ANSWER_LABEL = {"yes": "YES", "no": "NO"}


def build_system_prompt(max_turns: int, language: str) -> str:
    return f"""You are playing Emoji Twenty Questions. A secret emoji has been chosen from the candidate list below. Your job is to identify it.

RULES
- Each turn you take exactly ONE action:
  - "ask": ask ONE question that can be answered with yes or no.
  - "guess": name ONE emoji from the candidate list.
- Every action, whether ask or guess, uses up one turn. You have {max_turns} turns in total.
- The game ends when you guess correctly or when the turns run out.
- The answerer only sees your question, not your reasoning, and can ONLY reply "yes" or "no" with no explanation. Keep questions short, concrete, and unambiguous.
- Write your questions in {language}.
- Only guess when you are confident, or when turns are nearly exhausted. A wrong guess wastes a turn.
- Your guess MUST be one emoji copied exactly from the candidate list.

STRATEGY
- Use early questions to split the remaining candidates roughly in half (category, living/non-living, edible, man-made, color, etc.).
- The answerer does NOT see the candidate list. Ask about real-world properties of the thing depicted (is it alive, edible, man-made, used for music, bigger than a person...), never about the list itself, its order, or its groupings.
- Track which candidates remain consistent with all answers so far.
- Never repeat a question you already asked, and NEVER guess an emoji you already guessed wrong.
- If every remaining candidate has been ruled out, one earlier answer was probably based on a different everyday interpretation than yours. Revisit the least certain answers and ask a fresh, concrete question instead of guessing again.

CANDIDATE LIST
{candidate_list_text()}
"""


def build_user_prompt(history: list[dict], turns_used: int, max_turns: int) -> str:
    lines: list[str] = []
    if not history:
        lines.append("No questions have been asked yet. This is turn 1.")
    else:
        lines.append("Transcript so far:")
        for h in history:
            if h["action"] == "ask":
                lines.append(f'Turn {h["turn"]} - You asked: "{h["text"]}" -> Answer: {ANSWER_LABEL.get(h["answer"], h["answer"])}')
            else:
                verdict = "CORRECT" if h.get("correct") else "WRONG"
                extra = "" if h.get("inCandidates", True) else " (that emoji is NOT in the candidate list!)"
                lines.append(f'Turn {h["turn"]} - You guessed: {h["text"]} -> {verdict}{extra}')
    remaining = max_turns - turns_used
    lines.append("")
    lines.append(f"Turns used: {turns_used}/{max_turns}. Turns remaining: {remaining}.")
    if remaining <= 1:
        lines.append("THIS IS YOUR LAST TURN. You MUST use action=\"guess\" now and pick the single most likely emoji. Asking a question now means you lose.")
    elif remaining <= 3:
        lines.append("Very few turns left. Strongly consider guessing.")
    lines.append("Decide your next action.")
    return "\n".join(lines)


async def next_action(
    model: ModelInfo, history: list[dict], turns_used: int, max_turns: int, language: str | None = None
) -> dict[str, Any]:
    """返回 {"action": "ask"|"guess", "text": str, "usage": dict}。

    不要求模型输出思路：让模型解释推理过程会触发 Anthropic 的 reasoning_extraction 拦截。
    """
    raw, usage = await structured_call(
        model,
        system=build_system_prompt(max_turns, language or config.QUESTION_LANGUAGE),
        user=build_user_prompt(history, turns_used, max_turns),
        schema=GUESS_SCHEMA,
        tool_name="take_turn",
    )
    action = str(raw.get("action", "")).strip().lower()
    question = str(raw.get("question", "")).strip()
    guess = str(raw.get("guess", "")).strip()

    if action == "guess" or (action != "ask" and guess and not question):
        if not guess:
            raise LLMError("模型选择 guess 但没有给出 emoji")
        return {
            "action": "guess",
            "text": normalize(guess),
            "inCandidates": is_candidate(guess),
            "usage": usage,
        }
    if action == "ask" or question:
        if not question:
            raise LLMError("模型选择 ask 但没有给出问题")
        return {"action": "ask", "text": question, "usage": usage}
    raise LLMError(f"无法识别的模型动作: {raw}")
