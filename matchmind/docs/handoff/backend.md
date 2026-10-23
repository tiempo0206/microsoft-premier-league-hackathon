# B 后端交接（唯一入口）

状态日期：2026-10-23。B代码、合成数据、测试和部署材料已随PR #9进入main；B公网预览已验收。后续整合Agent从main接手即可，无需等待B本人继续配置。

## 1. 已上线服务

| 项目 | 当前值 |
| --- | --- |
| 后端URL | https://matchmind-backend-preview.onrender.com |
| 健康接口 | https://matchmind-backend-preview.onrender.com/api/v1/health |
| Render服务ID | srv-dbdegcnavr4c739pockg |
| 当前已验收部署ID | dep-dbdep9gae00c73fujcr0 |
| 云端固定源码 | bcaed0e1c899a0a27022d91c67b17e3537af702d |
| 来源分支 | main |
| 套餐 / 区域 / 实例 | Free / Singapore / 1 |
| Runtime / worker | Docker / 1 |
| Root Directory | matchmind/ |
| Dockerfile Path / Context | deploy/Dockerfile / . |
| Health Check Path | /api/v1/health |
| 自动部署 | Off，须显式部署选定提交 |

当前是B后端预览，入口backend.app:app，没有打包前端或注入模型。根路径返回JSON404、health中model_ready=false均为预期；不能据此认定服务失败，也不代表完整参赛网站已上线。

| 运行环境变量 | 当前值 |
| --- | --- |
| PORT | 10000 |
| MATCHMIND_SERVE_FRONTEND | 0 |
| MATCHMIND_DATA_DIR | data/extra/validated-demo |
| MATCHMIND_MAX_REPLAY_SESSIONS | 8 |
| MATCHMIND_MAX_CONCURRENT_ANALYSES | 1 |
| MATCHMIND_ANALYSIS_LIMIT_PER_HOUR | 30 |
| MATCHMIND_MODEL_TIMEOUT_SEC | 12 |

这些值已通过管理API回读；同一源码重新部署到Live后，公网数据/回放/幂等/重置/异常输入/SSE重连检查通过。push新main不会自动更新当前部署。

## 2. 其他Agent需要什么

- **调用后端**：只需上述URL，当前业务接口匿名，无需Render Key。
- **管理现有部署**：Agent具备HTTP/终端能力，持有GitHub代码访问权，并将有权操作此服务的Render管理Key放入私密变量RENDER_API_KEY，即可配置/发布现有服务。操作对象限定为上面的服务ID；不要求先加入Render工作区成员。
- **调用真实模型**：使用C提供的模型Key及配置。Render管理Key不是模型Key，不能放到前端或当作模型凭据。

凭据不在Git中。本机的加密存储不会自动同步到其他电脑，接手Agent须取得资源持有人授予的管理凭据。账号所有权和费用归属不随本文自动转移。

## 3. A立即接入现有接口

在A的frontend开发终端设置已有Vite代理并重启：

```powershell
$env:MATCHMIND_BACKEND_URL='https://matchmind-backend-preview.onrender.com'
pnpm run dev
```

浏览器保持相对/api/v1请求。正式版本使用同源网页和API。接口真源为[冻结契约2.0.0](../02_contract.md)。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | /api/v1/health | 健康与当前模式 |
| GET | /api/v1/matches | 比赛目录，使用返回的match_id |
| GET | /api/v1/matches/{match_id} | 比赛元数据 |
| GET | /api/v1/matches/{match_id}/events?from_sec=1500&to_sec=1650 | 事件与证据 |
| GET | /api/v1/matches/{match_id}/stats?at_sec=1650 | 指定时刻统计 |
| POST | /api/v1/replays | 创建回放，返回201 ReplaySnapshot |
| GET | /api/v1/replays/{replay_id} | 当前完整快照 |
| POST | /api/v1/replays/{replay_id}/control | 播放、暂停、重置、倍速 |
| GET | /api/v1/replays/{replay_id}/stream | SSE |
| GET | /api/v1/replays/{replay_id}/insights/{insight_id} | 已发布洞察 |

创建示例：`{"match_id":"MM-DEMO-01","speed":5}`。从返回的replay.replay_id读取ID，再发送control请求`{"action":"play"}`。其他action为pause、reset、set_speed；仅set_speed附带speed，允许1/2/5/10。

新回放idle、时钟1500（25:00），必须play才前进。每个逻辑操作用稳定UUID Idempotency-Key重试；控制可携带X-MatchMind-Expected-Run。reset增加run_id，旧run消息丢弃，新snapshot原子替换。

六种SSE名称：snapshot、match_event、match_state、insight、agent_status、error。先接完整snapshot，重连同样恢复快照；不承诺逐条日志补发。统计以服务器snapshot/state为准，不按事件再次累计。

## 4. C的接入边界

C的组合根ai.app:app已在main，使用B的create_app(analyzer=..., analysis_source="external")注入异步分析器；签名保持async analyze(dict)->dict。B打包AnalysisRequest并校验AnalysisResult，C无需反查B内部数据库。

