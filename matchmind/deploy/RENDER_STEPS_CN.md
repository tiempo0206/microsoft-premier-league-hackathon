# Render现有后端：接管、配置与验收

核对日期：2026-10-23。B预览已上线并通过公网验收。本文件取代旧的“等待注册/授权/选择B分支”流程；当前部署来源是main。

## 1. 直接使用已上线服务

| 项目 | 已核对值 |
| --- | --- |
| 公网URL | https://matchmind-backend-preview.onrender.com |
| 健康检查 | https://matchmind-backend-preview.onrender.com/api/v1/health |
| Render服务ID | srv-dbdegcnavr4c739pockg |
| 最近已验收部署ID | dep-dbdep9gae00c73fujcr0 |
| 云端固定提交 | bcaed0e1c899a0a27022d91c67b17e3537af702d |
| 来源分支 | main |
| 套餐/区域/实例 | Free / Singapore / 1 |
| Runtime | Docker，单worker |
| Root Directory | matchmind/ |
| Dockerfile Path | deploy/Dockerfile |
| Docker Build Context | . |
| Docker Command | 留空，使用镜像CMD |
| Health Check Path | /api/v1/health |
| Auto-Deploy | Off |

服务已存在，不需要整合者重复创建、重新注册B的账号或寻找已删除的角色分支。完整公共基线已通过PR #9合入main，具体采用版本由整合者fetch后审查。

## 2. 当前环境变量

| Key | Value |
| --- | --- |
| PORT | 10000 |
| MATCHMIND_SERVE_FRONTEND | 0 |
| MATCHMIND_DATA_DIR | data/extra/validated-demo |
| MATCHMIND_MAX_REPLAY_SESSIONS | 8 |
| MATCHMIND_MAX_CONCURRENT_ANALYSES | 1 |
| MATCHMIND_ANALYSIS_LIMIT_PER_HOUR | 30 |
| MATCHMIND_MODEL_TIMEOUT_SEC | 12 |

最后四项已通过Render API写入、回读、固定同一源码重新部署并完成公网回归。每小时上限按B的单调时钟小时桶实现，不是严格滚动窗口。当前入口为backend.app:app，不注入C模型，model_ready=false是预期。

## 3. 给其他Agent的管理权限

- 调用HTTP/SSE只需公网URL，应用接口当前匿名；不需要Render Key。
- 修改Render配置或发布需要有权操作此服务的Render管理API Key。将它放在Agent私密配置/环境变量RENDER_API_KEY，不能填到模型Key或前端变量中。
- 协作Agent具备终端/HTTP能力、代码访问权和上述管理凭据，就能管理现有部署，不要求先加入Render工作区成员。
- 操作对象明确限制为服务srv-dbdegcnavr4c739pockg。Key能力来自持有人权限，本文不分发凭据、不转移服务所有权、不授权付费升级。
- B本机已存加密凭据，但不会自动同步到别人的电脑。其他机器应独立完成经资源持有人授权的凭据配置；不要假设复制DPAPI文件就能解密。

官方API： https://render.com/docs/api 。服务读取GET /v1/services/{serviceId}；单变量修改PUT /v1/services/{serviceId}/env-vars/{key}；发布POST /v1/services/{serviceId}/deploys。优先逐项更新变量，保留其他人的配置。Key不入Git，日志不回显Authorization。

自动部署当前关闭。改配置/推送源码后，整合者须显式发布已审查的commitId，再查询该deploy直至live。不要把“main已更新”当作“线上已更新”。

## 4. A现在即可接入

A在frontend终端设置已有Vite代理，重启开发服务器：

```powershell
$env:MATCHMIND_BACKEND_URL='https://matchmind-backend-preview.onrender.com'
pnpm run dev
```

浏览器仍请求相对/api/v1/...。新回放初始idle，25:00；播放控制调用后时钟才前进。SSE支持快照重连，不保证逐条日志补发。前端统计采用snapshot/state真值，不再按事件二次累计。

## 5. C与最终网站发布

C的组合根ai.app:app和发布入口deploy.release_run已在main。整合者负责C模型endpoint/名称/Secret与实际云端探针；Render管理Key不能替代模型Key。

已有deploy/Dockerfile.release模板要求frontend/dist在构建上下文。dist通常不入Git，Render克隆仓库不会得到某人的本机构建产物。最终整合者应把A构建纳入Docker多阶段构建或CI产物打包，再切换为组合镜像。

沿用当前Root Directory=matchmind时，最终Dockerfile Path应为deploy/Dockerfile.release、context=.；开启MATCHMIND_SERVE_FRONTEND=1。B/C整体超时必须一致（C候选20秒应在云上复测），仍固定一个worker/实例。

数据默认validated-demo；C已修复历史证据截断问题，main交接记录离线门禁12/12正常输入通过、3/3篡改拒绝。采用增强数据前仍针对最终提交运行python -m deploy.adapter_check。历史报告不是当前阻塞清单。

最终整合步骤见 ../backend/INTEGRATOR_HANDOFF_CN.md 。模型费用、账号事务、最终发布与运行维护由接手的资源负责人承担，普通技术配置无需B本人重新参与。

## 6. 公网验收

以下命令在matchmind执行，使用项目Python3.12虚拟环境：

```powershell
.\.venv\Scripts\python.exe -m deploy.smoke_backend https://matchmind-backend-preview.onrender.com
```

已通过：health、目录、独立预期统计、创建/重复请求、播放暂停、重置、旧run、异常输入及SSE快照重连。探针只播放很短时间，不会跨AI触发点，不验证真实模型或浏览器。

根路径JSON404是B-only预览的预期。完整网站另验浏览器选择比赛→播放→统计→AI→证据/模式→断线恢复。model_ready只反映C的配置判断时，不能代替真实云端模型调用验证。

## 7. 如将来需要重建预览

仓库授权已经完成。仅在明确需要新服务时，使用New→Blueprint，选择main，Blueprint Path=matchmind/deploy/render-backend.yaml。文件仍定义一个Free、Singapore、单实例的B预览，内部branch也已改成main。不要同时用Blueprint管理现有手动Web Service；Blueprint Auto Sync与服务Auto-Deploy是不同开关。

手动新建时，使用本文件第一节的Root Directory=matchmind、Dockerfile Path=deploy/Dockerfile、context=.组合。另一种合法写法是Root Directory留空、Dockerfile=matchmind/deploy/Dockerfile、context=matchmind，不能交叉混用两套路径。

## 8. 最终负责人需要考虑的运行条件

Free空闲15分钟后休眠，唤醒约1分钟，且存在用量限制。正式评审的可访问性和费用方案由最终负责人评估；本次没有升级套餐或创建额外资源。重启/部署会清空内存回放，A应重新创建，不因此新增数据库。

官方资料：

- https://render.com/docs/docker
- https://render.com/docs/monorepo-support
- https://render.com/docs/infrastructure-as-code
- https://render.com/docs/free

B后端已完成公网预览；完整产品的模型、网页、评审可访问性和提交材料仍由最终整合/提交负责人验收。
