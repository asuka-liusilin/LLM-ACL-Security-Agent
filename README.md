# ACL 智能运维与安全校验 Agent 原型系统

面向网络运维的**自然语言 ACL 配置生成、Python 独立安全校验与 Agent 受约束任务调度**原型。
本项目为本科阶段项目选题时的可运行 Web 原型，旨在验证“生成-校验”闭环的技术可行性，当前运行于离线沙箱环境。

> 核心原则：大模型只负责“生成候选配置”，是否正确由独立的 Python 规则模块判断，
> Agent 只负责在受限范围内调度流程；系统不连接、不下发任何真实网络设备。

---

## 一、项目用途

- 演示“自然语言需求 → 结构化 ACL → 独立校验 → Agent 决策 → 修正 / 补信息 / 人工审核”的完整闭环；
- 用可重复的测试用例说明“生成与校验分离”和“Agent 受约束调度”的作用；
- 为后续接入真实大模型 API、真实测试集与模拟器验证提供代码骨架。

你可以用它回答三个问题：

1. 大模型生成的 ACL 可能出什么错？（结构错误、IP 非法、授权范围扩大、宽泛放行、默认策略相反……）
2. 独立校验如何发现这些错误？（四项检查 + 明确错误代码 + 风险等级）
3. Agent 如何在“不许乱来”的前提下推进任务？（状态机、重试上限、高风险拦截、人工审核）

---

## 二、功能清单

### 已实现

| 模块 | 内容 |
| --- | --- |
| 项目总览 | 运行模式、任务状态、调用次数、校验结果四张状态卡；由真实任务状态驱动的 6 步流程图 |
| 智能配置工作台 | 自然语言输入、4 个可真实触发不同结果的示例、参数区、加载/成功/失败状态、结构化 JSON、规则表、校验摘要、Agent 决策、补充信息、人工审核、任务历史 |
| Agent 执行过程 | 10 状态状态机可视化（只点亮真实进入过的状态）、决策记录（含原因与错误代码）、按时间排序的执行日志、重试进度 |
| 安全校验报告 | 四个维度的检查卡片、问题清单表、严重程度汇总、校验口径与局限说明 |
| 测试用例与实验 | 12 条人工标注用例、单条/批量执行、三组对比实验（A/B/C）、后端计算指标、未运行/未统计的明确显示 |
| 项目说明 | 项目简介、技术架构、技术栈实现状态、状态机说明、安全边界、已知局限 |
| 后端 | FastAPI + Pydantic，任务接口、事件接口、反馈接口、审核接口、测试用例接口、指标接口 |
| 校验模块 | 结构 / 字段值 / 授权范围符合度 / 预定义风险规则，返回错误代码、风险等级、触发依据与建议 |
| Agent | 生成、校验、决策、有限重试、请求补充、转人工审核，全部行动带原因记录 |
| 状态机 | 10 个状态 + 允许转换表 + 终态保护 + 重试计数 |
| 测试 | 后端 64 项 pytest（全部通过）、前端基础交互测试 |

### 未实现 / 部分实现

- **真实大模型推理**：API 模式代码已实现（OpenAI 兼容协议），但本机默认未配置 Key，所有演示结果都标注为“演示模式”；
- **Token 与 API 成本统计**：只有真实调用返回 `usage` 时才统计，当前显示“未统计”；
- **任务持久化**：任务在内存 + 浏览器 localStorage 中，后端重启后详情丢失；
- **WebSocket / SSE**：使用 650ms 轮询替代；
- **厂商语法转换、ACL 规则顺序语义、真实设备 / 模拟器验证**：计划扩展；
- **需求解析**：演示模式用确定性规则解析中文，只能处理结构较明确的表述（复杂表述会进入 NEED_INFO 或标记“无法判断”）。

---

## 三、技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | React 18、TypeScript、Vite 5、Tailwind CSS 3、React Router 6、lucide-react |
| 后端 | Python 3.13、FastAPI、Pydantic v2、Uvicorn |
| 校验 | 标准库 `json`、`ipaddress`、`re` |
| 测试 | pytest、Vitest + Testing Library |
| 模型 | OpenAI 兼容 `/chat/completions`（可选） |

未使用数据库、未使用第三方 Agent 框架（Agent 为自研轻量级实现，便于解释与测试）。

---

## 四、项目目录

