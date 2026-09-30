"""批量自动测试：后台任务跑 N 局并统计。"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from . import config
from .config import get_model
from .game import Game, store


class Batch:
    def __init__(self, models: list[str], games_per_model: int, judge_model: str, concurrency: int):
        self.id = uuid.uuid4().hex[:10]
        self.models = models
        self.games_per_model = games_per_model
        self.judge_model = judge_model
        self.concurrency = concurrency
        self.status = "running"  # running | done
        self.games: list[Game] = []
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.finished_at: str | None = None

    def stats(self) -> list[dict[str, Any]]:
        out = []
        for m in self.models:
            gs = [g for g in self.games if g.model.id == m]
            done = [g for g in gs if g.status in ("won", "lost")]
            won = [g for g in done if g.status == "won"]
            errors = [g for g in gs if g.status == "error"]
            out.append(
                {
                    "model": m,
                    "total": self.games_per_model,
                    "started": len(gs),
                    "finished": len(done),
                    "won": len(won),
                    "lost": len(done) - len(won),
                    "errors": len(errors),
                    "winRate": (len(won) / len(done)) if done else None,
                    "avgTurnsWhenWon": (sum(g.turns_used for g in won) / len(won)) if won else None,
                    "avgTurns": (sum(g.turns_used for g in done) / len(done)) if done else None,
                }
            )
        return out

    def view(self, include_games: bool = True) -> dict[str, Any]:
        v: dict[str, Any] = {
            "id": self.id,
            "status": self.status,
            "models": self.models,
            "gamesPerModel": self.games_per_model,
            "judgeModel": self.judge_model,
            "createdAt": self.created_at,
            "finishedAt": self.finished_at,
            "progress": {
                "total": len(self.models) * self.games_per_model,
                "finished": sum(1 for g in self.games if g.status in ("won", "lost", "error")),
            },
            "stats": self.stats(),
        }
        if include_games:
            v["games"] = [g.public_view() | ({"secretEmoji": g.secret_emoji} if g.status == "error" else {}) for g in self.games]
        return v


class BatchStore:
    def __init__(self) -> None:
        self._batches: dict[str, Batch] = {}

    def get(self, batch_id: str) -> Batch:
        b = self._batches.get(batch_id)
        if b is None:
            raise KeyError("batch 不存在")
        return b

    async def start(self, models: list[str], games_per_model: int, judge_model: str | None, concurrency: int = 3) -> Batch:
        for m in models:
            get_model(m)
        judge = judge_model or config.JUDGE_MODEL
        get_model(judge)
        batch = Batch(models, games_per_model, judge, concurrency)
        self._batches[batch.id] = batch
        asyncio.create_task(self._run(batch))
        return batch

    async def _run(self, batch: Batch) -> None:
        sem = asyncio.Semaphore(batch.concurrency)

        async def one(model_id: str) -> None:
            async with sem:
                game = await store.create(model_id, "auto", None, batch.judge_model)
                batch.games.append(game)
                await game.run_to_end()

        await asyncio.gather(
            *(one(m) for m in batch.models for _ in range(batch.games_per_model)),
            return_exceptions=True,
        )
        batch.status = "done"
        batch.finished_at = datetime.now(timezone.utc).isoformat()


batches = BatchStore()
