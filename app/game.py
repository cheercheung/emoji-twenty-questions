"""游戏状态与规则执行。

后端负责：
- 回合上限（每个 ask / guess 都消耗 1 回合）
- 猜测判定（去掉变体选择符后比较）
- 答案隔离（对局进行中 public_view 不含 secretEmoji）
"""
from __future__ import annotations

import asyncio
import random
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from . import config
from .config import ModelInfo, get_model
from .emojis import EMOJIS, is_candidate, name_of, normalize
from .guesser import next_action
from .judge import judge_question
from .llm import LLMError

Answer = Literal["yes", "no"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class GameError(Exception):
    pass


class Game:
    def __init__(
        self,
        model: ModelInfo,
        mode: str,
        secret_emoji: str,
        judge_model: ModelInfo | None,
        max_turns: int,
        language: str | None = None,
    ):
        self.id = uuid.uuid4().hex[:12]
        self.model = model
        self.mode = mode
        self.secret_emoji = normalize(secret_emoji)
        self.judge_model = judge_model
        self.max_turns = max_turns
        self.language = language  # "zh" | "en" | None（None 用 .env 默认）
        self.status: str = "playing"  # playing | won | lost | error
        self.turns_used = 0
        self.history: list[dict[str, Any]] = []
        self.pending: dict[str, Any] | None = None
        self.error: str | None = None
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.lock = asyncio.Lock()
        # 累计统计：猜测模型 / 裁判模型各自的调用次数、耗时、token、费用
        self.totals: dict[str, dict[str, float]] = {
            role: {"calls": 0, "ms": 0, "inputTokens": 0, "outputTokens": 0, "credits": 0.0, "cost": 0.0, "estimatedCalls": 0}
            for role in ("guess", "judge")
        }

    def _add_usage(self, role: str, ms: int, usage: dict[str, Any] | None) -> None:
        t = self.totals[role]
        u = usage or {}
        t["calls"] += 1
        t["ms"] += ms
        t["inputTokens"] += u.get("inputTokens", 0)
        t["outputTokens"] += u.get("outputTokens", 0)
        t["cost"] += u.get("cost", 0.0)
        t["credits"] += u.get("credits", 0.0)
        if not u.get("billed"):
            t["estimatedCalls"] += 1  # 这次没取到真实扣费，用的是估算

    def stats(self) -> dict[str, Any]:
        """overview 三行：guess / judge / total。"""
        g, j = self.totals["guess"], self.totals["judge"]
        return {
            "guess": {"model": self.model.id, "label": self.model.label, **g},
            "judge": {
                "model": self.judge_model.id if self.judge_model else None,
                "label": self.judge_model.label if self.judge_model else None,
                **j,
            },
            "total": {k: g[k] + j[k] for k in g},
        }

    # ---------- 视图 ----------

    def public_view(self) -> dict[str, Any]:
        finished = self.status in ("won", "lost")
        view: dict[str, Any] = {
            "id": self.id,
            "model": self.model.id,
            "modelLabel": self.model.label,
            "mode": self.mode,
            "judgeModel": self.judge_model.id if self.judge_model else None,
            "judgeLabel": self.judge_model.label if self.judge_model else None,
            "language": self.language,
            "status": self.status,
            "turnsUsed": self.turns_used,
            "maxTurns": self.max_turns,
            "history": self.history,
            "pending": self.pending,
            "stats": self.stats(),
            "error": self.error,
            "createdAt": self.created_at,
        }
        # 答案隔离：只有结束后才公布
        if finished:
            view["secretEmoji"] = self.secret_emoji
            view["secretName"] = name_of(self.secret_emoji)
        return view

    # ---------- 核心流程 ----------

    async def fetch_next(self) -> None:
        """向模型索取下一个动作。若返回 guess 立即判定。"""
        if self.status not in ("playing", "error"):
            return
        if self.pending is not None:
            # 已有待回答动作（若此前是裁判出错，恢复为 playing 让其重新裁判）
            self.status = "playing"
            self.error = None
            return
        self.status = "playing"
        self.error = None
        started = time.perf_counter()
        try:
            action = await next_action(
                self.model, self.history, self.turns_used, self.max_turns, config.question_language(self.language)
            )
        except LLMError as e:
            self.status = "error"
            self.error = str(e)
            return
        except Exception as e:  # noqa: BLE001
            self.status = "error"
            self.error = f"{type(e).__name__}: {e}"
            return

        # 模型产生这个动作花了多久
        usage = action.pop("usage", None) or {}
        action["modelMs"] = usage.get("ms") or round((time.perf_counter() - started) * 1000)
        action["guessTokens"] = usage.get("inputTokens", 0) + usage.get("outputTokens", 0)
        action["guessCost"] = usage.get("cost", 0.0)
        self._add_usage("guess", action["modelMs"], usage)

        if action["action"] == "guess":
            self._apply_guess(action)
        else:
            self.pending = action

    def _apply_guess(self, action: dict[str, Any]) -> None:
        self.turns_used += 1
        correct = normalize(action["text"]) == self.secret_emoji
        self.history.append(
            {
                "turn": self.turns_used,
                "action": "guess",
                "text": action["text"],
                "correct": correct,
                "inCandidates": action.get("inCandidates", is_candidate(action["text"])),
                "modelMs": action.get("modelMs"),
                "guessTokens": action.get("guessTokens", 0),
                "guessCost": action.get("guessCost", 0.0),
                "at": _now(),
            }
        )
        self.pending = None
        if correct:
            self.status = "won"
        elif self.turns_used >= self.max_turns:
            self.status = "lost"

    def _apply_answer(self, answer: Answer, answer_ms: int | None = None, usage: dict[str, Any] | None = None) -> None:
        if self.pending is None or self.pending.get("action") != "ask":
            raise GameError("当前没有待回答的问题")
        self.turns_used += 1
        entry = {
            "turn": self.turns_used,
            "action": "ask",
            "text": self.pending["text"],
            "answer": answer,
            "modelMs": self.pending.get("modelMs"),  # 模型提出问题的耗时
            "answerMs": answer_ms,  # 回答耗时（裁判或人）
            "guessTokens": self.pending.get("guessTokens", 0),
            "guessCost": self.pending.get("guessCost", 0.0),
            "judgeTokens": (usage or {}).get("inputTokens", 0) + (usage or {}).get("outputTokens", 0),
            "judgeCost": (usage or {}).get("cost", 0.0),
            "at": _now(),  # 回答时刻
        }
        self.history.append(entry)
        self.pending = None
        if self.turns_used >= self.max_turns:
            self.status = "lost"

    async def answer(self, answer: Answer) -> None:
        """人工回答：记录 → 若未结束再要下一动作。"""
        async with self.lock:
            if self.status != "playing":
                raise GameError(f"对局已结束或出错（{self.status}）")
            self._apply_answer(answer)
            if self.status == "playing":
                await self.fetch_next()

    async def auto_step(self) -> None:
        """自动模式走一步（每次只做一件事，便于页面逐步展示）：
        有待回答的问题 → 裁判回答；否则 → 猜测模型给出下一动作。"""
        async with self.lock:
            if self.status not in ("playing", "error"):
                return
            if self.pending is None:
                await self.fetch_next()
                return
            if self.judge_model is None:
                raise GameError("该对局未配置裁判模型")
            self.status = "playing"
            self.error = None
            started = time.perf_counter()
            try:
                verdict, usage = await judge_question(self.judge_model, self.secret_emoji, self.pending["text"])
            except LLMError as e:
                self.status = "error"
                self.error = f"裁判出错: {e}"
                return
            ms = usage.get("ms") or round((time.perf_counter() - started) * 1000)
            self._add_usage("judge", ms, usage)
            self._apply_answer(verdict, ms, usage)

    async def retry(self) -> None:
        async with self.lock:
            # 出错在裁判阶段时 pending 仍在，fetch_next 只会恢复状态，随后由 auto_step 重新裁判
            if self.status in ("playing", "error"):
                await self.fetch_next()

    async def run_to_end(self, max_steps: int | None = None) -> None:
        """自动跑完整局（批量测试用）。出错时最多重试 2 次。"""
        retries = 0
        steps = 0
        limit = max_steps or (self.max_turns * 2 + 5)
        while self.status in ("playing", "error") and steps < limit:
            steps += 1
            if self.status == "error":
                retries += 1
                if retries > 2:
                    break
                await asyncio.sleep(2)
                await self.retry()
                if self.status == "error":
                    continue
            await self.auto_step()


# ---------- 内存存储 ----------

class GameStore:
    def __init__(self) -> None:
        self._games: dict[str, Game] = {}

    async def create(
        self,
        model_id: str,
        mode: str,
        secret_emoji: str | None = None,
        judge_model_id: str | None = None,
        max_turns: int | None = None,
        language: str | None = None,
    ) -> Game:
        if mode not in ("human", "auto"):
            raise GameError("mode 必须是 human 或 auto")
        model = get_model(model_id)
        judge = None
        if mode == "auto":
            judge = get_model(judge_model_id or config.JUDGE_MODEL)
        if secret_emoji:
            if not is_candidate(secret_emoji):
                raise GameError("secretEmoji 不在候选集中")
        else:
            secret_emoji = random.choice(EMOJIS)["emoji"]
        game = Game(model, mode, secret_emoji, judge, max_turns or config.MAX_TURNS, language)
        self._games[game.id] = game
        return game

    def get(self, game_id: str) -> Game:
        g = self._games.get(game_id)
        if g is None:
            raise GameError("对局不存在")
        return g


store = GameStore()
