# ai 交接记录 — Role C（AI 核验与集成）

## 本轮交付（AI_RULES「每次交付给团队的固定格式」六项）

> 这张表按 `AI_RULES.md` 第 14–21 行的固定格式写，放在最上面，因为队友最先要的就是这六行。下面二十节是历史，这一格是现状。

| 项 | 现状 |
| --- | --- |
| **角色、分支、基线 SHA、契约版本** | C（AI 核验与集成 + 整合人）；**分支 `main`**，基线 `bcaed0e`（PR #9 把完整基线合进 main 之后的提交）；契约 **2.0.0 未改** |
| **本次完成的用户行为和修改文件** | 合并 PR #8；修掉 B 报的降级卡证据截断 bug；关闭 foul 口径；把完整基线合进 `main`；装 CI 与 CODEOWNERS。文件清单见第二十节 |
| **执行的测试命令、结果及失败原因** | `pytest tests -q` → **422 passed / 62 subtests**；`tools/check_frozen.py` → unchanged；`tools/check_scope.py --role C` → OK；`deploy.adapter_check` → **12/12 通过、3/3 篡改被拒、0 次模型调用**；`generate_types.py` + `generate_openapi.py` → 重新生成后 `git diff` 为空（无漂移）。**失败过两处**，原因见 19.1：一处是我的文档过期，一处是我验证环境的假阳性 |
| **Mock / fallback / live 的实际状态** | Mock：全部单测走注入的 httpx transport，零网络。fallback：`rule_fallback` 三态标签齐全，是默认降级路径。live：真实调用过的**只有** DeepSeek `deepseek-flash`（Chat Completions），**没有 Foundry、没有 Azure、没有云端复测** |
| **是否需要共享契约变更** | **需要，但没有做**：recap / storyline / 双语 sustained metric 的升级提案在 `evaluation/CONTRACT_2_1_PROPOSAL.md`，要 A/B 都点头才能动 `contracts/`。除此之外**没有**契约变更 |
| **仍未完成的内容** | 见第七节与 19.7：契约 2.1.0（等 A/B）、A2/A3 前端渲染（A）、演示视频（代表）、公网部署与仓库公开（需要 admin，我没有）、云上复测国内模型端点 |

---

- 开发者：C / **Meng Yuxuan**（`farlyfeifei`）
- 分支：`codex/ai-verification`（PR **#8**，目标分支 `codex/backend-ab-mvp`）。这里的 SHA 以前每轮都要手改，改一次就可能忘一次，所以现在**只记最新一轮**：第九轮 tip 写在第十七节末尾
- 基线 SHA：`4be6f02`（本地三方合并 `codex/backend-ab-mvp` + `docs/development-plan` + `codex/development-pack-cn-v2.1`，零冲突）
- 远端基线：`cd48448`（`codex/backend-ab-mvp` 的 tip；HTTPS 推送不通，改用 Git Data API 以单提交形式发布，所以 PR #1/#5 的文档没有在这个分支里重复）
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

### 2b. 12 用例评测又抓出两个中文误杀（都已修）

| 缺陷 | 现象 | 根因 | 修法 |
| --- | --- | --- | --- |
| 中文数字读不出来 | 「时间为115秒」提取不到 115，**中文路径 100% 校验失败** | 正则 lookbehind 用了 `\w`，而 Python 的 `\w` 匹配 CJK 汉字 | 字符类改成显式 ASCII |
| 汉字单字被当数字 | 「一次都没射门」的「一」被读成 1，「进攻三区」的「三」被读成 3 | 汉字「一二三」既是数字又是普通词 | 漂移检测不再扫裸单字，改由 `states_value` 在声称指标值时接受 |
| 坐标被判为编数字 | 「恢复点在 x=78」的 78 不在允许集合 | 允许集合只放了指标值 | 允许集合并入事件里真实存在的全部坐标 |

**这三条都属于"不修就会静默废掉一条评分项"的级别**：官方 §4.1(vi) 要多语言叙事，而它们让中文一次都出不来。修完 142 个测试全绿，中文正例可发布。


### 3. 三个角色真的不是三个 prompt（C4，**已接 Agent Framework**）

冻结契约的 `Trace.agent` 枚举就是 `analyst / narrator / auditor / validator`，所以角色划分不是临时编的，是协议里预先写死的。

**编排器可切换**：`MATCHMIND_ORCHESTRATOR=framework|direct`，默认 `direct`。

- `direct`（默认）：`ai/provider.py` 直连 Chat Completions，带真实工具循环。
- `framework`：`ai/agents.py` 用 `agent_framework.Agent` 三个实例共享一个 `OpenAIChatCompletionClient`，各自独立 instructions + 各自绑定工具。

两条路径的 prompt、校验器、fallback 逻辑完全同一份，只有执行者换了。实际走哪条会写进 trace（`orchestrator=...`），因为把没用的框架写进材料是本项目最要避免的事。

| | Agent Framework | 直连 |
| --- | --- | --- |
| 正例 2 个窗口 | 2/2 通过 | 2/2 通过 |
| agent 调用次数 | 8 | 8 |
| 中位延迟 | **8601ms** | 11414ms |

同模型同输入下框架路径快约 25%。**这是两个窗口的延迟观察，不是质量结论**，完整 12 窗口的框架版还没跑。

接线时踩到两个坑，都用真请求验证过：
1. `agent_framework 1.22.0` **不再导出 `ChatAgent`**，类名是 `Agent`。照抄旧教程会在 import 处失败。
2. DeepSeek 的 thinking 开关在框架里也能关：`ChatOptions` 是 TypedDict，OpenAI 客户端会转发 `extra_body`，所以 `{"thinking":{"type":"disabled"}}` 能到达 provider。实测同一 prompt：关掉 1047ms，开着 1719ms。


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

`evaluation/benchmark.py`：12 个窗口，单 Agent 与三 Agent **同输入、同模型、同确定性校验器**。

`ai/single.py` 是刻意做弱的基线：一个 Agent 同时写 claims、写叙事、自我复核。

**实测结果（2026-10-22，`deepseek-flash`，prompt `c3-1.1.0`）**：

| group | 用例 | passed | fallback | rejected | 模型调用 |
| --- | --- | --- | --- | --- | --- |
| positive | 2 | 2 | 0 | 0 | 11 |
| non_trigger | 4 | 3 | 1 | 0 | 19 |
| negative | 2 | 2 | 0 | 0 | 10 |
| tampered | 4 | 0 | 0 | 4 | **0** |

合计 7 张发布卡片、1 次诚实降级、4 次正确拒绝；**篡改组零模型调用**。

| | 三 Agent | 单 Agent |
| --- | --- | --- |
| 12 窗口模型调用 | 40 | 12 |
| 中位延迟 | 10484ms | 3781ms |
| 校验器拒绝的 claim | 5 | 8 |
| 叙事校验失败的窗口 | 4 | 7 |
| 能否标记 `passed` | 能 | **不能** |

诚实结论：**三 Agent 贵 3.3 倍调用、慢 2.8 倍，但错误 claim 和失败叙事都更少（5 vs 8、4 vs 7）**，而且单 Agent 在契约上根本拿不到 `passed`。12 个窗口不足以宣称泛化能力，报告里已写明样本量，**不要在提交材料里把它写成"多 Agent 更好"的统计结论**。

**注意用例分组的诚实性**：出厂 fixture 里**只有一个窗口会触发**高位夺回检测器，所以"4 个正例"物理上不存在。把 3 个不触发的窗口标成正例会虚高通过率，所以分组改成了 positive / non_trigger / negative / tampered。**这个空缺本身就是"数据太稀"的证据**，和第六节第 1 项那条契约变更呼应。


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
python -m pytest tests -q                       → 142 passed, 33 subtests passed
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
| 离线（裸调用 `analyze(request)`） | 无 | `rule_fallback` / `code_only` / `model=null` | ✅ 53 个 AI 测试里大部分走这条 |
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

> **这张表在第八轮（`70dec95`）刷新过。** 上一版写于第二轮之前，当时 A2A 与 overlay 还是“未做”，第三轮和第六轮已经交付；如果队友读到旧版本，会低估这个分支。刷新后的状态如下。

| 项 | 状态 | 说明 |
| --- | --- | --- |
| Agent Framework 编排 | **已接入，且是默认** | `MATCHMIND_ORCHESTRATOR=framework` 为默认；正例 2/2、12 窗口 6/12 发布，比直连快约 20–25%，质量打平。不可导入时自动降级为直连并在 trace 里写明。见第十节 |
| MCP server | **已完成，8 个工具** | `ai/mcp_server.py`：`list_matches` / `get_metrics` / `get_event_window` / `get_candidate_moments` / `explain_window` / `build_overlay` / `build_recap` / `get_threat_ranking`，复用同一份确定性代码。`python -m ai.mcp_server`（stdio）或 `--http` |
| A2A agent card + 端点 | **已完成**（第八轮补 A2A 传输） | `ai/a2a.py` 出 card（`/.well-known/agent-card.json`，8 个 skill，带 `x-matchmind` 诚实块写明只支持 `message/send`），`ai/a2a_transport.py` 是真正可调用的 `dispatch`，自由文本按 `-32602` 拒。**没有对接过第三方 A2A 实现**，材料里不能写“兼容 A2A” |
| broadcast overlay JSON 导出 | **已完成** | `ai/overlay.py`，`matchmind.overlay/1`，含下三分之一字幕（6000ms）与 pin（3000ms）的时长、每条文字图文的 `speech` 与一份有序 `speech_script`。见第十一节 |
| recap 角色 | **已完成** | `ai/recap.py`，`matchmind.recap/1`。整段 prefix 输入；它是唯一被允许报告比分的角色。见第十二节 |
| 威胁排序 | **已完成** | `ai/threat.py`，价值迭代算 xT 网格，样本薄时**拒绝出榜**而不是瞎排。见第 14.2 节 |
| storyline 限流 | **已完成** | `ai/storyline.py`，45 秒最小间隔、10 分钟 8 张卡上限、重复窗口抑制 |
| 会话/并发上限 | 沿用 B 的实现 | C 侧无独立限流，沿用 8 会话 / 30 次每小时 / 并发 1 |
| 降级卡的证据截断 | **已修（B 报的 bug）** | `ai/fallback.py` 的 12 条上限会把保留主张引用的证据丢掉，共享 `check_result` 因此拒卡；B 在增强数据上量到 **12 个正常输入里 4 个**。修法：卡片证据 = 基础选择 ∪ 全部保留主张的引用。验收 `deploy.adapter_check` → **12/12 通过、3/3 篡改被拒、0 次模型调用**。见第十九节 |
| foul 事件口径 | **B 已支持，我的文档已更正** | 冻结 schema 里的 `foul` 现在被 `backend/data.py` 接受（`outcome=none`、`end_position=null`，不转移持球）。`test_invariants.py` 从“两边差一个 foul”改成“两边必须相等”。见第十九节 |
| 审核员校准 | **两个方向都测了** | 误报：15/15 诚实卡被批准（0.0%）。漏报：10 类软越权 × 5 次 = 50/50 全抓到，且 50/50 点名的就是被做手脚的那一条（0.0% 漏）。**但语料是我自己写的**，100% 只能说明“我列得出的越权它都抓得住”，不能当通用准确率。见第十七节 |
| recap 跨窗口一致性 | **已做** | `ai/recap.py: recap_series_issues()` + `recap_from_insights_issues()`：累计计数不许倒退、同一个进球不许被两次记给不同球员、同窗口两份 recap 必须一致、卡片不许跨场次或漏卡 |
| 契约 2.1.0 | **提案，未执行** | `evaluation/CONTRACT_2_1_PROPOSAL.md`。要动 `contracts/` 必须 A/B 都点头，C 不单独动 |
| 演示视频 | **未做** | 脚本在 `evaluation/DEMO_SCRIPT.md`，录屏需要人来做 |
| `ai/framework_spike.py` | **一次性探针，不是产品路径** | 第八节之前用来回答"C4 能不能做到"的独立脚本，跑法写在它自己的 docstring 里。**没有任何模块 import 它，也没有测试覆盖它**——真实编排在 `ai/agents.py`，由 `test_orchestrator.py` 覆盖。读 `ai/` 的人请把它当历史记录，不要当入口 |
| possession 口径自检 | **刻意不做** | `AnalysisRequest` 不带 `Match.initial_possession_team`，无法在 C 侧重算；已在 `consistency_issues` 的 docstring 里写明这是刻意的空白，不猜 |
| 中文数字校验 | **覆盖十/百/千三级，单个数字仍刻意不认** | `chinese_numeral()` 解析 `十五 / 三十五 / 一百一十五 / 两百 / 一千二百`；`百分之三十七` 的 `百` 不会被当成 100。**刻意的空白**：孤立的 `一 / 二 / 三` 不当数字（`一次都没射门`、`进攻三区`），这类靠 auditor 兜。见第二十一节 |
| 视频 / 部署 | 不属本轮 | 见 B 的 handoff 与 `docs/05_acceptance.md` |
| 前端消费端 | **阻塞在 A 方** | A3 的 Insight 卡 / 证据高亮 / 双档切换还没写，C 的产出目前只能在 API 与快照里看到 |

