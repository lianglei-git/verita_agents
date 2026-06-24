### 功能1
负责展示每个agent的功能。

1： 用户输入
2： 调用系统agent，返回相应结果
3： 可查看数据结构，以及上下游关系。

时间轴功能，就是作为每个agent的上下游关系路径。点击每个不同的时间轴可跳转至不同的agent面板

项目架构：简单即可

前端：vite + react， 无需使用 ts 

后端: python 

公共文件：工作流配置json（实际可以放在接口返回中）、api接口json（前端调用，后端配置）。

前端职责：负责展示页面，调用接口，由于需要css、less交互等相对美观和复杂的需求，所以独立前端项目。

后端职责：负责承载多个agent的入口，对接测试和使用。每个agent可以理解为是一个sdk

---

## 文档

| 文档 | 内容 |
|------|------|
| [docs/DESIGN.md](docs/DESIGN.md) | 架构：全链路 Console + 单 Agent 工作台 + 嵌套自定义 UI |
| [docs/AGENT-CONFIG.md](docs/AGENT-CONFIG.md) | **极简 3 步**把 `agents/` 下小项目接入 Views |
| [../agents/README.md](../agents/README.md) | 仓库根 `agents/` 目录约定 |

## 目录结构

```
views/
├── run.py
├── requirements.txt
├── docs/                   # 设计 & 接入文档
├── backend/
├── frontend/
└── shared/
    ├── agents.manifest.json   # 注册 agents/ 下的 SDK
    └── workflows/             # demo-pipeline · mvp-pipeline ...
```

```
agents/                        # 仓库根目录（与 views 平级）
├── _template/                 # 复制此目录新建 agent
├── echo/                      # 接入示例
└── user-profile/              # 按 prd 逐步添加
```

## 启动方式

```bash
# 1. 安装 Python 依赖
pip install -r views/requirements.txt

# 2. 安装前端依赖
cd views/frontend && npm install

# 3. 开发模式（Flask API + Vite，一条命令）
cd views && python run.py

# 4. 生产模式（build 后由 Flask 挂载 dist）
cd views && python run.py --prod
```

- 开发：浏览器访问 `http://127.0.0.1:5173`
  - `/` 流水线调试台
  - `/agents` 独立工作台列表
  - `/agent/{id}` 单 Agent 调试（如 `/agent/user-profile`）
- 生产：浏览器访问 `http://127.0.0.1:5000`，Flask 同时提供 API 与静态页面

## 接入新 Agent（摘要）

1. `cp -r agents/_template agents/{your-id}`
2. 实现 `agent.py` 的 `run()`，填写 `config.json`
3. 在 `views/shared/agents.manifest.json` 注册

详见 [docs/AGENT-CONFIG.md](docs/AGENT-CONFIG.md)。

切换 MVP 全链路工作流：`GET /api/workflow?name=mvp-pipeline`

## 执行历史与上下游数据

每次运行 Agent 会自动创建/追加到执行记录（Run），记录各节点的：

- **上游参数 / 上游结果**
- **当前 Agent 参数 / 结果**
- **下游参数 / 下游结果**（下游执行后填充）

左侧「运行记录」可点击任意记录进行 **回顾（Review）**，只读查看当时的上下游数据。

### 相关 API

| 端点 | 用途 |
|------|------|
| `POST /api/runs` | 创建新执行 |
| `GET /api/runs` | 历史列表 |
| `GET /api/runs/{id}/context/{agent_id}` | 回顾某次执行的上下游数据 |
| `POST /api/runs/{id}/execute/{agent_id}` | 在执行记录中运行 agent |
| `GET /api/workflow?name=` | 加载指定工作流 |

## 扩展 Agent

- **实现**：`agents/{id}/` 独立开发
- **注册**：`shared/agents.manifest.json`
- **流水线**：`shared/workflows/*.json` 的 `execution_order`
- **自定义 UI**（可选）：`frontend/src/agents/{id}/` + `config.json` 中 `"view": {"type": "custom"}`
- **LLM**：使用 `agents/_lib/llm`，见 [agents/README.md](../agents/README.md)
