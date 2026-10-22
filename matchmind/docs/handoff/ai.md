# ai 交接记录 — Role C（AI 核验与集成）

- 开发者：C / **Meng Yuxuan**（`farlyfeifei`）
- 分支：`codex/ai-verification`
- 基线 SHA：`4be6f02`（由 `codex/backend-ab-mvp` + `docs/development-plan` + `codex/development-pack-cn-v2.1` 三方合并，零冲突）
- 依赖的前端基线：A1 `f88d286092e602d73804e1afeb114ec0f126b2ff`
- 契约版本：**2.0.0 未改**（`python tools/check_frozen.py` → `Frozen contracts and fixtures unchanged`）
- 本次范围：`ai/`、`evaluation/`、`tests/ai/`、`docs/handoff/ai.md`，以及集成人职责内的 `TEAM_ROLES.json` 与 `tools/check_scope.py`。**没有修改 B 的 `backend/`、A 的 `frontend/`、`contracts/`、`data/fixtures/` 任何一行。**

---

## 一、完成的用户行为

### 1. 替换了那 17 行桩（C3）

出厂桩只认 `contracts/examples/analysis_request.json` 逐字段一致的输入，换任何其它窗口都返回 `rejected / MODEL_UNAVAILABLE`。现在的 `ai/service.py`：

| 保证 | 实现 | 测试 |
| --- | --- | --- |
| 签名冻结 | `async def analyze(request) -> dict`，`config`/`provider` 只能是 keyword-only | `test_frozen_signature_is_async_and_identity_error_is_loud` |
| 裸调用零网络 | 不传参数 = 离线 rule_fallback，**即使本机环境有合法 key** | `test_bare_analyze_never_touches_the_network` |
| 事实只来自输入 | 每个数字必须等于 `request.metrics[k]`；证据 id 必须在窗口内 | `test_wrong_metric_number_is_rejected`、`test_invented_event_id_is_rejected` |
| 三态诚实 | `live_model` / `rule_fallback` / `precomputed`，`model` 只填模型真实返回的 `model` 字段 | `test_unconfigured_config_is_a_labelled_fallback` |
| 最多一次纠正 | 全局只有一次修复预算，实测有上限 | `test_correction_is_capped_at_one_round` |
| 有界失败 | 超时 / 401 / 非 JSON / 空响应 / 反序列化异常全部降级为带标签的 fallback，不无限重试 | `test_timeout_returns_fallback_and_says_why` 等 6 个 |

### 2. 算术自洽门（**这条是 B 的测试抓出来的**）

`tests/test_contracts.py::test_stub_does_not_fabricate_new_metrics` 把 `high_recoveries` 篡改成 8，原桩靠"不匹配就拒"过测。我第一版实现把 8 直接写进解释 —— **测试当场抓住我在编数字。**

修法是加一道 `verify.consistency_issues()`：用同一份事件重算检测器，若 `high_recoveries`/`linked_shots`/`home_shots`/`away_shots`/`window_seconds` 与事件对不上，**在叫模型之前就 reject**。

> 这是这套系统里最重要的一条：schema 只能证形状，这道门证算术。一个和证据矛盾的数字，无论措辞多漂亮都不能发布。

### 3. 三个角色真的不是三个 prompt（C4）

冻结契约的 `Trace.agent` 枚举就是 `analyst / narrator / auditor / validator`，所以角色划分不是临时编的，是协议里预先写死的。

| 角色 | 输入 | 输出 | 不能做什么 |
| --- | --- | --- | --- |
| analyst | 完整事件表 + 指标 + 允许数字 | 只输出 claims | 不写叙事、不定标题 |
| narrator | **只**拿到已通过代码校验的 claims | `{casual, analyst}` 双档 | 不许加新事实、新 id、新数字 |
| auditor | 事实 + claims + 叙事 | `approved` + 被否 claim id + 问题列表 | 不许改写文本，只能否 |
| validator | 全部 | 确定性校验 | 不调用模型 |

有测试证明三者拿到**三份不同的 system prompt**，且 auditor 真的收到了叙事文本：`test_roles_get_different_system_prompts_and_inputs`。

工具调用是真的：`ai/tools.py` 提供 `get_metrics` / `get_event_window` / `get_candidate_moments`，全部只读传过来的这一个 request，**不反查任何后端数据库**（角色卡 B4 的要求），且调用次数有上限。实测分析师确实会调工具。

