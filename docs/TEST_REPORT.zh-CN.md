> 🌐 [English](TEST_REPORT.md) | **简体中文**

# 测试与质量验收报告 (Test & Quality Assurance Report)

**测试基准环境**：Windows 11 x64、Python 3.14.3、PySide6 6.12.0、PyInstaller 6.22.3、Node.js 22.23.4 / 26.13.0。  
**凭据管理机制**：DeepSeek API 密钥由宿主环境变量或内存临时传入，全流程脱敏，禁止持久化至版本库。

---

## 1. 核心自动化测试执行摘要

| 测试类别 / 执行命令 | 验证目标 | 执行结果 | 性能与基准指标 |
|---|---|---|---|
| `python -m pytest tests -q` | Agent 核心逻辑、安全沙箱、解析引擎、自愈循环 | **84 passed / 0 failed** | 涵盖自愈闭环、契约检验、并发与重试 |
| `node --test tests/unit/...` | 内置样例服务层与单元功能测试 | **18 passed / 0 failed** | Node.js 22 运行时 |
| `node --test tests/e2e/flow.test.js` | 内置样例端到端业务流测试 | **1 passed / 0 failed** | 完整主流程通过 |
| `SpaceCodeAgent.exe --smoke-test` | 单文件二进制免安装运行时冒烟 | **退出码 0** | 冷启动耗时 **3.1 s** |
| `SpaceCodeAgent.exe --mock-run ... --allow-tests` | 二进制程序离线全流程生成与测试 | **退出码 0** | 全流程耗时 **14.2 s**，需求映射与验证 **100%** |
| 生成工程内置 `node --test` | 由 Agent 自动化执行的项目验收测试 | **19 passed / 0 failed** | 自动化记录于 `run_manifest.json` |
| **真实 DeepSeek-V4-Pro 端到端调用** | 生产环境完整生成、持久化与浏览器 UI 验收 | **退出码 0 (Completed)** | **27/27 测试全绿**，消耗 2,616,750 Tokens / **$0.1481**；Edge 浏览器 E2E 通过 |

> **单文件打包制品**：`dist/SpaceCodeAgent.exe`，文件大小为 **61,014,405 字节（58.2 MiB）**。

---

## 2. 持续集成与发布流水线 (CI/CD)