---

## 八、下一工作块（第八轮之后重写）

> 上一版这一节列的 5 条里有 4 条已经做完（框架版评测、MCP、recap、中文评测），只有契约升版仍是提案。现在真正剩下的是这些：

1. **等 PR #8 合进 `codex/backend-ab-mvp`，然后回填 `TEAM_ROLES.json` 的 `baseline_sha`** —— 它现在还是 `"pending: codex/ai-verification merge commit"`。这是 C1 唯一没闭环的一格，卡在合并动作上，不缺技术。
2. **契约 2.1.0**：按 `evaluation/CONTRACT_2_1_PROPOSAL.md`，先和 A/B 确认消费端，再动 `contract.schema.json`。这一步必须全员同意。
3. **稠密 fixture**：`evaluation/dense_fixture_proposal.py --minutes 45` 已证明能到 971 个事件，但要不要换掉现在这 30 事件的稀疏数据，是 B 的决定。
4. **演示窗口 1500–1650 → 1540–1690**：`fixture_qualify --recommend` 自己也是这么推荐的（recoveries=3、linked_shots=2、goal=E023 全在窗口内）。改一行，B 说了算。
5. **演示视频**：脚本在 `evaluation/DEMO_SCRIPT.md`，录屏需要人来做。

---

## 九、给队友的三句话

- **给 A**：`ai.app` 已经能被 uvicorn 拉起来，`/api/v1/health` 会如实报 `model_ready`。A3 只要按冻结的 `Insight` 结构渲染即可，`claims[].metric_key/metric_value` 和 `evidence_event_ids` 都是可信的；`verification.rejected_claims` 非空时请把"本卡已剔除 N 条未通过核验的主张"显示出来 —— 那是这套产品的卖点。
- **给 B**：我没有改你任何一行，`backend.app:app` 仍然无 dispatcher。B4 的注入在 `ai/app.py`，`analysis_source="external"`。注意 `MATCHMIND_MODEL_TIMEOUT_SEC` 现在设成 20，你的 `Settings.analysis_timeout` 会跟着走。
- **给提交代表**：真实调用过的**只有** DeepSeek 的 `deepseek-flash`（Chat Completions）。**没有用过 Foundry，没有用过 Azure。** Agent Framework 已接入且是默认编排器（见第十节），但**没有做过任何 Foundry 调用**，材料里不能写 Foundry。Agent Framework 可以写，因为 trace 里有真实执行记录。

---

## 十、第二轮：2026-10-23 夜间（MCP + 竞赛情报 + 自批判）

### 10.1 又修了 4 个真 bug

| # | 缺陷 | 怎么发现的 | 影响 |
| --- | --- | --- | --- |
| 7 | **修复路径选错**：把「审核员否掉的 claim」当成「代码门否掉的 claim」，于是走了昂贵的整轮重分析，廉价叙事重写永远不触发 | 框架版完整评测出现 6 次降级，看 trace 才定位 | 修完两个编排器从 2/12 打到 6/12 |
| 8 | **工具被模型传字符串参数就抛错**：`get_event_window("1500","1650")` 直接 `ValueError`，工具调用白费 | 消融实验日志里刷屏 `Function get_event_window failed` | 工具层对数字字符串做强制转换 |
| 9 | **默认编排器改成 framework 后，注入 mock transport 的测试被路由到框架、绕过 mock 直连真实 API**，跑了 60 秒真网络 | 13 个测试变红 + 耗时从 20 秒涨到 60 秒 | 注入 transport 时强制走直连，并加专门测试 |
| 10 | **「框架不可用」的降级是假的**：`ai.agents` 延迟导入，所以那个判断永远成立 | 降级测试没通过 | 选择器真的去 `import agent_framework` |

**第 9 条最值得记住**：一个默认值的改动把测试变成了付费 API 调用。任何「换默认实现」的动作都必须检查测试的 traffic 去哪。

### 10.2 新增交付

| 文件 | 内容 |
| --- | --- |
| `ai/mcp_server.py` | **MCP server**，5 个工具，复用同一份确定性代码，12 个测试。**这是判据点名 `MCP integration` 的能力，之前一个都没有** |
| `ai/framework_spike.py` | Agent Framework 接 DeepSeek 的可复现探针 |
| `evaluation/factcheck_bench.py` | 复核器**检出率/误报率**基准：**17/17 检出，0/4 误报**，已用回归测试锁死 |
| `evaluation/ablation.py` | 按角色消融实验（**结果不显著，已如实标注**，见下） |
| `evaluation/scan_competitors.py` / `fetch_readmes.py` | 参赛项目情报扫描（9 个查询 → 125 候选 → 17 份 README） |
| `evaluation/research/` | 竞品原始清单 + 17 份 README + 索引 |
| `evaluation/PLAN_REVIEW.md` | **自批判评估**：13 项竞品领先点、8 项自身弱点、借鉴清单 |
| `evaluation/README.md` | 五个 harness 的完整结果与限制 |

依赖新增一个：`mcp==2.3.0`（官方 SDK）。注意 **SDK 已是 2.x，`FastMCP` 改名为 `MCPServer`**，照抄 1.x 教程会在 import 处失败。

### 10.3 竞品情报的关键结论（详见 `evaluation/PLAN_REVIEW.md`）

扫描了 9 个查询、125 个候选仓库、113 个相关、17 份精读 README。**头部队伍普遍已经有而我们之前没有的三样**：MCP（5/5 最强项目都有）、broadcast overlay JSON（4 个）、A2A（3 个）。MCP 当晚补上了，另外两个排在 `PLAN_REVIEW.md` §5。

最值得偷的三个设计：
1. **Touchline 的按角色消融**：「关掉 FactChecker 后 99.7% 的数值/人名错误被拦下、零误报」「关掉 MomentScout 后每分钟 21 张卡而不是 0.7 张」—— 这才是 `Best Multi-Agent` 判据「an outcome a single agent could not achieve」的直接证据形式。
2. **GamePulse 的 overlay JSON 与真实数据校验**：同一份事件契约同时跑模拟赛与公开 Wyscout/Sportec 数据；模拟器总量对 1446 场真实联赛 8/8 达标。
3. **Second Act 的可证伪预测**：半场把每位教练的调整写成可测量的检验，下半场逐条确认或推翻。全场最有原创性的机制。

### 10.4 必须如实说明的两件事

**（1）消融实验目前不显著，不能拿来吹。** 6 个窗口、每变体只跑 1 次，各变体差异（降级数 1/3/5/5/2）落在模型随机波动范围内；第一轮里「去掉审核员反而降级更少」就是噪声。而且 `no_code_gate` 变体的坏 claim 数也是 0 —— 干净输入下模型很少编数字，所以 12 窗口实测**无法**证明代码门的价值。代码门的价值由 `factcheck_bench` 用受控污染证明（17/17）。**要发表消融，必须每变体重复 ≥3 次并报均值与离散度。**

**（2）修正一个我之前的错误诊断。** 我原先说「15 秒阈值漏掉了进球」。**实际是窗口边界问题**：第三次夺回在 1640、进球在 1680，默认检测窗口 1500–1650 里没有进球事件，而 1650–1800 窗口里没有那次夺回。**没有任何一张卡片能同时看到两者**，加宽阈值毫无用处。C 侧只能提供 45 秒的上下文档（当窗口同时包含两者时有效，已有测试证明），真正的修法是 B 侧选窗或加有界回看。已写进 `PLAN_REVIEW.md` §3.2 与第七节。

### 10.5 第二轮后的门禁状态

```
python -m pytest tests -q                       → 197 passed, 33 subtests passed
python tools/check_frozen.py                    → Frozen contracts and fixtures unchanged
python tools/check_scope.py --role C --base HEAD→ Role scope OK
python -m evaluation.factcheck_bench            → catch 17/17, false alarms 0/4
python -m evaluation.benchmark                  → 6 published / 2 fallback / 4 rejected（两个编排器一致）
```

契约仍然是 **2.0.0**，仍然没有改任何冻结文件、`backend/`、`frontend/`。

---

## 十一、第三轮：广播 overlay、A2A、编排策略

### 11.1 三个新交付（全部 C 自有，全部有测试）

| 文件 | 内容 | 对应判据 |
| --- | --- | --- |
| `ai/overlay.py` | **广播 overlay 载荷**：下三分之一、数据条、证据锚点，每个图形都带时间轴和 `source.mode`。`python -m ai.overlay` | 官方 §4.1「machine-readable enough to be rendered as synchronized graphical overlays」**之前完全没有** |
| `ai/a2a.py` | **A2A agent card**，`/.well-known/agent-card.json`，6 个 skill 与 MCP 工具一一对应，含 `x-matchmind` 诚实区块 | `Best Multi-Agent` 判据点名 A2A。三个头部竞品都有 |
| `ai/storyline.py` | **编排策略**：去重、间隔限流、10 分钟硬上限、连续性（「同一模式第 N 次」「相较上一张变化了哪些指标」） | 对应 Touchline 公布的 StorylineKeeper / MomentScout 两个消融项 |

`ai/app.py` 组合根新增两个接口（用 middleware 拦截，避不开 B 的 `/api/{unmatched}` JSON-404 兜底）：
- `GET /api/v1/replays/{id}/insights/{insight_id}/overlay`
- `GET /.well-known/agent-card.json`

MCP 工具从 5 个增加到 6 个，新增 `build_overlay`。

### 11.2 overlay 的三条诚实约束（都有测试）

1. **未通过核验的 insight 拒绝出 overlay** —— overlay 是最可能被广播观众看到的东西，不能让它比工程师看到的更宽松。
2. **每个图形都带 `source.mode`** —— 渲染方无法把 `rule_fallback` 当成实时模型输出播出去。
3. **数值只复制不重算** —— `stat_line` 的 `metric_value` 直接取自 claim，而 claim 的数值已被代码证明等于后端计算值。

### 11.3 storyline 的限流语义

初版用「新卡窗口终点 vs 上一卡窗口终点」做间隔判断，被测试抓住：`1500–1650` 和 `1600–1700` 终点差 50 秒会被放行，但它们描述的是同一段比赛，等于同一波进攻上两张卡。
改成**新卡窗口起点 vs 上一卡窗口终点**，重叠即拒。这是我这轮改的唯一一处设计缺陷，测试写对了。

### 11.4 还没做的

- **recap 角色**：官方 §4.1(iii) 明写 `automated match recaps`，契约 v0.1 有、2.0.0 砍了。这是我判断的下一块最高价值工作：它的输入粒度（整段 prefix）和 moment 角色（单窗口）不同，是多 Agent 不可合并的第二个天然战场。
- **storyline 还没接进发布链路**：它是纯策略 + 测试，激活需要在契约 2.1.0 里加 `Insight.sequence` / `Insight.continues_from`，否则前端无法渲染连续性而不自己编。
- **A2A 的 `/a2a` JSON-RPC 端点**：卡片有了，协议端点还没实现（那需要 HTTP 端点，落在 B 的 app 上，属于需要协调的部分）。

---

## 十二、第四轮：recap 角色

### 12.1 交付

