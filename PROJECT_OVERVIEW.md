# 仿版 Codex — 任务编排引擎 项目说明

## 一、项目概述

这是一个智能任务编排引擎，模仿 GitHub Copilot / OpenAI Codex 的任务处理思路。用户输入自然语言需求后，系统自动完成 5 个阶段：**分析复杂度 → 拆解子任务 → 分配模型 → 并行执行 → 聚合结果**。

核心思路：不是所有问题都需要"大模型深思熟虑"，简单翻译用便宜模型就够了，复杂重构才调度强模型和多模型协作。

## 二、文件结构

```
codex-clone/
├── server.py                  # 启动入口
├── main.py                    # FastAPI 应用 + 全部 API 路由
├── config.yaml                # 模型配置 + 路由策略配置
├── requirements.txt           # Python 依赖
├── .env                       # API Key（DeepSeek）
├── test_client.py             # 测试脚本
├── frontend/
│   └── index.html             # Web 前端界面（中文）
└── codex/                     # 核心引擎模块
    ├── models.py              # Pydantic 数据模型定义
    ├── config.py              # 配置加载逻辑
    ├── analyzer.py            # 第1阶段：复杂度分析器
    ├── decomposer.py          # 第2阶段：任务拆解器
    ├── router.py              # 第3阶段：模型路由器
    ├── executor.py            # 第4阶段：DAG 并行执行器
    ├── aggregator.py          # 第5阶段：结果聚合器
    ├── pipeline.py            # 流水线编排器（串联5阶段）
    └── adapters/
        ├── base.py            # LLM 适配器抽象基类
        ├── openai_compat.py   # OpenAI 兼容协议适配器
        └── registry.py        # 适配器注册中心
```

## 三、各文件详细说明

### server.py — 启动入口
- 自动加载 `.env` 中的环境变量
- 用 uvicorn 启动 FastAPI 服务，监听 `0.0.0.0:8000`
- 开启热重载（reload=True）

### main.py — API 应用
FastAPI 应用，注册了以下接口：

| 路由 | 方法 | 功能 |
|------|------|------|
| `/` | GET | 返回前端页面 `frontend/index.html` |
| `/execute` | POST | **完整流水线**：分析→拆解→路由→执行→聚合，一步到位 |
| `/analyze` | POST | **仅分析**：只做复杂度评估，不拆解不执行 |
| `/decompose` | POST | **分析+拆解**：返回复杂度和 DAG，不执行 |
| `/task/{task_id}` | GET | 查询异步任务状态和结果 |
| `/models` | GET | 查看所有注册的可用模型 |
| `/health` | GET | 健康检查 |
| `/static` | - | 静态文件服务（前端 CSS/JS） |

### config.yaml — 配置文件
- **models 段**：注册了 6 个模型（deepseek-chat、deepseek-reasoner、qwen-max、qwen-plus、glm-4、ernie-4.0），每个模型配置了 provider、endpoint、api_key_env、capabilities、cost_per_1k_tokens、max_tokens
- **routing 段**：配置分析/拆解/执行的默认模型、并行阈值（≥3 个独立子任务时并行）、是否冗余执行关键任务、最大重试次数、超时时间

### .env — 密钥文件
当前配置了 DeepSeek API Key

### requirements.txt — 依赖
```
fastapi
uvicorn
openai
pyyaml
pydantic
httpx
```

### frontend/index.html — Web 前端
- 纯 HTML/CSS/JS 单页应用，中文界面
- 顶部输入需求描述和上下文
- 三个按钮：完整执行、仅分析、分析+拆解
- 展示复杂度评估结果（等级、类型、预估子任务数、判断理由）、DAG 可视化、最终输出
- 调用后端 `/execute`、`/analyze`、`/decompose` 接口

---

### codex/models.py — 数据模型（Pydantic）
定义了所有核心数据结构：
- **ComplexityLevel**：枚举，simple / medium / complex
- **TaskType**：枚举，code_generation / bug_fix / refactor / analysis / question / other
- **ComplexityAssessment**：复杂度评估结果（level、task_type、estimated_subtasks、reasoning）
- **SubTask**：单个子任务（id、description、dependencies、assigned_model、status、result、error、attempts）
- **TaskDAG**：子任务组成的 DAG 图，包含拓扑排序、环检测、获取就绪任务等方法
- **SubtaskResult**：子任务执行结果
- **AggregatedResult**：聚合后的最终结果（summary、subtask_results、final_output）
- **TaskState**：完整任务状态（贯穿整个流水线）
- **ExecuteRequest / ExecuteResponse**：API 请求/响应模型

### codex/config.py — 配置加载
- 从 `config.yaml` 读取并解析为 `AppConfig` 和 `ModelConfig` 数据类
- 支持环境变量展开（如 `${DEEPSEEK_API_KEY}`）

