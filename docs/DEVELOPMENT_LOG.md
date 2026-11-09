# 分阶段落地记录与技术指标

> 本文件记录 实施计划中 M1–M7 的实际落地结果。
> 所有指标来自本机 Windows 11 x64 / Python 3.14.3 / Node 26.13.0 的真实运行，而非估算。

## 0. 环境基线

| 项 | 版本 |
|---|---|
| OS | Windows 11 (10.0.26200) x64 |
| Python | 3.14.3 |
| PySide6 | 6.12.0 |
| openai SDK | 3.46.0（`httpx2` 传输） |
| Pydantic | 2.14.3 |
| PyInstaller | 6.22.3 |
| Node.js（仅用于验证生成项目） | 26.13.0 |
| DeepSeek 端点 / 模型 | `https://api.deepseek.com` / `deepseek-v4-pro` |

## 1. 阶段总览

| 阶段 | 状态 | 主要产物 | 验收节点 | 关键指标 |
|---|---|---|---|---|
| M1 环境与接口 | ✅ | 项目骨架、PySide6 主窗、DeepSeek Provider、密钥脱敏 | Key 测试接口可用、Mock/协议调用通过 | 10 个模块 / 968 行；11 项测试（含 9 项 Provider 协议/重试） |
| M2 文档归一化 | ✅ | Parser、Pydantic IR、冲突/假设、GUI 预览 | 13 段 UML、FR/NFR/ASR 可见 | 2 文档 516 行；13/13 PlantUML；11 类视图；7 需求；8 冲突；8 假设；累计 28 测试 |
| M3 最小 Agent Loop | ✅ | Orchestrator、8 个工具、工作区策略、JSONL 审计 | 真实创建/读取/修改多文件 | 路径攻击 11 类全部拒绝；call_id 一一配对；累计 68 测试 |
| M4 规划与生成 | ✅ | Planner、Controller、内置 Space Fractions 样例 | 完整工程文件结构 + README/依赖/测试 | 样例 34 文件 / 2632 行；Mock 36 步 / 36 工具调用；文件映射 100%，测试验证 100%（有 Node 时）；19 项 Node 测试 |
| M5 校验与修复 | ✅ | 静态校验、测试运行器、验收器、修复回路 | 人为失败可修复或如实报告 | 6 类静态检查 + Web UI/持久化契约；node/pytest 白名单；3 轮修复上限；测试失败→反馈→重测 |
| M6 GUI 与发布 | ✅ | Worker/审批桥、进度/日志/文件/报告、EXE | 双击 EXE 完成生成 | one-file 61.0 MB；冷启动 3.1 s；EXE 全流程 14.2 s；GitHub Actions 构建与 smoke 通过 |
| M7 验收与收尾 | ✅（手动 VM 双击待补） | 测试报告、用户手册、样例输出、风险清单 | T01–T15 可复现 | 84 项 pytest 全绿；CI 全绿、EXE artifact 已上传；T14 真实模型生成 UI + 持久化，27/27 测试 + 浏览器 E2E；T15 在删除 Python/Qt 的 fresh runner 通过 |

## 2. 各阶段详情

### M1 环境与接口
- 建立 `space-code-agent` 包结构、配置中心（步数/费用/文件大小/重试上限）、事件模型。
- 实现 `DeepSeekProvider`：官方 Responses API、`reasoning.effort`、原生 `function_call`、
  429/5xx/网络退避、401/403 立即失败、400 记录脱敏摘要、Token/费用统计。
- `SecretRedactor`：注册密钥 + `sk-*`/Bearer/api_key 模式双重脱敏；GUI 掩码。
- GUI 初版：Key、模型、思考强度、双文档、输出目录、检查/生成/停止/打开、日志、进度。
- 修复 PySide6 生命周期问题（central widget 未挂载导致控件被 Qt 删除）与 offscreen 字体。

**指标**：10 个 Python 模块、968 行；11 项测试通过；Provider 9 项协议测试覆盖
文本/工具调用解析、429 重试、5xx 耗尽、401 不重试、请求体 schema。

### M2 文档归一化
- Markdown 解析：标题层级、39 章节、4 表格、10 代码块；UTF-8/BOM/大小/空文件/编码校验。
- PlantUML：真实解析 **13** 个块（文档自称 11），识别 11 类视图；提取 actor/participant/
  usecase/class/object/artifact/node/package/state/action/relation/message/note。
- 语义容错：`ObjectDiagram` 的 `participant`、协作图的 `->>` 记法均记录为低危冲突并继续。
- 需求归一化：3 条显式 + 3 条用例图推导 + ASR-2 推断；组件 4 个；冲突 8 个；假设 8 条。
- 识别文档问题：追溯矩阵仅 3 行、测试矩阵为空、ASR-2 无定义、重型中间件无业务约束。

**指标**：输入 315 + 201 行；13/13 视图；11 类；7 需求；4 组件；8 冲突；8 假设；累计 28 测试。

### M3 最小 Agent Loop
- 工具 8 个：`list_files`、`read_file`、`write_file`、`replace_in_file`、`search_in_files`、
  `inspect_project`、`run_tests`、`finish_task`；JSON Schema 参数校验与结构化错误。
