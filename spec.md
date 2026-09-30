# Emoji 二十问（"twenty cool calls"）— 完整规格

## 1. 背景与目标

"twenty cool calls" 是 emoji 版的「二十问」：先藏好一个 emoji，让大模型连续提出只能回答"是／否"的问题，争取在 20 轮内猜中它。

本项目的目标不是做一个"看起来像二十问的聊天界面"，而是真正测试模型如何逐步缩小范围。因此两条关键规则由后端强制执行：

1. **次数限制由后端执行**：模型每轮只能做一个动作，最多 20 轮，超出即判负。
2. **答案隔离由后端保证**：猜测模型在任何请求中都收不到隐藏 emoji；只有"裁判"能看到。

## 2. 已确认的决策

| 项目 | 决策 |
|---|---|
| 技术栈 | Python 3.11 + FastAPI 后端，纯 HTML/JS 静态页面（无前端框架） |
| 状态存储 | 内存字典（服务重启后对局丢失） |
| 模型接入 | EvoLink 网关，`.env` 中填 `EVOLINK_API_KEY` 即可 |
| 首版模型 | `claude-opus-5-5`、`claude-sonnet-5-5`、`claude-fable-5-1`、`gpt-6.1-sol`、`gpt-6-astra` |
| 模型选择 | 网页上每局开始时下拉选择猜测模型 |
| 自动裁判 | 首版包含：单局自动模式 + 批量测试模式 |
| 默认裁判模型 | `claude-sonnet-5-5`（可在 `.env` 和页面上改） |
| 页面范围 | 网页只保留**自动单局**；人工回答与批量测试的后端接口、命令行脚本保留 |
| 回答格式 | 只有 `yes` / `no`，不带任何解释，不存在“有歧义” |
| 语言 | 页面右上角切换 中文 / English：界面文字与模型提问语言同时切换，对局中切换对后续回合生效 |
| 模型标注 | 卡片顶部并排写明 Guess 与 Judge 所用模型的名称和 ID，Overview 里再次列出 |
| 版式 | 整局一个卡片：模型 → Question log → 答案 → Overview 三行 Guess / Judge / Total |
| 计时 | 每行记 Guess 用时、Judge 用时、合计；Overview 里有各自总用时 |
| 花费 | 取 EvoLink 真实扣费（调用前后 `/v1/credits` 差值），统计 Guess、Judge、Total |
| 候选集 | 精选 111 个差异明显的 emoji（`app/emojis.py`），不含肤色、ZWJ 组合、旗帜 |

## 3. 玩法与规则

### 3.1 回合定义

- 每一回合模型只能返回一个动作：
  - `ask`：提出一个只能用是／否回答的问题
  - `guess`：猜一个候选集中的 emoji
- **无论 ask 还是 guess，都消耗 1 回合**。总回合上限 `MAX_TURNS = 20`。
- 第 20 回合时，后端在提示词里告知模型"这是最后一回合，必须 guess"；若模型仍然 ask，后端把这次 ask 记录下来并判负。

### 3.2 回答

- 回答只能是 `yes` 或 `no`，不附带任何解释说明。
- 自动模式：裁判模型只返回 `yes / no`；问题不够清晰时选更接近事实的一个。
- 人工接口（`/answer`）同样只接受 `yes / no`。
- 轨迹中用 **YES / NO** 徽标标记每个回答。

### 3.3 猜测判定

- 后端将模型给出的 guess 与隐藏 emoji 比较，比较前统一去掉变体选择符 `U+FE0F`。
- 猜中 → `status = won`，游戏结束。
- 猜错 → 记录为一条历史（`guess ❌`），继续下一回合。
- 模型 guess 的 emoji 若不在候选集中，视为猜错，并在反馈中提醒它只能从候选集里猜。

### 3.4 结束条件

- `won`：猜中。
- `lost`：20 回合用完仍未猜中。
- `error`：模型调用失败（网络、鉴权、格式错误），可点击"重试"继续同一局。
- 结束后公布答案，并展示完整提问轨迹（每回合的问题/猜测 + 回答 + 模型简短思路）。

## 4. 系统架构

