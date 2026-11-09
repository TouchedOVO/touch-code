# 测试与验收报告

运行环境：Windows 11 x64，Python 3.14.3，PySide6 6.12.0，PyInstaller 6.22.3，
Node.js 26.13.0（仅用于验证生成项目）。DeepSeek API Key：**未提供**。

## 1. 执行证据

| 命令 | 结果 |
|---|---|
| `python -m pytest tests -q` | **80 passed in 6.83s** |
| `node --test tests/unit services/question-service/tests services/game-service/tests services/user-service/tests` | **15 passed / 0 failed**（约 0.29 s） |
| `node --test tests/e2e` | **1 passed / 0 failed**（约 0.18 s） |
| `SpaceCodeAgent.exe --smoke-test`（one-file） | 退出码 **0**，冷启动 **3.1 s** |
| `SpaceCodeAgent.exe --mock-run … --allow-tests`（one-file） | 退出码 **0**，**14.2 s**，状态 `completed`，覆盖 **100%** |
| 生成项目内 `node --test`（由 Agent 实际执行） | **16 passed / 0 failed**，0.84 s，manifest `exit_code=0` |

one-file 构建产物（`dist/` 不入库）：`dist/SpaceCodeAgent.exe`，**61,014,405 字节（58.2 MiB）**。

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
| T11 | 测试失败/完成被拒 | ✅ PASS | 完成拒绝→补充 README→成功；连续 3 次拒绝→`partial` 且如实列出缺失；`test_agent_loop.py` |
| T12 | 无 Node/npm 机器 | ✅ PASS | `js_syntax=skipped`、`run_tests=not_available`，报告写 `not run`；`test_tool_registry.py`；EXE 在仅含 System32 的 PATH 下仍完成生成并如实标注 |
| T13 | Mock 模型端到端 | ✅ PASS | 完整文件树、README、依赖、测试、报告；80 项测试中的 `test_mock_e2e.py` |
| T14 | 真实 DeepSeek 端到端 | ⏸ **NOT RUN** | 无 API Key。代码路径已实现，仅待凭据；不得声称已通过 |
| T15 | 干净 Windows 双击 EXE | ✅ 本机 PASS / ⚠ 未做全新 VM | one-file `--smoke-test`、GUI 启动（窗口标题可见）、Mock 全流程、最小 PATH 无 Node 生成均通过；未在未安装 Python 的全新虚拟机复测 |

## 3. 验收门槛核对（方案 §12）

1. **GUI 功能**：Key 输入/显示、模型/思考强度、双文档、输出目录、检查、生成、停止、打开目录、
   日志/任务/文件/验证/报告、Token/费用均可操作；模型名与端点正确。
   - EXE 双击启动已验证进程退出码与窗口构建；截图见 `docs/screenshots/gui-*.png`。
2. **真实 DeepSeek 生成**：代码已实现，**未执行**（缺 Key）。Mock 全链路证明工具/编排/验收/报告可用。
3. **报告追溯**：`GENERATION_REPORT.md` + `traceability_matrix.csv` 展示 7/7 需求的文件与测试映射；
   未实现项与偏离写入 `ASSUMPTIONS.md`（ASM-06）。
4. **测试证据**：生成项目 16 项 Node 测试由 Agent 实际执行并通过，manifest 记录 `exit_code=0`；
   未运行场景明确 `not run`，不以“文件存在”代替通过。
5. **安全与取消**：路径攻击拒绝、原子写入、默认不覆盖、密钥脱敏、取消后保留文件、报告不写入 Key。

## 4. 已知未覆盖项

- **真实 DeepSeek API 端到端（T14）**：需要用户提供 `DEEPSEEK_API_KEY`。Mock 模式不消耗额度，
  但不能替代真实模型验收。
- **全新 Windows 虚拟机（T15 严格版）**：本机已用 one-file EXE 验证，未做干净 VM 快照。
- **GUI 交互的自动化点击**：已用无头 Qt 驱动完整一次生成并截图；未覆盖真人拖拽/缩放/多显示器。
- **可取消的 HTTP 请求**：取消在模型调用/工具调用之间生效；单次 HTTP 请求无法中断，
  窗口关闭会等待安全检查点（最长 10 s，超时拒绝关闭）。
- **P1 项**：会话恢复 UI、差异预览、流式推理展示未实现；JSONL 历史已持久化，可据此扩展。
- **生成项目运行环境**：Node.js 测试需 Node ≥20；PostgreSQL/Redis 等未部署，已在假设中声明。
