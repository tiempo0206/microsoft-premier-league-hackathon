# MatchMind AI 三人开发启动说明

交付包 2.1，协议仍为 2.0.0，2026 年 10 月 21 日。目标是三人用不同 AI、每天少量时间完成一个可解释足球分析闭环。本包是经过离线检查的开发基线，包含契约、样例、Mock 和 AI 桩；完整网页、正式后端和真实多 Agent 仍由三位成员分工实现。

## 第一次使用

1. 三人一起看 docs/00_plan.md，确认 A 前端、B 数据后端、C AI与集成分别由谁负责，填 TEAM_ROLES.json。C 是唯一合并与共享契约负责人。
2. 在现有 GitHub 仓库旁解压本包。由 C 检查现有 CONTRIBUTING.md 和未提交改动，再把 starter-overlay 下的整个 matchmind 文件夹新增到仓库；不要覆盖仓库已有 README、CONTRIBUTING 或 CI。已有 matchmind 目录时先逐文件比较，禁止整目录覆盖。
3. C 在自己的分支提交这份基线并经团队确认集成，记录唯一 BASELINE_SHA。推送、开 PR 和部署需要用户按各自工具的权限要求授权。其他两人等这个基线进入共同分支后再开始各自分支；这是唯一一次共同等待。
4. 所有人都从同一个 BASELINE_SHA 开分支。A 读 roles/A_FRONTEND.md；B 读 roles/B_BACKEND.md；C 读 roles/C_AI.md。把对应文件全文发给自己的 AI。不要把三张角色卡同时交给 AI 要它包办全部。
5. 所有命令从仓库里的 matchmind 目录执行。Windows 可用 py -3.12 替代 python；macOS/Linux 按实际解释器用 python3。Node >=22.13、pnpm 11.25.0、Python 3.12。没有 pnpm 时，可由本人通过 npm 安装固定版本 pnpm@11.25.0。使用各自 .venv，环境与 node_modules 不提交。

## 国内环境先按新入口准备

先读 docs/01_cn_setup.md。前端默认项目级npmmirror，Python安装临时使用清华镜像；不依赖海外模型、Google字体、外链CDN或远程下载比赛数据。生产可以用Render或Azure等国际常驻容器。总方案与角色指令均为Markdown。

## 所有人先验证共同基线

```text
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install --index-url https://pypi.tuna.tsinghua.edu.cn/simple -r requirements-contracts.txt
python tools/check_frozen.py
python -m unittest discover -s tests -p "test_*.py"
```

无账号也能开始。A 可在另一个终端运行 `python -m tools.mock_api`，地址为 http://127.0.0.1:8765；B 导入 `ai.service.analyze` 桩；C 用 contracts/examples/analysis_request.json 开发，无需后端启动。

## 固定交付顺序

第一个闭环：一段 25:00—30:00 的原创合成赛事、一次高位夺回触发、两种观众文本、能展开证据、能暂停和重置。先完成离线规则回退，再接一次真实模型，最后接完整 Agent Framework 工作流与小样本对照。不要把 Mock 或回退称为实时 AI。

阅读顺序：本文件 → docs/01_cn_setup.md → AI_RULES.md → docs/00_plan.md → docs/02_contract.md → 对应角色卡。资源开通看 docs/03_resources.md；合并看 docs/04_merge.md；验收看 docs/05_acceptance.md。