### 4. B4 的 adapter 注入

B 的 `create_app(analyzer=...)` 是注入点，默认入口故意不注入。我没动 `backend/app.py`，而是新增 **`ai/app.py` 作为组合根**：

```
python -m uvicorn ai.app:app --host 127.0.0.1 --port 8000 --workers 1
```

`backend.app:app` 保持无 dispatcher（`test_backend_default_entry_point_stays_uninjected` 守着），所以 B 的后端镜像和部署校验完全不受影响。

顺带修了一个不诚实的地方：B 的 `/api/v1/health` 是常量 `{"status":"degraded","model_ready":false}`，一旦注入真模型这个响应就是假话。我在组合根用 middleware 覆盖成如实反映注入适配器的版本 —— 改在 C 的文件里，因为改 B 的文件会越界。

### 5. 评测台（C5）

`evaluation/benchmark.py`：12 个窗口 = 4 正例 + 4 负例 + 4 篡改，单 Agent 与三 Agent **同输入、同模型、同确定性校验器**。

`ai/single.py` 是刻意做弱的基线：一个 Agent 同时写 claims、写叙事、自我复核。

---

## 二、修改文件

新增（全部 C 所有）：

```
ai/config.py        模型配置；key 只从环境/被忽略的 .env 读，永不回显
ai/prompts.py       三个互斥的 system prompt + 版本号 c3-1.1.0 + 紧凑事实表
ai/provider.py      Chat Completions 传输层；DeepSeek thinking 开关；有界工具循环
ai/tools.py         三个只读工具，作用域锁死在这一个 request
ai/verify.py        确定性校验：数字、证据、量词、中文数字、算术自洽
ai/fallback.py      规则回退；只在指标与事件自洽时才肯生成解释
ai/service.py       冻结入口 analyze()，三角色编排 + 一次修复预算
ai/app.py           组合根：注入 adapter + 诚实 health
ai/probe.py         模型探针：默认只查配置，--live 才发一次真请求
ai/single.py        评测用单 Agent 基线
evaluation/benchmark.py   12 用例对照评测
evaluation/live_smoke.py  单次真实端到端
tests/ai/test_service.py  37 个用例，全部 mock 网络
tests/ai/test_app.py      9 个用例，组合根与 HTTP 接线
```

改动：

```
TEAM_ROLES.json        填三人角色与每日合并时间（C1 要求）
tools/check_scope.py   C 的白名单补上根配置、共享测试和 tools/ 自身
```

---

## 三、实际执行的测试与结果

在 `matchmind/` 下，用 `.venv\Scripts\python.exe`（Python 3.12.10）：

```
python -m pytest tests -q                       → 133 passed, 33 subtests passed
python tools/check_frozen.py                    → Frozen contracts and fixtures unchanged
python tools/check_scope.py --role C --base HEAD→ Role scope OK
python -m ai.probe                              → configured: true
python -m ai.probe --live                       → success, model=deepseek-flash, 875ms
python -m evaluation.live_smoke                 → 见下
python -m evaluation.benchmark                  → 报告落在 .artifacts/evaluation/
```

依赖（`requirements-dev.txt`，清华 TUNA 源，全部钉死版本）：`jsonschema 4.26.0`、`fastapi 0.157.0`、`pydantic 2.14.1`、`sse-starlette 3.5.0`、`uvicorn 0.54.0`、`agent-framework-core 1.22.0`、`agent-framework-openai 1.17.0`、`httpx 0.28.1`、`pytest 9.1.1`。**冻结包里的两个 agent-framework 版本号在 PyPI 上真实存在且是当前最新，不需要改锁。**

---

## 四、Mock / fallback / live 的真实状态

| 状态 | 是否有真实调用 | 标签 | 已验证 |
| --- | --- | --- | --- |
| 离线（裸调用 `analyze(request)`） | 无 | `rule_fallback` / `code_only` / `model=null` | ✅ 37 个测试走这条 |
| 无 key 的组合根 | 无 | 同上 + `error.code=MODEL_UNAVAILABLE` | ✅ |
| 真实模型 | **有** | `live_model` / `agent_and_code` / `model=deepseek-flash` | ✅ 实测通过 |
| 真实模型失败 | 有（失败） | 降级为 `rule_fallback` + `error.code` | ✅ 401 / 超时 / 非 JSON 均覆盖 |