### codex/analyzer.py — 复杂度分析器（第1阶段）
- 用 LLM 分析用户需求的复杂度
- 发送 system prompt 给模型，要求返回 JSON：`{level, task_type, estimated_subtasks, reasoning}`
- 从 3 个维度判断：子任务数量、依赖关系、领域知识广度
- 分类规则：简单（单步无依赖）、中等（2-3步有依赖）、复杂（4+步跨领域）
- 解析失败时有 fallback 默认值（medium / other / 1 subtask）

### codex/decomposer.py — 任务拆解器（第2阶段）
- 将需求拆解为 DAG 子任务图
- 简单任务直接跳过拆解，作为一个子任务执行
- 中/复杂任务用 LLM 生成子任务列表（JSON），每个子任务含 id、description、dependencies
- 返回 TaskDAG，自动检测并修复环

### codex/router.py — 模型路由器（第3阶段）
根据复杂度级别分配模型：
- **simple**：选最快/最便宜的模型（capabilities 含 "fast" 或按 cost 排序）
- **medium**：用默认执行模型
- **complex**：轮询分配多个模型以并行执行

### codex/executor.py — DAG 并行执行器（第4阶段）
- 按拓扑顺序执行子任务：每轮取出所有"依赖已满足"的任务并行运行
- 将已完成任务的输出作为上下文传给后续依赖任务
- 支持自动重试（最多3次，退避 1s/2s/4s）
- 支持超时控制

### codex/aggregator.py — 结果聚合器（第5阶段）
- 1 个子任务时直接返回，无需聚合
- 多个子任务时用 LLM 合并：去重、解决矛盾、按逻辑排序
- 聚合失败时 fallback 为简单拼接

### codex/pipeline.py — 流水线编排器
- 串联全部 5 个阶段
- 维护任务状态字典（内存中），支持按 task_id 查询
- 提供 `analyze_only()` 和 `decompose_only()` 两个轻量方法

---

### codex/adapters/base.py — 适配器基类
抽象类 `BaseLLMAdapter`，定义 `chat(messages, temperature, response_format)` 接口

### codex/adapters/openai_compat.py — OpenAI 兼容适配器
用 `openai` 库调用任意兼容 OpenAI 协议的 API（DeepSeek、Qwen、GLM、文心等），自动从环境变量读取 API Key

### codex/adapters/registry.py — 适配器注册中心
- 初始化时为 config 中每个模型创建对应的 adapter 实例
- `get(model_name)` 按名称获取适配器
- `close_all()` 关闭所有连接

## 四、核心流程示意

```
用户输入："帮我写一个用户登录系统，包含注册、登录、JWT鉴权"
    │
    ▼
[1. 分析] LLM判断 → complex / code_generation / 预估5个子任务
    │
    ▼
[2. 拆解] LLM生成DAG →
    ├─ 1. 设计数据库模型（无依赖）
    ├─ 2. 实现注册接口（依赖1）
    ├─ 3. 实现登录接口（依赖1）
    ├─ 4. 实现JWT中间件（依赖3）
    └─ 5. 聚合所有代码并写测试（依赖1,2,3,4）
    │
    ▼
[3. 路由] complex → 轮询分配 deepseek-chat / qwen-plus / glm-4 等
    │
    ▼
[4. 执行] 第1层并行：[1] → 完成
         第2层并行：[2, 3] → 都完成
         第3层：[4] → 完成
         第4层：[5] → 完成
    │
    ▼
[5. 聚合] LLM合并所有子任务输出 → 完整代码 + 说明
```

## 五、启动方式

```bash
cd codex-clone
pip install -r requirements.txt
python server.py
# 浏览器打开 http://localhost:8000
```

## 六、当前待完善的问题

1. **界面不够直观**：比赛展示时，评委不熟悉怎么输入需求，缺少引导示例和快速体验入口
2. **复杂度判断依赖单一 LLM**：analyzer.py 完全依赖 LLM 判断，解析失败时 fallback 为 medium，可以加规则引擎做 hybrid 判断
3. **DAG 可视化太简单**：前端只有文本展示，缺少图形化的 DAG 依赖图
4. **任务状态仅存内存**：重启后丢失，未对接数据库持久化
5. **只有 DeepSeek API Key**：config.yaml 配置了 6 个模型但只有 DeepSeek 的 key，其他模型未配置
6. **没有流式输出**：execute 接口是同步等待全部完成才返回，等待时间长
7. **缺少异步任务模式**：大任务应该先返回 task_id，后台执行，前端轮询
8. **结果对比功能**：complex 任务多模型执行时，看不到不同模型的输出对比
9. **缺少使用示例/模板库**：用户不知道能问什么
10. **没有历史记录**：查不到之前执行过的任务
