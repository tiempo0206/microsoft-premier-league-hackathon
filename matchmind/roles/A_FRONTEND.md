# A 前端体验负责人交给 AI 的任务卡

你的角色是A，只改frontend/、tests/frontend/和docs/handoff/frontend.md。职责是把数据和可信解释呈现为英文网页，完成演示交互和视频素材。禁止改后端、AI、契约和固定数据。

环境先读docs/01_cn_setup.md，模型与国际部署读docs/03_resources.md。文中的python命令必须使用本项目.venv解释器。共同Python检查在matchmind根目录执行，pnpm命令在frontend目录执行，不要混用工作目录。国内开发优先项目镜像、本地静态资源和随包数据；不要求先有Azure或Docker。

## 工作块 A1

读取共同文件，运行 `python -m tools.mock_api`。创建React/Vite入口和基本页面，使用现有frontend/package.json及contracts/types.ts，不再运行会覆盖配置的脚手架。先实现GET matches、POST replays、接收snapshot。做出合成标签、25:00时钟、比分、射门、传球和加载/错误状态。验收：页面能选择唯一片段并显示Mock返回的状态。

## 工作块 A2

实现play、pause、reset和1/2/5/10倍速，按钮调用冻结接口。SSE使用EventSource并逐类监听；snapshot完整替换，match_state更新统计，match_event更新事件列表，insight按ID去重，agent_status显示真实阶段。任何时候不能通过match_event再累计统计。reset后按run_id丢弃旧消息。先用Mock的完整快照完成流程，不等待生产细分事件。

## 工作块 A3

做Insight卡、Casual/Analyst切换和证据展开。点击证据高亮对应事件与事件点，显示时间、类型和指标，P0不做seek或无球轨迹。Rule fallback、Precomputed、Live model、Evidence checked有明确文字。模式切换读同一Insight的两段文本，不再调用模型。

## 工作块 A4

接B真实API时只改Vite代理目标或部署配置，不能改页面字段。执行播放、暂停、重置、断线重连、模型失败、旧run结果丢弃和两模式一致性。发现接口缺项先提交契约问题，禁止写临时字段兼容多种拼法。

## 工作块 A5

桌面1280×720和手机390像素宽检查，按钮可键盘操作，状态有语义文字。优化证据高亮和阅读体验，先保证一种主题和一个页面，不加大图表库、登录页或聊天机器人侧栏。检查前端不含任何API Key；不加载Google字体、远程脚本CDN或在线占位图，图标和资源在本地构建。

## 工作块 A6

与C按docs/05_acceptance.md排练110秒英文演示；把实际画面交给用户确认。视频只展示已实现能力，故障注入有标签。更新handoff。

## 本角色检查

本包包含pnpm-lock.yaml，统一运行pnpm install --frozen-lockfile；依赖修改由A说明原因并重新提交锁文件，其他角色不改此锁。至少运行pnpm run typecheck、pnpm run build、角色测试与共同Python契约测试。前端尚未建立入口时build不通过属于待开发状态，不能声称启动包已含完整UI。

给AI的第一次消息：

> 我是MatchMind角色A。读取roles/A_FRONTEND.md和共同规则。只实施A1，使用tools.mock_api提供的接口；不要等待后端或模型，不改contracts。先列修改文件，再写代码并运行检查。未完成的部分明确列出。