`ai/recap.py`（新增），`python -m ai.recap` 可独立运行，MCP 工具增到 **7 个**（新增 `build_recap`），A2A skill 同步到 7 个，18 个测试。

### 12.2 为什么它是一个独立的角色，而不是"更长的 moment 卡"

**因为它的输入粒度不同。** moment 卡读一个窗口，recap 读整段 prefix 并要判断跨窗口什么最重要。这正是 `Best Multi-Agent` 判据要的「specialized agents with distinct roles」，也是除了契约里 `agent_and_code` 那条之外，**第二个结构性的多 Agent 论证**。

而且它**实际解决了 10.4(2) 那个窗口边界缺陷**：实测输出里，recap 明确写出「比分 Harbor FC 1 - 0 Mountain United，进球来自 H01」和「最近一次夺回在 40 秒后奏效」。**任何单张 moment 卡都做不到这件事**，因为夺回和进球从来不在同一个窗口里。

```
python -m ai.recap
→ analyst: "300 seconds played, Harbor FC 1 - 0 Mountain United. Possession is 110 to 190
   seconds, 37% to the home side. 3 to 1 on shots, and 5 to 10 completed passes.
   Goals: H01 for HOME. The most recent recovery paid off 40 seconds later.
   The score changed inside this window. These are auditable counts, not a causal explanation."
```

### 12.3 三条约束（都有测试）

1. **不读 cutoff 之后的事件**：`recap_facts` 自己校验 `events[-1].timestamp_sec <= end_sec`；用 1650 截断时 `goals` 必须为空（1681 的进球在窗外），有专门测试。
2. **不重算，只复用**：用 C 的 `high_press_chains`（唯一实现），不写第二份；数值全部来自 `backend.stats`。
3. **叙事数字必须能在 facts 里找到**：有一条测试把叙事文本里的所有数字提取出来，逐个比对 facts，多一个就红。

### 12.4 还有一个内部函数值得说明

`recap_from_insights(insights)` 走的是**已发布卡片**路径而不是原始事件流 —— 这样 recap 只能提到观众真的看过的内容，不会悄悄引入一张没播过的卡。混用模式时会如实报告 `source_modes`（例如 `["live_model","rule_fallback"]`），不把两种来源抹平。

### 12.5 契约仍然缺的那一块

`recap` 现在是自描述载荷（`matchmind.recap/1` + 自带 `validate_recap`），**不在冻结契约里**。要进契约需要一次性升到 2.1.0：新增 `Recap` 定义 + `POST /api/v1/replays/{id}/recap`，同时把 `Insight.sequence` / `Insight.continues_from` 一起加（storyline 需要）。这是同一批改动，不要分两次做。

---

## 十三、第五轮：把"消融不显著"变成一条能站住的结论

### 13.1 3 次重复的消融结果（18 次运行/变体）

| 变体 | 降级数 | 每次重复 | 组内波动 | 含全称量词的卡 | 中位延迟 |
| --- | --- | --- | --- | --- | --- |
| `full` | 5/18 | 1,2,2 | 1 | 10 | 8109ms |
| `no_code_gate` | 4/18 | 1,1,2 | 1 | 6 | 8046ms |
| `no_auditor` | 6/18 | 2,2,2 | 0 | 9 | 8141ms |
| **`no_repair`** | **17/18** | 6,6,5 | 1 | 6 | 5750ms |
| `no_tools` | 6/18 | 2,2,2 | 0 | 6 | 8094ms |

**组间均值极差 4.33，组内波动最大 1 —— 所以只有一条结论通过噪声检验：**

> **修复轮值大约 12 张已发布卡片（18 张里）。去掉它，18 个窗口有 17 个降级；留着它，只有 5 个。**

去掉代码门 / 审核员 / 工具造成的差异都在 2 以内，和组内波动同量级 —— **这三条不能声称有效应**。

### 13.2 一个不能掩盖的怪现象

`no_code_gate` 变体的"含全称量词的卡"是 6 张，**比完整流水线的 10 张还少**。最可能的解释是：修复轮只在有东西被拒时才运行，而它会重新生成叙事、把概括性措辞带回来。两次小样本无法定论，所以数字照实记录，不做粉饰。

### 13.3 为什么代码门的价值不在这张表里

`published_with_bad_claims` 在所有变体里都是 0，包括 `no_code_gate`。**干净输入下模型很少编数字**，所以实测无法证明代码门的作用。它的价值由 `evaluation/factcheck_bench.py` 用受控污染证明：**17/17 检出、0/4 误报**。代码门的价值是"对抗性输入的属性"，不是"平均输入的属性"。

### 13.4 上限在窗口数，不在重复次数

6 个窗口、其中 2 个正例，是真正的约束。加重复只能收窄噪声，不能增加覆盖面。下一步该做的是**更多合格窗口**，也就是更稠密的 fixture —— 正是 `fixture_qualify.py` 在要求的。

---

## 十四、第六轮：A2A 传输与威胁排序

### 14.1 A2A 传输（`ai/a2a_transport.py`）

之前只有 agent card 没有端点，那是"描述"不是"服务"。现在 `POST /a2a` 实现了一个**明确声明的子集**：

| 支持 | 不支持（并在卡片里写明） |
| --- | --- |
| `message/send`，JSON-RPC 2.0，一次 HTTP 一次调用 | 流式 |
| 输入一个 `data` part：`{"skill": "<工具名>", "arguments": {...}}` | 任务生命周期（`tasks/get` / `tasks/cancel`） |
| 输出 `data` + `text` 两个 part | 推送通知、文件 part |
| 8 个 skill，白名单显式列出 | **自由文本意图解析** |

**为什么不解析自由文本**：整个产品的论点是"每个结论都要可追溯"。让端点去猜"那句话想调哪个工具"，等于在每个回答前面塞一个不可追溯的步骤。所以自由文本请求会被**明确拒绝并说明原因**，而不是被猜。

未支持的方法返回 `-32601` 并附上支持列表；参数或形状错误返回 `-32602` 并说明。**"威胁排序因为数据太少而拒绝"是成功返回，不是错误** —— 有专门测试守着这条，因为"带理由的拒绝"是这个产品在正常工作，不是故障。

### 14.2 威胁排序（`ai/threat.py`）

从 `socceraction` 借的思想，没有借依赖：用值迭代在**我们自己的事件**上重估一个 16×12 的"预期威胁"网格，让一次传球可以按它推进的价值排序，而不是被计数。

```
xT(zone) = P_shoot(zone) * P_goal(zone) + Σ_j P_move(zone,j) * xT(j)
```

两条诚实属性，都有测试：

1. **分辨率跟着数据走**：依次尝试 16×12、12×8、8×6、6×4，并把每次尝试的报告留在输出里。
2. **密度不够就拒绝**：连 6×4 都到不了每格 4 次观测，就不出数字。**这是一个结论而不是 bug：5 分钟的片段撑不起预期威胁网格**，需要整场。出厂 fixture 和稠密提案都会被拒；只有整场规模的样本能出网格，测试里构造了一个来证明代码路径是通的。

发布的数值带 `label`（"不可与已发表的 xT 比较"）和 `caveat`（"网格由它排序的同一批事件估出来，只能当片内排序装置，不能当进球概率"）。还有一条测试断言数学方向正确：**禁区的价值必须高于本方半场**。

**这条"数据太少就拒绝"的规则被实测证实了，而且是正反两面：**

| 样本 | 事件 | 转移 | 结果 |
| --- | --- | --- | --- |
| 出厂 fixture | 30 | 14 | 拒绝 |
| 稠密提案（5 分钟） | 110 | 82 | 拒绝（6×4 也只有 3.89 次/格） |
| 稠密提案（45 分钟半场） | **1015** | **696** | **可用，跑满 16×12 并收敛** |

45 分钟版本的排名第一是 `+0.4000` 的那脚传球 —— 正是脚本里导致进球的那次压迫传球（t=1602s）。这既是合理性信号，也把"这项技术需要整场而不是片段"从意见变成了测试断言。`dense_fixture_proposal.py --minutes 45` 可复现。

### 14.3 现在的门禁状态

```
python -m pytest tests -q                        → 284 passed, 33 subtests passed
python tools/check_frozen.py                     → Frozen contracts and fixtures unchanged
python tools/check_scope.py --role C --base HEAD → Role scope OK
python -m ai.a2a_transport                       → message/send demo + unsupported-method refusal
python -m ai.threat                              → available=false, "a five-minute clip is too short"
```

---

## 十五、第七轮：评测台与 fixture 解耦，以及三个被自己捅出来的坑

### 15.1 评测台不再绑死一个 fixture

`evaluation/benchmark.py` 新增 `--data-dir` / `--match-id` / `--auto-cases`。用例由扫描 fixture 的每个窗口推导，不再手写：

| fixture | 用例 | 正例 | 非触发 | 负例 | 篡改 |
| --- | --- | --- | --- | --- | --- |
| 出厂（300s） | 7 | **1** | 1 | 1 | 4 |
| 稠密半场（2700s） | 15 | **5** | 4 | 2 | 4 |

**「只有 2 个正例」这个问题被解决了** —— 不是靠嘴，是靠更长的 fixture 加上均匀埋设的压迫爆发。`spread_presses()` 每 7 分钟埋一组 3 次压迫；第一次我按均匀间隔撒开，每个窗口只有 1 次夺回、检测器根本不触发，是**用例扫描自己返回 0 个正例**把这个错误抓出来的。

正例现在强制**窗口不重叠**（`min_gap=window_sec`），否则 1500-1650、1560-1710、1620-1770 会是同一段比赛算三次，样本量是虚的。

### 15.2 坑一：指标定义没进事实块

审核员拒了这样一句：*"2 of the 3 were linked shots — followed by a shot within 15 seconds"*，理由是**FACTS 里没有 15 秒这个事实**。它是对的：事实块只写了 `linked_shots=2`，没写这个指标的定义。

修法：把 `METRIC_DEFINITIONS` 放进事实块（口径来自 `docs/02_contract.md`，是公开内容）。

### 15.3 坑二：给了模型数字，却不让它复述

上一修引入的新问题，而且立刻被评测打出来：事实块现在含 `x >= 66.67` 和 `within 15 seconds`，但 `66.67` **不在允许数字集合里**，于是 narrator 复述了一个刚被告知的数字、被自己的校验器判为编造 —— 5 个正例全灭。

修法是原则性的：**事实块里出现的任何数字，叙事都有权复述。** `allowed_numbers()` 现在从 `METRIC_DEFINITIONS` 里抽取所有数字。并加了一条不变量测试：事实块里的每个数字都必须在允许集合里 —— 这条测试本该在我第一次改动时就存在。

### 15.4 坑三：格式失败与语义异议共用一个纠正预算

诊断一个降级用例时发现：narrator 输出格式不合规 → 消耗掉唯一的纠正预算 → 审核员随后提出的语义异议没有预算了 → 降级，**尽管事实完全没问题**。

契约里的"每个任务最多一次纠正"讲的是**审核员提出纠正请求之后**。narrator 的格式失败不是审核员纠正。所以现在是两个独立预算：

- **格式重试**：narrator 代码校验失败 → 带问题清单重试一次（`NARRATOR_RETRY_FLOOR_SEC = 3.0` 秒余量才重试）
- **审核纠正**：审核员提出异议 → 丢掉被拒 claim + 重写叙事，仍只有一次

并且**叙事连续两次代码失败后不再做叙事修复** —— 那等于第三次重试，浪费时间。

### 15.5 另外三项

| 项 | 内容 |
| --- | --- |
| **响应缓存** `ai/cache.py` | 只缓存模型响应，不缓存整张卡片。这样身份字段、trace、代码门都照常跑，只省掉 HTTP 调用；命中时 trace 里如实写"N 个响应来自缓存，未做新推理"。`MATCHMIND_CACHE=0` 可关 |
| **无障碍语音** `ai/overlay.py` | 每个下三分之一和数据条都带 `speech`，整个载荷带按时间排序的 `speech_script`。校验器拒绝静默图形。**这不是完整无障碍**（需要真实音频 UI 和盲测），但载荷不再是无言的 |
| **成本核算** `ai/usage.py` | token 累加 + 按公开价目估算，**始终标注"估算非账单"**，缓存命中计为 0；未知模型返回 None 而不是错数字。写进 trace 便于每张卡片对账 |