```
static/index.html + app.js + style.css   ← 网页（人工回答 / 自动单局 / 批量测试）
            │  fetch /api/*
app/main.py  FastAPI 路由
app/game.py  游戏状态 + 规则执行（次数、猜测判定、答案隔离）
app/guesser.py  组装猜测模型提示词（不含答案）
app/judge.py    组装裁判提示词（含答案 + 当前问题）
app/llm.py      EvoLink 客户端：Claude Messages 适配器 / OpenAI Chat 适配器
app/batch.py    批量测试：后台任务 + 统计
app/emojis.py   100 个候选 emoji（含英文名）
app/config.py   .env 读取 + 模型注册表
```

### 4.1 游戏状态（内存）

```json
{
  "id": "uuid",
  "secretEmoji": "🐶",            // 仅服务端可见；对局进行中不会出现在任何 API 响应里
  "model": "claude-opus-5-5",
  "mode": "human" | "auto",
  "judgeModel": "claude-sonnet-5-5",
  "status": "playing" | "won" | "lost" | "error",
  "turnsUsed": 3,
  "maxTurns": 20,
  "history": [
    {"turn": 1, "action": "ask",   "text": "它是动物吗？", "answer": "yes",
     "modelMs": 2300, "answerMs": 800, "at": "ISO 时间"},
    {"turn": 2, "action": "guess", "text": "🐱", "correct": false, "modelMs": 2100, "at": "ISO 时间"}
  ],
  "pending": {"action": "ask", "text": "它会飞吗？"} | null,
  "error": null | "错误信息",
  "createdAt": "ISO 时间"
}
```

- `pending` 表示模型已给出、但尚未得到回答的动作。
- 对局进行中，API 响应里 **删除 `secretEmoji`**；结束后（won/lost）才返回。

### 4.2 模型输出 Schema（猜测模型）

```json
{
  "type": "object",
  "properties": {
    "action":   {"type": "string", "enum": ["ask", "guess"]},
    "question": {"type": "string", "description": "action=ask 时填写，否则为空字符串"},
    "guess":    {"type": "string", "description": "action=guess 时填写单个 emoji，否则为空字符串"}
  },
  "required": ["action", "question", "guess"],
  "additionalProperties": false
}
```

### 4.3 模型输出 Schema（裁判）

```json
{
  "type": "object",
  "properties": {
    "answer": {"type": "string", "enum": ["yes", "no"]}
  },
  "required": ["answer"],
  "additionalProperties": false
}
```

### 4.4 EvoLink 接入

- Base URL：`EVOLINK_BASE_URL`，默认 `https://direct.evolink.ai`
- 鉴权：`Authorization: Bearer <EVOLINK_API_KEY>`
- Claude 系列：`POST /v1/messages`，使用**强制工具调用**（`tool_choice: {type: "tool", name: "respond"}`）获得严格 JSON。
- GPT 系列：`POST /v1/chat/completions`，使用 `response_format: {type: "json_schema", strict: true}`。
- 兜底：若网关拒绝结构化参数，退回普通文本请求并从回复中提取 JSON。
- 每次调用超时 120 秒；网络错误、5xx、429 以及偶发的 404（EvoLink 临时路由错误）重试 1 次。

### 4.5 提示词原则

- 猜测模型系统提示包含：规则、候选集（emoji + 英文名）、剩余回合数、提问语言、输出格式要求。
- 猜测模型用户消息包含：到目前为止的完整问答轨迹。**绝不包含隐藏 emoji。**
- 裁判提示只包含：隐藏 emoji 及其英文名、当前问题。它看不到历史，避免被历史"带偏"。
- 最后一回合追加"必须 guess"的强提示。

