"""FastAPI 入口：静态页面 + 游戏 API。"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config
from .batch import batches
from .emojis import EMOJIS
from .game import GameError, store
from .recording import RecordingError, recordings

app = FastAPI(title="Emoji 二十问", version="0.1.0")
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


# ---------- 请求体 ----------

class CreateGameBody(BaseModel):
    model: str
    mode: Literal["human", "auto"] = "human"
    secretEmoji: str | None = None
    judgeModel: str | None = None
    language: Literal["zh", "en"] | None = None


class AnswerBody(BaseModel):
    answer: Literal["yes", "no"]


class StepBody(BaseModel):
    language: Literal["zh", "en"] | None = None


class BatchBody(BaseModel):
    models: list[str] = Field(min_length=1)
    gamesPerModel: int = Field(default=5, ge=1, le=50)
    judgeModel: str | None = None
    concurrency: int = Field(default=3, ge=1, le=8)


class RecordingBody(BaseModel):
    label: str = "game"
    fps: int = Field(default=30, ge=1, le=60)
    frames: int = Field(default=600, ge=1, le=3600)


def _game_or_404(game_id: str):
    try:
        return store.get(game_id)
    except GameError as e:
        raise HTTPException(404, str(e))


# ---------- 元信息 ----------

@app.get("/api/models")
def list_models():
    return {
        "models": [
            {"id": m.id, "label": m.label, "provider": m.provider, "inputPrice": m.input_price, "outputPrice": m.output_price}
            for m in config.MODELS
        ],
        "defaultJudge": config.JUDGE_MODEL,
        "maxTurns": config.MAX_TURNS,
        "questionLanguage": config.QUESTION_LANGUAGE,
        "languages": list(config.LANGUAGES),
        "apiKeyConfigured": bool(config.EVOLINK_API_KEY),
    }


@app.get("/api/emojis")
def list_emojis():
    return {"emojis": EMOJIS}


# ---------- 对局 ----------

@app.post("/api/games")
async def create_game(body: CreateGameBody):
    try:
        game = await store.create(body.model, body.mode, body.secretEmoji, body.judgeModel, language=body.language)
    except (GameError, ValueError) as e:
        raise HTTPException(400, str(e))
    async with game.lock:
        await game.fetch_next()
    return game.public_view()


@app.get("/api/games/{game_id}")
def get_game(game_id: str):
    return _game_or_404(game_id).public_view()


@app.post("/api/games/{game_id}/answer")
async def answer_game(game_id: str, body: AnswerBody):
    game = _game_or_404(game_id)
    try:
        await game.answer(body.answer)
    except GameError as e:
        raise HTTPException(409, str(e))
    return game.public_view()


@app.post("/api/games/{game_id}/auto-step")
async def auto_step(game_id: str, body: StepBody | None = None):
    game = _game_or_404(game_id)
    if game.mode != "auto":
        raise HTTPException(409, "只有自动模式对局可以调用 auto-step")
    if body and body.language:
        game.language = body.language  # 对局中切换语言：后续问题用新语言
    try:
        await game.auto_step()
    except GameError as e:
        raise HTTPException(409, str(e))
    return game.public_view()


@app.post("/api/games/{game_id}/next")
async def next_action(game_id: str):
    game = _game_or_404(game_id)
    await game.retry()
    return game.public_view()


# ---------- 批量 ----------

@app.post("/api/batch")
async def create_batch(body: BatchBody):
    try:
        batch = await batches.start(body.models, body.gamesPerModel, body.judgeModel, body.concurrency)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return batch.view(include_games=False)


@app.get("/api/batch/{batch_id}")
def get_batch(batch_id: str):
    try:
        return batches.get(batch_id).view()
    except KeyError as e:
        raise HTTPException(404, str(e))


# ---------- 录制 ----------

def _recording_or_404(recording_id: str):
    try:
        return recordings.get(recording_id)
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.post("/api/recordings")
async def create_recording(body: RecordingBody):
    try:
        rec = await recordings.start(body.label, body.fps, body.frames)
    except RecordingError as e:
        raise HTTPException(503, str(e))
    return {"id": rec.id}


@app.post("/api/recordings/{recording_id}/frames")
async def add_frames(recording_id: str, request: Request):
    rec = _recording_or_404(recording_id)
    try:
        await rec.write(await request.body())
    except RecordingError as e:
        raise HTTPException(500, str(e))
    return {"ok": True}


@app.post("/api/recordings/{recording_id}/finish")
async def finish_recording(recording_id: str):
    rec = _recording_or_404(recording_id)
    try:
        path = await rec.finish()
    except RecordingError as e:
        raise HTTPException(500, str(e))
    return {"id": rec.id, "url": f"/api/recordings/{rec.id}/video", "filename": path.name}


@app.get("/api/recordings/{recording_id}/video")
async def get_recording(recording_id: str):
    rec = _recording_or_404(recording_id)
    if not rec.done or not rec.path.exists():
        raise HTTPException(409, "视频尚未生成")
    return FileResponse(rec.path, media_type="video/mp4", filename=rec.path.name)


# ---------- 静态页面 ----------

@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
