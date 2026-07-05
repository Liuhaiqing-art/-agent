"""任务编排引擎 - Task Orchestration API"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.base import BaseHTTPMiddleware

from codex.adapters.registry import AdapterRegistry
from codex.config import load_config
from codex.models import ExecuteRequest, ExecuteResponse, ModelsResponse
from codex.pipeline import Pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("codex")

config = load_config()
registry = AdapterRegistry(config)
pipeline = Pipeline(config, registry)

BEIJING_TZ = timezone(timedelta(hours=8))


class BeijingTimeMiddleware(BaseHTTPMiddleware):
    """将响应头 Date 改为北京时间"""

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        now = datetime.now(BEIJING_TZ)
        response.headers["Date"] = now.strftime("%a, %d %b %Y %H:%M:%S GMT+8")
        return response


app = FastAPI(
    title="任务编排引擎",
    description="""智能分析用户需求复杂度，自动拆解为子任务 DAG，调度多模型并行执行，聚合结果输出。

### 核心能力
- **复杂度分析**：自动判断任务是简单/中等/复杂
- **任务拆解**：将复杂任务拆成 DAG 依赖图
- **多模型调度**：根据难易度分配合适的模型
- **并行执行**：无依赖的子任务并发运行
- **结果聚合**：合并多个输出为完整答案
""",
    version="1.0.0",
)

app.add_middleware(BeijingTimeMiddleware)


@app.on_event("shutdown")
async def shutdown():
    """服务关闭时清理连接"""
    await registry.close_all()


@app.post("/execute", response_model=ExecuteResponse, summary="完整流水线执行")
async def execute(request: ExecuteRequest):
    """运行完整 5 阶段流水线：分析复杂度 → 拆解任务 → 分配模型 → 并行执行 → 聚合结果"""
    if not request.requirement.strip():
        raise HTTPException(status_code=400, detail="需求不能为空")
    return await pipeline.execute(request)


@app.post("/analyze", summary="分析需求复杂度")
async def analyze(request: ExecuteRequest):
    """仅执行复杂度分析，不拆解也不执行"""
    if not request.requirement.strip():
        raise HTTPException(status_code=400, detail="需求不能为空")
    assessment = await pipeline.analyze_only(request.requirement, request.context)
    return assessment.model_dump()


@app.post("/decompose", summary="分析并拆解任务")
async def decompose(request: ExecuteRequest):
    """分析需求复杂度并拆解为子任务 DAG（不执行）"""
    if not request.requirement.strip():
        raise HTTPException(status_code=400, detail="需求不能为空")
    assessment, dag = await pipeline.decompose_only(request.requirement, request.context)
    return {
        "complexity": assessment.model_dump(),
        "dag": dag.model_dump(),
    }


@app.get("/task/{task_id}", response_model=ExecuteResponse, summary="查询任务状态")
async def get_task(task_id: str):
    """根据任务 ID 查询执行状态和结果"""
    state = pipeline.get_task(task_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")
    return ExecuteResponse(
        task_id=state.task_id,
        complexity=state.complexity,
        dag=state.dag,
        result=state.result,
        status=state.status,
        error=state.error,
    )


@app.get("/models", response_model=ModelsResponse, summary="查看可用模型")
async def list_models():
    """查看配置文件中注册的所有模型列表"""
    return ModelsResponse(models=[m.model_dump() for m in config.models])


@app.get("/health", summary="健康检查")
async def health():
    """服务健康检查"""
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
async def index():
    """前端界面入口"""
    return FileResponse("frontend/index.html")


app.mount("/static", StaticFiles(directory="frontend"), name="static")
