# 使用手册

## 1. 启动

### EXE（目标机器无需 Python）

双击 `SpaceCodeAgent.exe`。首次启动需解压运行时，约 3–6 秒。

### 源码

```powershell
cd space-code-agent
.venv\Scripts\python -m space_code_agent
```

## 2. 配置

1. **DeepSeek API Key**：`sk-...`，仅保存在本次进程内存；日志、报告、manifest 自动脱敏。
   勾选“显示”可核对；不勾选时为圆点掩码。
2. **模型**：锁定 `deepseek-v4-pro`（任务要求，GUI 中不可替换）。
3. **思考强度**：默认 `high`；复杂规划可用 `max`（费用更高）。
4. **Mock 模式**：无需 Key，使用内置 Space Fractions 样例；仍执行真实文件工具、校验、测试与报告。
5. **允许运行项目测试**：默认关闭。开启后每次执行前弹窗授权，仅允许 `node --test` /
   `npm test` / `pytest`，不接受任意命令。

## 3. 一次完整操作

1. 点击“浏览…”选择：
   - 架构文档：`Architecture_Documentation.md`
   - UML 视图：`Architecture_View.md`
   - 输出目录：例如 `.\out\demo`
2. 点击“检查输入”。通过后弹窗显示：行数、13 个 PlantUML、需求/冲突/假设统计。
3. 点击“生成项目”。
   - 若输出目录非空，程序创建 `generated-<时间戳>` 子目录，不动已有文件。
   - “任务”标签显示计划任务；“实时日志”显示阶段/工具/文件；“文件清单”显示真实写入与 SHA-256。
   - 状态栏显示 Tokens 与估算费用；进度按“第 n/60 步”显示，不伪造百分比。
4. 需要中止时点击“停止”。当前模型/工具调用结束后的安全检查点停止；已写文件保留。
5. 完成后：
   - 弹窗显示状态与覆盖率；
   - “报告”标签预览 `GENERATION_REPORT.md`；
   - 点击“打开目录”查看工程。

## 4. 输出目录内容

```text
<输出>/
├── README.md
├── package.json / requirements.txt
├── src/ 或 services/ apps/
├── tests/
├── docs/ASSUMPTIONS.md
├── docs/architecture-summary.md
├── GENERATION_REPORT.md
├── traceability_matrix.csv
├── run_manifest.json
└── .agent_state/<session>/     # 审计日志（隐藏）
```

`traceability_matrix.csv` 使用 UTF-8 BOM，可直接用 Excel 打开。

## 5. 命令行

```powershell
# 离线 Mock 全流程（不调用 API）
SpaceCodeAgent.exe --mock-run .\out\demo `
  --doc examples\inputs\Architecture_Documentation.md `
  --uml examples\inputs\Architecture_View.md --allow-tests

# 真实模型（Key 从环境变量读取）
$env:DEEPSEEK_API_KEY="sk-..."
SpaceCodeAgent.exe --run .\out\real `
  --doc ... --uml ... --allow-tests

# 冒烟自检
SpaceCodeAgent.exe --smoke-test
```

窗口化 EXE 无控制台；每次 headless 运行会在输出目录旁写
`<目录名>-agent-result.json`，记录状态、覆盖率、步数与报告路径。

## 6. 常见问题

| 现象 | 处理 |
|---|---|
| `401 auth` | Key 无效/过期；重新生成，勿粘贴多余空格 |
| `429 rate_limit` | 程序自动退避重试；仍失败请降低并发或稍后再试 |
| 连接超时 | 检查代理/TLS；程序对 429/5xx/网络错误重试 4 次 |
| 输出目录被占用 | 程序创建唯一子目录；请勿手改生成中的文件 |
| 未运行测试 | 未装 Node/Python、未勾选允许测试或未授权；报告会写 `not run` |
| EXE 被 Defender 拦截 | PyInstaller 未签名产物可能被误报；可校验哈希或从源码构建 |
| 中文乱码 | 源码/报告均为 UTF-8；Windows PowerShell 5 读取时请指定 `-Encoding UTF8` |

## 7. 安全建议

- 不要把 API Key 写入脚本、`.env` 或截图；本程序默认不持久化。
- 生成项目可能包含第三方依赖/脚本；运行前阅读其 `package.json` 与测试命令。
- 本程序没有 OS 级沙箱；不要以管理员身份运行未知生成物。
- 生成样例为教学 MVP，不声称生产就绪；重型中间件未部署。