---

## 十六、第八轮：审核员自相矛盾，以及被它掩盖的真相

### 16.1 最重要的一个发现

我在诊断降级用例时看到审核员的输出：

```json
{"approved": false, "rejected_claims": [], "narrative_problems": [],
 "issues": ["No factual violations found: C1 restates high_recoveries=3 ... Narratives use only supplied numbers"]}
```

**它自己的理由说"没有事实违规"，却把 `approved` 设成 false。** 这不是判断问题，是**输出里有一个它可以自相矛盾的冗余字段**。

代价有两个，第二个更要命：
1. 每张卡多花一次模型调用（先拒，再修复）
2. **让"可见的纠正"看起来像摆拍** —— 而"纠正可见"是这个产品唯一的卖点

### 16.2 修法：去掉那个字段，让代码推导

审核员现在只返回 `rejected_claims` / `narrative_problems` / `notes`，**决定由代码从列表推导**。`notes` 只记录、不阻断。它如果仍然写 `approved: false` 但一个东西都没点出来，代码判定为通过并记录这条矛盾 —— 因为代码门已经验证过卡上的每一个数字。

同时给审核员补了它真正该学的区分：当 `high_recoveries = 3` 时，"the 3 high recoveries"、"those 3"、"2 of those 3 were followed within 15 seconds" **都是复述已给的数字，不是无据泛化** —— 那个计数本来就来自指标，回头引用它没有增加任何主张。

### 16.3 新建的评测：审核员误拒率

`evaluation/auditor_calibration.py` —— 把代码门已经接受、且只含已给数字的 claim 集喂给审核员，统计它仍然拒绝的比例。代码校验器的误报率可以零成本测（`factcheck_bench`），**审核员是模型，只能真调**，这个空白以前没补。

| 提示词版本 | 运行次数 | 误拒率 |
| --- | --- | --- |
| `c3-1.2.0` | 6 | **33.3%** |
| `c3-1.3.0` | 10 | **0.0%** |

### 16.4 连带效果

稠密 fixture 评测：**11 个有效窗口全部发布、零降级**，调用数从 45 降到 39，**11 张里 8 张只用 3 次调用**（审核员一次通过），剩下 3 张的纠正是**真的点名了具体 claim**。

### 16.5 单 Agent 基线被公平化了，然后结论变了

旧基线用的提示词比产品分析师**更短**，等于让流水线占了便宜。现在基线带**同样的规则**：指标定义、量词规则、越权示例、双档要求。它唯一缺的是第二双眼睛。

公平化之后，两个"显而易见"的指标变成了陷阱：

- **`claims_rejected` 在两种模式间不可比** —— 它统计一次运行里的每一次拒绝，**包括流水线随后纠正掉的那些**。流水线数字更高意味着纠正活动更多，不是输出更差。
- 真正可比的是：**最终发布的卡有没有通过校验**。单 Agent 在 15 个窗口里有 **5 个（33%）** 原始输出过不了校验；流水线发布同样的窗口，因为拒绝在它内部是被处理的，不是被发出的。

**所以现在能说和不能说的：**

| 能说 | 不能说 |
| --- | --- |
| 三 Agent 花 2.8 倍调用、1.7 倍延迟 | 三 Agent 更快或更便宜 |
| 单 Agent 永远拿不到 `passed`（契约要求 `agent_and_code`） | 三 Agent 每次尝试编得更少 |
| 单 Agent 三分之一的原始输出过不了校验，流水线能发布它们 | 三 Agent 在统计上更好（样本、方差都还不够） |

稠密 fixture 的结果本身也会在运行间移动：两次跑出 **11/11** 和 **8/11**。报区间和样本量，别报点值。

---

## 十七、第九轮：把审核员的另一半也测了，以及一个比数字更重要的发现

### 17.1 上一轮留下的窟窿

上一轮的校准只回答了“不该拒的拒了没有”（0.0%）。没回答“**该拒的漏了没有**”。这个窟窿很致命，因为产品对外最大的卖点是“AI 不会胡说”，而任何人问一句“那你审核员漏报率多少”，当时的答案只能是“没测过”。

### 17.2 造了 10 类软越权，全部由代码门放行

关键设计：每个案例**必须原封不动通过 `check_claims` 和 `check_narratives`**。否则测的就又是代码门，不是审核员。数字全对、引用全在窗口内、不含被禁的因果词——但结论是错的。

| 类别 | 例子 | 代码门 |
| --- | --- | --- |
| 与数据矛盾 | “HOME 这个窗口大部分时间在控球”（实际 35 秒对 115 秒） | 放行 |
| 数字对、队错 | `home_shots = 2` 写成 “AWAY took 2 shots” | 放行 |
| 全称否定 | “AWAY 一次都没抢回来”（实际抢回两次） | 放行 |
| 量词越权 | “那几次抢断每一次都变成了射门”（三次里两次） | 放行 |
| 需要整场数据的最高级 | “这是全场压迫最猛的一段” | 放行 |
| 球员级断言，但没有球员数据 | “AWAY 右后卫一直被打到失去位置” | 放行 |
| 没人测量过的机制 | “压迫奏效是因为 AWAY 中场不再跟人” | 放行 |
| 预测 | “这个套路会决定剩下的比赛” | 放行 |
| 反事实 | “如果 AWAY 那波控球转化成了射门，比分会不一样” | 放行 |
| 越权写在文案而不是主张里 | 文案里说“压迫一来 AWAY 的阵型就散了” | 放行 |

**结论一行：代码门对这 10 类 0/10 全盲；同一套代码门对 `factcheck_bench` 里那 21 条硬篡改是 21/21。** 两个评测面对的是两个不同的靶子，这就是为什么必须有两个层。这句话可以对外说，因为两个数都是自己跑出来的。

### 17.3 数字

`python -m evaluation.auditor_calibration --runs 5`（5 次/案例，65 次真实调用）：

| 语料 | 案例 | 运行 | 结果 |
| --- | --- | --- | --- |
| 诚实卡（代码门已批准） | 3 | 15 | **15/15 批准 → 误报 0.0%** |
| 做手脚的卡（代码门也批准） | 10 | 50 | **50/50 抓到 → 漏报 0.0%** |
| — 其中点名的正是被做手脚那条 | 10 | 50 | **50/50 → 0.0% “抓错了对象”** |
| 合计正确判断 | 13 | 65 | **100.0%** |

为什么要三个数：一个“见谁都拒”的审核员在漏报侧是 100%，在诚实侧是 0%。只报一个方向，这个评测可以被一个坏模型刷满分。`summarise()` 里专门有个 `discrimination` 字段就是这个意思，并且有单测钉住：全拒 → 50%，全批 → 50%。

### 17.4 给自己泼的冷水（这段别删）

**100% 是语料作者写出来的，不是模型能力的上限。** 十个案例都是我列的、都写成判定明确的形态，窗口、模型、提示词都只有一套。它证明的是“我列得出的越权它抓得住”，**不是**“审核员准确率 100%”。没覆盖的：真话但误导、正确数字配错误因果链、跨窗口拼出来的假趋势、中文语料下的同类越权。

写进材料时的正确说法是：*“在 10 类可判定的软越权上，50 次运行全部被拒，且全部点名了被做手脚的那条主张”*，不是 *“审核员准确率 100%”*。

### 17.5 recap 跨窗口一致性

单份 recap 全绿、整个系列自相矛盾，是这种产品独有的失败模式，因为观众看到的是系列。新增两个纯确定性函数（零成本、无模型）：

- `recap_series_issues(recaps)`：自己按 cutoff 排序，先各自校验再比较。抓：累计计数倒退（控球/射门/传球/事件数/比分）、同一个进球被两次记给不同球员、时钟倒退、同窗口两份 recap 数据不一致、一个系列里混了两个 match。
- `recap_from_insights_issues(payload, insights)`：卡片版 recap 之前是自己从卡片推 cutoff，所以永远抓不到“卡片属于另一场”和“两张卡时间重叠”。现在能抓。

`python -m ai.recap --series 1550 1650 1800` 可直接演示。18 个新测试，含反向断言：**只增不减的计数不许被报警**，否则这个检查就变成噪音。

### 17.6 这轮被自己的测试抓出来的两个 bug

| bug | 怎么暴露的 |
| --- | --- |
| `summarise()` 依赖 `run_case()` 预先打好的 `approval_rate` 戳，喂给它没打过戳的数据就静默返回 0 次运行 | 写单测时发现——评测函数不该依赖上游字段，改成直接从 runs 算 |
| 我自己写的“计数倒退”测试用例其实没倒退（1650 减 5 仍是 30，比 1600 的 10 大） | 测试挂了。**是测试写错不是代码写错**，改成模拟真实的“只读了 1650–1700 而不是整个前缀” |

第二个值得记：如果当时图省事把断言改成 `assertTrue(problems) or True`，这个检查就永远测不出东西了。

### 17.7 门禁状态（第九轮结束）

- `python -m pytest tests -q` → **395 passed**（第八轮 363，本轮 +32：审核员语料 14 + recap 系列 18）
- `python tools/check_frozen.py` → 契约与 fixture 未改
- `python tools/check_scope.py --role C` → 通过
- 新增文件：`tests/ai/test_auditor_calibration.py`；修改：`evaluation/auditor_calibration.py`、`ai/recap.py`、`tests/ai/test_recap.py`、`evaluation/README.md`、`evaluation/SUBMISSION_POSITIONING.md`

---

## 十八、角色卡逐项对账

`roles/C_AI.md` 里有六个工作块和一份“本角色检查”。下面把每一项对到一个**跑得起来的测试名字**，因为“我觉得我做了”不算证据。

### 18.1 六个工作块

| 工作块 | 状态 | 证据 |
| --- | --- | --- |
| C1 基线导入、三人角色、类型生成、冻结摘要、共同测试、`analyze` 离线跑通并核对 fallback 标签、每日集成时间 | **完成，除 `baseline_sha`** | `TEAM_ROLES.json` 已填（同步时间 21:00）；`tools/check_frozen.py`；`tests/test_contracts.py`；`test_service.py::OfflineDefaultTests::test_unconfigured_config_is_a_labelled_fallback`。**`baseline_sha` 仍是 `pending`——要等 PR #8 合并，唯一一格卡在别人手上** |
| C2 开通国内模型、配置检查、一次真实 `--live` 探针、只记成功标志/模型名/usage/延迟、不记 Key | 完成 | `python -m ai.probe --live`；`ai/usage.py` 账本；`test_invariants.py::NoSecretsTests`（3 个，含“配置的公开视图永不暴露 Key”） |
| C3 结构化分析 + 双档叙事 + 审核 + 程序校验；`async analyze(dict)->dict`；先 mock 单测再实测；事实只来自输入；纠正最多一次；总 deadline 与并发生效；超时返回诚实 fallback | 完成 | 18.2 全部十三项；`tests/ai/test_service.py`（50 个测试）；`test_app.py::AnalyzeSignatureTests` 钉住签名 |
| C4 Agent Framework 接管已验证流程；单 Agent 导入 → 无密钥实例化 → 真实单次调用 → 串三角色；角色任务和输入不同；Trace 来自实际执行；注入“证据不足推断”展示审核能力 | 完成 | `MATCHMIND_ORCHESTRATOR=framework` 为默认；`test_orchestrator.py::SelectionTests`（5 个，含“缺框架要降级不是崩”）；`test_service.py::LivePathTests::test_roles_get_different_system_prompts_and_inputs`、`::test_traces_record_each_real_agent`；注入能力见 17.2 那十类 |
| C5 12 个起步评测，单/多 Agent 共享输入、模型、确定性校验器；记录错误/纠正成功/耗时/调用数；不保证更快更便宜；不改 B 的调用签名；两个观众文本一次结果产出 | 完成 | `evaluation/benchmark.py`；`evaluation/README.md` §2–§3（含“不可比指标”）；`narratives.casual` 与 `narratives.analyst` 在契约里是同一个 `Insight` 的两个字段，一次产出 |
| C6 每日合并小 PR + 跑共同检查；与 A/B 验收 reset/模式/模型故障/公网访问；填技术栈、模型路由、未实现项；与提交代表完成材料；公开与正式提交由有权限成员执行 | **部分** | 技术栈/模型路由/未实现项在第七节；材料底稿在 `evaluation/SUBMISSION_POSITIONING.md`。**合并、联合验收、录像这三件 A/B/代表不在场做不了** |