**一次真实成功的完整记录**（`evaluation/live_smoke.py`，非模拟）：

```
status=passed  elapsed=11718ms  model_calls=5
generation=live_model / deepseek-flash
verification=agent_and_code / passed / rejected_claims=[C4,C5]
claims 保留 C1(high_recoveries=3) C2(home_shots=2) C3(away_shots=0)
traces: analyst 3500ms → narrator 2703ms → auditor 3353ms(rejected) → narrator 2141ms(修复)
```

这段本身就是演示素材：**审核员砍掉了两条越权主张，纠正轮重写叙事，卡片仍然发布，并且在 `rejected_claims` 里如实记录被砍掉的是哪两条。** 110 秒视频里 80–95 秒那段故障演示，用真实数据就能演，不需要伪造。

---

## 五、三个必须让全队知道的实测结论

### 1. DeepSeek 的 thinking 默认是开的，会顶爆 deadline

官方文档：`{"thinking": {"type": "enabled/disabled"}}` 是**顶层字段**，默认 `enabled`、effort `high`。我在 `ai/provider.py` 里每次调用都显式关掉。已用真实请求验证该参数被接受。

### 2. 12 秒 deadline 装不下"一次纠正"，已按契约允许的方式改成 20 秒

实测一轮 analyst→narrator→auditor ≈ **9 秒**。12 秒预算下纠正轮永远拿不到预算 —— 也就是说**最值钱的那条链路在 12 秒下根本不会触发**。

`docs/02_contract.md` 原文：*「默认整体deadline12秒、并发1。**deadline参数可以在资源验证后改配置**，不改外部协议。」* 所以按实测把 `MATCHMIND_MODEL_TIMEOUT_SEC` 提到 **20**，**没有改协议**。

> 影响 A/B：A 的 `agent_status` 会显示更久的"分析中"；B 的 `Settings.analysis_timeout` 会自动跟着这个环境变量走，不需要改代码。

### 3. 冻结契约本身禁止把单 Agent 结果标成"已核验"

`check_result` 要求：`generation.mode == "live_model"` 时 `verification.method` 必须是 `agent_and_code`。**一个自己审自己的单 Agent 拿不到这个标签。** 这条约束本身就是"多 Agent 不是可有可无"的硬证据。

---

## 六、需要共享契约变更的地方（**提案，未执行**）

我**没有改任何冻结文件**。以下是按判据收益排序的一次性升版清单，建议**一次性升到 2.1.0**，不要一点点加。每一条都要动：`contract.schema.json` → `contracts/VERSION` → 重生成 `types.ts` → 重生成 `openapi.json` → 更新 `frozen.sha256.json` → A 接消费端。

| # | 变更 | 为什么（对应官方判据） | 消费者影响 |
| --- | --- | --- | --- |
| 1 | `Metrics` 增 `sustained_recoveries` / `sustained_shots`（≤45s 档） | **现有 15 秒阈值漏掉了本场唯一进球**：1640 那次夺回 40 秒后进球，没被计入 linked_shots。卡片现在对这个进球只字不提 | `Claim.metric_key` 枚举同步；A 的 chips 多两格；B 的 `window_metrics` 加两个纯函数 |
| 2 | `Metrics` 增 `pass_completion_rate` / `final_third_entries` / `avg_pass_distance` / `pass_difficulty` | 官方 §4.1(ii) 明写 `pass distance / accuracy / difficulty rating`，**目前一项都没有**，直接影响 Adherence 那 20% | A 的分析师模式多一组排序；B 加纯几何函数 |
| 3 | `Insight.narratives` 增 `broadcast` | 官方 §4.1(i)(e) 要"多档个性化"。现在 `narratives` 是 `additionalProperties:false` 且只允许 casual/analyst | 同一次调用多产出一段，零额外成本；A 加第三个切换按钮 |
| 4 | 新增 `POST /api/v1/replays/{id}/recap` + `Recap` 定义 | 官方 §4.1(iii) 明写 `automated match recaps`。v0.1 有、2.0.0 被砍了。**而且它是多 Agent 的第二个天然战场**（Recap 输入是整段 prefix，Moment 输入是单窗口，输入粒度不同不可合并） | B 加端点；A 加 recaps 区块；我出 recap 角色 |
| 5 | 新增 `GET /api/v1/matches/{id}/players` + `PlayerStats` | 官方 §4.1(i)(e) 点名 `player focused mode`。`roster.json` 已在仓库里但完全没用起来 | B 出接口；A 做点击球员 |
| 6 | `AnalysisRequest.language` 从 `en\|zh` 放宽 | 官方 §4.1(vi) `Multi-language storytelling`，现在枚举写死两种 | 只是多一个分支 |

