# B 后端交接：整合者从这里开始

2026-10-23，协议 **2.0.0**，唯一 B 分支 **codex/backend-ab-mvp**。
本文件可以直接转发给负责最终联调的人。B 不合并 A/C、不改冻结契约、不替 C 开发模型。

## 1. 已交付与使用顺序

1. 在同一历史中接纳团队已确认的 starter/A/B/C。当前 main 还没有应用基线，**不要把 B 整个分支直接当成只含后端的 main PR**；基线关系见 `B_DELIVERY_PLAN.md`。
2. 先在原始 B 基线上运行完整验收，再由整合者选择增强演示数据。
3. C 的组合根接入后，用其自己的 probe 检查真实模型；最后由 A 完成浏览器与证据卡联合验收。
4. 最后才发布；本文件提供准备材料，不表示已经创建公网服务。

已核对的远端：A `f88d286` / PR #3；C最新为 `70dec95` / PR #8（目标 B 分支），它相对本次验证的 `02228b8` 只更新文档/评测材料，`ai/`代码未变。后续 C 若继续更新，由整合者审查完整 diff 后选择版本。本机导出的 C 文件只用于隔离打包检查，**没有复制回 B 分支**。

## 2. B 的一条验收命令

以下命令在 `matchmind/` 执行，使用已有 Python 3.12 虚拟环境：

```powershell
.\.venv\Scripts\python.exe -m deploy.verify_backend
```

依次生成：原基线审计、增强场景及输入包、确定性分析、584 个原有合成回测、B/共同测试、原基线和三个增强场景的实际 HTTP/SSE 检查。验收自己申请临时 loopback 端口，结束后回收自己启动的进程，不关闭他人的服务。

产物在 `.artifacts/backend-delivery/`：`acceptance.json`、`showcase/`、`backtest/` 及日志。所有模型调用为零；不要把它当作模型训练或真实模型质量评测。

首次环境缺依赖时：

```powershell
.\.venv\Scripts\python.exe -m pip install --index-url https://pypi.tuna.tsinghua.edu.cn/simple -r backend/requirements.lock
```

macOS/Linux 使用 `.venv/bin/python`。不要复制别人的虚拟环境。

## 3. 数据：保留基线，增强场景显式选择

| 数据目录 | 用途 | 1500–1650 的高位夺回 / 关联夺回 | 时刻1650比分 |
| --- | --- | --- | --- |
| `data/extra/validated-demo` | 默认30条契约基线，不替换 | 3 / 2 | 0:0 |
| `data/extra/showcase/press` | 候选增强演示，128条事件；组合采用须过C门禁 | 3 / 2 | 1:0 |
| `data/extra/showcase/delayed` | 17秒后才形成射门的反例，127条事件 | 3 / 0 | 0:0 |
| `data/extra/showcase/quiet` | 普通传控反例，137条事件 | 0 / 0 | 0:0 |

增强数据全部是本次原创合成事件、CC0-1.0；无真实比赛、数据账号、球队标识或模型生成费用。每个目录单独包含一个比赛和五个受管文件：match、events、22人roster、独立expected、PROVENANCE与文件哈希。

**一次运行只选一个目录，不要把三个目录的文件混放。** 当前审计口径是一个目录一个比赛。比赛ID不同，A/C不能硬编码 `MM-DEMO-01`。

生成与核验：

```powershell
.\.venv\Scripts\python.exe -m data.generator.showcase --check
# 只有明确需要重新生成受管的 B 数据时使用 --write
.\.venv\Scripts\python.exe -m backend.showcase
```

生成器独立于 backend，固定 seed=20261023。位置是0–100事件坐标；每段传球的终点连接下一次动作起点。正常数据和篡改测试分开。球队、球员、顺序、射门/进球对应、时间守恒、逐秒预期和文件重现均有检查。

范围：三个脚本模板，不是经真实赛事标定的模拟器；失败传球和射门频次为明确编排，不宣称真实足球分布。22人名单/参与事件不等于22人连续追踪。没有速度、距离、xG或因果战术真值。

## 4. 给 C 的输入包

`python -m backend.showcase` 输出到 `.artifacts/backend-showcase/`：

- `analysis-requests.jsonl`：**12个合法 AnalysisRequest**，3场景×2观察窗×中英两种语言；每行就是请求本体，可传给 `await ai.service.analyze(request)`。
- `showcase-report.json`：指标、逐秒守恒检查、证据链、正反例标签；这是 B 的确定性报告，不是 Insight。
- `tampered-requests.jsonl`：3个 `{case_id, expected, request, runtime_fixture:false}` 包装对象；只能传其中的 request 做拒绝路径测试，**严禁放入比赛目录**。
- `manifest.json`：输入包哈希；`README.md`：可直接阅读的比较。

篡改分别是数字与事件矛盾、错比赛、未来事件。后两项应被契约拒绝；第一项请求形状合法，需要 C 的独立算术门拒绝。B不执行C的评测、不制造“模型零幻觉”成绩。