### 18.2 “本角色检查”十三项

| 检查项 | 测试 |
| --- | --- |
| 非 JSON 响应 | `test_service.py::BoundedFailureTests::test_non_json_content_falls_back` |
| 空响应 | `::test_empty_content_falls_back` |
| 错误 ID（编造的事件 id） | `::VerificationUnitTests::test_invented_event_id_is_rejected` |
| 越界时间 | `::RefusalTests::test_request_outside_window_is_rejected` |
| 错误数字 | `::test_wrong_metric_number_is_rejected`、`::test_metric_claim_stating_the_wrong_number_is_rejected` |
| 证据不足推断 | `::test_unsupported_causal_inference_is_rejected` |
| 超时 | `::test_timeout_returns_fallback_and_says_why` |
| 一次纠正上限 | `::CorrectionBudgetTests::test_correction_is_capped_at_one_round`、`::test_persistent_auditor_rejection_falls_back` |
| fallback 标签 | `::OfflineDefaultTests::test_unconfigured_config_is_a_labelled_fallback`、`::LivePathTests::test_valid_model_output_passes_with_live_labels` |
| 返回身份原样保留 | `::OfflineDefaultTests::test_identity_is_returned_unchanged` |
| 测试必须 mock 网络（机器上有 Key 也不许付费调用） | `::test_bare_analyze_never_touches_the_network`、`test_app.py::HttpTests::test_offline_composition_never_calls_a_model` |
| 共享契约的 mock 模式语义仍成立 | `tests/test_contracts.py`、`tests/test_mock_api.py`（B 的，C 只保证不破坏） |
| 通用 fallback 遇错输入优先 reject，而不是用错数字讲一遍 | `::RefusalTests::test_metrics_that_contradict_events_are_rejected_not_narrated`、`::test_shot_count_that_contradicts_events_is_rejected` |

**这张表的方法论**：角色卡写的每一项都要能被一个测试名字指出来；指不出来的，写进第七节“仍未完成”，而不是留一句“我做了”。

---

## 十九、第十轮：合并、B 报的一个真 bug、以及整合验收通过

这一轮不再是“我自己的活”，而是整合人的活：把 PR #8 合进整合分支、跑共同检查、处理 B 交接里指向我的问题。

### 19.1 合并

PR **#8** 已 squash 合并进 `codex/backend-ab-mvp`，合并提交 **`f3111a2`**。squash 是仓库既有惯例（B 的 PR #6 也是 squash 进 main 的）。

合并之后立刻在合并结果上跑全套检查，抓到两个失败，性质完全不同：

| 失败 | 是谁的问题 | 处理 |
| --- | --- | --- |
| `test_invariants.py::test_outcome_enum_matches_what_the_loader_accepts` | **我的文档过期了** | B 已经支持 `foul`，我的断言还写着“两边差一个 foul”。改成断言两边**相等**，并把 `PLAN_REVIEW 3.1b` 从“未修”改成“B 已关闭” |
| `tests/backend/test_reporting.py::test_export_refuses_shared_and_other_role_paths` | **不是 bug，是我验证环境的假阳性** | 那个守卫靠 `(ROOT.parent / ".git").exists()` 判断“仓库根”。我为了避开 `github.com:443` 把分支下成 zipball 解压验证，那个目录没有 `.git`，所以守卫退化。补一个 `.git` 目录后该测试通过——这也是我后来重新 fetch 成功、改回正常 git 工作区的理由 |

### 19.2 B 报的真 bug：降级卡的证据被截断

`backend/C_INTEGRATION_FINDINGS.md` 里 B 给我留了一条精确的报告，附复现命令，没有代我改代码：

> `ai/fallback.py::_evidence` 最多返回 12 个 ID，而 `rule_claims` 会从**每一条**链条里挑夺回/射门 ID。于是某条主张可以引用一个合法事件，而这个事件不在 `Insight.evidence_event_ids` 里。共享 `check_result` 正确地抛 `claim evidence mismatch`。

**这是真 bug，不是误报。** 我用自己的生成器独立复现了：6 条链条的窗口里，卡片证据被截到 12 条，主张引用了 13 条，缺 3 条，`check_result` 抛错。B 在它的增强数据上量到的影响面是 **12 个正常输入里 4 个**。小 fixture 太稀，永远碰不到这条边界。

修法（`ai/fallback.py: card_evidence`）：卡片证据 = 基础选择 **∪ 全部保留主张的引用**，保序、去重、不设总上限。B 明确写了不许为了让门禁变绿去削弱 `check_result`、删掉第三次夺回、篡改指标或悄悄截断——一条都没做。

顺手补了 10 个离线测试（`tests/ai/test_fallback_evidence.py`），其中一个专门钉住“这个窗口的引用确实超过 12 条”，否则测试会因为够不到上限而假绿；另一个钉住小 fixture 的卡片证据**没有被顺带撑大**。

### 19.3 B 的验收门禁：通过

B 准备的验收命令，在合并后的工作区跑：

```
python -m backend.showcase                              -> status passed, 12 valid, 3 tampered, 0 model calls
python -m deploy.adapter_check --output ...             -> status passed, 12/12 valid, 3/3 refused,
                                                           model_calls 0, network_connections blocked
```

**这意味着增强数据集（`data/extra/showcase/{press,delayed,quiet}`）对 C 来说已经解锁**——B 之前因为这个问题把组合运行的数据目录限定在 `validated-demo`。现在 B 的文档说“C 修复后由整合者运行 `deploy.adapter_check`”，这条已经执行并通过。

### 19.4 B 的另外两条纠正，都对我

1. **foul**：B 说得很直接——“C 原先‘B 不支持 foul’的说明已过期；B 不会代改 C 文档或测试”。这是对的：文档所有权在 C，漂移由 C 收。已改。
2. **演示窗口**：我原来建议把窗口从 1500–1650 挪到 1540–1690。B 的回答更省事——`data/extra/showcase/press` 这一场的进球**本来就在 1500–1650 里**（1650 时刻比分 1:0），采用它就不需要动窗口。两条建议都写进 `PLAN_REVIEW` §3.2，并注明各自适用于哪个数据集。

B 还有一条约束需要 C 一起守：**“第三次夺回没有关联射门，不得声称三次全部产生射门或三次导致了进球。”** 我们的 fallback 文案本来就是这么写的（“其中一次没有在 15 秒内形成射门，但同一波进攻后续完成了射门或进球”），`ai/verify.py` 也会拒绝更强的措辞，所以这一条不需要改代码，只需要不在材料里说过头。

### 19.5 门禁状态（第十轮，在合并分支上）

- `python -m pytest tests -q` → **422 passed, 62 subtests passed**（合并前的合并树是 411 passed + 2 failed）
- `python -m deploy.adapter_check` → **passed**（12/12 + 3/3，0 次模型调用，网络被阻断）
- `python tools/check_frozen.py` → 契约与 fixture 未改
- `python tools/check_scope.py --role C` → 通过
- 修改：`ai/fallback.py`、`tests/ai/test_invariants.py`、`evaluation/PLAN_REVIEW.md`、`docs/handoff/ai.md`、`TEAM_ROLES.json`；新增：`tests/ai/test_fallback_evidence.py`

### 19.6 `main` 第一次拿到了完整的基线

这一节是给队友看的**当前状态**，前面所有小节的 SHA 都只是历史。

| 分支 | 现在是什么 | 时间 |
| --- | --- | --- |
| **`main`** | **`8e740e5`，全队要提交的就是它**：starter v2.1 + A1 前端 + B 的后端/数据 + C 的 AI 管线与评测 | 2026-10-23 12:21 UTC+8 |
| `codex/backend-ab-mvp` | `37b023b`，已完成使命，被 `main` 吸收 | — |
| `codex/ai-verification` | 已合并（PR #8 squash 成 `f3111a2`），不要再往上开发 | — |

`main` 上实测：**422 passed / 62 subtests**、`check_frozen` 未改、`check_scope --role C` 通过、`deploy.adapter_check` **12/12 通过 + 3/3 篡改被拒 + 0 次模型调用**。

合并顺序有一个坑，值得记住：A1 的分支（PR #3）当初把整个 starter 包也一起提交了，所以它 squash 进 `main` 之后，`matchmind/` 下的文件在 `main` 和整合分支两边都成了“新增”，git 报的是 **add/add 冲突**而不是内容冲突。解法是把 `main` 合进整合分支，冲突文件一律取整合分支那一版（内容本来就更新），得到的合并提交 `37b023b` 的树与合并前**逐字节相同**——那次合并只补了祖先关系，没有改任何内容。

两个 PR 的状态要说明，免得后面有人误合：

- **#5（B 的开发包）已关闭**。它把整个包存成 `docs/development-pack-v2.1/package/starter-overlay/matchmind/…` 的嵌套副本，235 个文件；`main` 现在已有 `matchmind/` 下的同一份内容，合并会变成两份。
- **#1（开发计划文档）仍是 draft**。`main` 的 `docs/` 目前只有 `docs/hackathon.md`，这个 PR 会补上 `docs/contracts.md` 与 `docs/development-plan.md`（290 行）。它是 draft，我没有替作者标成 ready 并合并。

### 19.7 下一步（按紧急度）

1. **代表**：把 #1 标 ready 并合并，`main` 的文档就完整了；然后录 110 秒视频（`evaluation/DEMO_SCRIPT.md`），公开仓库，正式提交。
2. **B**：决定演示用哪套数据。`validated-demo` + 窗口 1540–1690，或者直接用已经通过门禁的 `data/extra/showcase/press`（进球本来就在 1500–1650 里）。两条都写进 `PLAN_REVIEW` §3.2。
3. **A**：A2/A3 的卡片渲染。C 的产出目前只能在 API、overlay 快照和 MCP 里看到，视频里不能假装界面已经能显示。
4. **C（我）**：契约 2.1.0 要 A/B 点头才能动；除此之外 C 侧已无单方可做的项。

---

## 二十、`AI_RULES.md` 逐条对账（以及这轮补的两处）

方案包里的 `AI_RULES.md` 是"所有开发 AI 共用的规则"，`01_三人开发与AI指令.md` 末尾还有"不同 AI 的并行与合并规则"。这一轮我把两份文件逐条对着仓库查了一遍，**发现两条明确派给 C 的动作从来没做过**，已经补上；其余各条能给出证据，列在下面。

### 20.1 这两条漏了，现在是补上的

方案原文（`01_三人开发与AI指令.md` §PR 必须写清楚）：

> 提供 `integration-snippets/ci.yml` **供C**在看过仓库现有CI后放入根 `.github/workflows`。不要直接替换现有CI。**CI需要新增前端构建和正式后端测试**。

> 目前不能独立保证GitHub主分支保护已启用。**拥有仓库管理权限的人**按团队决定配置 required checks 和 review。

**实际情况：仓库里根本没有 CI。** `.github/` 下只有一个 PR 模板和一个 issue 模板，`integration-snippets/ci.yml` 从第一天起就躺在那儿没人装；CODEOWNERS 也不存在。这一条是写给整合人的，而整合人就是我——四轮下来我一直在跑本地检查，却从没把检查装到仓库上。已补：

