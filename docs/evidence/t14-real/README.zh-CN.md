> 🌐 [English](README.md) | **简体中文**

# T14 — 生产级大模型端到端生成验收记录 (DeepSeek-V4-Pro)

**测试日期**：2026-11-09  
**服务接口端点**：`https://api.deepseek.com`  
**调用与响应模型**：`deepseek-v4-pro`（官方原生接口，无降级替换）  
**执行模式**：真实 API 调用模式  
**Agent 交付状态**：`completed`（已完成）  
**系统功能验收**：**通过 (PASS)** — 包含 Web 前端 UI、状态持久化、完整交互流程与 27 项自动化测试  

---

## 1. 复现执行命令

```powershell
$env:DEEPSEEK_API_KEY = "<用户环境变量中配置的 API Key>"
python -m space_code_agent --run .\out\t14-real `
  --doc .\examples\inputs\Architecture_Documentation.md `
  --uml .\examples\inputs\Architecture_View.md `
  --allow-tests --max-steps 80
```

---

## 2. 核心技术指标与运行度量

| 度量维度 | 实测数据 | 技术说明 |
|---|---|---|
| **交互步骤 / 工具调用 / 请求次数** | 75 步 / 114 次 / 75 次 | 状态机有序收敛 |
| **Token 分布结构** | 输入 2,525,691 / 输出 91,059 / 缓存命中 2,370,432 / 深度推理 51,670 | 充分利用官方提示词缓存 |
| **消耗 Token 总量** | **2,616,750 Tokens** | 包含多轮架构设计与代码构建 |
| **实测综合开销** | **$0.148089 USD** | 具备显著的工程性价比 |
| **执行耗时统计** | Agent 执行 1,375.4 s / 审计报告生成 1,720.1 s | 包含测试套件实际运行耗时 |
| **静态分析检查** | 结构、JSON、Python、JS、链接、需求追溯全部通过 | 严格符合交付校验门禁 |
| **核心交付契约** | deliverables、JSON、traceability、**web_ui**、**persistence** 全部通过 | 包含 Web 交互与防重启数据丢失 |
| **生成测试套件** | **27 / 27 passed** | Node.js 22 环境独立复测全通 |
| **需求追溯性** | 7/7 核心需求全量映射，7/7 具备 `Covers:` 测试用例全量验证 | 双向追踪证据链完备 |
| **无头浏览器端到端测试** | **通过 (PASS)** | 基于 Playwright / Edge Headless 跑通全流程 |

---

## 3. 生成工程结构与技术规格

```text
generated-project/
├── README.md / package.json / .env.example
├── docs/ASSUMPTIONS.md                   # 架构假设、设计决策与技术边界说明
├── public/
│   ├── index.html                       # 涵盖介绍、主菜单、题目作答、结算报告与帮助面板
│   ├── app.js                           # 前端交互状态机与 REST API 客户端
│   └── styles.css                       # 响应式布局与无障碍高对比度样式
├── src/
│   ├── app.js / server.js / http.js / config.js
│   ├── domain/fraction.js / game.js     # 分数核心运算与游戏规则领域模型
│   ├── repositories/                    # 基于原子化写入的文件持久化仓储
│   ├── routes/                          # REST API 路由层
│   └── services/                        # 业务服务层（题目、游戏、用户）
├── data/seed-questions.json             # 预置六年级分数运算题库
└── test/                                # 27 项自动化测试套件（含服务重启恢复验证与 E2E 流）
```

- **Web 前端界面**：涵盖开场引导、主功能菜单、答题主流程、得分报告与帮助说明，支持键盘操作与 ARIA 规范。
- **状态持久化**：采用基于文件系统的原子写入（临时文件写入 + 重命名替换），配套专门的重启测试，验证服务重启后题目与结算历史完整保留。
- **自动化测试**：所有测试用例显式声明 `Covers:` 需求编号，支持按需求维度精准验收。

---

## 4. 大模型自主执行与自愈表现

1. **结构化计划生成与自我纠错**：初始规划输出尝试在 `requirement_ids` 中引用假设编号（`ASM-04/ASM-05`），触发校验器拦截；模型自主修正并在第二轮生成合法规划（包含 9 项分解任务与 31 个目标文件）。
2. **测试驱动下的自愈修复闭环**：初始代码尝试引用第三方 Express 框架，导致测试报 `Cannot find module 'express'`；控制器捕获错误回传后，模型在**第一轮自愈中**重构为基于 Node 原生 `node:http` 的零依赖实现，使 27 项测试全部通过。
3. **架构选型与边界说明**：模型规范生成 `ASSUMPTIONS.md`，客观阐明当前工程采用模块化单体架构，并将微服务与外部数据库集群列为进阶演进选项。

---

## 5. 归档凭据文件清单

| 文件名 | 内容与证据说明 |
|---|---|
| `GENERATION_REPORT.md` | 真实运行生成的审计与交付报告 |
| `traceability_matrix.csv` | 需求 → 文件 → 测试双向追溯矩阵（UTF-8 BOM） |
| `run_manifest.json` | 包含 Token 消耗、校验状态、测试结果及文件 SHA-256 |
| `test-output.txt` | 独立 `node --test` 执行日志（27 项全部通过） |
| `browser-e2e.json` | 基于 Edge/Playwright 的浏览器 E2E 自动化测试结果 |
| `browser-e2e.png` | 浏览器端最终结算界面截图凭证 |
| `run-events.txt` | 脱敏后的 Agent 全过程事件流审计日志 |
| `generated-project/` | 由大模型自主生成的完整工程源码及资源 |
