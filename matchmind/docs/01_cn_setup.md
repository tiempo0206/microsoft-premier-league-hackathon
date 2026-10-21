# 国内开发环境与网络约束

交付包2.1，协议仍为2.0.0。国内开发优先使用随包数据、项目级依赖镜像和国内模型API；生产可部署在国际站点。开发者不需要先申请Azure、Foundry、GPU、足球数据账号或服务器。

## 统一环境

Python 3.12，Node >=22.13，pnpm 11.25.0。先检查已经安装的版本，能用就复用；不要为了本项目改坏其他项目的全局环境。Python使用各自.venv；Node依赖放frontend/node_modules，不提交环境目录。缺少工具时优先官方发行版或可核验的镜像，保留HTTPS与校验，不从聊天附件安装未知SDK。

Node包注册表已在frontend/.npmrc指定为https://registry.npmmirror.com/，只影响本项目。Python使用下面命令临时指定清华PyPI镜像，不修改全局pip配置。pnpm的网络超时与重试写在项目pnpm-workspace.yaml；不要把所有新配置都写进.npmrc。

## Windows PowerShell

以下命令在matchmind目录执行；直接调用虚拟环境解释器，不需要修改PowerShell执行策略或激活脚本。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --index-url https://pypi.tuna.tsinghua.edu.cn/simple -r requirements-contracts.txt
.\.venv\Scripts\python.exe tools/check_frozen.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

A的终端一保持在matchmind，运行Mock：

```powershell
.\.venv\Scripts\python.exe -m tools.mock_api
```

A的终端二进入frontend；已装固定版本pnpm时不要重复全局安装：

```powershell
# 仅在没有pnpm时由本人选择执行：
npm install --global pnpm@11.25.0 --registry=https://registry.npmmirror.com/
cd frontend
pnpm install --frozen-lockfile
pnpm run typecheck
# A完成页面入口后再运行：pnpm run dev
```

B在matchmind安装后端依赖，C只安装AI依赖；都先完成共同契约依赖安装：

```powershell
# B
.\.venv\Scripts\python.exe -m pip install --index-url https://pypi.tuna.tsinghua.edu.cn/simple -r backend/requirements.txt
# C
.\.venv\Scripts\python.exe -m pip install --index-url https://pypi.tuna.tsinghua.edu.cn/simple -r ai/requirements.txt
```

上面角色命令可以分开交给各自AI，不要求三人安装全部依赖。不要把Windows路径原样复制到macOS。

## macOS或Linux

在matchmind目录执行，使用机器实际已有的Python3.12入口：

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --index-url https://pypi.tuna.tsinghua.edu.cn/simple -r requirements-contracts.txt
.venv/bin/python tools/check_frozen.py
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
# A终端一
.venv/bin/python -m tools.mock_api
# A另开终端，进入matchmind/frontend
pnpm install --frozen-lockfile
pnpm run typecheck
# B安装 -r backend/requirements.txt；C安装 -r ai/requirements.txt，继续使用同一镜像参数。
```

## 镜像缺包或网络故障

2026年10月21日本机已查到镜像上的React19.3.1、Vite8.3.5、TypeScript7.0.2、pnpm11.25.0，以及jsonschema4.26.0、FastAPI0.157.0、agent-framework-core1.22.0和agent-framework-openai1.17.0。记录见docs/mirror_probe.json。这里只验证了包元数据和版本可查询，不等于其他成员网络可用或所有传递依赖已经下载。

遇到404先保持固定版本，单次切回官方源；不要擅自降级、删锁文件或改共享类型。Python可把--index-url换成https://pypi.org/simple。前端可在同一项目执行：

```text
pnpm install --frozen-lockfile --registry=https://registry.npmjs.org/
```

若已有node_modules曾用不同store目录、不同pnpm配置或不同主版本安装，先说明这是可再生成的本项目依赖目录，让AI核对实际路径，再按包管理器提示重新安装。不要删除整个仓库，不要在非交互终端反复等待确认。依赖目录不可从Windows复制给macOS/Linux。

GitHub偶发不可达时，先使用本开发包，不要等待克隆大型第三方仓库。C可以用git bundle给已授权队友提供共同Git基线，避免每个人各自git init形成无关历史；原仓库已有私有历史时，只在已授权团队内传递。

```text
# C在实际仓库执行，main需替换为仓库真实共同分支
git bundle create matchmind-baseline.bundle main
# 队友先验证，再从同一历史克隆
git bundle verify matchmind-baseline.bundle
git clone -b main matchmind-baseline.bundle matchmind-team
# 确认之后再设置团队真实GitHub远程地址
```

bundle包含指定分支的提交历史，不只是当前文件；GitHub恢复后再按正常PR流程同步。不要把私有仓库同步到未授权的第三方镜像，也不要把未审查密钥带进基线。

## 前端必须遵守的国内友好约束

- 页面样式、字体和图标随构建打包；默认使用系统字体和本地SVG。不要把Google Fonts、外链脚本CDN、远程占位图或在线图标作为运行前提。
- 合成比赛数据直接随仓库交付，运行时不访问真实赛事站点、Hugging Face或GitHub Raw来取数据。
- 浏览器仅调用同源/api；模型请求由后端发起。国际网页也不能把国内模型Key放进前端。
- 中国开发机用千问/DeepSeek官方API和已固定的软件包；不要求下载模型权重、安装GPU驱动或拉完整Docker环境。
- 本地回放、Mock和契约测试必须在无模型账号时可运行；CI默认不做真实付费请求。

资料入口：清华镜像 https://mirrors.tuna.tsinghua.edu.cn/help/pypi/ ，npmmirror https://npmmirror.com/ ，pnpm配置 https://pnpm.io/settings 。
