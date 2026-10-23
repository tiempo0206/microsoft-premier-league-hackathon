# Role B: reproducible data and analysis delivery

Unified scope, branch, acceptance gates and resource requirements: **B_DELIVERY_PLAN.md**. This document describes the implementation and generated artifacts under that plan.

Scope: B-owned data preparation, deterministic statistics/evidence, API/replay transport and deployment verification. Contract stays 2.0.0. No frontend, AI prompts/model implementation, shared schema or frozen fixture changes. The current dataset is a synthetic 25:00–30:00 excerpt, not a full match or tracking feed.

## Execution plan and acceptance

1. **Evidence calculation**: derive high-recovery chains and the existing numeric trigger from the same functions used by runtime metrics. Verify direction, boundary times, duplicate-shot counting, negative windows and possession-time conservation. Build AI input using one shared B function; retain the existing request shape.
2. **Analysis export**: export deterministic JSON, Markdown and a validated offline AnalysisRequest. Include audited source hashes, count evidence, metric definitions, positive/negative window results and explicit data limitations. Fail on invalid data, never call a model and never label this artifact an AI Insight.
3. **Delivery acceptance**: one command checks preparation/readiness, exports analysis, runs generated-case regression and backend/common tests, starts its own loopback API, verifies actual HTTP/control/SSE and stops only its own child. Record public deployment and Linux image checks as outstanding until actually performed.

Implement and verify these slices in order. No new third-party dependency, service, database or account is required. Use the existing .venv; generated artifacts remain ignored under .artifacts/ on the existing E: checkout. Inspect complete diffs and role/frozen checks before committing to codex/backend-ab-mvp. PR and merge remain deferred by the human.

## Review decisions

- Preserve the sparse, audited 30-event baseline; do not expand to a speculative 90-minute simulator.
- Keep HTTP payloads unchanged. Extra analysis files are B engineering/handoff artifacts, not new frontend API fields.
- Count a recovery once if one or more same-team, same-possession shots follow within 15 logical seconds inside the observed window. This is an event heuristic, not tactical causality.
- Keep observed facts, offline inputs and future AI output distinct. C supplies any semantic interpretation and real-model workflow later.
- Runtime remains one worker/instance with bounded temporary sessions. A/C delivery and a real cloud account are integration dependencies, not reasons to invent login or storage features.
- Kimi probe: no CLI or desktop process available at task start; no Kimi planning ran. Codex owns implementation and review. DSPy skipped because this slice performs deterministic calculations and transport only.

## 给后端负责人的运行与交接说明

在仓库 `matchmind` 目录执行：

```powershell
.\.venv\Scripts\python.exe -m deploy.verify_backend
```

已有环境可直接运行，不需要新账号、模型 Key、Docker、数据库或下载比赛数据。该命令实际执行：数据来源/完整性与可重复性检查 → 统计和证据计算 → 分析包导出 → 正常/异常合成回测 → 后端及共同测试 → 启动独立临时 API → HTTP/回放/SSE 验收 → 关闭自己启动的服务。失败会返回非零退出码，具体阶段写入验收记录。

输出在 `.artifacts/backend-delivery/`：

| 文件 | 用途 |
| --- | --- |
| `readiness.json` | 数据与运行配置检查；坏数据禁止继续 |
| `data-analysis.json` | 全片段统计、每项计数的事件 ID、持球时间区间、事件时刻快照、正负窗口与输入哈希 |
| `data-analysis.md` | 可直接阅读的分析说明 |
| `analysis-request.json` | 与运行时共用构建函数的 C 输入样例；带固定离线身份，不能直接发布到真实回放 |
| `acceptance.json` | 验收结果、失败阶段或测试数、源码哈希，以及尚未验证的部署/前端/AI 项 |
| `backtest/` | 独立正常/异常合成数据集、开发/留出种子回归结果及失败案例；不用于模型训练 |
| `tests-*.log` / `server.log` | 本次本地检查日志，不上传凭证 |

该目录已忽略，不把本机日志提交仓库。分析输出可重复生成，默认命令只写上述产物，不修改源数据。输出路径保护会拒绝写入当前仓库的共享契约、冻结数据和其他成员目录。只导出分析时可运行 `python -m backend.reporting --output-dir .artifacts/backend-analysis`。

### 现在得到的事实

- 30 条原创合成事件，第一节 25:00–30:00。到 30:00：比分 HOME 1:0 AWAY，射门 3:1，传球 5:13，成功传球 5:10，合成持球时间 110:190 秒。
- 固定观察窗 1500–1650：HOME 高位夺回 3 次，其中 E007→E009 相隔7秒、E013→E015 相隔9秒；第三次 E019 在窗口内没有满足15秒条件的射门。
- 反例窗 HOME 1500–1559、AWAY 1500–1650、HOME 1651–1800 都不满足触发条件。运行时先计算同一规则，未达标不入 AI 调度队列。
- 每个逻辑秒检查持球时长守恒、计数非负与单调、成功传球不超过总传球、进球不超过已记录射门。进球确认只增加一次比分。
- 数字和 ID 校验不能证明真实战术因果；当前报告是确定性分析，不是模型输出，也不是90分钟实况或真实跟踪数据。

### 与 A / 未来 C 的边界

A 继续使用现有十个 HTTP 接口及六种 SSE 消息；没有新增字段、端点或前端依赖。B 的统计仍是唯一数值真源。额外分析文件用于工程检查和交接，不能要求 A 临时改协议来展示它们。

真实 AI 由团队另行安排。C 可先读取 `analysis-request.json`，按冻结 AnalysisRequest/AnalysisResult 开发；集成时使用运行时分配的 replay/run/task 身份。B 不实现提示词、模型供应商或语义审核。本次没有新增任何依赖和真实模型调用。

本地 B 闭环及 Linux 镜像、容器 HTTP/SSE、合成回测和重启验证已通过。本机已使用 WSL2 原生 Docker Engine 替代故障 Desktop；启动入口是桌面“启动 Docker”。Render 公网 SSE、A 页面和 C 真实模型仍须在实际环境验收；Render 注册与授权步骤见 `deploy/RENDER_STEPS_CN.md`。继续在 `codex/backend-ab-mvp` 开发，按人类要求最后再处理 PR/合并。