```
demo/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI 入口与全部 API
│   │   ├── schemas.py         # Pydantic 数据模型（ACL、校验结果、任务、事件）
│   │   ├── states.py          # 状态枚举、允许转换表、状态机
│   │   ├── intent_parser.py   # 演示模式的中文需求解析（确定性规则）
│   │   ├── generator.py       # 演示生成器 / 测试用固定配置 / 模型生成器
│   │   ├── validator.py       # 四项独立校验（核心）
│   │   ├── agent.py           # Agent 调度、决策、重试、人工审核
│   │   ├── testcases.py       # 12 条内置用例（含人工标注真值）
│   │   ├── test_runner.py     # A/B/C 三组流水线执行器
│   │   ├── metrics.py         # 指标计算与统计存储
│   │   ├── store.py           # 内存任务存储
│   │   ├── llm_client.py      # 可替换的模型客户端
│   │   └── config.py          # 环境变量配置
│   ├── tests/                 # pytest：校验、状态机、Agent、指标、API
│   ├── requirements.txt
│   └── pytest.ini
├── frontend/
│   ├── src/
│   │   ├── pages/             # 6 个页面
│   │   ├── components/        # 布局、流程图、校验视图、JSON 查看器等
│   │   ├── services/api.ts    # 后端调用封装
│   │   ├── store/             # 会话状态、轮询、本地历史
│   │   ├── types/             # 与后端对齐的 TS 类型
│   │   └── test/              # 前端测试
│   ├── package.json
│   └── vite.config.ts
├── .env.example
├── .gitignore
└── README.md
```

---

## 五、环境要求

- Windows 10/11（也适用于 macOS / Linux）、Git Bash 或 PowerShell
- **Python 3.11+**（本项目在 3.13 上开发验证）
- **Node.js 18+**（本项目在 22.22.2 上验证），npm 10+
- 无需任何网络设备、无需 Docker、无需数据库

> 国内网络提示：pip 与 npm 建议使用国内镜像（见下文命令）。

---

## 六、如何安装依赖

### 6.1 后端

在项目根目录 `demo/` 下执行（**每条命令单独一行，逐个回车**）：

```bash
cd backend
```

```bash
python -m venv .venv
```

Windows（Git Bash / PowerShell 均可用）：

```bash
.venv/Scripts/python.exe -m pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
```

macOS / Linux：

```bash
./.venv/bin/pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
```

### 6.2 前端

新开一个终端窗口，回到 `demo/` 目录：

```bash
cd frontend
```

```bash
npm install
```

说明：

- `frontend/.npmrc` 已经设置了 `legacy-peer-deps=true`，否则 npm 10 可能因
  `lucide-react` 与 React 版本校验报 `ERESOLVE` 错误；
- 如果下载很慢，可以换镜像：`npm install --registry=https://registry.npmmirror.com`；
- 如果 npm 卡住不动，通常是本机代理指向了未启动的端口，清掉代理变量再装：
  `HTTP_PROXY= HTTPS_PROXY= npm install`。

---

## 七、如何启动

### 7.1 启动后端（必须使用 `backend` 作为工作目录）

```bash
cd backend
```

```bash
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000
```

看到 `Uvicorn running on http://127.0.0.1:8000` 即成功。接口文档：<http://127.0.0.1:8000/docs>

### 7.2 启动前端

另开一个终端：

```bash
cd frontend
```

```bash
npm run dev
```

### 7.3 访问网页

浏览器打开：**<http://127.0.0.1:5173>**

前端通过 Vite 代理把 `/api` 转发到 `http://127.0.0.1:8000`，因此两个服务都要启动。

> 也可以 `cd frontend && npm run build`，后端启动时会自动托管 `frontend/dist`，
> 之后直接访问 <http://127.0.0.1:8000> 即可（单端口运行）。

---

## 八、演示模式与 API 模式

| | 演示模式（默认） | API 模式 |
| --- | --- | --- |
| 是否需要 Key | 不需要 | 需要 `LLM_API_KEY` |
| 配置来源 | 确定性规则生成器 | 真实模型服务 |
| 是否真实大模型推理 | **否** | 是 |
| 结果标注 | 明确标注“演示模式” | 标注模型名与真实调用次数 |
| 统计口径 | 生成器调用次数 | 真实 API 调用次数、Token（服务返回时） |

切换方式：工作台「任务参数 → 执行模式」下拉框；后端无 Key 时 API 模式选项为禁用状态。
**切换参数会真实传给后端并影响流程**，不是纯视觉控件。

---

## 九、如何配置模型 API Key（可选）

