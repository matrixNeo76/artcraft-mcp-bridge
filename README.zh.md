# ArtCraft MCP Bridge

[![checks](https://github.com/matrixNeo76/artcraft-mcp-bridge/actions/workflows/checks.yml/badge.svg)](https://github.com/matrixNeo76/artcraft-mcp-bridge/actions/workflows/checks.yml)

[English](README.md) · [Italiano](README.it.md) · [Español](README.es.md) · **中文**

本桥接器把 **Crafting Apps**（CADCraft、DeckCraft、DesignCraft、EffectCraft、FigCraft、FilmCraft、
GridCraft、LightCraft、PdfCraft、PhotoCraft、SoundCraft、VectorCraft、WordCraft）与 MCP 客户端连接起来：不再退化到
没有界面的 CLI，而是通过应用自身的**控制通道**驱动正在运行的应用，使工具直接作用于已打开的窗口。

## 问题

每个 Crafting App 都提供一个无界面（headless）的 MCP 服务器（`<app>-cli.exe mcp`）。但许多工具只有在
应用真正运行时才有意义：绘图、截取画布、移动光标。在 headless 模式下这些工具要么消失，要么失败，而客户端
无法知道原因。

## 工作方式

1. 应用以 `--control <端口>` 启动（PhotoCraft 还需要 `--control-token-file`）；
2. 注册在连接器中的 **shim** 在该端口上执行一次**握手**；
3. 如果对端确实讲这套协议**而且是正确的应用**（命令目录，阈值 0.9），就进入 **bridged** 模式并把请求转发给
   应用；否则进入 **headless** 模式，并在 stderr 上声明。使用 `--require-bridge` 时直接以退出码 3 结束，
   而不是回退。

PdfCraft 是第 3 点的例外：它使用*控制文件*，而且它的 MCP 服务器没有 bridge 标志（`mcp --connect` →
`unknown option`）。它的窗口同样可以被驱动，方式是**翻译**：[craft-bridge-ui.py](tools/craft-bridge-ui.py)
把应用声明的 15 个方法暴露为同样数量的 MCP 工具，每次调用执行一次
`pdfcraft-cli ui --control FILE <方法>`。

没有静默回退：所选模式始终会被声明，端口上是谁在应答也会被识别（应用**以及**正在运行的构建版本）。表格也是
如此：每个应用所需的挂接标志不是靠记忆——我们会去问 CLI 的 help，当它无法确认时，诊断会明说。

## 目录结构

```
tools/     工具（Python）：shim、窗口翻译器、ident、doctor、config、launch、verify、sweep、tests、探索类工具
install/   install-craft-mcp.ps1（生成式 MCP 的多客户端注册）
reports/   生成的产物：测试套件与 sweep 报告、工具清单、图片
docs/      采用 OKF v0.2 格式的文档（节点与关系）- 见 docs/index.md
```

## 快速开始

```bash
# 1. 安装 shim 的副本并重写连接器条目（会先备份）
python tools/craft-bridge-config.py --apply
# 2. 在 Freebuff 中：Connectors -> Refresh

# 3. 以控制通道启动应用（窗口会保持打开）
python tools/craft-bridge-launch.py

# 4. 验证：先给出整体结论，再用真实命令验证每一条条目
python tools/craft-bridge-doctor.py
python tools/craft-bridge-verify.py
```

恢复为 headless：`python tools/craft-bridge-config.py --restore`。

## 其他 MCP 客户端

Freebuff 不是唯一的客户端。一条命令就能把同一个桥接器写入你已有的其它客户端 —— Claude Desktop、Claude Code、Cursor、Windsurf、VS Code、Cline、LM Studio、Zed、Codex（ChatGPT 桌面版）以及 DeepSeek Harness（`dsh`）—— 每个都有各自的文件与格式，来自同一来源，不碰不属于我们的内容：

```bash
python tools/craft-bridge-connect.py --list     # 哪些客户端在这里，它们从哪里读取
python tools/craft-bridge-connect.py            # 试运行：会改动什么
python tools/craft-bridge-connect.py --apply    # 写入，并先备份
```

逐客户端的做法（包括两个非 JSON 的）见 [docs/operations/connect-a-client.md](docs/operations/connect-a-client.md)。

想一眼看清整体状态 —— 结论、条目、客户端、基线、feed、日志 —— 看一个 JSON 和读取它的页面：

```bash
python tools/craft-bridge-report.py             # reports/bridge-status.json + .html
python tools/craft-bridge-report.py --serve     # 另起本地服务器并打开页面（Ctrl+C 停止）
```

## 已验证状态（2026 年 10 月 13 日）

| 验证项 | 结果 |
|---|---|
| 能在窗口上成功调用并可被驱动的应用 | 13/13（12 个通过 shim 进入 bridged——含 `figcraft`——，PdfCraft 通过翻译） |
| 用真实命令执行配置条目 | 14/14 |
| 故障测试套件（29 个用例，注入故障） | 在 PdfCraft 窗口关闭时 28 个执行 + 1 个跳过（唯一的实时用例会说明原因），`--static` 下 24+1，连续两轮结果一致 |
| 已注册桥接器的客户端 | 已知 14 个，本机存在 7 个，全部为 **13/13**（此前：`agents` 13，`claude-desktop`、`antigravity` 与 `claude-code` 为 **12** 条 headless 条目，`windsurf` 为 **0**，`cursor` 与 VS Code 编辑器尚未配置） |
| 已安装版本与启动器发布的版本对比 | 13 个中对比了 12 个（10 月 13 日的 feed）：feed 尚未列出 `figcraft`，因此对它没有可比对象，诊断会如实说明 |
| 已安装 CLI 与已发布 CLI 的字节对比 | 12 个中试了 1 个：SoundCraft 完全一致（`sha256 915ee3abb121…`）；其余应用磁盘上没有压缩包 |
| 应用与 CLI 的路径 | 12/12 来自 `App Paths` 注册表（表格只作确认，不作决定） |
| PdfCraft 窗口的方法 | 15/15 与应用声明的完全一致；192 个命令、107 个控件、窗口截图 |
| 表格声明的挂接标志 | 13/13 得到 CLI help 的确认（11 个 `--connect`/`--bridge` 和 1 个 `--attach` 挂接，PdfCraft 无标志且使用 `--control`） |
| 各服务器的工具清单 | 14/14 服务器，636 个工具（`pdfcraft`：窗口的 15 个方法；`figcraft`：18） |
| 整体诊断 | `tutto in ordine` |

## 文档

文档位于 [docs/index.md](docs/index.md)：它是一个 **OKF v0.2** 包，每个概念一个节点，节点之间有显式关系
（架构、工具、运维、已发现的缺陷）。包含全部实测数据的长篇完整说明见
[docs/reference/craft-bridge.md](docs/reference/craft-bridge.md)（英文）。

```bash
uvx okfgen validate docs --strict                      # 符合规范：35 个概念，0 个错误
uvx okfgen visualize docs -o reports/okf-graph.html    # 生成该包的可交互图
```

生成的图位于 [reports/okf-graph.html](reports/okf-graph.html)：35 个节点，182 条关系。

## 已安装的版本 vs 已发布的版本

可执行文件的版本只说明它自称是什么，并不说明它就是发行方分发的那一版。ArtCraft 启动器在磁盘上保存了它用于更新
应用的清单（仓库、最新发行版、带 `sha256` 的软件包）：[craft-bridge-feed.py](tools/craft-bridge-feed.py)
把该清单与已安装的构建放在一起比较，指出两者不一致的地方。使用 `--bytes` 时它还会提出唯一一个版本号无法回答的
问题：把已安装的可执行文件与已发布包**内部**的那一个做对比，在内存中读取、不解压任何东西——`--download <slug>`
会下载该软件包（使用前先校验 feed 的摘要，一次只下一个应用，且只从 feed 的主机下载）。在 `doctor` 中，版本落后
只算一条 `nota`，不是 `FIX`：桥接器在旧版本上同样可用。详情见
[docs/tools/craft-bridge-feed.md](docs/tools/craft-bridge-feed.md)。

## 自动检查

每次推送到 `main`（以及每个 pull request）都会运行 [checks.yml](.github/workflows/checks.yml)：工具语法、
接口、应用表格与文档化端口的一致性、安装器的确定性、OKF 包的合规性，以及带 `--ci` 的测试套件——在没有应用的
runner 上，它会**说明原因**后跳过环境相关用例，而真正的故障仍然是 FAIL。完整套件运行在装有这些应用的
self-hosted runner 上（仓库变量 `CRAFTBRIDGE_SELF_HOSTED=1`）：它在推送到 `main` 和手动触发时运行，绝不
在 pull request 上运行——仓库是公开的，陌生人的代码不会在装有这些应用的机器上执行。某个用例相对已保存的基线变差时，
套件以 3 退出，因此回归会拦住这次推送，而不是留在报告里。详情见
[docs/operations/ci.md](docs/operations/ci.md)。

## 已声明的限制

- **仅限 Windows**：测试套件和启动器使用 `taskkill` 和 `DETACHED_PROCESS`。
- 窗口截图要求窗口可见；处于后台的应用可能返回超时，看起来像桥接器故障，其实不是。
- 可执行文件的版本不等于它的内容：版本号相同且启动日志中没有修订号的两个构建无法区分（没有二进制哈希校验）。
- 尚未观察过智能体在 Freebuff 中通过界面实际使用这些服务器：所有验证都是通过协议直接与二进制文件对话完成的。

## 许可证

**MIT** — 完整文本见 [LICENSE](LICENSE)：可自由使用、修改和再分发，包括用于闭源产品，只要版权声明和许可证
随软件一同保留。软件按“原样”提供，不附带任何担保。