**建议顺序**：先做 3 和 4（改动小、判据收益大、不碰 B 的统计口径），再做 1（它能补上"漏掉进球"这个演示硬伤，但需要 B 配合加函数），2 和 5 视剩余时间。

---

## 七、仍未完成 / 已知限制

| 项 | 状态 | 说明 |
| --- | --- | --- |
| Agent Framework 编排落地 | **未接入运行时** | `agent_framework 1.22.0` 与 `OpenAIChatCompletionClient` 已装好、导入验证通过，但当前跑的是 `ai/provider.py` 的直连 Chat Completions（带真实工具循环）。原因：DeepSeek 在 **tools + thinking 同时开启**时要求逐轮回传 `reasoning_content`，否则 400；关掉 thinking 后直连路径更稳。接框架是下一步，需在 C4 单独做并保留 trace 对照。**提交材料不得声称已使用 Agent Framework。** |
| MCP server | **未做** | 三个工具已成型，包一层 MCP 是最便宜的 Agentic 加分点，见下一块 |
| 会话/并发上限 | 沿用 B 的实现 | C 侧无独立限流，沿用 8 会话 / 30 次每小时 / 并发 1 |
| possession 口径自检 | **刻意不做** | `AnalysisRequest` 不带 `Match.initial_possession_team`，无法在 C 侧重算；已在 `consistency_issues` 的 docstring 里写明这是刻意的空白，不猜 |
| 中文数字校验 | 部分覆盖 | 只认 `十 / X十 / 十Y / X十Y` 形态，其它写法靠 auditor 兜；已在 docstring 里写明限制 |
| 视频 / 部署 | 不属本轮 | 见 B 的 handoff 与 `docs/05_acceptance.md` |
| 前端消费端 | **阻塞在 A 方** | A3 的 Insight 卡 / 证据高亮 / 双档切换还没写，C 的产出目前只能在 API 与快照里看到 |

---

## 八、下一工作块

1. **把 Agent Framework 真正接进 `ai/agents.py`**：三个 `ChatAgent` 共享一个 `OpenAIChatCompletionClient`（base_url 指向 DeepSeek），保留 `ai/provider.py` 作为对照基线，用同一套 12 用例跑出"框架版 vs 直连版"的调用数与耗时对比。
2. **MCP server**：把 `ai/tools.py` 的三个工具包成 MCP，让工具调用走 MCP 而不是函数直调 —— 判据里点名了 `MCP integration`，且完全本地、不需要云。
3. **契约 2.1.0 一次性升版**：按第六节的 3 → 4 → 1 顺序，先和 A/B 确认消费端，再动 `contract.schema.json`。
4. **`POST /recap` 的 recap 角色**：输入整段 prefix，与 moment 角色共用同一套校验器和 fallback。
5. 补中文叙事的真实模型实测（目前中文只在 fallback 路径被自动测过）。

---

## 九、给队友的三句话

- **给 A**：`ai.app` 已经能被 uvicorn 拉起来，`/api/v1/health` 会如实报 `model_ready`。A3 只要按冻结的 `Insight` 结构渲染即可，`claims[].metric_key/metric_value` 和 `evidence_event_ids` 都是可信的；`verification.rejected_claims` 非空时请把"本卡已剔除 N 条未通过核验的主张"显示出来 —— 那是这套产品的卖点。
- **给 B**：我没有改你任何一行，`backend.app:app` 仍然无 dispatcher。B4 的注入在 `ai/app.py`，`analysis_source="external"`。注意 `MATCHMIND_MODEL_TIMEOUT_SEC` 现在设成 20，你的 `Settings.analysis_timeout` 会跟着走。
- **给提交代表**：真实调用过的**只有** DeepSeek 的 `deepseek-flash`（Chat Completions）。**没有用过 Foundry，没有用过 Azure，Agent Framework 尚未接入运行时。** 提交材料按这个写，别多写一个词。
