# 不同 AI 的并行与合并规则

## 共同基线先行

C只新增matchmind子目录，不改仓库现有协作规范。团队确认TEAM_ROLES后，先提交共同基线，记录commit SHA。A/B/C都从这一SHA开分支；禁止各自让AI重新脚手架整个仓库。分支建议codex/frontend-xxx、codex/backend-xxx、codex/ai-xxx，具体仍服从仓库原有规则。

## 文件归属

| 文件范围 | Owner | 其他人怎样依赖 |
| frontend/、tests/frontend/ | A | 只通过HTTP与共享类型对接 |
| backend/、data/generator/、data/extra/、tests/backend/、deploy/ | B | 复用固定fixtures；只调用ai.service.analyze |
| ai/、evaluation/、tests/ai/ | C | 只接收AnalysisRequest并返回AnalysisResult |
| contracts/、data/fixtures/、tools/、共享测试、根配置 | C作为集成人 | 日常冻结，变更需受影响成员审查 |
| docs/handoff/frontend.md / backend.md / ai.md | 各自对应角色 | 写自己的进度，不互相改 |

A修改前端自己的依赖文件，B修改backend/requirements.txt，C修改ai/requirements.txt。新增依赖前先与共同约束比较，不能让各自AI独立升级Python/Node主版本。C负责整合跨模块依赖锁；本包提供精确顶层版本，不把它冒称为完整跨平台传递依赖锁。

## 每个工作块

1. 拉取共同分支最新状态，先查看git status，保留已有改动；不要用reset --hard或强推。
2. 告诉AI本次角色、任务编号、允许目录和契约版本。只做一个小块。
3. 运行共同契约测试和角色测试。用 `python tools/check_scope.py --role A --base HEAD` 检查当前未提交变更；B/C换角色。若检查已提交分支与基线的差异，--base填BASELINE_SHA。
4. 审查完整diff、更新自己的handoff，再提交小变更。工具只能报告路径，不能代替人的代码审查。
5. C每天固定一次集成。先合并不会破坏消费者的契约兼容改动，再合并模块。发生冲突由原Owner解决本模块，C决定共享边界。

## PR 必须写清楚

写任务、变更文件、契约版本、实际测试命令和结果、演示方式、是否有模型真实调用以及未完成项。至少另一名成员审查。不得仅写“代码已完成，请合并”。主分支先跑共同测试，再跑已实现的前后端检查；功能从Mock换真实API时必须做一次端到端联调。

提供 integration-snippets/ci.yml 供C在看过仓库现有CI后放入根.github/workflows。不要直接替换现有CI。CI需要新增前端构建和正式后端测试，不能把仅通过契约测试等同于产品验收。

## 契约变更

提出原字段、新字段、消费者影响、兼容策略、样例和测试。受影响者确认后由C改真源、生成类型、升级VERSION、更新冻结摘要，再一次合并。不能手改types.ts，不能只更新哈希消除失败，不允许在冻结日前一天加第二套API。

目前不能独立保证GitHub主分支保护已启用。拥有仓库管理权限的人按团队决定配置required checks和review；这需要真实管理权限，不是文档写一句就已经生效。
