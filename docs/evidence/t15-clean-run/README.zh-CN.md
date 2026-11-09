> 🌐 [English](README.md) | **简体中文**

# T15 — 纯净宿主环境执行验证记录 (Clean Host Runner Verification)

**CI 流水线运行记录**：[T15 clean Windows runner #1](https://github.com/TouchedOVO/touch-code/actions/runs/42643238074)  
**验收结论**：**通过 (PASS)**  
**运行环境**：GitHub-hosted `windows-latest`（纯净临时 Windows 虚拟机）  
**提交版本**：`7e9f17e`  
**可执行程序哈希 (SHA-256)**：`A5E23A34D25197017056002930457FC7E27707A9A846C0DE3D82E0C3DB92C561`  

---

## 1. 验证目标与隔离策略

本测试旨在验证编译打包后的单文件二进制程序 `SpaceCodeAgent.exe` 在**完全未安装 Python 与 Qt 运行时**的纯净宿主环境下具备自包含独立运行能力。

验证步骤：
1. 在 CI 运行机上编译生成单文件 `SpaceCodeAgent.exe`。
2. **彻底剥离全局 Python 与 Qt 环境**：
   - 清除 Runner 预装的 Python 工具缓存及 `Program Files\Python*` 目录；
   - 彻底删除项目本地虚拟环境 `.venv`；
   - 删除系统中的 `python.exe` 与 `py.exe` 启动器；
   - 将系统 `PATH` 环境变量精简重置为仅包含 `System32`、`Windows` 及生成项目所需的 Node 22 路径。
3. 执行校验确认：执行 `Get-Command python` 与 `Get-Command pip` 均返回失败，且文件系统中无任何残留 Python 运行时。
4. 在该纯净隔离环境下执行单文件 EXE：
   - 执行 `--smoke-test`（无头 Qt 模式） → 退出码 **0**；
   - 启动 GUI 桌面应用进程 → 稳定驻留运行；
   - 执行全流程无头生成测试：`--mock-run … --allow-tests`，基于两份架构文档完成工程构建。
5. 结果校验：
   - 交付状态达成 `completed`；
   - 需求文件映射率 **100%**，测试验证率 **100%**；
   - 生成工程内的 Node.js 测试套件执行全量通过。

---

## 2. 归档凭据清单

| 文件名 | 内容与检验范围 |
|---|---|
| `t15-result.json` | 记录 `python_available: false`、EXE 哈希、交付状态、需求覆盖率与测试结果 |
| `agent-result.json` | CLI 运行的完整结构化输出与执行状态元数据 |
| `run_manifest.json` | 纯净环境下生成的运行清单与文件哈希 |
| `GENERATION_REPORT.md` | 生成的交付审计报告 |
| `traceability_matrix.csv` | 需求追溯矩阵 |

---

## 3. 运行环境与工程结论

本验证在剥离了全局 Python/Qt 依赖的临时干净 Windows 运行机上自动化完成，充分证明了单文件二进制包 `SpaceCodeAgent.exe` 具备完备的自包含便携特性，对宿主操作系统的运行库环境无前置依赖。
