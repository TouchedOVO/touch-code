# 测试与验收报告

运行环境：Windows 11 x64，Python 3.14.3，PySide6 6.12.0，PyInstaller 6.22.3，
Node.js **22.23.4 / 26.13.0**（生成项目测试）。DeepSeek API Key：由用户在本机环境变量中提供，
**未写入仓库**。

## 1. 执行证据

| 命令 | 结果 |
|---|---|
| `python -m pytest tests -q` | **84 passed**（含测试失败→修复→重测、UI/持久化契约用例） |
| `node --test tests/unit/http.test.js tests/unit/schema.test.js tests/unit/persistence.test.js services/question-service/tests/questions.test.js services/game-service/tests/game.test.js services/user-service/tests/auth.test.js` | **18 passed / 0 failed**（Node 22） |
| `node --test tests/e2e/flow.test.js` | **1 passed / 0 failed**（Node 22） |
| `SpaceCodeAgent.exe --smoke-test`（one-file） | 退出码 **0**，冷启动 **3.1 s** |
| `SpaceCodeAgent.exe --mock-run … --allow-tests`（one-file） | 退出码 **0**，**14.2 s**，状态 `completed`，映射/验证均 **100%** |
| 生成项目内 `node --test`（由 Agent 实际执行） | **19 passed / 0 failed**，manifest `exit_code=0` |
| **真实 `deepseek-v4-pro` 运行** | 退出码 **0**，Agent `completed`，**27/27** 测试通过，2,616,750 tokens / **$0.148089**；浏览器 UI + 持久化，浏览器 E2E 通过 |

one-file 构建产物（`dist/` 不入库）：`dist/SpaceCodeAgent.exe`，**61,014,405 字节（58.2 MiB）**。

### 1.1 GitHub Actions

