# 真实历史数据交接包（直接含数据，研究用途）

2026-10-24。已取得并核验原始文件。本包交给C统筹数据接入/校准，A可使用同一份[接手提示词](HANDOFF_PROMPT.md)。不需要B再次找数据、发样本或手工配置。

## 直接拿数据

拉取仓库后，samples/已有：

| 文件 | 内容 |
| --- | --- |
| wyscout-2499719.match.original.json | 来源比赛对象，Arsenal–Leicester City，2017-08-11，全场4–3 |
| wyscout-2499719.events.original.jsonl | 该比赛1,768条原始事件字段值 |
| wyscout-2499719.1H-1500-1800.original.jsonl | 上半场25:00–30:00的96条原始事件 |

**样本已经在Git里，不需要先重新下载。** 如需完整赛季/其他比赛，直接下载本仓库[仅数据Release](https://github.com/tiempo0206/microsoft-premier-league-hackathon/releases/tag/data-wyscout-2017-18-v1)的events.zip、matches.zip；其中英格兰部分有380场、643,150条事件，重复事件ID为0。Release也提供小交接包和校验文件。压缩包含多个赛事，英格兰成员分别为events_England.json、matches_England.json。

获取方法是补充，不是必须重做的步骤：它让接手者能补齐其他比赛、验证字节来源，或在GitHub下载受限时使用发布方原始入口。

## 一条离线核验命令

在matchmind目录，用项目Python3.12环境执行：

```powershell
.\.venv\Scripts\python.exe -m data.generator.real_history --verify
```

只读仓库样本，无网络、无模型。检查SHA-256/字节数、比赛ID、事件ID唯一性、坐标范围，以及96条片段是否恰好是全场记录中1H、1500<=eventSec<=1800的原样选择。

可选：从发布方取完整原件，校验后写入独立缓存：

```powershell
.\.venv\Scripts\python.exe -m data.generator.real_history --fetch-full --cache-dir .artifacts/real-history-source-cache
```

macOS/Linux使用.venv/bin/python。也可把从Release下载的两个zip放入该缓存，再运行同一命令核验；已有正确文件不会重复下载。缓存不得指向受管运行数据或其他源码目录。工具不会转换协议、导入运行目录或重部署。

## 核验与来源

- [manifest.json](manifest.json)：研究标识、来源/版本、原件MD5与SHA-256、样本哈希。
- [source-verification.json](source-verification.json)：完整英格兰源文件流式检查结果和字段缺口。
- [ATTRIBUTION.md](ATTRIBUTION.md)与[CC BY 4.0全文](LICENSE-CC-BY-4.0.txt)：作者、DOI、署名与变更说明；这不是项目原创CC0合成数据。
- 原始源： [Events](https://figshare.com/articles/dataset/Events/7770599)、[Matches](https://figshare.com/articles/dataset/Matches/7770422)。发布方API元数据提供download_url、大小和MD5。

选择与JSON重新序列化是本包的变更，原始字段值、事件ID、队伍/球员ID保持；样本不是源文件格式字节一致的截段。完整zip与发布方校验值一致。25:00片段的起始比分不能用全场4–3代替。

## C/A如何使用

**默认建议：用于校准和对照合成数据。** 对同类事件、同一窗口和同一统计定义比较传球/射门频次、坐标分布及事件间隔；先定义provider映射，再给出合成参数和对照结果。单场片段只说明该样本，不能冒充整个英超分布。Wyscout的Shot类别和任意足球官方射门口径不可未经核对直接画等号。

当前样本原始eventName计数：Pass59、Duel16、Shot4、Others on the ball9、Save attempt2、Interruption3、Free Kick3。没有直接的recovery或possession_id，不能硬套原演示的3/2触发结论。

如果C选择独立真实历史模式，先确定比赛规则和版本化的来源/日期/起始状态表示，再协调A呈现。协议2.0.0固定synthetic=true，不能把真实记录伪装成synthetic来通过校验。浮点半场秒、进攻队相对坐标、乌龙球/进球、持球段和事件种类都要有明确映射；未知事实保留未知。

官方[规则§4.7](https://github.com/microsoft/insidethegamehackathon/blob/main/OFFICIAL%20RULES.md#47-use-of-footage)要求使用合成足球数据。参赛主链路继续保留明确标注的合成比赛；真实数据可先支撑校准/对照。新的历史模式及其提交范围由C/代表确定，不由本包自动启用。

## 与现在线上隔离

本包synthetic=false、runtime_compatible=false；文件名不匹配运行Catalog的*.match.json，且不在两份Dockerfile的数据COPY目录中。当前默认数据、冻结fixture、schema、模型和Render配置均未修改。本轮不触发线上部署或模型调用。

C是#15的数据统筹/整合接收人；A若先收到，可直接校验和读取这些样本，按提示词推进自己负责的展示/接口消费并与C对齐。实际数据/契约变更通过正常分工实施，不要求B本人回来继续查源或补文件。