| 新增 | 内容 | 为什么这样写 |
| --- | --- | --- |
| `.github/workflows/ci.yml` | 两个 job。`python`：装 `requirements-dev.txt`（已 `-r` 聚合三份依赖）→ `check_frozen` → **重新生成 types/OpenAPI 并 `git diff --exit-code`** → `pytest tests -q`。`frontend`：`pnpm install --frozen-lockfile` → `typecheck` → `build` → `pnpm test` | 没有替换任何现有 CI（因为不存在）。**没有**把 B 的 `deploy.verify_backend`（跑 584 次回测、起真 uvicorn）和 `deploy.adapter_check`（需要 B 先生成 showcase 包）塞进 CI——那两个是提交前的人工验收，写进 CI 只会让它一直红 |
| `.github/CODEOWNERS` | 按 `CODEOWNERS.fragment` 的骨架填**真实**账号（三个用户名都用 API 核过存在）：A=@tiempo0206、B=@wunianze666-netizen、C=@farlyfeifei。`contracts/`、`data/fixtures/`、`tools/`、`TEAM_ROLES.json` 归整合人 | 文件开头写明它**只请求 review、不阻断合并**：真正的 required checks 需要 admin 打开分支保护，而我没有 admin（`permissions.admin: false`）。写一句"已启用保护"就是撒谎 |

顺带核了两件相关的事，都不需要改：

- **`ai/requirements.txt` 相对 B 验证过的 `02228b8` 没有任何变化**，所以 B 的 `deploy/requirements-release.lock`（42 个包，基于 `02228b8` 固定）**仍然匹配**，不需要复核快照。
- **生成文件没有漂移**：`python tools/generate_types.py` 和 `generate_openapi.py` 重跑之后 `git diff` 为空，`check_frozen` 依然 unchanged。这一条以前只是"应该没漂"，现在是"跑过，没漂"。

### 20.2 十条共用规则

| # | 规则 | 状态 | 证据 |
| --- | --- | --- | --- |
| 1 | 只做本角色任务；先读契约再动手；不凭旧聊天改字段 | 遵守 | 契约 2.0.0 全程未改；每轮先跑 `check_frozen` |
| 2 | 遵守文件白名单；不重写别人模块；新增依赖要说明 | 遵守 | `check_scope --role C`；`backend/`、`frontend/`、`contracts/`、`data/fixtures/` 零改动；`ai/requirements.txt` 自 `02228b8` 未动 |
| 3 | `contract.schema.json` 是真源，`types.ts` 是生成文件；时间语义与窗口边界 | 遵守，**本轮验证** | 20.1 的重生成检查；`tests/ai/test_metric_definitions.py`、`test_invariants.py` |
| 4 | 只用 `tools/reference.py` 做参考；不把 Mock 当正式后端；不把静态 `analysis_result.json` 当真实模型输出 | 遵守 | 所有单测注入 httpx transport；`generation.mode` 三态；`model_calls: 0` 在 adapter 报告里 |
| 5 | C 不能等 B：先用固定输入完成校验、失败回退和真实模型探针 | **完成** | `analyze()` 离线可用；`python -m ai.probe --live` 跑过 |
| 6 | 前端不持密钥；`.env` 不入库/不贴群聊/不进日志视频提示词；只发必要数据 | 遵守 | `NoSecretsTests`（3 个）；tracked 树 `sk-` 模式零命中；`input_safety_issues` 只放行白名单 id |
| 7 | 自动测试不做真实付费调用 | 遵守 | `test_bare_analyze_never_touches_the_network`、`test_offline_composition_never_calls_a_model`；CI 里也没有 Key |
| 8 | 一次一个小块；先列文件与验收命令；完成后更新 handoff（版本/文件/接口/测试/已知限制/下一块） | **本轮补齐** | 本文件顶部的"本轮交付"六项表，就是这条要求的格式 |
| 9 | 不无限重试；不放宽校验掩盖错误；不删失败测试；最多一次纠正；deadline 生效；reset 后旧任务不发布 | 遵守 | `CorrectionBudgetTests`（7 个）；两次失败就 fallback；本轮修的 bug 是**加严**校验不是放宽 |
| 10 | 提交/推送/PR/合并遵守权限；文档不能代替授权；**C 做最终合并** | 遵守，**本轮执行** | PR #8 → #9 → `main`。但仓库公开需要的 admin 权限我没有，这一格交回给 owner |

### 20.3 中国开发与国际部署约束

| 约束 | 状态 |
| --- | --- |
| 依赖镜像走 `docs/01_cn_setup.md`；包版本不变；镜像缺包不私自降级或重建锁文件 | 遵守：本轮**没有动过任何锁文件**。CI 里 `pnpm install` 保留 `frontend/.npmrc` 的 npmmirror 配置，不让它悄悄回落到默认源 |
| 前端不用海外字体/脚本 CDN/远程比赛样本；生产同源、单进程、密钥在后端 | 属 A/B；C 侧只在 CI 里跑 `typecheck`/`build`，不引入任何远程资源 |
| **云上再次验证国内 API，不能从开发机成功推断云上成功** | **已做（第二十二节）**：Render 新加坡主机上的真实请求打到了 `api.deepseek.com`，产出 `live_model` + `agent_and_code` + `passed` 的卡。这条以前是"未做"，现在是"做过，证据在公网 URL 上" |
| 集成人负责跨模块依赖整合、CI 与代码归属 | 本轮补齐 CI 与 CODEOWNERS（20.1） |

### 20.4 一个我要说明的守卫盲区

`tools/check_scope.py` 只扫 `matchmind/` 内的路径（`git diff --relative -- .`），所以 **`.github/` 和仓库根 `docs/` 它是看不见的**。我没有为了让新文件"通过检查"去扩白名单——那会让守卫看起来覆盖得比实际更宽。正确说法是：这两处只有人工 diff 审查，CI 与 CODEOWNERS 的改动必须有人看。要真正覆盖，得改守卫的扫描根，那是另一件事，我不在这一轮顺手改。

### 20.5 本轮修改文件

- 新增：`.github/workflows/ci.yml`、`.github/CODEOWNERS`
- 新增：`evaluation/evidence/README.md`、`evaluation/evidence/live-run-2026-10-23-framework.json`、`tests/ai/test_live_evidence.py`
- 修改：`evaluation/live_smoke.py`（`--record` + 两处诚实化）、`evaluation/README.md`、`docs/handoff/ai.md`

### 20.6 CI 不是"写好了"，是"在 GitHub 上绿了"

写完 YAML 就宣布"有 CI"是我一贯要挑的毛病，所以这一条实际验证过。推送 `dc24f0b` 到 `main` 后，workflow 自己触发并跑完：

```
gh run view 39903517201
  contracts and offline suite          completed / success
  frontend typecheck, build and test   completed / success
```

两个 job 都真绿：Python 侧装的是 `requirements-dev.txt` 里钉死的版本、跑 `check_frozen`、重生成 `types.ts`/`openapi.json` 并 `git diff --exit-code`、再跑全套 pytest；前端侧用 `pnpm install --frozen-lockfile` 走 `frontend/.npmrc` 里钉的 npmmirror 源，然后 `typecheck` / `build` / `pnpm test`。

这一条顺带解决了一个我之前没意识到的问题：**从第九轮起 CI 是空的，意味着我的所有检查只在我这台机器上发生过**。现在别人提 PR 也会被同样检查一遍。

**后续又补了第三个 job（第十四轮）**：`frontend consumer against a real B/C application`。前两个 job 各测一边——Python 测试摸不到前端，前端 job 不起服务——**所以 A 的消费端和 B 的接口哪天不说话了，CI 也不会红**。`tests/frontend/backend-probe.mjs` 本来就干这件事（在回环端口起组合应用、5 倍时钟、`MATCHMIND_MODEL_PROVIDER=mock`，跑暂停冻结 / 两会话隔离 / 快照重连 / 旧 run 拒绝），只是没接进 CI。现在三个 job 全绿：`39967587069`。

---

## 二十一、第十二轮：B 的全套验收在 `main` 上通过，以及一个中文数字的真 bug

### 21.1 共同检查：B 的一条命令验收

`C6` 要求"每日合并小PR并跑共同检查和已有角色测试"。前几轮我跑的都是我自己那部分；这一轮在 `main` 上跑了 B 的整套验收（`python -m deploy.verify_backend`，包含数据审计、确定性分析、584 个合成回测、真实 HTTP/SSE 检查、回收进程）：

```
status: passed
synthetic_backtest: normal 512 / invalid 72 / failed 0
                    false_triggers 0 / missed_triggers 0
                    logical_seconds_checked 154112 / snapshot_comparisons 1536
http_and_sse:      stats, retry, play_pause, reset, old_run, invalid_input,
                   SSE_snapshot_reconnect  —— 数据集含 quiet（不该触发的那套）
tests:             backend 85 passed, common 19 passed
model_ready:       false（该进程没配 Key，如实报告，不是失败）
```

这是整条集成链第一次被 B 自己的标准验过：A1 前端、B 的后端/数据、C 的管线在同一个提交上一起通过。**零模型调用**，因为 `model_job_requested: false`。

### 21.2 中文数字：一个会冤枉模型的 bug

上一版只认 `十 / X十 / 十Y / X十Y`，文档里写着"部分覆盖"。查了一遍发现它不是覆盖面小的问题，是**读错**：

- `一百一十五` 会被匹配到里面的 `十五`，读成 **15**。于是一个正确写出 115 的模型，会被判成"陈述了未提供的数字 15"——**报错信息本身都是错的**。
- `states_value("持球一百一十五秒", 115)` 返回 `False`，所以中文输出只要把数字写全，指标主张就会被丢掉。

改法：新增 `chinese_numeral()`，按位解析 `十五 / 三十五 / 一百一十五 / 两百 / 一千二百`（"两百"→200，"一千二百"→1200），并且：

- `numbers_in` 改成扫描**连续数字串**而不是搜 `十` 的组合。`三十五个` 现在整串读 35，不再被拆成 15。
- `百分之三十七` 里的 `百` **不算 100**（那是百分比前缀，不是数量）。不做这一步的话，任何中文百分比句子都会被判成伪造了 100。
- **孤立的单个数字仍然不认**。`一次都没射门`、`进攻三区` 继续是零命中——这是刻意的取舍，写进 docstring。

4 个新测试钉住：百位整串读取、正确的中文百位指标被接受、百分比前缀不误读、孤立单字继续不识别。

### 21.3 发布门：`release_check --profile integrated` 从 2 项阻塞到全绿

B 的 `deploy/release_check.py` 是"整合者接手时才跑到"的那道门，之前没人跑过。第一次跑的结果：

```
blocking: ["A_bundled_frontend_artifact", "same_origin_frontend_enabled"]
```

两条都不难，但都要有人真的做：前端 `dist/` 没构建过，同源托管开关没打开。做完（`pnpm run build` + `MATCHMIND_SERVE_FRONTEND=1`）再跑：

```
blocking: []
  audited_reproducible_data        passed
  C_composition_source             passed
  C_pinned_dependencies_installed  passed
  A_bundled_frontend_artifact      passed
  same_origin_frontend_enabled     passed
model_calls: 0
model_endpoint_verified: false      ← 如实：这一步不验模型
frontend_browser_verified: false    ← 如实：这一步不验浏览器
```

### 21.4 组合入口真的能把三块东西一起端出来

门禁过了不等于能跑，所以顺手起了 `deploy.release_run`（B 的发布入口，固定单 worker，指向 C 的组合根 `ai.app:app`），用 `curl` 打了三个点：

```
GET /api/v1/health   -> {"status":"ok","contract_version":"2.0.0","mode":"production","model_ready":true}
GET /                -> 200 text/html 677B        （A 的 dist，和 API 同源）
GET /api/v1/matches  -> [{"match_id":...,"home":"Harbor FC",...}]
GET /.well-known/agent-card.json -> {"schemaVersion":".../agent-card.json","name":"MatchMind",...}
GET /api/v1/replays/NOPE/insights/NOPE/overlay -> 404
```

`model_ready: true` 是因为本机 `.env` 有 Key；本机跑通**不等于**云端跑通——`docs/03_resources.md` 和 `AI_RULES.md` 都明确要求从真实宿主再测一次。那一步在第二十二节完成了。

### 21.5 门禁状态（第十二轮）

- `python -m pytest tests -q` → **433 passed, 62 subtests passed**（上一轮 429，+4）
- `python -m deploy.verify_backend` → **passed**（21.1）
- `python tools/check_frozen.py` → unchanged
- `python tools/check_scope.py --role C` → OK
- 修改：`ai/verify.py`、`tests/ai/test_service.py`、`docs/handoff/ai.md`