- 工作区策略：拒绝绝对路径/盘符/UNC/`\\?\`/`..`/ADS/设备名/点结尾；真实路径包含性检查；
  junction 逃逸测试通过；输入文档与 `.env`/私钥类文件禁写；临时文件 + `os.replace()` 原子落盘。
- Orchestrator：有界步数、Token/费用/时长预算、取消、call_id 配对、上下文压缩、
  完成声明必须通过本地验收、连续拒绝转 partial。
- 审计：`.agent_state/<session>/events.jsonl`、`tools.jsonl`、`history.jsonl`。

**指标**：11 类非法路径全部拒绝；8 个工具 schema；累计 68 项 pytest 通过；
Agent Loop 覆盖成功/参数错误/取消/步数预算/完成拒绝→修复/连续拒绝→partial。

### M4 规划与生成
- Planner：模型输出严格 `ProjectPlan`（任务/文件树/需求映射/验证/偏离），校验失败重试一次，
  再失败回退确定性计划；计划必须包含 README、依赖、测试、ASSUMPTIONS。
- Controller：`VALIDATING_INPUT → NORMALIZING → PLANNING → IMPLEMENTING → VERIFYING →
  REPORTING`；非空输出目录自动创建唯一子目录；API Key 不落盘。
- 内置 Space Fractions：3 个零依赖 Node 服务 + 学生端 + 教师后台 + SQL + Compose + 16 项测试。
- 需求映射：计划声明 + 源码 `Covers:` 标记 + 文档产物三重映射。

**指标**：样例 33 文件 / 2558 行；Mock 35 步 / 35 工具调用 / 4200 tokens / $0.001274；
需求覆盖 7/7 = 100%；Node 单元/集成 15 项 + E2E 1 项全绿；总耗时（源码运行）约 2.6 s。

### M5 校验与修复
- 6 类静态检查：结构、JSON、Python AST、JS `node --check`、README 链接、需求追溯。
- DeliveryValidator：必需文件（README/依赖/测试/ASSUMPTIONS）、空壳文件、JSON 语法、
  FR 全映射；未通过不得完成。
- 测试运行器：仅 `node --test` / `npm test` / `pytest` 三种模板；默认关闭；逐次 GUI 授权；
  环境变量白名单；300 s 超时；缺失 Node 明确 `not run`。
- 修复：完成被拒 → 反馈缺失项 → 模型补齐；Controller 最多 3 轮新会话修复；仍失败转 partial。

**指标**：6 类检查全部在样例上 pass；Node 缺失时 `js_syntax=skipped`、测试 `not run`；
完成拒绝→修复成功用例通过；连续 3 次拒绝正确转 partial。

### M6 GUI 与发布
- `AgentWorker(QThread)` + `ApprovalBridge`：API/工具/测试全部在后台；授权弹窗阻塞工作线程、
  由 GUI 主线程应答；停止按钮设置 cancel token；关闭窗口等待安全检查点。
- 事件驱动 UI：阶段、任务清单、实时日志、文件表（大小/SHA-256）、验证结果、报告预览、
  Tokens/费用、真实文件数/工具调用数（非伪造百分比）。
- EXE：PyInstaller one-dir 调试通过后构建 one-file；内置样例数据、图标、版本信息。

**指标**：one-file `SpaceCodeAgent.exe` **61,014,405 B（58.2 MiB）**；`--smoke-test` 退出码 0，
冷启动 3.1 s；EXE 内完成 36 步生成 + 19 项 Node 测试共 14.2 s；GUI 自动化跑通并输出 3 张截图。

### M7 验收与收尾
- 84 项 pytest 全绿；样例 19 项 Node 测试全绿；EXE one-file 全流程退出码 0。
- T14 真实 `deepseek-v4-pro`：75 步 / 114 工具调用 / 2,616,750 tokens / $0.1481，生成浏览器 UI
  与重启恢复持久化，27/27 测试和 Edge 浏览器 E2E 通过；含 1 轮自动修复。证据见 `docs/evidence/t14-real/`。
- T15 仍需完全未安装 Python/Qt 的干净 Windows VM；CI artifact 与 smoke 已通过。
- 产出 `docs/TEST_REPORT.md`、`docs/USER_GUIDE.md`、截图、样例工程、构建脚本。

## 3. 最终指标汇总

| 指标 | 数值 |
|---|---|
| Agent Python 源码 | 34 文件 / 5627 行 |
| Agent 测试 | 7 文件 / 985 行 / **84 项全绿** |
| 内置样例 | 34 文件 / 2632 行 / 19 项 Node 测试 |
| PlantUML 解析 | 13/13 块，11 类视图 |
| 需求覆盖（Mock 样例） | 7/7 = 100% |
| Mock 工具调用 | 36 次，步数 36/60 |
| Mock Token / 估算费用 | 4,320 / $0.001313 |
| one-file EXE | 58.2 MiB，冷启动 3.1 s |
| 安全测试 | 11 类路径攻击拒绝 + 密钥脱敏 + 覆盖保护 |
| 真实 API | 已执行（deepseek-v4-pro，75 步 / 114 工具 / 2,616,750 tokens / $0.1481）；UI + 持久化，27/27 测试 + 浏览器 E2E 通过 |