## 5. HTTP API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/models` | 可选猜测模型 / 裁判模型列表 |
| GET | `/api/emojis` | 候选 emoji 列表 |
| POST | `/api/games` | 新建对局 `{model, mode, secretEmoji?, judgeModel?, language?}`（language 为 `zh` / `en`）；`secretEmoji` 缺省则随机；返回对局 + 模型第一个动作 |
| GET | `/api/games/{id}` | 查询对局 |
| POST | `/api/games/{id}/answer` | 人工回答 `{answer: yes/no}`；后端记录、判定、再次调用模型 |
| POST | `/api/games/{id}/auto-step` | 自动模式走一步：裁判回答当前问题 → 模型下一动作；可带 `{language}` 切换后续提问语言 |
| POST | `/api/games/{id}/next` | 在 `pending` 为空或 `status = error` 时重新向模型要下一动作（重试） |
| POST | `/api/batch` | 发起批量测试 `{models: [...], gamesPerModel, judgeModel}`，后台运行 |
| GET | `/api/batch/{id}` | 批量进度、每局结果、按模型统计（胜率、平均回合数、错误数） |

## 6. 网页

单页，只有**自动单局**，版式参考 `IMG_1133.png`。整局是**一个卡片**，自上而下：

1. **模型**：并排写明 Guess 模型和 Judge 模型（名称 + ID）；右侧是状态（进行中 / 已猜中 / 未猜中 / 出错）和回合数。
2. **Question log**：每行 `序号 · ask()/guess() · 内容 · Yes/No · Guess 用时 · Judge 用时 · 合计 · 该回合花费`。guess 行由后端规则判定，不调用 Judge，Judge 用时为空。
3. **答案**：对局结束后公布隐藏 emoji 和胜负。
4. **Overview**：三行 **Guess / Judge / Total**，列为 模型、调用次数、用时、Tokens、花费（美元 + credits）。对局进行中实时更新。

其他：顶部有 中文 / English 切换；`?autostart=1` 可打开即开始。

### 6.1 花费统计（EvoLink 真实扣费）

- EvoLink 文本接口的响应里没有金额，但 `GET /v1/credits` 返回本密钥累计已用 credits，且每次调用后立即更新。
- Dashboard 里的逐条扣费记录走的是登录会话接口，用 API 密钥访问不了（`/api/log/*` 返回 403，`/v1/tasks` 只列图片类任务），文档也只公开了 `/v1/credits`。
- 因此每次模型调用前后各查询一次 `/v1/credits`，**差值就是这次调用的真实扣费**（单位 credits）。实测整局统计与账户实际扣除完全一致。
- 美元 = credits × `EVOLINK_CREDIT_USD`（默认 0.0147，取自 EvoLink 定价页）。
- 兜底：多个调用并行时（批量测试）差值无法归到单次调用，或查询失败时，退回 token 用量 × `app/config.py` 单价估算，并在页面注明有几次是估算。
- 用时只计模型调用本身，不含查询 credits 的时间。
- 对局状态 `stats: {guess, judge, total}`，各含 `calls, ms, inputTokens, outputTokens, credits, cost, estimatedCalls`。
- 注意：同一个密钥若同时被别的程序使用，那部分扣费会被算进来。

### 6.2 提示词约束（实测后补充）

- 候选集以**不带分类**的平铺列表给猜测模型：裁判看不到候选表，按内部分类名提问会得到与表不一致的回答。
- 要求猜测模型只问现实属性，不重复提问，不重复猜已猜错的 emoji。
- **不要求模型输出思路**：让模型解释推理过程会触发 Anthropic 的 `reasoning_extraction` 安全拦截（Opus 5.5 实测返回 `stop_reason: refusal`）。
- `auto-step` 每次只做一件事（Judge 回答，或 Guess 出下一动作），页面因此能逐步刷新。

## 7. 命令行批量测试

`python scripts/run_batch.py --models claude-opus-5-5 gpt-6.1-sol --games 10`
输出每模型统计表，并把完整结果写入 `results/batch-<时间>.json`。

## 8. 运行方式

```bash
cp .env.example .env         # 填入 EVOLINK_API_KEY
uv sync                      # 或 pip install -r requirements.txt
uv run uvicorn app.main:app --reload
# 打开 http://127.0.0.1:8000
```

## 9. 后续可扩展（不在首版）

- SQLite 持久化，长期统计各模型表现
- 从 Unicode 官方列表扩展候选集
- 让人当"猜测者"、模型当裁判的反向玩法
- 多轮消息形式（assistant/user 交替）替代单条轨迹文本，对比效果
