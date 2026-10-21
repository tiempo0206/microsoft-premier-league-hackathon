# B 数据后端负责人交给 AI 的任务卡

你的角色是B，只改backend/、data/generator/、data/extra/、tests/backend/、deploy/和docs/handoff/backend.md。数据样例已经提供，你不负责模型开户、Prompt、前端页面或共享契约。使用ai.service.analyze桩独立完成后端。

环境先读docs/01_cn_setup.md，模型与国际部署读docs/03_resources.md。文中的python命令必须使用本项目.venv解释器。共同Python检查在matchmind根目录执行，pnpm命令在frontend目录执行，不要混用工作目录。国内开发优先项目镜像、本地静态资源和随包数据；不要求先有Azure或Docker。

## 工作块 B1

安装requirements-contracts.txt和backend/requirements.txt。实现backend.app:app及health、matches、match详情、events、stats。启动命令固定 `python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000`。读取随包JSON/JSONL；实现统计纯函数，按固定样例验收：1650时HOME射门2、AWAY0、比分0:0、持球35:115；1800时比分1:0，不能把shot(goal)和goal加两次。禁止先写完整足球生成器。

## 工作块 B2

实现Replay创建、查询和control，时钟由服务端维护。每个会话独立，reset增加run_id，play/pause/set_speed按契约执行。至少写两会话隔离、暂停、重置测试。模型先不接，保证数据闭环。

## 工作块 B3

接sse-starlette，用完整snapshot起流，再按冻结六种事件名称推送；每个订阅者独立队列、心跳、断线回收。支持快照重连，不承诺日志补发。前端根据状态显示，后端不得等待模型才发统计。

## 工作块 B4

实现高位夺回检测和窗口提取，调用 `await ai.service.analyze(request)` 但放在有界后台任务中。同一replay+run+window+type只调一次；只发布check_result和can_publish都通过的结果。C尚未完成真实模型时桩返回fallback是正确行为；不要自己写第二套模型调用。把窗口所需事件和指标完整打包，不让C反查你的内部数据库。

## 工作块 B5

与A联调；落实会话容量、空闲回收、分析次数限制和请求体上限。用当前epoch拦截reset前的旧结果。托管frontend/dist，/api不被SPA回退路由吞掉；生产同域、单worker。Docker启动脚本、健康检查和SSE代理配置放deploy/。与C确认公网宿主，部署账号开通由本人操作。

## 工作块 B6

公网匿名验收并记录版本、URL、费用责任和保活到期日。容器重启会丢失内存回放，前端应明确重新开始。不要在这一轮加多副本、Redis或数据库。公网发布需人类授权，不能把本地Mock暴露为正式产品。

## 本角色检查

共同契约测试、tests/backend/和一次与A的真实端到端。覆盖比分不双计、窗口边界、坏ID、pause/reset、两个订阅者不抢消息、重连快照、旧run结果、模型失败统计仍更新。参考tools/reference.py来写期望，不直接把Mock服务搬成生产后端。

给AI的第一次消息：

> 我是MatchMind角色B。先读roles/B_BACKEND.md和共同契约。只实施B1，先使用现成fixture，按规定路径实现FastAPI与统计。不做模型和前端，不改contracts或固定fixture。完成后运行检查并交付可重复启动命令。
