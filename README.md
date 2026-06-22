# Pydantic AI Web Console

一个可本地启动、可演示、可测试的 Web 智能体控制台。后端使用 Python，Agent 层基于 `pydantic-ai-slim`，并提供：

- 多轮会话聊天
- Agent 流式输出与执行状态展示
- 本地 `SKILL.md` Skills 列表
- MCP Server 配置与状态展示
- 工具调用日志展示
- 本地 stdio mock MCP Server
- 可切换到火山方舟真实大模型

## 架构说明

当前项目的 Agent 内核已经是 Pydantic 体系：

- Agent 框架：`pydantic-ai-slim`
- 真实模型：`OpenAIChatModel + OpenAIProvider`
- MCP 接入：`pydantic_ai.mcp.MCPServerStdio / MCPServerSSE / MCPServerStreamableHTTP`
- 前端：FastAPI 提供静态页面与 SSE

说明：

- 题目中写的是 `pydantic-deepagents`
- 当前实现采用的是可安装、可运行的 Pydantic AI 体系，即 `pydantic-ai-slim`

## 技术选型

- 后端: FastAPI
- Agent: `pydantic-ai-slim`
- MCP 接入: `mcp` + `pydantic_ai.mcp`
- 真实模型接入: 火山方舟 OpenAI 兼容接口
- 前端: 原生 HTML / CSS / JavaScript
- 测试: `pytest`

## 项目结构

```text
app/
  main.py              # FastAPI 入口
  api.py               # HTTP / SSE 接口
  agent.py             # Pydantic AI Agent、mock/ark 模型切换、事件映射
  config.py            # 环境变量与 MCP 配置解析
  skills.py            # Skill 发现
  session_store.py     # 会话与模型消息历史存储
  mcp/
    service.py         # MCP server 构造与状态探测
    mock_server.py     # 本地 stdio mock MCP server
  static/
    index.html         # 对话页
    logs.html          # 工具日志页
    app.js
    logs.js
    styles.css
skills/
  code-review/SKILL.md
  test-generator/SKILL.md
  data-analysis/SKILL.md
tests/
```

## 核心能力

### 1. 聊天与会话

- 支持多轮对话
- 支持新建会话
- 支持重置当前会话
- 会话历史保存在服务进程内存中
- 除了前端消息历史，还会保存 Pydantic AI 的 `message_history`

### 2. Skills

内置 3 个本地 Skill：

- `code-review`
- `test-generator`
- `data-analysis`

Skill 采用 `SKILL.md` 目录结构，前端和 `/api/skills` 都可以查看。

### 3. MCP

默认配置了一个本地 stdio MCP Server：

- `mock-tools`

它暴露三个示例工具：

- `mock-tools_summarize_text`
- `mock-tools_time_now`
- `mock-tools_echo_json`

前端会展示：

- MCP Server 是否连接成功
- 当前加载到的工具名

## 启动方式

### 1. 创建虚拟环境并安装依赖

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -U pip
.\.venv\Scripts\python -m pip install -e .[dev]
```

### 2. 准备环境变量

```powershell
Copy-Item .env.example .env
```

### 3. 启动服务

```powershell
.\.venv\Scripts\python -m uvicorn app.main:app --reload
```

打开：

- `http://127.0.0.1:8000/` 对话页
- `http://127.0.0.1:8000/logs` 工具日志页

## LLM 模式

项目支持两种模式：

### 1. `mock`

默认值：

```env
LLM_MODE=mock
```

特点：

- 不依赖外部模型
- 适合本地演示和测试
- 基于 `pydantic_ai.models.function.FunctionModel`
- Skill / MCP / 会话 / 工具日志都能完整演示

### 2. `ark`

使用火山方舟真实模型：

```env
LLM_MODE=ark
ARK_API_KEY=你的密钥
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
ARK_MODEL=doubao-seed-2-0-lite-260215
```

当前实现走的是火山方舟 OpenAI 兼容接口，对应你给的 curl：

```bash
curl https://ark.cn-beijing.volces.com/api/v3/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ARK_API_KEY" \
  -d '{
    "model": "doubao-seed-2-0-lite-260215",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Hello!"}
    ]
  }'
```

在本项目中，不需要自己手写这个 curl，设置好环境变量后直接启动服务即可。