正例的进球已经在固定1500–1650窗口内，不改协议窗口即可演示。**第三次夺回没有关联射门**；不得声称“三次全部产生射门”或“三次导致了进球”。

运行调度只会在固定窗口满足规则时触发 HOME 分析。quiet/delayed 的“不自动出卡”是正确行为；C可直接消费离线请求来验证它们。不要为了演示卡片绕过规则。

## 5. A 接口保持不变

开发代理已有 `MATCHMIND_BACKEND_URL`。启动 B：

```powershell
$env:MATCHMIND_DATA_DIR="data/extra/showcase/press"
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --workers 1
```

A 在自己的终端把 `MATCHMIND_BACKEND_URL` 设为 `http://127.0.0.1:8000`，再重启已有 Vite 服务。前端代码无需被 B 改写。

- 目录来自 `GET /api/v1/matches`，新建使用返回的 match_id。
- 新会话 idle，必须调用 control/play；推荐演示5倍速，不做seek。
- 播放30秒墙上时间后到达1650分析触发点；可手动暂停等待模型。
- 六种 SSE 名称不变；snapshot/state是统计真值，按run原子替换，旧run不发布。
- 前端应显示真实 `live_model` / `rule_fallback` / `precomputed`；C health 中的配置齐全不是云端模型已通过探针的证据。

## 6. foul 修复的语义交接

B 已接受冻结 schema 中的 `foul`，只接受 `outcome=none`、`end_position=null`。
`team_id/player_id` 表示犯规动作执行者；犯规本身不宣告持球转移，所以不计射门/进球/传球，也不把动作执行队改为持球队。此时 possession_id 可以引用犯规发生时另一队的持球段。

这是新增事件类型的 B 解释，未改 schema。C若采用自己的持球复算器，需要保持同一口径。C原先“B不支持foul”的说明已过期；B不会代改C文档或测试。

## 7. 给整合者的发布入口

B默认入口仍是 `backend.app:app`，不注入模型。C的组合入口为 `ai.app:app`。
**不要只在 Render 填 Key，却继续启动 B-only 镜像。**

准备好的材料：

- `deploy/release_check.py`：只读检查数据、C模块/固定依赖、A构建产物、同源开关。缺项时明确blocked，不自动安装、不联网、不修改A/C。
- `deploy/release_run.py`：检查通过后启动C组合根，固定单worker。
- `deploy/Dockerfile.release`：组合镜像模板；依赖C现有 requirements 和A已构建的dist。
- `deploy/Dockerfile.release.dockerignore`：默认排除，明确放行运行文件；不复制.env、测试、评测、node_modules或虚拟环境。
- `deploy/release.env.example`：仅占位配置，**不是被B自动读取的.env**。

整合者在**已经接纳C代码和A构建产物**的目录执行：

```powershell
.\.venv\Scripts\python.exe -m pip install --index-url https://pypi.tuna.tsinghua.edu.cn/simple -r backend/requirements.lock -r ai/requirements.txt
$env:MATCHMIND_SERVE_FRONTEND="1"
$env:MATCHMIND_DATA_DIR="data/extra/validated-demo"
$env:MATCHMIND_MODEL_TIMEOUT_SEC="20"
.\.venv\Scripts\python.exe -m deploy.release_check --profile integrated
.\.venv\Scripts\python.exe -m deploy.release_run
```

C可从其忽略的`.env`读取模型配置，但B的开关/超时/数据目录读取**进程环境**，必须如上设置，或由托管平台注入。保持两侧共用同一个20秒候选预算，云端实测后调整，不单独改C导致B提前截断。

**增强数据的已知C阻塞项**：C `02228b8` 的降级证据截断导致12个正常输入中4个输出违反证据包含关系；详见 `C_INTEGRATION_FINDINGS.md`。C修复前，组合运行请把上面数据目录改为 `data/extra/validated-demo`。增强组合启动已增加离线门禁，失败就明确退出，不带病上线。C修复后由整合者运行：

```powershell
.\.venv\Scripts\python.exe -m deploy.adapter_check --output .artifacts/C-offline-compatibility.json
```

门禁要求12个正常输入全部过契约、3个篡改被拒；禁止网络，不消耗模型额度。最终镜像默认仍是原基线。组合镜像依赖快照在 `deploy/requirements-release.lock`，已从实际Linux安装结果固定所有42个包，基于C `02228b8`；C依赖变更后需整合者复核快照，不能直接改C requirements来迎合旧锁。

容器由整合者构建，不要求 B 更改 A 源码或合并分支：

```text
docker build -f deploy/Dockerfile.release -t matchmind-release:reviewed .
docker run --name matchmind-release-local -p 127.0.0.1:8000:10000 matchmind-release:reviewed
```

容器缺Key时C保持明确的规则降级；真实Key在运行时通过托管Secret/已忽略的本地运行配置注入，**不放build-arg、不放镜像、不写命令历史**。

