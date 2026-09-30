"""命令行批量测试。

用法：
  uv run python scripts/run_batch.py --models claude-opus-5-5 gpt-6.1-sol --games 10
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import config  # noqa: E402
from app.batch import batches  # noqa: E402


async def main() -> None:
    parser = argparse.ArgumentParser(description="Emoji 二十问批量测试")
    parser.add_argument("--models", nargs="+", default=[m.id for m in config.MODELS], help="猜测模型 ID 列表")
    parser.add_argument("--games", type=int, default=5, help="每个模型跑多少局")
    parser.add_argument("--judge", default=config.JUDGE_MODEL, help="裁判模型 ID")
    parser.add_argument("--concurrency", type=int, default=3)
    args = parser.parse_args()

    batch = await batches.start(args.models, args.games, args.judge, args.concurrency)
    total = len(args.models) * args.games
    while batch.status != "done":
        await asyncio.sleep(3)
        done = batch.view(include_games=False)["progress"]["finished"]
        print(f"\r进度 {done}/{total}", end="", flush=True)
    print()

    print(f"\n{'模型':<22}{'胜':>4}{'负':>4}{'错误':>5}{'胜率':>8}{'均回合(胜)':>12}")
    for s in batch.stats():
        wr = f"{s['winRate']*100:.0f}%" if s["winRate"] is not None else "-"
        avg = f"{s['avgTurnsWhenWon']:.1f}" if s["avgTurnsWhenWon"] is not None else "-"
        print(f"{s['model']:<22}{s['won']:>4}{s['lost']:>4}{s['errors']:>5}{wr:>8}{avg:>12}")

    out_dir = ROOT / "results"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"batch-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps(batch.view(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n完整结果已写入 {out}")


if __name__ == "__main__":
    asyncio.run(main())
