# 冻结接口与集成契约

契约版本 2.0.0。机器可执行真源是 contracts/contract.schema.json；类型由 python tools/generate_types.py 生成到 contracts/types.ts。所有对象禁止未知字段。只改变模型供应商不改变本协议。协议变更必须由 C 发起版本记录和兼容性检查，禁止各角色私自增改。

## 服务边界

正式运行只有一个 Python 后端进程和一个前端构建目录，不拆 AI 微服务、不引入 Redis、Celery 或数据库。B 从 `ai.service` 导入 `async def analyze(request: dict) -> dict`，在有界后台任务中调用；C 保持这个导出名称、异步签名和 AnalysisRequest/AnalysisResult 不变。数据读取与统计不等待模型。此单进程方案要求公网只运行一个 worker/replica，否则内存会话无法一致；扩容不是本轮范围。

前端开发使用 Vite 将 /api 代理到本地 Mock 或正式后端。生产由后端托管 frontend/dist，浏览器只访问同一域名。前端没有模型 URL、模型密钥或 AI 内部接口。

## HTTP 接口

| 方法及路径 | 请求 | 成功响应 |
| GET /api/v1/health | 无 | {status, contract_version, mode, model_ready} |
| GET /api/v1/matches | 无 | Match[] |
| GET /api/v1/matches/{match_id} | 无 | Match |
| GET /api/v1/matches/{match_id}/events | from_sec / to_sec 可选 | Event[] |
| GET /api/v1/matches/{match_id}/stats | at_sec 可选 | MatchState |
| POST /api/v1/replays | CreateReplay | 201 ReplaySnapshot |
| GET /api/v1/replays/{replay_id} | 无 | ReplaySnapshot |
| POST /api/v1/replays/{replay_id}/control | ControlReplay | ReplaySnapshot |
| GET /api/v1/replays/{replay_id}/stream | Last-Event-ID 可选 | text/event-stream |
| GET /api/v1/replays/{replay_id}/insights/{insight_id} | 无 | Insight |

所有非创建成功响应为200。错误统一 {error:{code,message,retryable}}；400 INVALID_REQUEST、404 NOT_FOUND、409 STATE_CONFLICT、429 CAPACITY_LIMIT。AI 内部模型故障通常通过标记 fallback 的 AnalysisResult 和 SSE 状态呈现，不能让统计 API 整体 503。服务启动时验证静态数据，坏 fixture 应启动失败并报清楚文件位置。

## 时间与回放

clock_sec、timestamp_sec 和 window 均为比赛逻辑秒，duration_ms 为墙上时钟耗时。当前片段是第一节25:00—30:00，绝不能在 UI 写成完整比赛。片段初始比分0:0，仅代表本合成片段的设定。所有事件查询及证据窗口使用闭区间；同秒事件再按 event_id 稳定排序。持球时长按半开时间段积分，避免重复累计边界。

CreateReplay 必须给 match_id 与 speed。默认推荐5倍速，允许1/2/5/10。控制 action 只允许 play、pause、reset、set_speed；set_speed 必须提供 speed，其他 action 不携带 speed。P0 不做 seek，点击证据仅选中和高亮对应片段，不能暗中改比赛时钟。

新会话为idle，clock_sec=1500，run_id=1，统计为片段初始快照。play 进入playing；pause 冻结时钟和赛事事件，可继续发布已完成且窗口不晚于当前时钟的 AI 结果；ended 后 play 返回409，需先reset。reset 保留 replay_id 和当前speed，run_id增加1，清空统计、洞察、轨迹和待发布队列，回到idle。seq在同一 replay 生命周期只增不减，不能随reset归零。

模型请求携带 replay_id、run_id、task_id、window；返回值必须原样带回这三个身份字段。发布前调用 check_result，再用 can_publish 检查当前会话、代数与时钟。旧代结果允许后台结束或被取消，但不能发布到新回放。两个会话不能互相控制、抢走对方结果或复用带旧身份的响应。

默认持续播放；为了在视频里读解释，演示者可在触发后手动暂停，AI仍完成当前窗口。不要依赖90分钟高速播放与慢模型碰巧同步。

## SSE

六种 event 名称严格为 snapshot、match_event、match_state、insight、agent_status、error。data 是 StreamMessage，包含 replay_id、run_id、seq、kind、payload；event 必须等于 kind。SSE id 格式为 replay_id:run_id:seq。seq不是赛事 event_id，客户端不要求连续但丢弃同一代已见或更小的seq。

建连和断线重连都先发完整 snapshot，包含当前Replay、MatchState、最近洞察和Agent轨迹。P0 只支持快照恢复，不重放传输日志；收到 Last-Event-ID 也以新快照恢复，文档和 UI 不承诺无损逐条补发。新run快照原子替换客户端旧状态；收到旧run消息一律丢弃。每个订阅者独立有界队列，慢消费者不能阻塞回放；超限后断开并由重连快照恢复。

match_event 仅用于时间线，不能由前端再次累计统计；match_state 是当前统计真值。前端按insight_id去重，最多保留最近20条。定期发送SSE注释心跳，不把心跳当业务序号。生产反向代理必须禁用缓冲并验证流可及时到达。

## 数据与足球口径

坐标0—100，x向屏幕右，y向下；本片段HOME向右攻、AWAY向左攻。高位使用进攻方向换算后的x>=66.67。进球只由goal事件增加比分，shot(outcome=goal)只增加射门数，不再增加比分。传球成功率分母为pass事件数，分子为outcome=successful的pass；分母0显示“—”。

possession_seconds 是按已记录事件的持球队伍分段推算的合成持球时间。第一条事件前使用Match.initial_possession_team；缺少真实连续持球追踪，不能声称真实英超官方控球率。状态只在明确记录的队伍变化后转移，未记录的争抢不推断。

高位夺回场景：窗口内某队至少3次高位recovery，其中至少2次在同possession_id的随后15秒内形成该队shot。linked_shots数的是“形成射门的夺回次数”，一次夺回后多次射门仍计1。固定演示窗口1500—1650，HOME高位夺回3次，关联2次；HOME持球35秒、AWAY115秒。触发器是可复核的启发式，不等于完整战术或因果真值。

前端简图只画事件点或传球线，不插值出22人无球位置。本包不包含真实录像、队徽、球员肖像或持续跟踪数据。

## AI 输出和核验边界

request.events 已截断到窗口且属于同一match；request.metrics由B按统一口径计算。C需要验证ID、窗口和数值，防止模型改写这些事实。每条metric claim必须引用metric_key和metric_value，解释性主张不能伪装为精确数字。Narrative的两个版本必须基于同一claims；不能仅检查引用ID存在就把所有自然语言都视为正确。

status=passed只能对应真实模型流程、agent_and_code核验和非空模型标识；rule_fallback与precomputed必须为fallback并显示不同标签。rejected不得含可发布Insight。trace记录实际执行角色、状态与耗时，不能用固定动画冒充真实调用。独立审核LLM提供语义检查，代码校验保证结构和数值，两者不等同于证明真实战术因果。

每个任务最多一次纠正，默认整体deadline12秒、并发1。deadline参数可以在资源验证后改配置，不改外部协议。P95延迟先测量后报告，不承诺一定8秒。会话最多8个、任务每小时全局上限30，均为起始保护配置；公开服务由B/C实际实现限流、空闲回收与预算提示。
