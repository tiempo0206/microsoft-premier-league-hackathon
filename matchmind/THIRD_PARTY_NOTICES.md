# 开源复用选择与许可记录

核验日期2026年10月21日。本包没有克隆大型业务项目或复制其业务源码。以下按依赖接入，保留安装包中的许可证，提交时列出实际使用的版本；版本元数据不代表已对所有第三方功能做过测试。

| 项目 | 决策 | 许可及理由 |
| microsoft/agent-framework | C实际工作流使用 | MIT；有自定义Chat Completions端点和角色协作能力 |
| fastapi/fastapi | B的API框架 | MIT；已有输入校验、OpenAPI和异步生态 |
| sysid/sse-starlette | B的SSE传输 | BSD-3-Clause；避免重复实现断线/心跳传输细节 |
| mswjs/msw | 可选，不进入P0依赖 | MIT；团队已有MSW经验时可用；本包已给零前端依赖的Mock服务器 |
| hudl/open-data 原statsbomb/open-data | 不导入实际数据 | 独立数据许可，不能按代码MIT处理；赛事主数据要求合成，本轮不承担数据授权和大型下载 |
| Friends-of-Tracking-Data-FoTD/Last-Row | 不作为P0依赖 | 已查看项目存在；真实轨迹方向需要额外数据范围与许可核验，本轮事件样例不需要 |

React、Vite、Pydantic、JSON Schema等按各自软件许可证使用。原创fixture标记CC0-1.0；没有球队队徽、真人肖像或真实比赛镜头。是否采用第三方数据、素材或额外代码由团队另行核验。

不套用完整多租户SaaS模板、Dify部署栈或足球强化学习环境。它们会引入账户、数据库、构建和运行环境等本闭环无需的依赖；开源组件只接到各自冻结边界内。