## 火山方舟接入步骤

1. 编辑 `.env`

```env
LLM_MODE=ark
ARK_API_KEY=你的 ARK API Key
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
ARK_MODEL=doubao-seed-2-0-lite-260215
```

2. 启动服务

```powershell
.\.venv\Scripts\python -m uvicorn app.main:app --reload
```

3. 打开页面后直接聊天

此时 Agent 会使用真实方舟模型推理，而不是本地 mock 模型。

## 环境变量

见 [.env.example](/D:/gowork/agent/.env.example:1)

重点变量：

- `LLM_MODE`
  可选 `mock` / `ark`
- `ARK_API_KEY`
  火山方舟 API Key
- `ARK_BASE_URL`
  默认为 `https://ark.cn-beijing.volces.com/api/v3`
- `ARK_MODEL`
  默认为 `doubao-seed-2-0-lite-260215`
- `MCP_SERVERS_JSON`
  MCP Server 列表，JSON 字符串
- `SKILLS_DIR`
  本地 Skills 根目录
- `PROJECT_ROOT`
  项目根目录

## MCP 配置说明

### 本地 stdio

默认配置示例：

```json
[
  {
    "name": "mock-tools",
    "transport": "stdio",
    "enabled": true,
    "command": ".venv\\Scripts\\python",
    "args": ["-m", "app.mcp.mock_server"],
    "cwd": ".",
    "env": {}
  }
]
```

### 远程 HTTP / SSE

也可以把 `MCP_SERVERS_JSON` 改成远程配置，例如：

```json
[
  {
    "name": "remote-mcp",
    "transport": "http",
    "enabled": true,
    "url": "http://127.0.0.1:9000/mcp"
  }
]
```

如果没有真实 MCP Server：

- 可以直接使用项目内置的 `mock-tools`
- 或把远程 MCP 配置禁用，系统会降级为仅使用本地 Skill 与内置工具

## 测试

```powershell
.\.venv\Scripts\python -m pytest -q
```

当前本地最近一次执行结果：

```text
  platform win32 -- Python 3.13.1, pytest-9.1.1, pluggy-1.6.0
  rootdir: D:\gowork\agent
  configfile: pyproject.toml
  testpaths: tests
  plugins: anyio-4.14.0, langsmith-0.8.18, asyncio-1.4.0
  asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
  collected 10 items                                                                                                                                       
  
  tests\test_agent.py .....                                                                                                                          [ 50%]
  tests\test_config.py ...                                                                                                                           [ 80%]
  tests\test_session_store.py .                                                                                                                      [ 90%]
  tests\test_skills.py .                                                                                                                             [100%]

```

测试覆盖与题目要求的对应关系：

- Skill 发现
  对应 [tests/test_skills.py](/D:/gowork/agent/tests/test_skills.py:1)
- Agent 创建
  对应 [tests/test_agent.py](/D:/gowork/agent/tests/test_agent.py:1) 中的 `test_agent_runtime_creation`
- 配置解析
  对应 [tests/test_config.py](/D:/gowork/agent/tests/test_config.py:1)
- 会话持久化
  对应 [tests/test_session_store.py](/D:/gowork/agent/tests/test_session_store.py:1)
- 工具结果格式化
  对应 [tests/test_agent.py](/D:/gowork/agent/tests/test_agent.py:1)

交付说明：

- 评审方可以直接运行上面的 `pytest` 命令验证
- 也可以查看仓库中的 GitHub Actions CI 自动测试结果

## 演示建议

进入页面后可尝试：

- `请展示可用的 skill，并看看 code-review skill 适合做什么`
- `帮我做一次代码评审，下面这段python代码：
def calc_price(num):
    return num * 10`
- `基于刚才的问题，补充更多极端边界测试`
- `现在时间是什么？`

## 已知限制

- `mock` 模式重点是保证离线可演示与可测试，不是完整智能推理。
- 会话历史当前持久化到本地 `SESSION_STORE_PATH` 指定的 JSON 文件。
- 当前只实现了基础单用户控制台，不含鉴权。
- 工具日志展示的是核心事件，不是完整 tracing。
- `ark` 模式依赖外部 API 可用性、网络连通性和有效的 `ARK_API_KEY`。