B在回放到1650时检查1500–1650观察窗：至少3次高位夺回、至少2次在同队同possession的15秒内形成射门，才调度一次分析。C分析不阻塞统计；reset/过期取消任务，旧run或超时结果不发布。小时限制是单调时钟小时桶，并非严格滚动小时。

展示实际live_model / rule_fallback / precomputed及真实trace。C裸analyze调用保持离线规则降级。此前密集数据的证据截断问题已在main修复；已执行的离线门禁为12/12正常输入通过、3/3篡改拒绝、零模型调用。

## 5. 已交付的数据和分析输入

| 数据目录 | 事件数 | HOME高位夺回 / 关联夺回（1500–1650） | 1650比分 |
| --- | ---: | --- | --- |
| data/extra/validated-demo | 30 | 3 / 2 | 0:0 |
| data/extra/showcase/press | 128 | 3 / 2 | 1:0 |
| data/extra/showcase/delayed | 127 | 3 / 0 | 0:0 |
| data/extra/showcase/quiet | 137 | 0 / 0 | 0:0 |

一次运行选一个目录，不混放元数据；不要硬编码唯一match_id。每组有match、events、22人roster、独立expected和PROVENANCE/SHA记录。全部为原创合成数据，不需数据账号、GPU或模型训练。

时间为比赛逻辑秒；事件窗口闭区间，持球时长半开区间。坐标0–100、x右y下，按进攻方向判断高位。仅goal增加比分，shot(goal)只计射门。foul只接受outcome=none/end_position=null，动作执行队不因此变为持球队。

`python -m backend.showcase`输出12份合法中英分析请求和3份单独篡改输入到.artifacts/backend-showcase/。正常请求每行是AnalysisRequest；篡改文件有包装对象，只用于拒绝路径测试，不能载入运行目录。详细统计、证据口径及产物见[DATA_PIPELINE.md](../../backend/DATA_PIPELINE.md)。

## 6. 本地与公网验收命令

以下命令在matchmind目录、项目Python3.12虚拟环境运行。整合者首次安装全项目依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install --index-url https://pypi.tuna.tsinghua.edu.cn/simple -r requirements-dev.txt
.\.venv\Scripts\python.exe -m deploy.verify_backend
.\.venv\Scripts\python.exe -m deploy.adapter_check
.\.venv\Scripts\python.exe -m deploy.smoke_backend https://matchmind-backend-preview.onrender.com
```

macOS/Linux使用.venv/bin/python。完整B验收含独立正常/异常回测、临时HTTP/SSE服务和进程回收；输出在.artifacts/backend-delivery/。已记录B测试85、共同测试19、512正常+72异常回测通过，公网smoke通过。合成回归不是足球预测准确率。

数据复现：`python -m data.generator.showcase --check`。只导出确定性分析：`python -m backend.reporting --output-dir .artifacts/backend-analysis`。这些命令不调用真实模型。

## 7. 整合者接下来完成

1. 使用main现有A/B/C代码。A交付前端构建；frontend/dist通常被Git忽略，须把构建纳入Docker多阶段构建或CI产物打包，不能依赖某人的本机dist。
2. 使用已有deploy/Dockerfile.release模板和deploy/release_run组合入口。当前Root Directory=matchmind时，Dockerfile Path为deploy/Dockerfile.release、context=.，开启MATCHMIND_SERVE_FRONTEND=1，保持单worker/实例。
3. C提供模型endpoint/名称/Secret及预算。若采用20秒候选整体超时，B/C同时设置MATCHMIND_MODEL_TIMEOUT_SEC=20，并从实际云宿主验证；当前B预览为12秒。
4. 在组合环境执行python -m deploy.release_check --profile integrated；正式发布前保证A产物、C依赖和配置均齐全。模板的依赖快照在deploy/requirements-release.lock，C依赖变更后同步核对。
5. Agent通过Render API发布明确选定的提交，等Live后跑公网smoke，再做浏览器→回放→真实AI/降级→证据/模式→断线恢复。单独health或后端smoke不证明完整产品已验收。

本地组合入口：设置MATCHMIND_SERVE_FRONTEND=1、数据目录和共享超时后，运行`python -m deploy.release_run`。B设置读取进程环境；C可读自己的忽略.env。完整配置占位见deploy/release.env.example。

接手后常规构建、配置、发布和运行维护由整合者负责，无需B本人重新参与；模型账号与费用由资源持有人处理。本文件不批准新建付费资源或扩大账号权限。

## 8. 需要保留的边界

- 当前Free预览存在空闲休眠；重启或部署会丢失内存回放，前端重新创建。无必须引入的数据库或对象存储。
- 合成持球时间来自已记录队伍变化，不是官方跟踪控球率；无连续22人位置、速度、距离、xG或战术因果真值。
- 未预期内部异常仍可能由框架返回500；冻结错误枚举未定义通用内部错误码，需要时由整合者协调协议处理。常见输入/容量/模型失败路径已有明确处理。
- 最终前端体验、云端真实模型和评审期可访问性仍需整合者完成验收。

给接手Agent的任务：从main读取本文件，复用现有B服务与C组合根，使用私密RENDER_API_KEY管理指定Render服务，完成A构建、模型配置、组合发布和最终验收，并交付最终URL、提交版本及运行状态。不要要求B再次手工配置，不改冻结协议来绕过失败。