---

## 二十二、公网部署：Render 上的真实一次

负责人给了 Render 的管理密钥、服务 ID 和仓库信息，要求直接部署。做完的结果先写在最前面：

**线上地址 `https://matchmind-backend-preview.onrender.com`，跑的是组合镜像（C 的组合根 + A 的前端 + B 的数据），一次真实的 `live_model` 卡已经在公网上产出。**

### 22.1 服务原来配的是错的镜像

`GET /v1/services/srv-dbdegcnavr4c739pockg` 读出来的配置：

```
rootDir:        matchmind/
branch:         main
dockerfilePath: deploy/Dockerfile          ← 这是 B 的"纯后端"镜像
SERVE_FRONTEND: 0
MODEL_TIMEOUT:  12
```

`deploy/Dockerfile` 里没有 `ai/`，也没有前端。也就是说按原配置部署出来的服务**永远不会有 AI 卡片**——这正是 B 在 `INTEGRATOR_HANDOFF_CN.md` §7 里警告的那件事：

> **不要只在 Render 填 Key，却继续启动 B-only 镜像。**

改成 B 指定的组合镜像：

| 项 | 改成 |
| --- | --- |
| `dockerfilePath` | `deploy/Dockerfile.release` |
| `MATCHMIND_SERVE_FRONTEND` | `1`（同源托管 A 的 dist） |
| `MATCHMIND_MODEL_TIMEOUT_SEC` | `20`（B 的 12 秒装不下一次纠正） |
| `MATCHMIND_MODEL_PROVIDER / BASE_URL / NAME` | `deepseek` / `https://api.deepseek.com` / `deepseek-flash` |
| `MATCHMIND_ORCHESTRATOR` | `framework` |
| `MATCHMIND_THINKING` | `disabled` |
| `MATCHMIND_MODEL_API_KEY` | 由负责人在平台上填，不进仓库、不进镜像 |

其余限额项（8 会话 / 30 次每小时 / 并发 1）保持不动。

### 22.2 一个真实的部署阻塞：`dist` 被 gitignore 了

第一次触发部署会必然失败，原因在组合镜像第 19 行：

```dockerfile
COPY frontend/dist ./frontend/dist
```

`frontend/dist` 在**两个** `.gitignore` 里都被忽略（项目级一条、仓库根一条 `dist/`，深的那个赢），而 Render 是从 git 构建的。于是 `release_check --profile integrated` 在构建期就会因为没有 `A_bundled_frontend_artifact` 而失败。

处理：把 `dist` 纳入版本控制（4 个文件 / 249 KB），根 `.gitignore` 加 `!matchmind/frontend/dist/` 并写明理由。**选择跟踪而不是 `git add -f`**，是为了让"前端改了但 dist 没重构建"这件事在 `git status` 里看得见，而不是被 ignore 规则藏起来。

同一张构建期门禁也在提醒：`deploy/Dockerfile.release` 的第 1 行原本就写着 "Integrator supplies … A's already built frontend/dist"——**它一直假设整合者会把 dist 放进去，而没人做过**。

### 22.3 部署与验证

```
POST /v1/services/{id}/deploys
  -> dep-dbdgonui0phs739oipb0  build_in_progress -> update_in_progress -> live
```

公网实测（全部是真实请求，不是本地）：

```
GET /api/v1/health   -> {"status":"ok","contract_version":"2.0.0","mode":"production","model_ready":true}
GET /                -> 200 text/html 677B          （A 的 dist，与 API 同源）
GET /api/v1/matches  -> MM-DEMO-01
POST /api/v1/replays -> R-80b456f0...（speed 5）
POST .../control {"action":"play"}  -> 1755 秒时比分 1:0
GET /api/v1/replays/{id} -> insights[0] =
      window 1500-1650, high_recoveries 3, linked_shots 2
      generation   = {mode: live_model, provider: deepseek, model: deepseek-flash}
      verification = {status: passed, method: agent_and_code, rejected_claims: ["C5"]}
GET .../insights/{id}/overlay -> {"schema":"matchmind.overlay/1", ...}
GET /.well-known/agent-card.json -> {"name":"MatchMind", ...}
```

**这一条最有价值**：`rejected_claims: ["C5"]` 说明在公网上、用真模型，确实有一条主张被审核员砍掉，卡片仍然 `passed` 发布出来了。这是整个产品卖点在公网上的第一次实证。

trace 也来自这次真实执行：

```
validator  started   orchestrator=agent_framework
analyst    completed 4549ms  framework claims=4 rejected=1 tools=get_metrics,get_candidate_moments
analyst    completed 2912ms  framework claims=5 rejected=0 tools=none
narrator   rejected  1462ms  issues=1
narrator   completed 1661ms  agent_framework; code-check retry (issues=0)
auditor    completed 1338ms
```

注意 `narrator rejected -> code-check retry -> completed`：**代码门在公网上真的拦了一次并修好了**，不是排练。

### 22.4 这一节要写清楚的边界

- 免费的 Render 实例**空闲后会休眠**，冷启动首请求要等几十秒。演示前先手动打开一次预热，或者负责人评估常驻实例的费用。**不要声称"随时秒开"。**
- 服务名仍是 `matchmind-backend-preview`（当初 B 建的名字），URL 也带着 `preview`。改名会换域名，提交前动它没有收益，所以留着。
- 只有**一次**真实调用被公网验证。它证明"这条链路在云上能通"，**不证明**稳定性、并发或费用。`SUBMISSION_POSITIONING.md` 的措辞规则继续有效。
- 模型 Key 只存在于 Render 的环境变量里，仓库、镜像、日志里都没有。部署脚本手里那份 token 是负责人的管理密钥，用完应当轮换。
- 这一轮改了 `deploy/` 之外的镜像选择与平台配置，**没有改 B 的 Dockerfile、也没有改任何 `backend/` 代码**。

### 22.5 门禁状态（第十三轮）

- 公网 `deploy.release_check --profile integrated` 的构建期检查在镜像里跑过并通过（镜像因此才起得来）
- 本地 `python -m pytest tests -q` → 433 passed（本轮只改文档与 `.gitignore` + 新增 dist）
- `tools/check_frozen.py` → unchanged；`tools/check_scope.py --role C` → OK
- 新增：`frontend/dist/`（4 个文件）；修改：`.gitignore`、`matchmind/.gitignore`、本文件、`evaluation/SUBMISSION_POSITIONING.md`

---

## 二十三、整合人对账：A 和 B 的角色卡

我是整合人，所以"他们说自己做完了"不能当证据。这一节把 `roles/A_FRONTEND.md` 和
`roles/B_BACKEND.md` 的每个工作块对到**跑过的东西**上，并明确标出哪几条我只核对了代码、没有能力亲自验证
（我没有浏览器）。这份对账单是给提交代表用的：被问到"某块谁做的、证据在哪"，照这张表念。

### 23.1 我实际跑了什么

| 命令 | 结果 | 覆盖谁的卡 |
| --- | --- | --- |
| `pytest tests/ai -q` | **330 passed** | C |
| `pytest tests/backend -q` | **85 passed, 62 subtests** | B |
| `pytest tests/test_contracts.py tests/test_mock_api.py -q` | **15 + 4 = 19 passed** | 共同基线 |
| `pnpm test`（前端单元） | **27 passed** | A |
| `pnpm run test:backend`（前端消费端 × 真实 B/C 进程） | **passed**，见 23.2 | A × B × C |
| `python -m deploy.verify_backend` | **passed**，512 正常 / 72 异常 / 0 失败 | B |
| `python -m deploy.adapter_check` | **passed**，12/12 合法 + 3/3 篡改被拒，0 次模型调用 | C × B |
| 公网 health / `/` / replays | `model_ready: true`、200 HTML、`live_model` 卡 | 全部 |

合计 Python **434**、前端 **27**，与 PR 里报的数一致——**数对得上，不是各报各的**。

### 23.2 A 的六个工作块

| 块 | 状态 | 证据（我核过的那部分） |
| --- | --- | --- |
| A1 比赛中心、从 mock snapshot 到真实 API | 完成 | 公网 `/` 返回 A 的 dist；`GET /api/v1/matches` 的内容渲染在页面上；`backend-probe` 的 `catalogue and event recovery` 通过 |
| A2 播放/暂停/重置/倍速、六种 SSE 逐类处理、reset 后按 run_id 丢弃旧消息 | 完成 | `pnpm run test:backend` 实测 8 项全过，其中 `controls and pause freeze`、`two-session isolation`、`snapshot reconnect without duplicates`、`idempotent reset and stale-run rejection` 直接对应 A2；观测到的 stream kinds = snapshot / match_event / match_state / agent_status / insight（`error` 没被触发所以没出现，不算缺失） |
| A3 Insight 卡、Casual/Analyst 切换、证据展开、来源标签 | 完成 | 公网卡片上读到 `Live model` 标签、`Evidence checked`、`rejected_claims` 文案、"Where it happened"、"Event timeline"；探针的 `same-insight audience texts and event references` 通过；`MatchIntelligence.tsx` 切换语态只读同一 Insight 的两段文本，不触发模型调用 |
| A4 接真实 API 时不改页面字段、不私造字段 | 完成 | `frontend/src/contract.ts` **只有 re-export**，指向生成的 `../../contracts/types`，没有任何本地重定义；`check_frozen` 通过，契约仍是 2.0.0 |
| A5 1280×720 与 390 像素宽、键盘可操作、语义文字、前端无 Key、不加载海外字体/CDN/远程图 | **代码层面通过，浏览器层面我没验** | 源码与构建产物里 **0 个 `http(s)://` 外链**；CSS 断点在 1440 / 1000 / 900 / 700 / 600；15 处 `onKeyDown/tabIndex/aria-*`；`NoSecretsTests` 通过、tracked 树 `sk-` 零命中。**但"390 像素下真的不塌"要人眼看**——A 的 PR 里报了浏览器验证，我这里只标注"A 报告、我未复核" |
| A6 与 C 排练 110 秒演示、视频只展示已实现能力、故障注入有标签、更新 handoff | **未完成（只差录屏）** | `evaluation/DEMO_SCRIPT.md` 已由我按现在的产品重写（原来还写着"UI 未建，禁止拍界面"）；`docs/handoff/frontend.md` A 已更新。**录像需要人。** |

### 23.3 B 的六个工作块

| 块 | 状态 | 证据 |
| --- | --- | --- |
| B1 版本化数据、基础接口、统一统计 | 完成 | 验收的分析导出与 301 项逻辑秒不变量通过；公网 `matches`、`stats` 正常 |
| B2 独立会话、服务端时钟、播放/暂停/倍速/重置、run_id | 完成 | 验收含 `play_pause`、`reset`、`old_run`；`test_play_pause_speed_and_two_session_isolation`、`test_create_and_reset_idempotency_and_old_run_guard` 通过 |
| B3 六种冻结 SSE、独立队列、快照恢复、不补发日志 | 完成 | 契约 `StreamMessage` 的 const 集合 = `agent_status, error, insight, match_event, match_state, snapshot`，正好六个；`test_sse_begins_with_snapshot_even_with_last_event_id`、`test_subscribers_receive_independently_and_reconnect_is_snapshot`、`test_slow_subscriber_is_disconnected_without_blocking_other` 通过 |
| B4 高位夺回检测、窗口提取、有界后台调用、同窗口只调一次、只发布双校验通过的结果 | 完成 | 验收的 `retry` / `invalid_input` 项通过；`test_budget_deduplication_and_queue_bounds`、`test_queue_wait_is_part_of_total_deadline`、`test_queue_capacity_rejection_does_not_consume_budget` 通过 |
| B5 会话容量、空闲回收、次数限制、请求体上限、同域单 worker、`/api` 不被 SPA 吞 | 完成 | 公网单进程同源：`/` 200 HTML，`/api/v1/does-not-exist` 返回 **JSON 404**（没被 SPA 回退吞掉）。**注意**：深层路径 `/some/deep/link` 也是 JSON 404——A1 没有客户端路由，这是正确行为，但写材料时别说"支持任意深链" |
| B6 公网匿名验收 + 记录版本/URL/费用/保活 | **公网验收完成，费用口径要代表落一句** | 见第二十二节：公网已跑通真实模型调用。费用与保活口径：团队账号、**free 计划、空闲会休眠、无固定保活到期日**。必须写进材料，不能承诺"一直在" |

