Codex Clone — 任务编排引擎
https://img.shields.io/badge/python-3.9%252B-blue.svg
https://img.shields.io/badge/FastAPI-0.115.0-green.svg
https://img.shields.io/badge/License-MIT-yellow.svg
一个模仿 GitHub Copilot / OpenAI Codex 思路的智能任务编排引擎。用户只需输入自然语言需求，系统便会自动完成 分析复杂度 → 拆解子任务 → 分配模型 → 并行执行 → 聚合结果 五个阶段，最终输出高质量答案。
核心设计哲学：不是所有问题都需要“大模型深思熟虑”。简单翻译用便宜模型，复杂重构才调度强模型和多模型协作，在效果与成本之间取得平衡。
✨ 功能特色

    🧠 智能复杂度分析：自动判断任务难度（简单/中等/复杂），并预估子任务数量

    📋 自动任务拆解：将复杂需求拆分为带依赖关系的 DAG 子任务图

    🚀 灵活模型路由：根据复杂度级别自动选择最合适的 LLM（便宜模型处理简单任务，强大模型处理复杂任务）

    ⚡ 并行执行：DAG 中无依赖的子任务并发执行，大幅缩短总耗时

    🔗 结果聚合：多个子任务输出自动合并、去重、逻辑排序，生成最终答案

    🌐 Web 交互界面：开箱即用的中文前端，支持输入需求、查看复杂度评估、DAG 可视化与最终结果

    🔌 多模型适配：支持任意 OpenAI 兼容协议模型（DeepSeek、Qwen、GLM、文心等），通过配置文件轻松扩展
    
🏗️ 架构概览

    分析器：调用 LLM 评估任务复杂度（simple / medium / complex）、类型及预估子任务数

    拆解器：对中/复杂任务生成 DAG（每个节点为子任务，边表示依赖关系）

    路由器：根据复杂度选择模型（simple 用低成本模型，complex 可轮询多个模型）

    执行器：按拓扑顺序并行执行子任务，自动注入依赖上下文，支持重试与超时

    聚合器：合并多子任务输出，生成最终结构化结果
    <img width="727" height="773" alt="图片" src="https://github.com/user-attachments/assets/b7aa8965-b5b1-4dd1-8ff8-ec965ea2124d" />

