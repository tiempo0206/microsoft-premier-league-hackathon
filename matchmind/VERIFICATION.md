# 启动包验证记录

交付包2.1，验证日期：2026年10月21日。验证的是交付基线，不是参赛产品验收。

- 19项离线unittest通过：Schema、字段和数值拒绝、越界事件、错误match、旧run、不同回放会话、未来窗口、规则回退标签、Mock HTTP与SSE。
- contract.schema.json生成的TypeScript类型经过本地TypeScript 7.0.2 --noEmit检查。
- 前端顶层依赖安装并生成pnpm-lock.yaml；Node验证环境为24.19.0，最低支持目标22.13尚未单独实测。
- Microsoft agent-framework-core 1.22.0 / agent-framework-openai 1.17.0安装、导入及OpenAIChatCompletionClient离线构造成功。构造使用无效示例域和占位密钥，网络请求为0。
- 模型探针默认模式已验证不会发起模型请求。真实千问、DeepSeek、Foundry调用均未执行，账号配额与网络未验证。
- 固定数据是原创五分钟合成片段，30条事件，无真实赛事素材。
- 未创建完整React产品、正式FastAPI后端、真实多Agent、公网部署或赛事提交；这些按角色卡继续实现。
- 未改动团队GitHub仓库，未创建远程分支、PR、推送、合并或开通付费资源。
- Kimi路线未探测到可用CLI/桌面会话；方案与最终审查由Codex完成。DSPy本轮跳过，以闭环交付和基础评测为先。

本包可复查命令：

```text
python -m pip install -r requirements-contracts.txt
python tools/check_frozen.py
python -m unittest discover -s tests -p "test_*.py"
python tools/probe_model.py
```

完整前端build、真实后端测试、真实模型兼容和公网可用性必须由角色开发完成后再验收，不能用本记录替代。
- 2.1改为Markdown总方案与开发卡，不包含PDF/Word。核心协议和样例与2.0基线一致。
- 国内镜像的8组包元数据请求返回200且包含目标版本；未声称已通过国内镜像安装所有依赖。
- 本次新增frontend/.npmrc与网络重试配置，不更改API、类型、数据或模型代码。
- 2.1已核对pnpm读取的registry为npmmirror、strictSsl为true；Markdown相对链接与打包摘要已检查。
