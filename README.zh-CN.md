> 🌐 [English](README.md) | **简体中文**

# SpaceCode Agent

**面向 Windows 环境的架构文档驱动代码生成智能体 (Architecture-Document-Driven Code Agent)**  
通过结构化解析架构设计文档与 UML 视图规范，自动化生成可运行、通过自动化测试且具备完整追溯证据链的软件工程项目，并提供端到端的交付质量审计报告。

[![Python](https://img.shields.io/badge/python-3.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/PySide6-6.12-41CD52?logo=qt&logoColor=white)](https://doc.qt.io/qtforpython-6/)
[![Tests](https://img.shields.io/badge/tests-84%20passed-brightgreen)](#测试与质量保障)
[![Windows build](https://github.com/TouchedOVO/touch-code/actions/workflows/windows-build.yml/badge.svg)](https://github.com/TouchedOVO/touch-code/actions/workflows/windows-build.yml)
[![Download v1.0.0](https://img.shields.io/badge/Download-SpaceCodeAgent.exe-2ea44f?logo=github)](https://github.com/TouchedOVO/touch-code/releases/tag/v1.0.0)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**独立二进制下载**：[SpaceCodeAgent.exe v1.0.0](https://github.com/TouchedOVO/touch-code/releases/download/v1.0.0/SpaceCodeAgent.exe)  
（文件大小：64,195,999 字节；SHA-256：`1CD71031F6E2CEBCC9DA3ACC07570507DFF2111E36329010880677BF26D1B182`；目标运行机无需预装 Python 或 Qt 运行时）。

SpaceCode Agent 读取输入的架构说明文档（`Architecture_Documentation.md`）与 UML 视图规范（`Architecture_View.md`），基于 AST 解析并提取 13 处 PlantUML 图表与多维需求模型，随后在严格受限的沙箱工具层中执行规划与工程构建，经静态验证与测试准入检查后，输出完整的工程文件、测试用例与追溯性报告。

> **核心目标**：输入结构化架构文档，直接输出生产就绪、具备自动化测试验证的工程源码与审计证据，而非零散的代码片段。

---

## 核心特性 (Key Features)

- **真实文件系统级构建**：所有源码与配置文件均通过原子化工具层（`write_file` / `replace_in_file`）写入隔离工作区，附带完整的 SHA-256 完整性证据链。
- **DeepSeek-V4-Pro 官方接口原生集成**：直连 DeepSeek 官方 Responses API（`https://api.deepseek.com`），原生支持 Function Calling 与思考深度（`reasoning.effort`）配置，内置指数退避重试与状态容错机制。
- **全要素需求归一化与追溯**：基于 AST 解析架构文档与 13 种 PlantUML 图表，建立结构化需求模型（FR / NFR / ASR），并在代码中生成精准映射的 `Covers:` 证据链与追溯矩阵（CSV）。
- **受控有界执行闭环 (Confined Agent Loop)**：内置 8 项原子操作工具、工作区路径沙箱限制、执行步数及 Token 预算控制；任务完成声明必须通过交付验证器门禁，杜绝幻觉伪完成。
- **内置质量自愈机制**：集成静态代码检查、受控测试运行器（Node.js / pytest）与自动修复循环，对测试失败或语法错误具备自动化多轮自愈能力。
- **原生 Windows 桌面集成**：基于 PySide6 构建高响应度图形界面，提供 API 密钥动态脱敏、执行进度监控与结构化日志；支持单文件绿色打包，开箱即用。

---

## 架构体系 (System Architecture)

```
[Architecture_Documentation.md + Architecture_View.md]
                           │
                           ▼
             ┌───────────────────────────┐
             │   解析与需求归一化引擎     │
             │ Markdown + PlantUML 解析  │
             └─────────────┬─────────────┘
                           │ 需求模型 / 冲突分析 / 假设项
                           ▼
             ┌───────────────────────────┐
             │       规划与执行器         │
             │   DeepSeek-V4-Pro Provider │
             └─────────────┬─────────────┘
                           │ 受控工具调用循环
                           ▼
             ┌───────────────────────────┐
             │     工作区安全工具层       │
             │  8 项原子工具 + 路径沙箱   │
             └─────────────┬─────────────┘
                           │ 生成的工程文件
                           ▼
             ┌───────────────────────────┐
             │     验证器与自愈循环       │
             │   静态检查 / 受控测试     │
             └─────────────┬─────────────┘
                           │ 验证通过
                           ▼
[交付工程源码] + [GENERATION_REPORT.md] + [traceability.csv] + [run_manifest.json]
```

---

## 快速上手 (Quick Start)

### 1. 环境准备

推荐在 Python 虚拟环境中运行：

```powershell
git clone https://github.com/TouchedOVO/touch-code.git
cd touch-code
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e ".[dev]"
```

若需执行生成工程的 Node.js 自动化测试，需安装 Node.js ≥ 20。

### 2. 运行桌面端应用

```powershell
python -m space_code_agent
```

### 3. 运行模式

- **脱机 Mock 模式**：无需配置 API Key，直接选用内置的 Space Fractions 基准工程。系统将完整演练文件生成、路径沙箱检查、自动化测试校验与报告输出全流程。
- **真实模型生成模式**：在界面中输入 DeepSeek API 密钥（内存驻留、自动掩码），选择输入文档与输出目录，系统将根据架构模型进行全自主规划、代码编写与测试验证。

---

## 构建与打包 (Build Windows EXE)

项目支持通过 PyInstaller 构建免安装的单文件可执行程序：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1 -Clean
```

打包产物将输出至 `dist\SpaceCodeAgent.exe`。

---

## 测试与质量保障 (Testing)

项目集成完备的自动化测试体系，覆盖协议解析、工具权限、安全沙箱、重试机制与端到端生成流程：

```powershell
# 运行完整自动化测试套件
pytest tests -v
```

当前包含 84 项测试用例，覆盖范围包括：
- Markdown 与 PlantUML AST 解析规范性；
- 工作区路径遍历（Path Traversal）与符号链接越权防御；
- 敏感信息动态掩码（Secret Redaction）；
- 大模型接口超时、429 限流及故障重试策略；
- 自动化代码生成与测试修复反馈回路；
- GUI 核心组件生命周期与无头冒烟测试。

---

## 目录结构 (Project Layout)

```
space-code-agent/
├── src/space_code_agent/        # 核心源码
│   ├── config.py                # 全局运行时配置与约束参数
│   ├── parser.py                # 架构文档与 PlantUML 解析器
│   ├── models.py                # 强类型需求与元数据模型
│   ├── provider/                # DeepSeek API 适配器与网络传输层
│   ├── agent/                   # Agent 执行状态机与提示词工程
│   ├── tools/                   # 工作区受控工具集与路径策略
│   ├── validator/               # 交付质量检验与测试执行桥
│   ├── ui/                      # PySide6 桌面交互界面
│   └── samples/                 # 内置基准测试工程（Space Fractions）
├── tests/                       # 自动化测试用例集
├── examples/                    # 示例输入文档与报告范例
├── scripts/                     # 构建与 CI 自动化脚本
└── docs/                        # 详细设计、测试报告与使用文档
```

---

## 安全模型与运行边界 (Safety Model)

- **路径隔离策略**：所有文件读写均由 `WorkspacePolicy` 执行严格的规范化检查，强制限制在指定工作区根目录内，拦截任何上层路径穿越（`..`）、系统特殊设备文件或 UNC 路径注入。
- **命令受限执行**：系统默认禁止运行外部进程。仅在用户明确授权后，方可通过白名单受限运行 `node --test`、`npm test` 或 `pytest`。
- **凭据生命周期控制**：API 密钥仅保存在内存中，严禁写入磁盘；在日志记录、交付报告导出以及运行元数据清单中均执行强脱敏处理。

---

## 当前技术选型与已知限制 (Limitations & Trade-offs)

- **生成项目架构规范**：当前基准实现采用模块化单体架构（Modular Monolith）、Node.js 原生 HTTP 服务与基于本地文件系统的持久化方案，未接入分布式微服务与外部 PostgreSQL 数据库。
- **交互功能待扩展项**：当前版本暂未提供历史会话恢复界面、代码变更实时差异对比（Diff View）以及推理过程的流式打字展示。
- **环境适配**：自动化流水线已在纯净 Windows 运行环境中验证了 EXE 打包与全流程执行。

---

## 开源许可 (License)

本项目采用 [MIT 许可证](LICENSE) 授权开源。
