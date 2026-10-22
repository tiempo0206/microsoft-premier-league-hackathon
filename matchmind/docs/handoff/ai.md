# ai 交接记录 — Role C（AI 核验与集成）

- 开发者：C / **Meng Yuxuan**（`farlyfeifei`）
- 分支：`codex/ai-verification`（远端 tip `27e4dd5`，PR **#8**，目标分支 `codex/backend-ab-mvp`）
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

| 项 | 状态 | 说明 |
| --- | --- | --- |
| Agent Framework 编排 | **已接入，且是默认** | `MATCHMIND_ORCHESTRATOR=framework` 为默认；正例 2/2、12 窗口 6/12 发布，比直连快约 20–25%，质量打平。不可导入时自动降级为直连并在 trace 里写明。见第十节 |
| MCP server | **已完成** | `ai/mcp_server.py`，5 个工具（`list_matches` / `get_metrics` / `get_event_window` / `get_candidate_moments` / `explain_window`），12 个测试，复用同一份确定性代码。`python -m ai.mcp_server`（stdio）或 `--http` |
| A2A agent card + 端点 | **未做** | 判据点名 A2A，三个头部竞品都有。见 `evaluation/PLAN_REVIEW.md` §5 第 2 项 |
| broadcast overlay JSON 导出 | **未做** | 官方 §4.1 要求输出「machine-readable enough to be rendered as synchronized graphical overlays」。见 §5 第 3 项 |
| 会话/并发上限 | 沿用 B 的实现 | C 侧无独立限流，沿用 8 会话 / 30 次每小时 / 并发 1 |
| possession 口径自检 | **刻意不做** | `AnalysisRequest` 不带 `Match.initial_possession_team`，无法在 C 侧重算；已在 `consistency_issues` 的 docstring 里写明这是刻意的空白，不猜 |
| 中文数字校验 | 部分覆盖 | 只认 `十 / X十 / 十Y / X十Y` 形态，其它写法靠 auditor 兜；已在 docstring 里写明限制 |
| 视频 / 部署 | 不属本轮 | 见 B 的 handoff 与 `docs/05_acceptance.md` |
| 前端消费端 | **阻塞在 A 方** | A3 的 Insight 卡 / 证据高亮 / 双档切换还没写，C 的产出目前只能在 API 与快照里看到 |

---

## 八、下一工作块

1. **完整 12 窗口的框架版评测**：现在只测了 2 个正例。拿到完整对照后，才能决定默认编排器是 `direct` 还是 `framework`，也才能在材料里写框架的使用效果。
2. **MCP server**：把 `ai/tools.py` 的三个工具包成 MCP，让工具调用走 MCP 而不是函数直调 —— 判据里点名了 `MCP integration`，且完全本地、不需要云。
3. **契约 2.1.0 一次性升版**：按第六节的 3 → 4 → 1 顺序，先和 A/B 确认消费端，再动 `contract.schema.json`。
4. **`POST /recap` 的 recap 角色**：输入整段 prefix，与 moment 角色共用同一套校验器和 fallback。
5. 补中文叙事的**完整**评测（现在正例 P2 已通过，但样本只有 1 个窗口）。

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

### 14.3 现在的门禁状态

```
python -m pytest tests -q                        → 284 passed, 33 subtests passed
python tools/check_frozen.py                     → Frozen contracts and fixtures unchanged
python tools/check_scope.py --role C --base HEAD → Role scope OK
python -m ai.a2a_transport                       → message/send demo + unsupported-method refusal
python -m ai.threat                              → available=false, "a five-minute clip is too short"
```
