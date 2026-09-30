"""EvoLink 客户端。

两种适配器：
- anthropic: POST /v1/messages，用强制工具调用拿到严格 JSON
- openai:    POST /v1/chat/completions，用 response_format=json_schema

两者都提供兜底：若网关拒绝结构化参数，则退回普通文本并从回复中提取 JSON。
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any

import httpx

from . import config
from .config import ModelInfo


class LLMError(Exception):
    pass


_client: httpx.AsyncClient | None = None


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None:
        # 外网请求沿用系统/环境代理；本机地址（如本地模拟网关）直连，不走代理
        direct = httpx.AsyncHTTPTransport()
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(config.LLM_TIMEOUT, connect=15),
            mounts={"all://127.0.0.1": direct, "all://localhost": direct},
        )
    return _client


def _headers() -> dict[str, str]:
    if not config.EVOLINK_API_KEY:
        raise LLMError("未配置 EVOLINK_API_KEY，请在 .env 中填写")
    return {
        "Authorization": f"Bearer {config.EVOLINK_API_KEY}",
        "Content-Type": "application/json",
    }


def _extract_json(text: str) -> dict[str, Any]:
    """从可能带围栏/前后缀的文本中提取第一个 JSON 对象。"""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    else:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            text = text[start : end + 1]
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as e:
        raise LLMError(f"模型返回的不是合法 JSON: {e}: {text[:300]}")
    if not isinstance(obj, dict):
        raise LLMError("模型返回的 JSON 不是对象")
    return obj


async def _post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{config.EVOLINK_BASE_URL}{path}"
    last_err: Exception | None = None
    for attempt in range(2):
        try:
            resp = await _http().post(url, headers=_headers(), json=payload)
        except httpx.HTTPError as e:
            last_err = LLMError(f"网络错误: {e}")
            await asyncio.sleep(1.5)
            continue
        if resp.status_code == 400:
            # 参数被拒绝，不重试，交给调用方决定是否降级
            raise _BadRequest(resp.text[:500])
        # 404 也重试一次：EvoLink 偶发 "model not supported in this group" 的临时路由错误
        if resp.status_code >= 500 or resp.status_code in (429, 404):
            last_err = LLMError(f"HTTP {resp.status_code}: {resp.text[:300]}")
            await asyncio.sleep(2)
            continue
        if resp.status_code >= 400:
            raise LLMError(f"HTTP {resp.status_code}: {resp.text[:300]}")
        try:
            return resp.json()
        except ValueError:
            raise LLMError(f"响应不是 JSON: {resp.text[:300]}")
    raise last_err or LLMError("未知错误")


class _BadRequest(LLMError):
    pass


# ---------- Anthropic Messages 适配器 ----------

async def _anthropic_structured(
    model: str, system: str, user: str, schema: dict, tool_name: str, max_tokens: int
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
        "tools": [
            {
                "name": tool_name,
                "description": "Return your decision in the required structured format.",
                "input_schema": schema,
            }
        ],
        "tool_choice": {"type": "tool", "name": tool_name},
    }
    try:
        data = await _post("/v1/messages", payload)
    except _BadRequest:
        # 网关可能不支持 tool_choice，降级为纯文本 + 提取 JSON
        payload.pop("tools")
        payload.pop("tool_choice")
        payload["system"] = system + "\n\nRespond with ONLY a JSON object matching this schema:\n" + json.dumps(schema)
        data = await _post("/v1/messages", payload)
    u = data.get("usage") or {}
    usage = {
        "inputTokens": int(u.get("input_tokens") or 0)
        + int(u.get("cache_creation_input_tokens") or 0)
        + int(u.get("cache_read_input_tokens") or 0),
        "outputTokens": int(u.get("output_tokens") or 0),
    }
    if data.get("stop_reason") == "refusal":
        details = data.get("stop_details") or {}
        raise LLMError(
            f"模型拒绝了这次请求（安全拦截，类别: {details.get('category', '未知')}）。"
            f"{str(details.get('explanation', ''))[:200]}"
        )
    for block in data.get("content", []):
        if block.get("type") == "tool_use" and isinstance(block.get("input"), dict):
            if not block["input"] and data.get("stop_reason") == "max_tokens":
                raise LLMError("模型输出被 max_tokens 截断，未返回完整结果")
            return block["input"], usage
    texts = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
    if texts:
        return _extract_json("\n".join(texts)), usage
    raise LLMError(f"Anthropic 响应中没有可用内容: {json.dumps(data)[:300]}")


# ---------- OpenAI Chat Completions 适配器 ----------

async def _openai_structured(
    model: str, system: str, user: str, schema: dict, tool_name: str, max_tokens: int
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": tool_name, "strict": True, "schema": schema},
        },
    }
    try:
        data = await _post("/v1/chat/completions", payload)
    except _BadRequest:
        payload.pop("response_format")
        payload["messages"][0]["content"] = (
            system + "\n\nRespond with ONLY a JSON object matching this schema:\n" + json.dumps(schema)
        )
        data = await _post("/v1/chat/completions", payload)
    try:
        msg = data["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        raise LLMError(f"OpenAI 响应格式异常: {json.dumps(data)[:300]}")
    content = msg.get("content")
    if isinstance(content, list):  # 某些网关返回分段
        content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
    if msg.get("refusal"):
        raise LLMError(f"模型拒绝回答: {msg['refusal']}")
    if not content:
        raise LLMError("模型返回空内容")
    u = data.get("usage") or {}
    usage = {"inputTokens": int(u.get("prompt_tokens") or 0), "outputTokens": int(u.get("completion_tokens") or 0)}
    return _extract_json(content), usage


# ---------- 真实扣费查询 ----------

_inflight = 0  # 正在进行的模型调用数
_epoch = 0     # 每开始一次调用 +1，用来发现"我的调用期间有别人开始了"


async def _used_credits() -> float | None:
    """查询本密钥累计已用 credits（GET /v1/credits）。失败返回 None。"""
    try:
        resp = await _http().get(f"{config.EVOLINK_BASE_URL}/v1/credits", headers=_headers(), timeout=10)
        return float(resp.json()["data"]["token"]["used_credits"])
    except Exception:  # noqa: BLE001
        return None


# ---------- 统一入口 ----------

async def structured_call(
    model: ModelInfo,
    system: str,
    user: str,
    schema: dict,
    tool_name: str = "respond",
    max_tokens: int = 1024,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """调用模型，返回 (符合 schema 的 dict, 用量)。

    用量 = {"inputTokens", "outputTokens", "ms", "credits", "cost", "billed"}。
    billed=True 表示 credits / cost 是 EvoLink 的真实扣费；False 表示按单价估算的兜底值。
    """
    global _inflight, _epoch
    if model.provider not in ("anthropic", "openai"):
        raise LLMError(f"未知 provider: {model.provider}")
    adapter = _anthropic_structured if model.provider == "anthropic" else _openai_structured

    # 真实扣费 = 调用前后已用额度之差。只有这次调用全程没有别的调用并行时，差值才属于它。
    _epoch += 1
    my_epoch = _epoch
    alone = _inflight == 0
    _inflight += 1
    before = after = None
    try:
        if alone:
            before = await _used_credits()
        started = time.perf_counter()
        obj, usage = await adapter(model.id, system, user, schema, tool_name, max_tokens)
        usage["ms"] = round((time.perf_counter() - started) * 1000)  # 只计模型调用本身
        if before is not None:
            after = await _used_credits()
    finally:
        _inflight -= 1

    alone = alone and _epoch == my_epoch
    if alone and before is not None and after is not None and after > before:
        usage["credits"] = round(after - before, 4)
        usage["cost"] = usage["credits"] * config.CREDIT_USD
        usage["billed"] = True
    else:
        usage["cost"] = model.cost(usage["inputTokens"], usage["outputTokens"])
        usage["credits"] = usage["cost"] / config.CREDIT_USD if config.CREDIT_USD else 0.0
        usage["billed"] = False
    return obj, usage
