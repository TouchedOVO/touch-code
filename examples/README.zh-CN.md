> 🌐 [English](README.md) | **简体中文**

# 示例输入与基准用例 (Examples)

`inputs/` 目录下提供的两份 Markdown 文件为基准测试架构设计文档，用于验证 SpaceCode Agent 在多视图、多需求与复杂 UML 模型下的端到端解析与代码生成能力。

---

## 包含文件

- **`inputs/Architecture_Documentation.md`**：系统架构设计说明书（文本主体），包含 39 个章节分级、4 张需求与度量表格、10 个技术规范与配置代码块，涵盖功能需求、非功能需求与技术约束。
- **`inputs/Architecture_View.md`**：系统架构视图规范，包含 13 个标准的 PlantUML 图表定义（覆盖用例图、类图、时序图、组件图、部署图、状态机等 11 类标准架构视图）。
- **`report-sample/GENERATION_REPORT.md`**：标准交付报告示例，展示完成生成后系统输出的质量指标、架构对齐分析及完整追溯矩阵。

---

## 使用方式

在 SpaceCode Agent 图形界面中：
1. 架构文档选择 `examples/inputs/Architecture_Documentation.md`；
2. UML 视图选择 `examples/inputs/Architecture_View.md`；
3. 指定本地空目录作为输出工作区，即可执行完整的解析与工程生成流程。