### 23.4 B 的"本角色检查"逐项

| 检查项 | 结果 |
| --- | --- |
| 共同契约测试、`tests/backend/`、与 A 的真实端到端 | 19 + 85 + `test:backend` 探针全过 |
| 比分不双计 | 验收 0 失败，`tests/backend` 有对应用例 |
| 窗口边界 / 坏 ID | 通过（越界窗口与坏 ID 被拒） |
| pause / reset | 探针 `controls and pause freeze` + 验收 `reset` |
| 两个订阅者不抢消息 | `test_subscribers_receive_independently...` |
| 重连快照 | `snapshot reconnect without duplicates` |
| 旧 run 结果 | `idempotent reset and stale-run rejection` |
| 模型失败统计仍更新 | 公网 + 本地 fallback 实测：出现 `rule_fallback` 卡时时钟仍在走 |
| 不把 Mock 当正式后端 | 公网跑的是真实模型路径；探针显式 `MATCHMIND_MODEL_PROVIDER=mock` 并报 `model_calls: 0` |

### 23.5 结论：现在谁卡着谁

- **A**：代码层面六块全完成，只差**录屏**这一件人做的事。
- **B**：六块全完成，`foul` 语义已闭环；只剩"费用/保活"一句话要代表落进材料。
- **C（我）**：单方可做的已清空，见第七节与 19.7。
- **只在负责人手上**：仓库改 public（规则 §4.4，需要 admin）、分支保护（admin）、视频（人）。

**方法论**：能跑的都跑了，跑不了的说"我没验"，而不是"应该没问题"。A5 的浏览器观感和 B6 的费用口径，是两处明确的"不由我背书"。

---

## 二十四、真实历史数据：#15 的接收决定与验收

B 交付了真实历史数据（`data/extra/real-history-wyscout`，PR #17 已入 main），并按分工把**接入方案与验收状态的决定权交给 C**。B 的交接要求 C 明确回答四件事：**走校准还是独立历史模式、数据版本与校验结果、映射与统计口径、来源署名与线上是否变更**。这一节就是那个回答。

### 24.1 决定：走校准，不替换运行时

| 选项 | 为什么 | 决定 |
| --- | --- | --- |
| 用真实数据替换演示数据 | 官方规则 §4.7 要求合成足球数据；冻结契约 `synthetic: true` 是必填常量；B 的包自己标了 `synthetic=false`、`runtime_compatible=false` | **不采用** |
| 独立"真实历史模式" | 需要一个版本化的来源/日期/起始状态表示，那是契约变更，要 A/B 一起点头，且提交前临时加第二套表示风险高 | **不在本期做**，记进提案待议 |
| **用真实样本校准/对照合成数据** | 零风险、不动运行时、直接支撑"创优的合成数据"这条评分点，而且是**可测量**的 | **采用** |

线上服务、冻结契约、默认合成数据、模型与渲染配置**一律未改**。B 说"本次不触发部署"——我核过 `deploy/Dockerfile.release` 的 COPY 清单里没有这个目录，所以合并 #17 不会影响已在跑的镜像，**因此没有重新部署**。

### 24.2 数据版本与校验

```
python -m data.generator.real_history --verify
-> {"status": "passed", "synthetic": false, "runtime_compatible": false,
    "match_id": 2499719, "full_match_events": 1768, "clip_events": 96, "model_calls": 0}
```

来源：Arsenal 4–3 Leicester City，2017-08-11，上半场 25:00–30:00（`eventSec` 1501.6–1798.3）。CC BY 4.0，署名与变更说明在包内 `ATTRIBUTION.md`。**这是 CC BY 4.0，不是本项目 CC0 的合成数据**，任何材料都不能把它混成我们自己的数据。

### 24.3 新增：校准工具与它的结论

`evaluation/real_data_calibration.py`（纯离线、零模型调用）把真实 5 分钟和我们的两个合成 5 分钟放在**同一窗口、同一统计口径**上比：

| 指标（同为 300 秒窗口） | 真实样本 | 合成（出厂） | 合成（稠密提案） | 合成（稠密 · **校准后**） |
| --- | --- | --- | --- | --- |
| 事件数 | 96 | 30 | 110 | 106 |
| **每事件秒数** | **3.12** | **10.0** | 2.73 | **2.83** |
| 传球占比 | 61.5% | 60.0% | 85.5% | 83.0% |
| **每 10 分钟射门** | **8.0** | 10.0 | 20.0 | **8.0** |
| 前场三区起脚传球占比 | 28.8% | 33.3% | 18.1% | 17.0% |
| 事件间隔中位数 | 1.9 s | 10.0 s | 2.0 s | 2.0 s |

四条结论，按重要性：

1. **出厂数据的"构成"是真实的，密度不是。** 传球占比差 2.4%、前场三区占比差 15.6%，都在容差内；但稀了 3.2 倍。这正好是 `fixture_qualify` 早就判它不合格的那一条——现在这条判断有了真实比赛的背书，而不是我们自定的阈值。顺带一个诚实的巧合：那条阈值（≤3.0 秒/事件）是我在拿到这份数据之前凭足球常识定的，真实样本是 3.12，**误差 4%**。
2. **射门频次是可以用旋钮修的，而且已经修好了。** 稠密提案原本每 30 秒一次射门（每 10 分钟 20 次，真实样本是 8 次）。新增 `dense_fixture_proposal.CALIBRATED = {"shot_chance": 0.30}` 之后是 **8.0，和真实样本完全一致**，密度仍在容差内。**默认参数不变，所以已经发布的 110 事件夹具逐字节没变**（有测试钉住）。
3. **传球占比修不了，原因是算术，不是参数。** 真实样本 34% 是拼抢/中断/散球，而冻结契约**没有任何一个事件类型对应它们**；在 300 秒窗口里，我们唯一的非传球动作就是夺回。要凑到 61.5% 得凭空造出约 **37 次夺回 / 5 分钟——约等于每场 665 次**，是真实足球的好几倍。为了让表格好看去灌这些数字，正好会污染这个产品存在的意义。**所以差距留在报告里**；真正的解法是新增事件类型，那是契约变更，得全队决定。
4. **十二项比较里六项超容差，工具把它们排在通过项前面打印。** 一张全是绿的表格是没人会去核对的表格。

### 24.4 口径与拒绝计算的项

映射表在代码里（`WYSCOUT_MAPPING`），逐条写明哪个 Wyscout 名字映射到我们的词汇、哪些有歧义、哪些根本没有对应：

- `Pass` → `pass`（直接）；`Shot` → `shot`（但 Wyscout 的 Shot 类比我们的"射门"更宽）
- `Free Kick` 有歧义（可能是传球也可能是射门，记录不总说清）→ 计数但不映射
- `Duel` 是拼抢，**不等于我们的 `recovery`**（抢回球权），因为记录没说谁赢下
- `Others on the ball` / `Save attempt` / `Interruption` → 无对应

**拒绝计算**（写进报告的 `refusals`，并有测试钉住）：`high_recoveries`、`linked_shots`、
`sustained_control`、3 次夺回/2 次关联射门这个触发条件、传球成功率。原因是原始记录没有
`possession_id`，也不记录谁赢下拼抢——这些指标只能靠编，而"编出来"恰好就是这个指标要抓的东西。B 在交接里也明确禁止补造 3/2 触发。

### 24.5 验收与门禁

- `python -m data.generator.real_history --verify` → **passed**
- 新增 `evaluation/real_data_calibration.py` + `tests/ai/test_real_data_calibration.py`（13 个测试）
- `python -m pytest tests -q` → **453 passed, 69 subtests**（上一轮 434；+13 校准测试，+6 来自 B 的 #17）
- `tools/check_frozen.py` → unchanged；`tools/check_scope.py --role C` → OK
- **线上未变更**：目录不在两份 Dockerfile 的 COPY 路径里，默认合成数据与冻结 fixture 未动，未重新部署

### 24.6 顺手抓到的自己一个 bug

第一版校准工具把"百分比容差"和"分数增量"混着比：`1.5 <= 50.0` 永远成立，于是 **+150% 的超标被打印成 `ok`**——工具在说"一切都好"，而它右边的表格说的正相反。已改成两边同单位，并加了一条回归测试（`test_an_overshoot_is_not_reported_as_ok`）。

这个 bug 值得记，因为它是最危险的一类：**一个会自我安慰的检查，比没有检查更糟**。

---

## 二十五、第十五轮：收掉 A 剩下的两个 PR，以及我自己文档里的两处假话

### 25.1 合了什么

| PR | 内容 | 处理 |
| --- | --- | --- |
| **#20** | 证据面板的键盘焦点往返（选中事件→跳到位置面板→返回原按钮并重新展开）+ 44px 触控目标 + 前端文档与我的校准结论对齐 | squash 合并，`1360326` |
| **#22** | **110 秒英文录制套件**：剪辑分镜、计时旁白、18 条可导入 SRT、preflight 证据 | 与 #20 冲突，我解完再合，`2636e09` |

**#22 的冲突是真的**：两个分支都重写了 `docs/handoff/frontend.md` 的同一个标题区。我保留了双方内容（按落地顺序），并在最前面加了一段"C 的整合说明"，把 #20 先合、bundle 名字已变这件事写清楚。合并后 457 测试通过、dist 与重新构建逐字节一致。

### 25.2 A 在套件里点了我一句，是对的

A 在自己的录制套件末尾留了一条给 C 的 review 项：

> `evaluation/SUBMISSION_POSITIONING.md` 里还留着一句"A2/A3 未建"，尽管 PR #14 已经合了。

**这是真的，而且 README 里也有同款。** 我上一轮把演示脚本改对了，但漏了这两处：README 的"未建不声称"清单里还写着"播放控制和证据卡未建"，`SUBMISSION_POSITIONING` 还写着"不能声称完整 UI"。

现在两处都改成实际存在的能力（播放/倍速、Casual/Analyst、证据展开、pitch/timeline 高亮、键盘焦点往返、来源面板），并把"未完成"收缩到它真正的位置：**片子还没拍**。

**方向是往"少说"那边错的，但少说也是错。** 评委点开公网就能看到这些界面，文档说没有，只会显得我们不了解自己的产品。

### 25.3 重新部署并逐字节核对

#20 换了前端 bundle，所以必须重新部署。部署后核对：

```
js:  /assets/index-DnW473jk.js     local == public  (sha256 20ff045be18cfdc3...)
css: /assets/index-Bkk-p2ET.css    local == public  (sha256 8ab4470be0931fca...)
GET /api/v1/health -> ok / 2.0.0 / production / model_ready true
```

A 的套件里 `preflight.json` 记的是旧的 `index-DiFIbE5M.js`@`1113388`。**我没有改写它**——那是一份带时间戳的证据，改了就失真。

我本来想直接给 A 的套件 README 加一段"C 的整合说明"，让录制的人照新 bundle 走。`tools/check_scope.py --role C` 立刻报了 `OUTSIDE ROLE SCOPE: frontend/demo/recording-kit/README.md`，我**撤回了那处修改**——`frontend/` 是 A 的目录，守卫拦得对。信息留在这里，同时列进给 A 的待办：

- 录制请照**现在**这版 bundle（`index-DnW473jk.js` / `index-Bkk-p2ET.css`），不要照 `preflight.json` 里的旧哈希；
- `frontend/demo/recording-kit/preflight.json` 需要一个新时间戳的重跑（A 自己做，或授权我做一次）。

### 25.4 门禁状态（第十五轮）

- `python -m pytest tests -q` → **457 passed, 69 subtests**
- 前端 29 测试通过；`dist` 与重新构建逐字节一致
- `tools/check_frozen.py` → unchanged；`tools/check_scope.py --role C` → OK
- 公网已更新到 `2636e09` 的 bundle，健康检查正常
- 这次 push 又碰到 `github.com:443` 不通，改用 Git Data API 单提交发布（`53c5189`），随后 fetch 成功并把本地对齐
