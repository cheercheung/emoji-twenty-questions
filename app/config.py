"""环境变量与模型注册表。"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class ModelInfo:
    id: str
    label: str
    provider: str  # "anthropic" -> /v1/messages, "openai" -> /v1/chat/completions
    input_price: float = 0.0   # 美元 / 100 万输入 token
    output_price: float = 0.0  # 美元 / 100 万输出 token

    def cost(self, input_tokens: int, output_tokens: int) -> float:
        return (input_tokens * self.input_price + output_tokens * self.output_price) / 1_000_000


# 首版可选模型。provider 决定走哪种 EvoLink 接口。
MODELS: list[ModelInfo] = [
    # 花费默认取 EvoLink 的真实扣费（调用前后 /v1/credits 的差值）。
    # 下面的单价（美元 / 100 万 token：输入, 输出）只在取不到真实扣费时用来兜底估算，
    # 例如批量测试并发调用时无法把扣费归到单次调用。
    ModelInfo("claude-opus-5-5", "Claude Opus 5.5", "anthropic", 3.80, 19.00),
    ModelInfo("claude-sonnet-5-5", "Claude Sonnet 5.5", "anthropic", 1.90, 9.50),
    ModelInfo("claude-fable-5-1", "Claude Fable 5.1", "anthropic", 9.50, 47.50),
    ModelInfo("gpt-6.1-sol", "GPT-6.1 Sol", "openai", 1.80, 9.00),
    # GPT-6 Astra 未找到 EvoLink 报价，这里用 OpenAI 官方价，实际可能更低
    ModelInfo("gpt-6-astra", "GPT-6 Astra", "openai", 10.00, 50.00),
]
MODEL_BY_ID: dict[str, ModelInfo] = {m.id: m for m in MODELS}


def get_model(model_id: str) -> ModelInfo:
    if model_id not in MODEL_BY_ID:
        raise ValueError(f"未知模型: {model_id}")
    return MODEL_BY_ID[model_id]


EVOLINK_API_KEY: str = os.getenv("EVOLINK_API_KEY", "").strip()
EVOLINK_BASE_URL: str = os.getenv("EVOLINK_BASE_URL", "https://direct.evolink.ai").rstrip("/")
JUDGE_MODEL: str = os.getenv("JUDGE_MODEL", "claude-sonnet-5-5").strip()
QUESTION_LANGUAGE: str = os.getenv("QUESTION_LANGUAGE", "中文").strip()
MAX_TURNS: int = int(os.getenv("MAX_TURNS", "20"))
LLM_TIMEOUT: float = float(os.getenv("LLM_TIMEOUT", "120"))
# 1 个 EvoLink credit 折合多少美元（定价页：1 credit ≈ $0.0147）
CREDIT_USD: float = float(os.getenv("EVOLINK_CREDIT_USD", "0.0147"))

# 页面可切换的语言：代码 -> 写进提示词的语言名
LANGUAGES: dict[str, str] = {"zh": "简体中文 (Simplified Chinese)", "en": "English"}


def question_language(code: str | None) -> str:
    """把页面语言代码转成提示词里的语言名；未指定时用 QUESTION_LANGUAGE。"""
    return LANGUAGES.get(code or "", QUESTION_LANGUAGE)
