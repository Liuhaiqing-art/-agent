from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ComplexityLevel(str, Enum):
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


class TaskType(str, Enum):
    CODE_GENERATION = "code_generation"
    BUG_FIX = "bug_fix"
    REFACTOR = "refactor"
    ANALYSIS = "analysis"
    QUESTION = "question"
    OTHER = "other"

class AgentMode(str, Enum):
    DEFAULT = "default"     # 默认模式
    HERMES = "hermes"       # 爱马仕模式
    OPENCLAW = "openclaw"   # 极速管家模式

class SubtaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class FileContent(BaseModel):
    filename: str = Field(description="文件名")
    mime_type: str = Field(description="文件类型，如 text/plain 或 image/png")
    data: str = Field(description="Base64 编码后的文件内容")

class ComplexityAssessment(BaseModel):
    level: ComplexityLevel = Field(description="复杂度级别：simple=简单, medium=中等, complex=复杂")
    task_type: TaskType = Field(description="任务类型：code_generation=代码生成, bug_fix=修Bug, refactor=重构, analysis=分析, question=问答")
    estimated_subtasks: int = Field(default=1, description="预估子任务数量")
    reasoning: str = Field(default="", description="复杂度判断依据")


class SubTask(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8], description="子任务ID")
    description: str = Field(description="子任务描述")
    dependencies: list[str] = Field(default_factory=list, description="依赖的子任务ID列表")
    assigned_model: Optional[str] = Field(default=None, description="分配的模型名称")
    status: SubtaskStatus = Field(default=SubtaskStatus.PENDING, description="执行状态")
    result: Optional[str] = Field(default=None, description="执行结果")
    error: Optional[str] = Field(default=None, description="错误信息")
    attempts: int = Field(default=0, description="重试次数")


class TaskDAG(BaseModel):
    tasks: list[SubTask]

    def get_task(self, task_id: str) -> Optional[SubTask]:
        for t in self.tasks:
            if t.id == task_id:
                return t
        return None

    def get_dependents(self, task_id: str) -> list[SubTask]:
        return [t for t in self.tasks if task_id in t.dependencies]

    def get_ready_tasks(self) -> list[SubTask]:
        """Tasks whose dependencies are all completed."""
        completed_ids = {t.id for t in self.tasks if t.status == SubtaskStatus.COMPLETED}
        ready = []
        for t in self.tasks:
            if t.status != SubtaskStatus.PENDING:
                continue
            if all(d in completed_ids for d in t.dependencies):
                ready.append(t)
        return ready

    def all_done(self) -> bool:
        return all(t.status in (SubtaskStatus.COMPLETED, SubtaskStatus.FAILED) for t in self.tasks)

    def has_cycle(self) -> bool:
        """DFS-based cycle detection."""
        visited: set[str] = set()
        rec_stack: set[str] = set()

        def dfs(node_id: str) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)
            task = self.get_task(node_id)
            if task:
                for dep_id in task.dependencies:
                    if dep_id not in visited:
                        if dfs(dep_id):
                            return True
                    elif dep_id in rec_stack:
                        return True
            rec_stack.discard(node_id)
            return False

        for t in self.tasks:
            if t.id not in visited:
                if dfs(t.id):
                    return True
        return False

    def topological_order(self) -> list[list[SubTask]]:
        """Return tasks grouped by level (independent tasks in same level)."""
        if self.has_cycle():
            raise ValueError("DAG contains a cycle")

        in_degree: dict[str, int] = {t.id: len(t.dependencies) for t in self.tasks}
        adj: dict[str, list[str]] = {t.id: [] for t in self.tasks}
        for t in self.tasks:
            for dep in t.dependencies:
                if dep in adj:
                    adj[dep].append(t.id)

        levels: list[list[SubTask]] = []
        processed: set[str] = set()

        while len(processed) < len(self.tasks):
            current_level: list[SubTask] = []
            for t in self.tasks:
                if t.id not in processed and in_degree[t.id] == 0:
                    current_level.append(t)
            if not current_level:
                break
            levels.append(current_level)
            for t in current_level:
                processed.add(t.id)
                for neighbor in adj.get(t.id, []):
                    in_degree[neighbor] -= 1

        return levels


class SubtaskResult(BaseModel):
    task_id: str = Field(description="子任务ID")
    description: str = Field(description="子任务描述")
    model: str = Field(description="使用的模型")
    status: SubtaskStatus = Field(description="执行状态")
    output: Optional[str] = Field(default=None, description="输出内容")
    error: Optional[str] = Field(default=None, description="错误信息")


class AggregatedResult(BaseModel):
    summary: str = Field(description="完成摘要")
    subtask_results: list[SubtaskResult] = Field(description="各子任务结果")
    final_output: str = Field(description="聚合后的最终输出")


class TaskState(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8], description="任务ID")
    requirement: str = Field(description="原始需求")
    context: str = Field(default="", description="附加上下文")
    complexity: Optional[ComplexityAssessment] = Field(default=None, description="复杂度评估")
    dag: Optional[TaskDAG] = Field(default=None, description="子任务DAG图")
    result: Optional[AggregatedResult] = Field(default=None, description="聚合结果")
    status: str = Field(default="pending", description="任务状态")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="创建时间")
    error: Optional[str] = Field(default=None, description="错误信息")


class ExecuteRequest(BaseModel):
    requirement: str = Field(description="你的需求描述")
    context: str = Field(default="", description="额外上下文信息（如项目背景、技术栈等）")
    mode: AgentMode = Field(default=AgentMode.DEFAULT, description="运行模式开关")
    files: list[FileContent] = Field(default_factory=list, description="上传的文件/图片列表")

class ExecuteResponse(BaseModel):
    task_id: str = Field(description="任务ID")
    complexity: Optional[ComplexityAssessment] = Field(default=None, description="复杂度评估结果")
    dag: Optional[TaskDAG] = Field(default=None, description="子任务DAG图")
    result: Optional[AggregatedResult] = Field(default=None, description="聚合结果")
    status: str = Field(description="任务状态")
    error: Optional[str] = Field(default=None, description="错误信息")


class ModelsResponse(BaseModel):
    models: list[dict] = Field(description="可用模型列表")
