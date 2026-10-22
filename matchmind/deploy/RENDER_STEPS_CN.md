# 后端上线闭环：Render 注册、授权与验收

核对日期：2026-10-22。此说明只负责 B 后端。先部署可供 A 联调的 API 预览，再由团队整合前端和 C 的真实 AI。当前没有创建 Render 服务，也没有真实模型调用；本机 Docker 镜像尚未成功构建。

## 你现在需要准备什么

| 项目 | 现在是否需要 | 具体动作 |
| --- | --- | --- |
| Render 账号 | 公网预览需要 | 在 [Render 控制台](https://dashboard.render.com/) 注册，建议选择你已有的 GitHub 身份；登录、邮箱或额外账号验证由你本人完成 |
| GitHub 仓库授权 | 公网构建需要 | 允许 Render 读取团队仓库；GitHub 协作者权限与 Render App 安装权限是两回事 |
| 模型 API Key | B 当前不需要 | 真实模型由 C/团队确认后接入；不要为了启动后端先购买模型额度 |
| Azure / Foundry | 当前后端预览不需要 | 技术选型应对应实际参赛类别；不要同时注册所有微软产品 |
| 数据账号 / GPU / 数据库 / 对象存储 | 不需要 | 已有可重复生成的本地合成片段和来源记录；当前单进程内存回放足够 |
| Docker Desktop | Render 构建不需要 | Render 在云端构建 Dockerfile；本机 Docker 故障不妨碍注册或本地 Python 开发 |

不用把密码、GitHub Token、Render API Key 或模型 Key 发到聊天里。当前流程只需要你本人完成账号登录和仓库授权。给协作 Agent 提供服务 URL、所选分支、构建提交 SHA 和已脱敏的失败提示即可。

## 第一步：注册并连接私有仓库

1. 打开 [Render 控制台](https://dashboard.render.com/)，完成注册，使用有仓库权限的 GitHub 账户。
2. 在 Account Settings → Account Security → Git Deployment Credentials 连接 GitHub；若注册流程已经连接，检查授权范围即可。
3. 确认能选中 `tiempo0206/microsoft-premier-league-hackathon`。如果只有自己的仓库，看 [Render GitHub App 安装入口](https://github.com/apps/render/installations/new)。仓库在 tiempo0206 名下时，可能需要所有者安装/批准 App 并将该仓库加入访问范围；不要反复注册 GitHub 或重新接受已接受的邀请。
4. 不用把仓库改成公开来解决 App 权限。比赛最终提交的公开代码要求由团队在提交前处理。

依据：[Render Git provider 官方说明](https://render.com/docs/git-provider)。这些步骤不保证所有中国大陆网络和账号都能正常访问；如遇平台验证限制，记录具体提示后再处理，不先付费。

## 第二步：用准备好的配置创建一个后端服务

前置条件：B 分支 `codex/backend-ab-mvp` 已推送到 GitHub。若 GitHub 分支列表中看不到它，必须先完成推送，不能选择只有文档的 main 代替。

1. 控制台选择 New → Blueprint，连接上述仓库。
2. 选择分支 `codex/backend-ab-mvp`。
3. Blueprint Path 填 `matchmind/deploy/render-backend.yaml`。文件使用 JSON 语法，是合法 YAML，已通过官方 JSON Schema 本地校验；仍需 Render 页面确认后才算平台接受。
4. 检查变更预览只创建 **1 个 Web Service**：`matchmind-backend-preview`，Docker，Singapore，Free。没有 Postgres、Redis、磁盘和付费后台任务。
5. 确认 Dockerfile 是 `./matchmind/deploy/Dockerfile`，Docker Context 是 `./matchmind`，健康路径 `/api/v1/health`，`PORT=10000`，单实例、单 worker。
6. 确认当前账户页面显示的价格与用量条款符合预期，再点击 Deploy Blueprint。若 Free 不可选或出现付费要求，先停在此页记录提示，不默认升级。
7. Blueprint 创建后，在 Blueprint Settings 把 **Auto Sync 设为 No**。服务配置的自动部署已经关闭，但 Blueprint 本身有独立同步开关。以后手动部署指定提交，避免中途更新影响演示。

官方入口：[Blueprint 设置步骤](https://render.com/docs/infrastructure-as-code)、[配置字段](https://render.com/docs/blueprint-spec)。不需要安装 Render CLI 或提供 API Key。

若使用 New → Web Service 手动建服务，不要再同时为它创建 Blueprint。选择 Docker 和同一分支；保持仓库 Root Directory 为空，Dockerfile Path 填 `./matchmind/deploy/Dockerfile`、Docker Build Context 填 `./matchmind`；其他值照配置文件设置。推荐优先使用 Blueprint，避免路径填错。

## 第三步：检查构建与公网 API

构建日志应完成 pip 依赖安装、离线数据 preflight passed、Uvicorn 监听平台 PORT。当前没有本地成功镜像证据，所以第一次云端构建仍是待验证关卡，不能承诺必定成功。

服务 Live 后取得 `https://实际服务名.onrender.com`，依次验证：

1. `/api/v1/health` 返回 HTTP 200、`contract_version=2.0.0`。`status=degraded`、`model_ready=false` 是当前未接真实模型的诚实状态。
2. `/api/v1/matches` 中 `MM-DEMO-01` 的 `generator_version=fixture-2.0.1`。
3. `/api/v1/matches/MM-DEMO-01/stats?at_sec=1650` 中比分 0:0、射门 HOME=2 / AWAY=0、合成持球秒数 35:115。
4. 在本项目 matchmind 目录执行以下命令。它会创建一个短回放，验证重试、播放暂停、重置、错误输入、旧 run 拒绝和 SSE 快照恢复；不会请求 AI 分析。

```powershell
.\.venv\Scripts\python.exe deploy/smoke_backend.py https://实际服务名.onrender.com
```

输出 `result=passed` 后，记录 URL、Git 提交 SHA、服务区域、实例类型和日期。根路径 `/` 当前返回 JSON 404 是预期：这只是 API 预览，没有前端页面。

如 Free 服务刚唤醒，先打开 health 等启动完成，再运行检查。失败时向 Agent 提供脱敏日志和检查输出；不要仅凭 Live 标签认定业务可用。

## 第四步：让 A 接上后端

A 已有的 Vite 配置支持环境变量，不需要修改字段或前端源码。由 A 在其前端终端执行：

```powershell
$env:MATCHMIND_BACKEND_URL='https://实际服务名.onrender.com'
pnpm run dev
```

A 保持请求相对路径 `/api/v1/...`，Vite 代理到公网 B。新建回放为 idle，时钟25:00；需要 A2 播放按钮调用 control 后才会推进。B 已支持六种 SSE 消息和 controls；A1 当前只消费快照。详细接口见 `backend/INTEGRATION.md`。

最后的比赛网站由整合者打包 A 交付的 dist 与 C 的 AI 模块，再启用同源静态托管。当前 Python-only 镜像不包含这两者，不能只开启一个开关就变成最终参赛网站。真实模型接入后还须从云服务器实测模型 endpoint、认证、超时和费用保护。

## 成本与提交前边界

- Free 适合先联调；官方说明空闲15分钟休眠，唤醒约1分钟，并有月度时长、带宽、构建限制。正式评审前应评估常驻实例。见 [Render 免费层说明](https://render.com/docs/free)。
- 最终演示前再评估一台付费常驻实例，价格以 [Render 当前价格页](https://render.com/pricing) 和创建页为准；计算资源与模型调用费用分开，不自动购买升级。
- 容器重启、重新部署或休眠恢复会丢失内存回放；前端重新创建即可。当前没有必须持久化的用户数据，因此不加数据库。
- [官方比赛规则](https://github.com/microsoft/insidethegamehackathon/blob/main/OFFICIAL%20RULES.md) 要求合成足球数据、AI 驱动的可解释与个性化体验。它没有要求所有项目统一使用 Azure 托管；参赛类别仍决定必须实际使用的技术。Foundry/Azure 类别不能用 Render 代替对应技术的实际使用。当前后端加预计算桩还不是完整参赛作品。
- 提交截止北京时间 **2026-10-28 14:59**；评审截止北京时间 **2026-11-11 15:59**。最终版本需保持评审可访问，不能提交后马上关机。公开代码、演示视频和真实技术使用由团队提交前逐项核对。

闭环完成标准：账号授权 → 云端构建成功 → 公网 smoke passed → A 接口消费者连通 → A/C 完成最终界面与真实 AI → 整合部署并匿名浏览器验收。当前已完成本地后端及接口级验证，公网阶段等待账号与平台构建。
