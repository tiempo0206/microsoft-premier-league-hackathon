# 国内模型与国际部署

交付包2.1，核验日期2026年10月21日。以下是公开文档与包元数据核验，不是你们账号的成功调用记录。本包未使用任何真实密钥、未执行付费推理，也没有保证免费额度或某一网络必达。

## 无账号时仍可完成的开发

数据直接随包提供，不需要申请足球数据账号或下载大型数据集。A 使用本地 Mock，B 使用 AI 桩，C 用离线输入做输出校验。先完成这三件事，资源注册只由C处理，不让另外两个人等待。

## 国内模型主路线

主选阿里云百炼按量API的千问模型，先以当前文档示例qwen-plus做JSON探针；模型别名并非不可变快照，正式评测需记录响应里的实际model和日期。如控制台提供适合的固定版本，在一组评测中固定它。网页聊天会员或Coding Plan不自动等于产品API额度。

C本人完成账号注册、必要实名认证、服务协议和费用设置。进入百炼控制台，选择中国内地可用地域，创建最小权限API Key，复制控制台对应Base URL与可用模型名。当前北京官方文档使用 https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1；以本人控制台为准，不混用其他地域或套餐的密钥和地址。模型密钥只放C本地/部署服务器环境变量。

先设置 MATCHMIND_MODEL_PROVIDER=dashscope、MATCHMIND_MODEL_BASE_URL、MATCHMIND_MODEL_NAME、MATCHMIND_MODEL_API_KEY。运行 `python tools/probe_model.py` 只检查配置是否齐全，不打印密钥、不调用模型。确认费用由本人承担后，显式运行 `python tools/probe_model.py --live`，只发送一次很小的JSON请求。成功后保存成功标志、模型、延迟和usage；不要保存请求头或密钥。该探针还不等于完整工作流验收。

Windows PowerShell临时变量示例：`$env:MATCHMIND_MODEL_NAME='qwen-plus'`。密钥由本人在本地输入，不发送给聊天AI。程序不会自动读取.env；实际服务由C选用dotenv加载或显式环境变量，必须在README写清楚。

错误定位：401先核对Key与地域；403检查模型权限；404检查Base URL与模型名；429核对额度和限流；400检查JSON参数支持。不要通过关闭TLS校验修复网络问题。免费试用是否提供、有效期与是否用完即停，以账号控制台为准；预算告警不能代替程序硬限流。

## 备用路线

DeepSeek官方API当前文档使用base_url=https://api.deepseek.com、model=deepseek-flash。使用同样的Chat Completions JSON对象协议，provider设deepseek。不要沿用旧教程中的过时模型名。是否需要实名、充值和可用额度由C在官方平台核实。备用只切provider配置；不要求三个人都申请账号。

两个供应商都不通时，A/B继续使用明确标注的rule_fallback。正式参赛需完成实际AI能力，不可把纯规则版本说成多Agent。自部署大模型、下载权重和训练模型不在P0。

## 保留微软技术价值

使用 microsoft/agent-framework 的 Python Chat Completions 客户端 OpenAIChatCompletionClient，传入国内供应商base_url、model与key，避免误用当前走Responses API的OpenAIChatClient。包选agent-framework-core和agent-framework-openai，不安装all可选项。官方支持自定义兼容端点，实际供应商兼容性仍必须探针和工作流实测。

先验证直接JSON请求，再接框架单Agent，再接三角色；任何一步失败都先定位本层，不能同时换框架、换模型和改协议。实际部署可用国产模型，但提交中只写真实使用的微软产品。没有Foundry资源时主攻多Agent类别，不宣称已使用Foundry，也不为了专项奖阻塞闭环。


## 国际部署与模型连通性

本轮允许把最终产品部署到国际站点。开发过程只需本机Node/Python，容器镜像和前端生产构建可以在部署平台或GitHub Actions的国际构建环境完成，不要求三位成员在国内反复拉取Docker Hub镜像。

资源从零开始时，优先由B验证Render Docker Web Service；已有可用Azure订阅时可直接用普通Azure Container Apps，无需为了换平台重做。两种方式都保持一个后端进程、一个常驻实例、同源前端和内存会话，不在本轮拆前后端站点。

部署的是B最终完成的后端和A的构建产物，不是tools.mock_api。Render可以从仓库内Dockerfile构建镜像；B在deploy/提供Dockerfile和.dockerignore，分别构建frontend/dist、安装后端与AI依赖，并由后端托管静态文件。所有浏览器请求走同域/api，密钥通过服务器运行时环境变量提供，不写进镜像构建参数、仓库或前端bundle。

公共服务监听0.0.0.0，端口遵循平台PORT；只开一个uvicorn worker，健康检查用/api/v1/health。根目录和Dockerfile路径以实际仓库matchmind子目录为准。命令示例仅在B实现backend.app:app之后使用：

```text
python -m uvicorn backend.app:app --host 0.0.0.0 --port $PORT --workers 1
```

单常驻容器方便保持SSE和回放内存。不要把该后端原样塞进短生命周期Serverless函数。免费服务可用于联调，但Render官方说明空闲15分钟会休眠，唤醒可能约一分钟；团队应为评审期选择本人同意的稳定方案，并检查账户额度与费用。这里不承诺零费用常驻，也不替团队购买资源。

Azure路线需先有有效订阅，使用普通Container Apps并验证外部入口、target port和单副本。Azure或Render的注册、身份验证、仓库访问授权及支付均由本人操作；开通失败不影响A/C继续开发。

## 部署后必须重新做的验证

1. 从国际宿主实际运行一次模型探针，检查中国内地API的地域、账号权限、出站网络和延迟；本地成功不等于海外服务器成功。
2. 国内模型入口不通时先由C检查配置与区域，再考虑官方DeepSeek备用入口，或调整部署地域；所有切换只改后端配置，不改共享协议、不让A重写页面。仍不可用时保持明确fallback状态，直到真正完成实测。
3. 用匿名浏览器检查页面、同源API和SSE；再用国内开发机与另一外部网络分别访问。国际部署不自动保证中国境内访问流畅。
4. 完整运行play/pause/reset、旧run拦截、断线快照恢复和两种观众模式。容器重启会丢失内存回放，前端应允许重新开始。
5. 记录真实服务URL、模型provider/model、部署版本、成本负责人和评审期保活方式。未实际使用Foundry就不写成已使用，微软框架也以实际执行记录为准。

GitHub Codespaces仅作为短时联调备选，不作为常驻评审服务承诺。公网发布前由用户确认平台、费用和访问范围；本次交付只提供文档和配置，没有实际部署。

## 国内安装入口

使用docs/01_cn_setup.md。默认Node镜像已限定在frontend/.npmrc；Python每条安装命令临时指定清华镜像，不改系统全局配置。版本与契约仍冻结，镜像缺包先切官方源，不升级依赖来碰运气。

部署参考：https://render.com/docs/docker 、https://render.com/docs/deploy-fastapi 、https://render.com/docs/free 、https://learn.microsoft.com/en-us/azure/container-apps/quickstart-portal 。