## 8. 账号、模型和平台：只准备必要项

| 项目 | 现在的状态/动作 | 交付给整合者 |
| --- | --- | --- |
| 数据、统计、规则模型 | B已提供，无需账号/GPU/训练 | 数据目录、版本、预期、输入包 |
| GitHub私有仓库 | 已有协作权限 | 整合者确认同一基线和A/B/C提交 |
| Render | 已注册，团队仓库未授权；**由 tiempo0206 配置 GitHub App** | Render工作区/服务链接，确认费用责任 |
| DeepSeek模型 | C交接称已实测；优先复用团队授权资源，B不重复开户 | C确认provider/base_url/model，Secret由持有人直接填云平台 |
| Microsoft Agent Framework | C提供库接入；库本身不要求Azure资源 | 安装C固定依赖，真实trace显示实际framework路径 |
| Azure/Foundry | B不创建；不是B预览部署前置条件 | 若另选Foundry/Azure奖项，由团队明确实现与负责人 |

模型交付配置名：`MATCHMIND_MODEL_PROVIDER`、`MATCHMIND_MODEL_BASE_URL`、`MATCHMIND_MODEL_NAME`、`MATCHMIND_MODEL_API_KEY`、`MATCHMIND_ORCHESTRATOR`、`MATCHMIND_THINKING`。
现有C路径可选 `provider=deepseek`、`base_url=https://api.deepseek.com`、`model=deepseek-flash`、`orchestrator=framework`、`thinking=disabled`。B只核对传输配置名，不实现第二套provider。

若团队确实没有可用模型账号，由模型持有人打开 https://platform.deepseek.com/ 注册、按平台要求认证/开通API余额、在API Keys页创建项目Key，再由C执行其 `python -m ai.probe`；`--live`会产生一次真实调用，按团队授权执行。之后还要从实际云宿主再测。官方入口：https://api-docs.deepseek.com/ 。不要把Key发群聊或贴PR。

Render授权入口：https://github.com/apps/render/installations/new 。需要所有者把目标仓库加入Repository access。原 `render-backend.yaml` **仍只部署B预览**；最终组合发布由整合者选择已确认的整合分支、Dockerfile=`matchmind/deploy/Dockerfile.release`、context=`matchmind`、健康路径=`/api/v1/health`、单实例、AutoDeploy关闭。不要凭空填写一个尚不存在的整合分支。

平台若始终不能连私有Git，Render官方支持预构建镜像，但那另需镜像仓库/发布授权。本轮不为绕过授权擅自fork、公开源码或发布镜像。

## 9. 最终联调验收，由接手的人执行

1. A比赛目录 → B创建/控制 → SSE时钟/比分/统计；断线后快照恢复。
2. 正例到1650触发C；等待期间统计继续；C的真实结果与双模式叙事显示来源标签。
3. 点击证据仅高亮已有事件，不跳时钟、不读取未来。
4. quiet/delayed不自动触发；篡改请求在模型前拒绝，真实模型次数由C usage验证。
5. 在C分析中reset，旧run结果不出现；重复控制不重复执行。
6. 人工让模型超时/失效，统计继续且结果明确降级。不要把离线fallback拍成真实模型成功。
7. 公网基线：`python -m deploy.smoke_backend https://你的服务`；增强数据正式采用后加 `--dataset press`。再做浏览器联合验收。这个探针不会跨分析触发点，不替代真实模型验收。
8. 单worker/单实例，重启后内存会话丢失是已记录行为，A应重新创建。

## 10. 竞赛表达与证据边界

B贡献可如实表述为：**可重复的合成场景 → 独立预期核验 → 事件级证据链 → 有界异步AI交接 → 可恢复的实时回放**。
技术演示优先展示“正例有依据、反例不乱触发、篡改被拒、模型失败仍能看球”的完整体验。

对应官方 §4.1 的数据创新/可解释输出、§6.2 的技术实现与可维护性；多Agent差异化由C的实际framework/审核/修复证据支持，不以堆库名代替执行。**不承诺获奖，也不把584个合成软件回归用例写成真实足球准确率。**

官方规则核对入口：https://github.com/microsoft/insidethegamehackathon/blob/main/OFFICIAL%20RULES.md 。材料需英文或英文翻译；公开代码、<2分钟真实运行视频、可供评审访问的项目由提交负责人完成。B不擅自修改仓库可见性。

## 11. 未完成且不能被“准备好了”掩盖的事项

- Render私有仓库授权、云端构建/可用性和实际费用设置。
- A后续播放控制、AI卡片、证据和观众模式。
- C最新代码的最终审查、真实Key与云端模型探针、语义评测。
- 联合浏览器验收、正式main整合、最终PR和提交材料。

本轮 Kimi运行入口不可用，未调用Kimi；由Codex实施并审查。DSPy skipped：B是确定性数据与调度层，不属于本轮模型优化职责。