1. 复制 `.env.example` 为 `.env`（放在项目根目录 `demo/` 下）；
2. 填写（以 DeepSeek 为例）：

```ini
LLM_API_KEY=sk-xxxxxxxxxxxxxxxx
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
LLM_TIMEOUT=30
```

3. 重启后端。访问 `/api/health` 应看到 `"api_mode_available": true`。

安全约定：

- Key 只从**后端环境变量**读取，前端永远拿不到；
- `.env` 已在 `.gitignore` 中，不会被提交；
- 后端只把模型返回的文本按 JSON 解析，**绝不执行**其中任何内容；
- 调用失败（超时、HTTP 错误、非 JSON）会转成中文错误并作为可修正问题交给 Agent。

> 说明：API 模式下**需求解析仍由确定性规则完成**，模型只负责生成配置。
> 这样校验模块有一个独立于模型的授权范围基准，避免“模型自己理解、自己生成、自己判断”的循环论证。

---

## 十、如何运行自动化测试

### 后端（64 项）

```bash
cd backend
```

```bash
.venv/Scripts/python.exe -m pytest
```

覆盖：JSON 结构、非法 JSON、缺字段、非法 IP、非法 CIDR 前缀、授权范围扩大、宽泛放行拦截、
合法配置通过、NEED_INFO、有限重试、重试上限、高风险不可绕过、每次重生成后重新校验、
状态机非法转换、零分母指标、API 契约与错误处理。

### 前端

```bash
cd frontend
```

```bash
npm test
```

覆盖：页面加载、导航、示例填充、任务提交与结果渲染、空输入提示。

---

## 十一、API 一览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 后端状态、当前模式、是否可用 API 模式 |
| POST | `/api/tasks` | 创建任务并异步执行生成/校验/Agent 流程 |
| GET | `/api/tasks` | 任务摘要列表（内存） |
| GET | `/api/tasks/{id}` | 任务详情：状态、每次生成与校验、决策、事件、用量 |
| GET | `/api/tasks/{id}/events` | 事件与决策（轮询用） |
| POST | `/api/tasks/{id}/feedback` | 提交补充信息，继续 NEED_INFO 任务 |
| POST | `/api/tasks/{id}/review` | 人工审核：`approve` / `reject` / `request_changes` |
| GET | `/api/test-cases` | 内置用例及最近一次执行结果 |
| POST | `/api/test-cases/run` | 运行用例（`group`: `basic` / `validate` / `agent`） |
| GET | `/api/metrics` | 指标（未运行时返回 `NOT_RUN`） |
| POST | `/api/experiments/run` | 运行三组对比实验并返回指标 |
| POST | `/api/experiments/reset` | 清空本进程统计记录 |

统一数据模型：

```json
{
  "rules": [
    {
      "action": "permit",
      "protocol": "tcp",
      "source": "192.168.1.10/32",
      "destination": "10.0.0.10/32",
      "destination_port": 443
    }
  ],
  "default_action": "deny"
}
```

> 这是**项目统一中间模型**，不等同于任何厂商设备可直接使用的 ACL 语法。

---

## 十二、校验与风险规则（当前范围）

| 维度 | 检查内容 | 典型错误代码 |
| --- | --- | --- |
| A 结构 | JSON 可解析、`rules` 是数组、必要字段齐全、类型正确、无额外字段 | `JSON_PARSE_ERROR`、`MISSING_RULES`、`RULE_MISSING_FIELD`、`UNKNOWN_FIELD` |
| B 字段值 | `action` / `protocol` / `default_action` 取值、IP/CIDR 合法性（主机位须为 0）、IPv4 约束、端口范围 | `INVALID_SOURCE_IP`、`INVALID_PROTOCOL`、`INVALID_PORT`、`IP_VERSION_MISMATCH` |
| C 需求符合度 | 源/目标是否越权、动作是否相反、协议/端口是否被扩大 | `SOURCE_SCOPE_EXCEEDED`、`DESTINATION_SCOPE_EXCEEDED`、`ACTION_CONTRADICTS_INTENT`、`PORT_SCOPE_EXPANDED` |
| D 风险规则 | any→any 放行、单侧 0.0.0.0/0 放行、默认放行 | `BROAD_PERMIT_ANY`(CRITICAL/拦截)、`PERMIT_ANY_SOURCE`、`DEFAULT_PERMIT` |

风险等级：`INFO / LOW / MEDIUM / HIGH / CRITICAL`，由规则代码决定，不由模型“随口”给出。

