# Emoji 二十问（twenty cool calls）

[English](README.md) | **简体中文**

藏好一个 emoji，给模型 20 个回合，只能得到“是”或“否”的回答。一个大模型（**Guess** 猜测模型）负责提问和猜测，另一个大模型（**Judge** 裁判模型）知道答案，只回答 YES 或 NO。每一局都会列出完整的提问记录，以及每次调用的用时、Tokens 和真实花费，方便比较不同模型缩小范围的能力。

所有模型（Claude 和 GPT）都通过 [EvoLink](https://evolink.ai) 网关调用，只需要一个 API Key。完整规格见 [spec.md](spec.md)。

## 环境要求

- Python 3.11 或更高版本
- [uv](https://docs.astral.sh/uv/)（推荐），或者直接用 `pip`
- 一个有余额的 EvoLink 账号

## 快速开始

### 1. 领取 EvoLink API Key

1. 打开 <https://evolink.ai/dashboard/keys> 并登录（没有账号先注册）。
2. 新建一个 API Key 并复制，通常以 `sk-` 开头。

### 2. 把 Key 填入环境文件

```bash
cp .env.example .env
```

打开 `.env`，把占位符换成你的 Key：

```dotenv
EVOLINK_API_KEY=sk-你的真实密钥
```

`.env` 已写在 `.gitignore` 里。不要提交它，也不要把 Key 发给别人。

### 3. 安装并启动

用 uv：

```bash
uv sync
uv run uvicorn app.main:app --reload
```

或者用 pip：

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload
```

### 4. 开始玩

打开 <http://127.0.0.1:8000>。

1. 选择 **Guess** 模型、**Judge** 模型和隐藏 emoji（留空则随机）。
2. 点击开始，对局会自动一回合一回合地进行。
3. 右上角可以切换 中文 / English，界面文字和模型提问的语言会一起切换。

结果卡片包含：

- 顶部并排写明 Guess 和 Judge 各自使用的模型
- 提问记录，每行有：动作、内容、Yes / No、Guess 用时、Judge 用时、合计
- 底部概览三行（Guess、Judge、Total）：调用次数、用时、Tokens、花费

如果某次模型调用失败，对局会停在错误状态，点击“重试”可以继续同一局。

## 让 AI Agent 帮你配置

如果你用编程 Agent（Claude Code、Cursor、Codex 等），在 Agent 里打开本项目目录，把下面这段提示词发给它。Agent 会安装依赖，打开浏览器让你登录并获取 Key，把 Key 写进 `.env`，然后启动项目。

```text
请帮我配置并运行这个项目，按顺序完成下面的步骤。

1. 阅读 README.zh-CN.md 和 .env.example，了解项目。

2. 如果 .env 不存在，复制 .env.example 生成 .env。
   如果 .env 里已经有真实的 EVOLINK_API_KEY（不为空，也不是
   "your_key_here"），直接跳到第 5 步。

3. 在浏览器中打开 https://evolink.ai/dashboard/keys 。
   - 如果你有浏览器工具，就用它打开；否则执行系统命令
     （macOS：open <网址>，Linux：xdg-open <网址>，Windows：start <网址>）。
   - 如果页面要求登录，停下来等我自己登录或注册。
     不要替我输入密码或任何登录凭据。
   - 我登录之后，在该页面新建一个 API Key（命名为
     "emoji-twenty-questions"）并复制。如果你无法读取或操作页面，
     就请我自己创建 Key，然后粘贴给你。

4. 把 Key 写入 .env，作为 EVOLINK_API_KEY 的值，替换掉占位符。
   文件里的其他内容不要改。不要在对话、日志或命令输出里打印 Key，
   不要把它写进其他任何文件，也绝不要提交 .env。

5. 安装依赖并启动服务：
     uv sync
     uv run uvicorn app.main:app --reload
   如果没有安装 uv，改用：
     python3.11 -m venv .venv
     .venv/bin/pip install -r requirements.txt
     .venv/bin/uvicorn app.main:app --reload
   让服务在后台运行，保持不退出。

6. 检查配置是否成功：
     curl -s http://127.0.0.1:8000/api/models
   返回里的 "apiKeyConfigured" 必须是 true。这只能说明 Key 不为空，
   所以还要真正开一局来确认 Key 可用：
     curl -s -X POST http://127.0.0.1:8000/api/games \
       -H 'Content-Type: application/json' \
       -d '{"model":"claude-sonnet-5-5","mode":"auto"}'
   如果返回里有 "status":"error"，把 "error" 的内容告诉我，
   并先解决问题（Key 错误、余额不足、网络不通）再继续。

7. 在浏览器中打开 http://127.0.0.1:8000 ，然后告诉我已经可以用了。
```

## 命令行批量测试

让每个模型跑多局，统计胜率：

```bash
uv run python scripts/run_batch.py --models claude-opus-5-5 gpt-6.1-sol --games 10
```

| 参数 | 默认 | 说明 |
|---|---|---|
| `--models` | 所有已注册模型 | 要测试的猜测模型 ID |
| `--games` | `5` | 每个模型跑多少局 |
| `--judge` | `JUDGE_MODEL` | 裁判模型 ID |
| `--concurrency` | `3` | 同时进行的对局数 |

脚本会打印每个模型的胜、负、错误数、胜率和平均回合数，完整结果写入 `results/batch-<时间>.json`。

## 环境变量

只有 `EVOLINK_API_KEY` 是必填的。修改 `.env` 后需要重启服务。每个变量的详细说明见 [.env.example](.env.example)。

| 变量 | 默认 | 说明 |
|---|---|---|
| `EVOLINK_API_KEY` | 必填 | EvoLink 密钥，在 <https://evolink.ai/dashboard/keys> 领取 |
| `EVOLINK_BASE_URL` | `https://direct.evolink.ai` | 网关地址。默认线路不通时换成 `https://api.evolink.ai` |
| `JUDGE_MODEL` | `claude-sonnet-5-5` | 默认裁判模型，页面下拉框可以覆盖 |
| `QUESTION_LANGUAGE` | `中文` | 批量脚本的提问语言。网页以右上角的语言切换为准 |
| `MAX_TURNS` | `20` | 每局回合上限 |
| `LLM_TIMEOUT` | `120` | 单次模型调用超时（秒） |
| `EVOLINK_CREDIT_USD` | `0.0147` | 1 个 EvoLink credit 折合多少美元，用于换算花费 |

## 模型

| ID | 名称 | 接口 |
|---|---|---|
| `claude-opus-5-5` | Claude Opus 5.5 | `POST /v1/messages` |
| `claude-sonnet-5-5` | Claude Sonnet 5.5 | `POST /v1/messages` |
| `claude-fable-5-1` | Claude Fable 5.1 | `POST /v1/messages` |
| `gpt-6.1-sol` | GPT-6.1 Sol | `POST /v1/chat/completions` |
| `gpt-6-astra` | GPT-6 Astra | `POST /v1/chat/completions` |

要增删模型，修改 [app/config.py](app/config.py) 里的 `MODELS` 列表。`provider` 字段决定走哪种接口：`anthropic` 用强制工具调用拿严格 JSON，`openai` 用 `response_format=json_schema`。网关若拒绝结构化输出参数，程序会自动退回纯文本并从中提取 JSON。

## 后端强制执行的规则

1. **回合上限。** 每次 ask 和每次 guess 都消耗 1 回合。最后一回合会明确要求模型必须 guess。20 回合内没猜中即判负。
2. **答案隔离。** 猜测模型的提示词里永远不含隐藏 emoji，对局进行中 API 也不返回它。只有裁判能看到答案和当前问题。

隐藏 emoji 来自 [app/emojis.py](app/emojis.py) 里精选的 111 个差异明显的 emoji。猜了候选集之外的 emoji 算猜错。

## 花费如何统计

花费是 EvoLink 的真实扣费：每次调用前后各查询一次 `/v1/credits`，取差值，再按 `EVOLINK_CREDIT_USD` 折算成美元。批量测试时多个调用同时进行，扣费无法归到单次调用，这时改用 [app/config.py](app/config.py) 里的 token 单价估算。

## 项目结构

```
app/main.py      FastAPI 路由
app/game.py      游戏状态与规则执行
app/guesser.py   猜测模型的提示词（永远不含答案）
app/judge.py     裁判模型的提示词
app/llm.py       EvoLink 客户端，适配 Claude 和 GPT 两种接口
app/batch.py     批量测试与统计
app/emojis.py    候选 emoji 集
app/config.py    环境变量与模型注册表
static/          网页（纯 HTML、CSS、JS）
scripts/         命令行批量脚本
```

对局状态保存在内存里，服务重启后对局会丢失。

## 常见问题

| 问题 | 解决办法 |
|---|---|
| 页面顶部提示没有配置密钥 | `.env` 里的 `EVOLINK_API_KEY` 为空。填好后重启服务 |
| 对局因鉴权错误停止 | Key 写错、已被删除，或者还是占位符。到 <https://evolink.ai/dashboard/keys> 重新创建 |
| 对局因余额或额度错误停止 | 到 EvoLink 控制台充值 |
| 超时或连接失败 | 设置 `EVOLINK_BASE_URL=https://api.evolink.ai`，或调大 `LLM_TIMEOUT` |
| 改了 `.env` 没有生效 | 重启服务。`--reload` 只监听代码文件 |
| macOS 开了系统代理 | 访问网关的请求会走代理。访问 `127.0.0.1` 和 `localhost` 的请求是直连，本地模拟网关仍可使用 |
