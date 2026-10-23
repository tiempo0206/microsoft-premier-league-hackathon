# C AI核验与集成负责人交给 AI 的任务卡

你的角色是C。日常功能只改ai/、evaluation/、tests/ai/和docs/handoff/ai.md；另承担共享基线维护和每日合并。共享契约变更必须单独审查，不能利用集成人身份随意改A/B代码。P0不启用DSPy优化；先完成可解释闭环和小型固定评测。

环境先读docs/01_cn_setup.md，模型与国际部署读docs/03_resources.md。文中的python命令必须使用本项目.venv解释器。共同Python检查在matchmind根目录执行，pnpm命令在frontend目录执行，不要混用工作目录。国内开发优先项目镜像、本地静态资源和随包数据；不要求先有Azure或Docker。

## 工作块 C1

把共同基线导入仓库，记录BASELINE_SHA并确认三人角色。运行生成类型、冻结摘要与共同测试，向A/B发同一commit。使用contracts/examples/analysis_request.json独立运行ai.service.analyze，核对fallback标签。与成员确认每天一次集成时间。不要等待模型账号才发基线。

## 工作块 C2

按docs/03_resources.md由本人开通一个国内模型API。先配置检查，再在用户允许费用后显式运行一次 --live 探针；只记录成功标志、模型名、usage和延迟，不记录Key。如果平台注册/实名/支付阻塞，继续离线审核模块，同时尝试文档中的官方备用供应商。不要向AI聊天发送密钥。

## 工作块 C3

实现独立的结构化分析、双模式叙事、审核和程序校验，保持async analyze(dict)->dict边界。先用模型mock单测验证分支，再用少量实际合成窗口实测。所有事实来自输入，审计提出correction request后最多纠正一次。总deadline与并发生效；超时或错误返回诚实的规则fallback，不无限重试。

## 工作块 C4

用Microsoft Agent Framework接管已验证流程，选择OpenAIChatCompletionClient接国内Chat Completions端点。先单Agent导入与无密钥实例化，再真实单次调用，再串联analyst/narrator/auditor。角色有不同任务和输入，不复制同一个Prompt改名字。Trace来自实际执行。通过注入“对方体能下降”等证据不足推断展示审核能力；故障注入标为测试，不伪装为自然输出。

## 工作块 C5

做12个起步评测，单Agent和多Agent共享输入、模型和确定性校验器。记录错误、纠正成功、耗时与调用数，不保证多Agent一定更快或更便宜。B用异步任务调用时不改签名；两个观众文本在一次结果中产出，由A本地切换。

## 工作块 C6

每日合并小PR并跑共同检查和已有角色测试；与A/B验收reset旧任务、模式、模型故障、公网访问。填实际技术栈、模型路由和未实现项，与提交代表完成材料。源码公开和正式提交由具有权限的成员在用户授权下执行。

## 本角色检查

非JSON、空响应、错误ID、越界时间、错误数字、证据不足推断、超时、一次纠正上限、fallback标签、返回身份原样保留。测试必须mock网络，不能因开发机恰好有密钥就调用付费API。共享初始契约测试中mock模式语义需继续成立。若通用fallback遇到错误输入，优先reject而不是用错数字生成解释。

给AI的第一次消息：

> 我是MatchMind角色C。先读roles/C_AI.md、AI_RULES.md和docs/02_contract.md。只完成C1并验证无密钥AI边界；不要开始部署、付费调用或改前后端。先把共同基线准备好，让A/B可以立即开工，再报告资源开通所需的人类操作。