**重要**：`permit ip any any` 在本数据模型下被视为重点审查的宽泛放行规则，
但真实风险还与规则顺序、ACL 应用位置、接口方向、设备默认行为有关。
本原型的规则集只覆盖已实现的检查范围，**不能替代完整的网络安全审计**。

---

## 十三、安全边界

1. 不连接、不修改任何真实网络设备，不自动下发配置；
2. 不要求用户提供设备管理员密码；
3. 模型 API Key 只存后端环境变量，前端与 Git 都没有；
4. 用户输入与模型输出都不会被当作系统命令执行；
5. 模型输出必须通过结构化解析 + 规则校验，校验未通过不得作为可用配置；
6. 命中 `BROAD_PERMIT_ANY` 等严重风险 → `BLOCKED`，普通重试不能绕过；
7. 关闭“高风险拦截”开关也不会让高风险配置变成 `SUCCESS`，只会转人工审核；
8. 最大重试次数 0–3，由状态机强制约束，超过即停止自动处理；
9. 无法判断需求符合度时标记“无法判断”，而不是默认通过（安全失败策略）；
10. 日志不记录 API Key；审核通过只代表确认候选配置，`deployed` 永远为 `false`。

---

## 十四、当前局限

- 演示模式不是真实大模型，**指标接近饱和（如召回率 100%）是规则与用例同源设计造成的**，不能作为方法有效的证明；
- 用例规模小（12 条），真值为作者手工标注，不是设备实测；
- 未处理 ACL 规则顺序、应用方向、设备语法差异；
- 需求解析规则有限，复杂句式会进入 NEED_INFO；
- 任务在内存中，后端重启后前端只能看到本地缓存摘要；
- 未接入计费，Token 与成本在有真实调用且服务返回 `usage` 前一律显示“未统计”。

---

## 十五、推荐的 3—5 分钟导师演示流程

1. **项目总览（20 秒）**：指出“当前没有执行任务，因此状态卡是空的”，说明系统不虚构数据；
   再讲下方 6 步流程图代表的技术路线。
2. **正常需求（40 秒）**：工作台点击「示例 A」→ 执行。展示需求解析、结构化 JSON、规则表、
   四项校验全部通过、Agent 决策“通过检查但仍需人工审核” → 点“批准配置”，强调 `未下发任何设备`。
3. **授权范围扩大 + 反馈修正（60 秒）**：点击「示例 C」执行。第一次校验命中
   `SOURCE_SCOPE_EXCEEDED`（HIGH），Agent 选择重新生成；第二次收敛回 `/32` 并通过校验（最终状态为“需要人工审核”）。
   在“修正过程对比”里说明每次重生成都会重新校验。
4. **宽泛放行 + 安全拦截（40 秒）**：点击「示例 D」执行。命中 `BROAD_PERMIT_ANY`(CRITICAL) →
   `BLOCKED`，说明即使把最大修正次数调到 3，也只会生成 1 次并直接拦截（可在参数区现场改）。
5. **需要补充信息（30 秒）**：点击「示例 B」执行 → `NEED_INFO`，填入
   “源地址 192.168.1.10，目标地址 10.0.0.10，HTTPS 服务” → 任务继续并给出结果。
6. **执行过程与报告（40 秒）**：打开「Agent 执行过程」看状态机只点亮真实进入的状态、决策原因与日志；
   再打开「安全校验报告」说明四个维度与“通过 ≠ 绝对安全”。
7. **测试与实验（60 秒）**：进入「测试用例与实验」→ 运行全部用例（12/12 符合预期）→
   运行三组对比实验，指出 A 组没有校验能力所以指标为“未统计”、C 组有修正成功率；
   强调这些是演示模式自测数据，接入真实模型后需重新评估。

---

## 十六、常见问题

**Q：页面显示“后端未连接”？**
A：因为后端服务部署在 Render 免费云服务器上，为了节省资源，系统在长时间无访问时会自动休眠（冷启动机制）。首次访问时，服务器需要 30~50 秒进行唤醒。请耐心等待半分钟后**刷新页面**，即可恢复正常连接。。

**Q：为什么示例 D 无法“修正成合法配置”？**
A：该风险不可通过简单重生成消除，按设计必须人工处理，这正是要展示的安全边界。

**Q：历史任务点开报错？**
A：后端重启后内存任务清空。前端会提示并用本地缓存展示摘要。

**Q：审核通过后配置会下发吗？**
A：不会。审核只改变任务状态并记录审核意见，接口始终返回 `deployed: false`。
