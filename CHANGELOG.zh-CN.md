> 🌐 [English](CHANGELOG.md) | **简体中文**

# 更新日志 (Changelog)

## 1.0.0 — 2026-11-09

首个公开发布版本。

### 新增功能 (Added)

- **PySide6 桌面客户端**：提供图形交互界面，支持 API 密钥管理、输入校验、执行进度与实时日志监控、生成文件清单展示、校验结果可视化、交付报告预览，以及任务中止与快速定位输出目录等操作。
- **DeepSeek-V4-Pro Responses API 适配器**：集成函数调用（Function Calling）、推理强度配置（Reasoning Effort）、有界指数退避重试、Token 与成本计量，以及敏感信息脱敏机制。
- **需求解析引擎**：支持 Markdown 与 PlantUML 解析（覆盖 13 种文本块与 11 类架构视图），基于 Pydantic 构建强类型需求模型，支持跨模块需求冲突检测与假设项追踪。
- **受控 Agent 执行闭环**：实现「规划 → 执行 → 观测 → 验证」标准化循环，内置 8 项操作工具、工作区路径沙箱策略、原子化文件写入、JSON Schema 输出校验及交付准入控制门禁。
- **交付校验与质量保障体系**：集成静态代码检查、受控测试运行器、测试失败自动修复循环、需求追溯性矩阵（CSV）以及机器可读的运行清单（Run Manifest）。
- **内置离线 Mock 样例工程**：提供零外部依赖的 Space Fractions 示例（含 33 个源码文件及 16 项 Node.js 测试），支持全流程脱网测试与基准验证。
- **打包分发与 CI 流水线**：提供 PyInstaller 单文件/单目录打包规范、应用资产与版本元数据；配置 Windows CI 工作流（运行记录 [#6](https://github.com/TouchedOVO/touch-code/actions/runs/42640206235)），覆盖 Python 测试、Node.js 22 测试、可执行文件构建、安装后冒烟测试及 `SpaceCodeAgent-windows-x64` 制品归档。
- **全流程自动化测试**：集成 84 项 pytest 单元与集成测试，覆盖 AST 解析、安全沙箱、工具调用、Provider 重试容错、任务中断、Token 预算控制、自愈修复机制、端到端 Mock 生成及 GUI 冒烟测试。
- **测试证据与验收归档**：规范化浏览器 UI 与持久化契约，建立针对单条需求的 `Covers:` 证据链，并在 `docs/evidence/t14-real/` 下归档完整的 T14 阶段真实浏览器端 E2E 验证数据。

### 当前技术选型与已知限制 (Known Limitations & Trade-offs)

- **生成工程的架构选型**：当前生成的演示工程采用模块化单体架构（Modular Monolith）、Node.js 原生 `node:http` 服务及基于文件系统的 JSON 持久化方案，未采用微服务架构及独立关系型数据库（PostgreSQL）；详细架构边界与设计取舍见生成的 `ASSUMPTIONS.md`。
- **待完善功能**：
  - 会话中断恢复（Session Resume）界面；
  - 代码变更差异预览（Diff Preview）；
  - 模型思考推理过程的实时流式展示（Streaming Reasoning）。
- **运行环境验证范围**：T15 自动化流水线已在剥离 Python/Qt 运行时依赖的纯净环境中完成 EXE 冒烟、无头 GUI 启动及端到端生成测试；未在 Windows 物理机桌面环境中执行人工交互测试。
