> 🌐 [English](USER_GUIDE.md) | **简体中文**

# 用户操作手册 (User Guide)

SpaceCode Agent 是一款基于架构文档驱动的自动化代码生成工具。通过输入系统架构说明书与 UML 视图规范，自动完成需求建模、任务规划、受控代码生成、静态质量检验与测试验收，并生成可追溯的交付审计报告。

---

## 1. 启动方式

### 方案 A：独立可执行文件（推荐，宿主机无需 Python 环境）
直接运行 `SpaceCodeAgent.exe`。
> 首次启动时，PyInstaller 打包程序将自动解压运行时组件，初始化耗时约 3–6 秒。

### 方案 B：源码运行
```powershell
cd space-code-agent
.\.venv\Scripts\Activate.ps1
python -m space_code_agent
```

---

## 2. 核心参数与运行配置

1. **DeepSeek API 密钥**：
   - 输入有效的 DeepSeek API Key（以 `sk-` 开头）。
   - **安全策略**：密钥仅暂存在当前进程的内存中，严禁写入磁盘。在控制台日志、交付报告与运行元数据（Manifest）中均自动执行掩码脱敏。
   - 勾选“显示密钥”可明文核对，默认处于圆点掩码状态。
2. **模型引擎**：
   - 预设绑定 `deepseek-v4-pro`，确保具备对复杂软件架构多视图的推理与结构化工具调用能力。
3. **推理深度配置 (Reasoning Effort)**：
   - 默认推荐：`high`（高深度推理）；
   - 对于超大规模或高度复杂的架构冲突推导，可切换为 `max`（将消耗更多 Token 算力）。
4. **离线 Mock 模式**：
   - 勾选后无需配置 API 密钥，直接基于内置的 Space Fractions 基准工程运行。系统将完整演练文件沙箱写入、静态检查、自动化测试与审计报告生成全流程。
5. **项目测试执行权限**：
   - 默认为禁用状态。
   - 开启后，Agent 发起的每次测试执行均会通过 GUI 弹窗请求人工授权，且仅允许调用预设白名单命令（`node --test` / `npm test` / `pytest`），杜绝任意系统指令执行。

---

## 3. 标准操作流程

1. **输入文件选定**：
   - **架构设计文档**：点击“浏览…”选择 `Architecture_Documentation.md`；
   - **UML 视图文档**：点击“浏览…”选择 `Architecture_View.md`；
   - **输出工作区**：指定本地目标目录（如 `.\out\demo`）。
2. **文档合规性前置检查**：
   - 点击“检查输入”按钮。系统将执行 AST 解析，验证文件编码、有效行数、13 处 PlantUML 块完整性，并在弹窗中汇总功能需求、设计冲突与架构假设统计数据。
3. **启动工程生成**：
   - 点击“生成项目”按钮。
   - **输出目录安全隔离**：若目标目录非空，系统将自动生成具备时间戳的唯一子目录（如 `generated-YYYYMMDD-HHMMSS`），避免覆盖既有文件。
   - **状态监控**：
     - **任务清单 (Tasks)**：动态展示当前已规划和执行中的任务阶段；
     - **实时日志 (Logs)**：展示当前执行步骤、工具调用与沙箱操作明细；
     - **生成文件清单 (Files)**：实时展示已生成文件的相对路径、大小与 SHA-256 校验码；
     - **执行进度与成本**：状态栏精确显示离散步数（如第 n/60 步）、Token 消耗总量及实时核算成本。
4. **任务中止**：
   - 若需提前终止任务，可点击“停止”按钮。系统将在当前模型请求或工具原子操作完成后安全停机，并保留已写入的工程文件与审计日志。
5. **交付验收与查看**：
   - 执行完成后，系统将弹出状态摘要对话框，展示最终交付状态与需求覆盖率；
   - 切换至“报告预览”标签，可直接查阅渲染后的 `GENERATION_REPORT.md`；
   - 点击“打开输出目录”按钮，即可直接在文件管理器中定位交付产物。

---

## 4. 交付产物目录结构

生成的工作区目录包含以下工程文件与审计证据：