最终 `main` 运行：[Windows build #6](https://github.com/TouchedOVO/touch-code/actions/runs/42640206235) — **conclusion: success**

| 作业 | 结果 | 证据 |
|---|---|---|
| `Agent test suite (Windows)` | ✅ success | Python 3.14 + PySide6，**84 项 pytest** 通过；Node 22 已配置 |
| `Generated sample tests (Node)` | ✅ success | Node 22：**18 项单元/集成 + 1 项 E2E** 全绿 |
| `Build one-file EXE` | ✅ success | PyInstaller 构建 + `--smoke-test` 退出码 0 |
| Artifact `SpaceCodeAgent-windows-x64` | ✅ 可下载 | 63,669,245 B；SHA-256 `0178a9f688b36944012d9b86eb271d3c414e1d548c251c74b089ea6cbb39a1b3` |

代码修复提交 `9d484d6` 的运行 [#2](https://github.com/TouchedOVO/touch-code/actions/runs/42619336153) 与
T14 证据提交 `9bfa376` 的运行 [#5](https://github.com/TouchedOVO/touch-code/actions/runs/42626131295)
同样均为 success。

### 1.2 真实 DeepSeek 运行（T14）

证据目录：[`docs/evidence/t14-real/`](evidence/t14-real/README.md)

| 指标 | 值 |
|---|---|
| 请求模型 / 返回模型 | `deepseek-v4-pro` / `deepseek-v4-pro` |
| Agent 步数 / 工具调用 / 请求数 | 75 / 114 / 75 |
| 输入 / 输出 / 缓存 / 推理 tokens | 2,525,691 / 91,059 / 2,370,432 / 51,670 |
| 总 tokens / 估算费用 | 2,616,750 / **$0.148089** |
| Agent 耗时 / 报告总耗时 | 1,375.4 s / 1,720.1 s |
| 独立重跑生成项目测试 | **27 / 27 passed**（Node 22，exit 0） |
| 静态检查 | structure / json / python / js / links / traceability 全 pass |
| 交付契约 | deliverables / json / traceability / **web_ui** / **persistence** 全 pass |
| 报告映射 / 验证 | 7/7 / 7/7（含逐需求 `Covers:` 测试证据） |
| 浏览器 E2E | **PASS** — Edge headless：菜单 → 帮助 → 10 题 → 结果页（10 / 100） |

**功能结论：通过。** 真实模型生成了浏览器 UI（开场/菜单/答题/结果/帮助）、可重启恢复的 JSON
持久化仓储（含重启测试）、REST API 和 27 项测试。首次实现因缺少 Express 导致测试失败，控制器
反馈后模型完成了 **1 轮自动修复**，改为零依赖 `node:http` 并通过全部测试与浏览器 E2E。计划在
第一次因引用 `ASM-04/ASM-05` 被拒绝，第二次生成成功（9 任务 / 31 文件），未回退到确定性计划。
重大偏离（模块化单体、可选 PostgreSQL/重型中间件）已在生成项目的 ASSUMPTIONS 中声明。

### 1.3 T15 干净 Windows runner

运行：[T15 clean Windows runner #1](https://github.com/TouchedOVO/touch-code/actions/runs/42643238074) — **success**  
证据目录：[`docs/evidence/t15-clean-run/`](evidence/t15-clean-run/README.md)

| 步骤 | 结果 |
|---|---|
| 构建 one-file EXE | success |
| 删除 Python 工具缓存 / Program Files Python* / 项目 `.venv` / 启动器 | success |
| 验证 `python`、`pip` 均不可用，无残留 Python 目录 | success |
| EXE `--smoke-test`（headless Qt） | exit 0 |
| GUI 进程启动后存活 | 6 s 后仍存活 |
| 无 Python 环境下完整 `--mock-run --allow-tests` | `completed`，映射/验证 100%，生成测试通过 |
| EXE SHA-256 | `A5E23A34D25197017056002930457FC7E27707A9A846C0DE3D82E0C3DB92C561` |

> 这是 GitHub 托管的 fresh Windows runner，Python/Qt 在运行 EXE 前已移除；不是人工桌面双击，
> 但已独立证明 EXE 不依赖 Python/Qt 安装。Node 22 保留用于生成项目测试，符合“目标机无需 Python”的要求。

## 2. 验收用例矩阵（对应方案 §12）

| 编号 | 测试内容 | 结果 | 证据 |
|---|---|---|---|
| T01 | 两份正确 Markdown | ✅ PASS | 13/13 PlantUML、11 类视图、7 需求；`test_parser.py` |
| T02 | 文件不存在/空文件/乱码 | ✅ PASS | `not_found` / `empty` / `encoding` / `too_large` 四类错误；GUI 基本校验测试 |
| T03 | 需求与视图冲突 | ✅ PASS | 8 个冲突：11 vs 13、ASR-2 无定义、测试矩阵为空、语法偏差、重型组件；`test_parser.py` |
| T04 | 合法工具调用落盘 | ✅ PASS | `test_agent_loop.py` 写入多文件并回传 `call_id` |
| T05 | 工具参数缺失/非法 | ✅ PASS | 返回 `invalid_arguments`，循环继续；`test_tool_registry.py` |
| T06 | `../`、绝对路径、UNC、ADS、设备名、junction 越界 | ✅ PASS | 11 类全部拒绝；`test_security.py`（junction 用例真实创建联接点） |
| T07 | 覆盖同名文件 | ✅ PASS | 默认 `exists` 拒绝；显式 `overwrite=true` 才允许；输入文档受保护 |
| T08 | 429 / 5xx / 断网 | ✅ PASS | 429 重试后成功；503 重试耗尽；连接错误重试；`test_provider.py` |
| T09 | API Key 失效 | ✅ PASS | 401 不重试，错误消息经脱敏，不含 Key；`test_provider.py` |
| T10 | 用户点击停止 | ✅ PASS | 取消 token 在首步前生效，未写文件，仍生成 cancelled 报告；`test_mock_e2e.py` |
| T11 | 测试失败/完成被拒 | ✅ PASS | 完成拒绝→补充 README→成功；测试失败→回传 stderr→修复→重测通过；连续 3 次拒绝→`partial`；`test_agent_loop.py` / `test_mock_e2e.py` |
| T12 | 无 Node/npm 机器 | ✅ PASS | `js_syntax=skipped`、`run_tests=not_available`，报告写 `not run`；生成完成但状态为 `partial`，不误报成功；`test_tool_registry.py` / `test_mock_e2e.py`；EXE 在仅含 System32 的 PATH 下同样如此 |
| T13 | Mock 模型端到端 | ✅ PASS | 完整文件树、README、依赖、测试、报告；84 项测试中的 `test_mock_e2e.py` |
| T14 | 真实 DeepSeek 端到端 | ✅ **PASS** | 真实 `deepseek-v4-pro`（75 步 / 114 工具 / 2,616,750 tokens / $0.1481）生成浏览器 UI + 持久化；27/27 测试、7/7 验证、Edge 浏览器 E2E 均通过；含 1 轮自动修复。证据：`docs/evidence/t14-real/` |
| T15 | 干净 Windows 双击 EXE | ✅ **PASS（自动化干净 runner）** / ⚠ 未手动双击 | GitHub fresh Windows runner：构建后删除 Python/Qt/venv 与启动器，`Get-Command python` 失败；EXE smoke、GUI 启动、Mock 全流程、生成测试均通过（EXE SHA-256 `A5E23A34…C561`）。证据：`docs/evidence/t15-clean-run/`；手动桌面 VM 双击未做 |

## 3. 验收门槛核对（方案 §12）

1. **GUI 功能**：Key 输入/显示、模型/思考强度、双文档、输出目录、检查、生成、停止、打开目录、
   日志/任务/文件/验证/报告、Token/费用均可操作；模型名与端点正确。
   - EXE 双击启动已验证进程退出码与窗口构建；截图见 `docs/screenshots/gui-*.png`。
2. **真实 DeepSeek 生成**：已用真实 `deepseek-v4-pro` 完成浏览器 UI + 持久化项目（75 步、
   2,616,750 tokens、27/27 测试通过），并通过 Edge 浏览器 E2E；T14 = **PASS**。
3. **报告追溯**：`GENERATION_REPORT.md` + `traceability_matrix.csv` 展示 7/7 需求的文件与逐需求测试映射；
   未实现项与偏离写入 `ASSUMPTIONS.md`（ASM-06）。
4. **测试证据**：Mock 生成项目 19 项 Node 测试、真实运行生成项目 27 项 Node 测试均由 Agent 实际执行并通过，
   manifest 记录 `exit_code=0`；未运行场景明确 `not run`，不以“文件存在”代替通过。
5. **安全与取消**：路径攻击拒绝、原子写入、默认不覆盖、密钥脱敏、取消后保留文件、报告不写入 Key。

## 4. 针对代码审查问题的修复

| 审查问题 | 修复 | 本地验证 |
|---|---|---|
| PEP 639 许可证分类器冲突 | 删除 `License :: OSI Approved :: MIT License`，保留 `license = "MIT"` 与 `license-files` | `pip install --dry-run -e .` 元数据构建成功（setuptools 84.2.1） |
| Node 22 将目录当模块入口 | workflow、`package.json`、README、CONTRIBUTING、测试报告全部改为显式测试文件 | Node **22.23.4** 下 18 + 1 项测试全绿 |
| 测试失败未进入修复闭环 | Controller 在测试失败后把命令、退出码、精简 stderr 回传模型，修复后重新静态检查并重测，最多 3 轮 | 新增 `test_test_failure_triggers_model_repair_and_retest`；84 项测试全绿；真实 T14 第 1 轮修复 Express 缺失后 27/27 通过 |
| 需求覆盖率可能高估 | 拆分 `mapped` / `implemented` / `verified` / `unverified` / `failed`；只有源码 + 测试且测试真实通过才记 `verified`；测试未运行时状态降为 `partial` | 报告、CSV、manifest 均输出两套覆盖率；测试断言 7/7 映射、7/7 验证，未运行场景为 partial |
| 最终状态可能不一致 | 单一 `final_status` 同时写入 UI/CLI、`GENERATION_REPORT.md`、`run_manifest.json`；manifest 另存 `agent_status` | 测试失败用例断言 `run.status=partial` 且 `agent_status=completed` |
| 指定模型未锁定 | GUI 模型只读；`AppConfig.validate()` 强制 `deepseek-v4-pro`；CLI 需显式 `--allow-model-override`；`test_connection` 不再把“模型未确认”报成成功 | `test_config_validation` 新增锁定断言 |
| README 安装步骤不可靠 | 改为 `python -m pip install -e ".[dev]"` 后再运行模块 | 元数据 dry-run + 源码运行 `--version` 通过 |
| CI 无 EXE 产物 / 作业跳过 | `build-exe` 依赖 Python 与 Node 两个测试作业；仍上传 one-file EXE artifact | GitHub Actions [run #6](https://github.com/TouchedOVO/touch-code/actions/runs/42640206235) 三作业全绿，artifact `SpaceCodeAgent-windows-x64`（63,669,245 B）可下载 |
| 真实模型生成缺少独立证据 | 使用用户提供的 Key 执行真实 `deepseek-v4-pro`，保存脱敏日志、manifest、测试输出、生成源码与浏览器 E2E | 真实运行 `completed`，75 步，27/27 测试通过，UI/持久化契约 pass，Edge 浏览器 E2E pass |

## 5. 已知未覆盖项

- **T15 手动桌面 VM**：已在 fresh GitHub Windows runner 上删除 Python/Qt 后通过 smoke、GUI 启动与
  Mock 全流程；尚未做人工双击的桌面 VM 截图。
- **微服务/云原生拓扑**：T14 生成的是模块化单体 + 文件持久化，已在 ASSUMPTIONS 中记录为重大偏离；
  若要求独立微服务 + PostgreSQL/K8s 严格一致，仍需另一轮实现。
- **T14 功能复核**：27/27 测试、UI/持久化契约与浏览器 E2E 已通过；人工视觉/多浏览器兼容性未覆盖。
- **GUI 交互的自动化点击**：已用无头 Qt 驱动完整一次生成并截图；未覆盖真人拖拽/缩放/多显示器。
- **可取消的 HTTP 请求**：取消在模型调用/工具调用之间生效；单次 HTTP 请求无法中断，
  窗口关闭会等待安全检查点（最长 10 s，超时拒绝关闭）。
- **P1 项**：会话恢复 UI、差异预览、流式推理展示未实现；JSONL 历史已持久化，可据此扩展。
- **生成项目运行环境**：Node.js 测试需 Node ≥20；PostgreSQL/Redis 等未部署，已在假设中声明。