GitHub Actions 主干工作流：[Windows build #6](https://github.com/TouchedOVO/touch-code/actions/runs/42640206235) — **Status: Success**

| CI 作业名称 | 执行环境 | 检验范畴 | 结果与制品标识 |
|---|---|---|---|
| `Agent test suite (Windows)` | Windows / Python 3.14 | 84 项核心 pytest 用例与 AST 语法检查 | ✅ 通过 |
| `Generated sample tests (Node)` | Windows / Node 22 | 19 项 Node.js 单元、集成与 E2E 测试 | ✅ 通过 |
| `Build one-file EXE` | Windows / PyInstaller | 编译单文件 EXE 并执行免安装冒烟检查 | ✅ 退出码 0 |
| `Artifact: SpaceCodeAgent-windows-x64` | 发布资产归档 | 自动归档免安装二进制安装包 | 63,669,245 字节；SHA-256：`0178a9f688b36944012d9b86eb271d3c414e1d548c251c74b089ea6cbb39a1b3` |

---

## 3. 真实大模型端到端生成验收 (T14 实测)

测试归档路径：[`docs/evidence/t14-real/`](evidence/t14-real/README.md)

| 核心指标 | 实测参数 | 备注说明 |
|---|---|---|
| **指定模型 / 实际响应模型** | `deepseek-v4-pro` / `deepseek-v4-pro` | 官方原生接口，无降级与静默替换 |
| **Agent 状态机交互** | 75 轮状态交互 / 114 次工具调用 / 75 次 API 请求 | 状态机有序收敛 |
| **Token 开销统计** | 输入 2,525,691 / 输出 91,059 / 缓存命中 2,370,432 / 深度推理 51,670 | 总计 2,616,750 Tokens |
| **综合算力成本** | **$0.148089 USD** | 符合高性价比生产标准 |
| **耗时统计** | Agent 执行 1,375.4 s / 交付报告构建 1,720.1 s | 包含多轮推理与外部测试运行 |
| **独立重跑生成工程测试** | **27 / 27 passed** | Node 22 环境独立复测全通 |
| **静态与交付契约检查** | 结构、JSON、Python、JS、链接、追溯矩阵全部通过 | 包含 Web UI 交互契约与防重启丢失持久化契约 |
| **需求覆盖与验证率** | 映射率 7/7 (100%)，验证率 7/7 (100%) | 源码中均包含 `Covers:` 证据注解 |
| **无头浏览器端到端测试** | **PASS** | Edge Headless：通过欢迎页、菜单、帮助、10 道答题流程并生成结算报告 |

**质量评估结论**：真实模型生成的代码成功包含完整的浏览器端前端交互、支持防重启丢失的文件级 JSON 持久化存储、标准 REST API 以及 27 项自动化测试。在初次执行中，因第三方依赖缺失导致单元测试报错，控制器准确捕获 stderr 并回传模型，触发**自动自愈闭环**，模型在 1 轮内自动重构为基于 Node 原生 `node:http` 模块的零依赖实现并全量通过所有测试。

---

## 4. 纯净环境独立运行验证 (T15 隔离测试)

流水线记录：[T15 clean Windows runner #1](https://github.com/TouchedOVO/touch-code/actions/runs/42643238074) — **Status: Success**  
测试归档路径：[`docs/evidence/t15-clean-run/`](evidence/t15-clean-run/README.md)

为验证单文件二进制包的独立性与便携性，在 GitHub 托管的纯净 Windows 运行机上执行隔离测试：
1. **环境净化**：构建完成后完全清除系统 Python 工具缓存、Program Files 中的 Python 目录、项目虚拟环境及系统启动器，验证 `python` 与 `pip` 命令彻底失效。
2. **免依赖冒烟测试**：在无全局 Python/Qt 运行时的环境下执行 `SpaceCodeAgent.exe --smoke-test`，正常启动并返回退出码 0。
3. **GUI 进程生命周期**：验证桌面客户端主事件循环正常初始化且稳定驻留。
4. **全流程代码生成与测试**：在纯净环境下以 `--mock-run --allow-tests` 运行，顺利完成全量工程生成、静态校验及 19 项 Node.js 测试，验证需求覆盖率达成 100%。

---

## 5. 系统需求与安全防御验证矩阵

| 用例编号 | 验证场景与输入条件 | 预期行为与判定准则 | 验证结果 | 对应测试工程用例 |
|---|---|---|---|---|
| **T01** | 标准架构说明书与 UML 视图文档 | 结构化解析 13 个 PlantUML 块与 11 类视图，抽取 7 项核心需求 | ✅ 通过 | `tests/test_parser.py` |
| **T02** | 路径不存在、空文件、畸形字符集、超大文件 | 正确触发异常枚举（`not_found`, `empty`, `encoding`, `too_large`）并提示 | ✅ 通过 | `tests/test_parser.py`, GUI 校验 |
| **T03** | 需求声明与视图模型存在逻辑冲突 | 准确识别 8 类设计冲突（如视图块数量差异、缺失定义、未受约束的重型中间件） | ✅ 通过 | `tests/test_parser.py` |
| **T04** | 调度器工具调用文件写入 | 沙箱内多文件原子化写入并严格匹配 `call_id` 回传 | ✅ 通过 | `tests/test_agent_loop.py` |
| **T05** | 工具调用缺少必要参数或类型不符 | 返回结构化 `invalid_arguments` 错误响应，状态机正常维持 | ✅ 通过 | `tests/test_tool_registry.py` |
| **T06** | 路径遍历攻击（`../`、绝对路径、UNC、NTFS 数据流、设备名、符号链接逃逸） | `WorkspacePolicy` 强效拦截 11 类非法路径，阻止越权访问 | ✅ 通过 | `tests/test_security.py` |
| **T07** | 同名文件覆盖保护 | 默认阻止未声明的覆盖写入；仅显式配置 `overwrite=true` 时方可覆盖 | ✅ 通过 | `tests/test_security.py` |
| **T08** | 网络断连、HTTP 429 限流与 5xx 故障 | 触发指数退避重试；重试耗尽后安全报告错误 | ✅ 通过 | `tests/test_provider.py` |
| **T09** | API 凭据失效或鉴权未通过（HTTP 401） | 立即熔断并终止重试，日志脱敏输出，严禁回传明文 Key | ✅ 通过 | `tests/test_provider.py` |
| **T10** | 用户中途主动中止任务 | 取消信号实时注入，安全清理临时状态并导出中止审计记录 | ✅ 通过 | `tests/test_mock_e2e.py` |
| **T11** | 测试用例失败或交付验证被拒绝 | 控制器回传结构化错误触发模型重写自愈；超过 3 次转入 `partial` 降级 | ✅ 通过 | `tests/test_agent_loop.py` |
| **T12** | 宿主缺少 Node.js 运行环境 | 标记 `run_tests=not_available`，报告显示 `not run`，整体以 `partial` 保守交付 | ✅ 通过 | `tests/test_tool_registry.py` |
| **T13** | 脱网 Mock 端到端全流程 | 零外部网络依赖，生成完整工程文件树、测试与追踪报告 | ✅ 通过 | `tests/test_mock_e2e.py` |
| **T14** | 生产模型端到端真实调用 | 75 轮交互生成 Web 前端、持久化模块并通过 27 项自动化测试与浏览器 E2E | ✅ 通过 | `docs/evidence/t14-real/` |
| **T15** | 纯净独立 Windows 环境运行 | 在剥离 Python/Qt 环境的系统下验证免安装 EXE 冒烟与端到端生成 | ✅ 通过 | `docs/evidence/t15-clean-run/` |

---

## 6. 代码审查与架构缺陷收敛记录

| 审查关注点 | 技术归因与风险评估 | 改进方案与实施策略 | 验证结论 |
|---|---|---|---|
| **PEP 639 许可证声明冲突** | setuptools 高版本对元数据规范校验趋严 | 规范化 `pyproject.toml`，移除废弃分类器，声明规范 `license = "MIT"` | 构建通过，无警告 |
| **Node.js 22 测试路径兼容性** | Node 22 原生测试运行器调整了目录解析机制 | 在自动化测试与 CI 脚本中显式声明各测试套件的入口文件路径 | 19 项 Node 测试在 Node 22/26 下全绿 |
| **构建失败自愈回路缺失** | 传统代码生成缺少闭环检验机制 | 实现反馈闭环：将测试退出码与精简 stderr 反馈模型，支持最多 3 轮自动自愈 | 真实场景下成功自愈依赖缺失，测试 100% 通过 |
| **需求覆盖率统计口径** | 仅按文件存在判定易造成伪覆盖率 | 细化统计维度：区分映射（Mapped）、实现（Implemented）与验证（Verified）；仅当关联测试真实执行且通过时方可标记 Verified | 审计报告与 CSV 具备严谨的一致性 |
| **多终端交付状态同步** | 异常分支可能导致不同模块呈现的状态不一致 | 抽象统一的 `final_status` 全局枚举，贯穿 GUI、CLI 报告与机器可读 Manifest | 测试用例断言状态判定 100% 对齐 |
| **模型指定策略** | 防止误调用低参数版本模型 | 锁定模型为 `deepseek-v4-pro`，并在全局配置校验层实施白名单强制锁定 | 杜绝模型静默降级 |