```text
<工作区输出目录>/
├── README.md                      # 生成工程的主说明文档
├── package.json / requirements.txt# 依赖与脚本声明
├── src/ 或 services/ apps/         # 业务源码模块（含 Covers: 需求标记）
├── tests/                         # 单元测试与端到端测试套件
├── docs/
│   ├── architecture-summary.md    # 架构设计摘要与模块映射
│   └── ASSUMPTIONS.md             # 架构选型假设、技术边界与权衡决策
├── GENERATION_REPORT.md           # 交付审计报告（Markdown 格式）
├── traceability_matrix.csv        # 需求追溯矩阵（带 UTF-8 BOM，适配 Excel）
├── run_manifest.json              # 机器可读的运行元数据与 SHA-256 清单
└── .agent_state/<session>/        # 会话运行审计日志（隐藏目录）
```

---

## 5. 命令行接口 (CLI)

支持通过无头模式集成至自动化流水线或脚本中：

```powershell
# 1. 离线 Mock 端到端全流程（无需网络通信与 API 密钥）
SpaceCodeAgent.exe --mock-run .\out\demo `
  --doc examples\inputs\Architecture_Documentation.md `
  --uml examples\inputs\Architecture_View.md `
  --allow-tests

# 2. 真实大模型生成模式（API 密钥通过环境变量传入）
$env:DEEPSEEK_API_KEY="sk-..."
SpaceCodeAgent.exe --run .\out\real `
  --doc examples\inputs\Architecture_Documentation.md `
  --uml examples\inputs\Architecture_View.md `
  --allow-tests

# 3. 运行环境自检与冒烟测试
SpaceCodeAgent.exe --smoke-test
```

> **无头模式结果归档**：CLI 运行完成后，将在输出目录同级生成 `<目录名>-agent-result.json`，系统化记录交付状态、覆盖率、步数及报告路径。

---

## 6. 常见问题排查 (Troubleshooting)

| 异常现象 / 报错信息 | 根因分析 | 推荐解决方案 |
|---|---|---|
| `HTTP 401 Unauthorized` | API 密钥无效、过期或格式包含多余空格 | 重新从 DeepSeek 平台复制密钥，确认无前导/后置空白字符 |
| `HTTP 429 Rate Limit` | 达到服务商接口并发或频次限制 | 程序已内置指数退避重试；若持续报错，建议检查账户并发配额或稍后重试 |
| 网络连接超时 (Timeout) | 本地网络波动或代理链路异常 | 检查本地网络代理与 TLS 设置；系统针对网络错误已内置 4 次退避重试 |
| 输出目录写入冲突 | 指定路径被其他进程独占或存在写保护 | 系统会自动创建唯一时间戳子目录；请确保工作区具有完整读写权限 |
| 测试执行被标记为 `not run` | 宿主机缺少 Node.js/Python 运行时，或未勾选允许测试 | 确认宿主机已安装所需测试运行环境，并在界面中开启测试授权 |
| Windows Defender 提示风险拦截 | 未签名的 PyInstaller 打包程序可能触发启发式扫描 | 对比官方发布的 SHA-256 哈希值确认完整性，或选择通过源码运行 |
| 控制台输出字符乱码 | 编码格式与当前代码页不匹配 | 源码与报告均采用 UTF-8 编码；在 Windows PowerShell 下读取时请显式指定 `-Encoding UTF8` |

---

## 7. 运行环境与安全规范

- **凭据最小泄露原则**：切勿将 API 密钥硬编码到公开脚本、配置文件或截图中；应用在退出后即释放相关内存。
- **第三方代码审查**：生成的工程可能包含外部脚本与依赖定义；在宿主机正式运行前，请审查 `package.json` 中的构建脚本与测试代码。
- **权限最小化**：严禁以 Windows 系统管理员（Administrator）权限运行生成的未知工程代码。
- **架构定位与技术选型**：当前生成的示例工程采用模块化单体架构与本地持久化方案，专注于核心业务闭环与契约验证；如需投入高并发生产环境，应根据企业架构标准接入微服务框架与独立数据库集群。
