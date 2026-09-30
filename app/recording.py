"""对局录制：页面逐帧上传 JPEG，这里用 ffmpeg 编码成 9:16 的 MP4。"""
from __future__ import annotations

import asyncio
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from .config import ROOT

OUT_DIR = ROOT / "recordings"
WIDTH, HEIGHT = 1080, 1920


class RecordingError(Exception):
    pass


class Recording:
    def __init__(self, proc: asyncio.subprocess.Process, path: Path):
        self.id = uuid.uuid4().hex[:12]
        self.proc = proc
        self.path = path
        self.done = False
        self.lock = asyncio.Lock()

    async def write(self, data: bytes) -> None:
        """追加若干帧（首尾相接的 JPEG）。"""
        async with self.lock:
            if self.done or self.proc.stdin is None:
                raise RecordingError("录制已结束")
            try:
                self.proc.stdin.write(data)
                await self.proc.stdin.drain()
            except (BrokenPipeError, ConnectionResetError):
                raise RecordingError(f"ffmpeg 已退出: {await self._stderr()}")

    async def finish(self) -> Path:
        async with self.lock:
            if not self.done:
                self.done = True
                if self.proc.stdin is not None:
                    self.proc.stdin.close()  # communicate() 不带 input 时不会关 stdin，ffmpeg 等不到 EOF
                _, err = await self.proc.communicate()
                if self.proc.returncode != 0 or not self.path.exists():
                    raise RecordingError(f"ffmpeg 编码失败: {err.decode(errors='replace').strip()[-500:]}")
            return self.path

    async def _stderr(self) -> str:
        self.done = True
        if self.proc.stdin is not None:
            self.proc.stdin.close()
        _, err = await self.proc.communicate()
        return err.decode(errors="replace").strip()[-500:]


class RecordingStore:
    def __init__(self) -> None:
        self._recordings: dict[str, Recording] = {}

    def get(self, recording_id: str) -> Recording:
        r = self._recordings.get(recording_id)
        if r is None:
            raise KeyError("录制不存在")
        return r

    async def start(self, label: str, fps: int, frames: int) -> Recording:
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is None:
            raise RecordingError("未找到 ffmpeg，无法生成视频。请先安装（macOS：brew install ffmpeg）")
        OUT_DIR.mkdir(exist_ok=True)
        safe = re.sub(r"[^A-Za-z0-9._-]+", "-", label).strip("-") or "game"
        path = OUT_DIR / f"emoji20q-{safe}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.mp4"
        proc = await asyncio.create_subprocess_exec(
            ffmpeg, "-y", "-loglevel", "error",
            "-f", "image2pipe", "-framerate", str(fps), "-c:v", "mjpeg", "-i", "-",
            "-frames:v", str(frames),
            "-vf", f"scale={WIDTH}:{HEIGHT}:in_range=pc:out_range=tv,format=yuv420p",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-movflags", "+faststart",
            str(path),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        rec = Recording(proc, path)
        self._recordings[rec.id] = rec
        return rec


recordings = RecordingStore()
