> 🌐 [English](architecture-summary.md) | **简体中文**

# 系统架构设计摘要 (Architecture Summary)

<!-- Covers: FR-1, FR-DERIVED-1, FR-DERIVED-2, FR-DERIVED-3, NFR-1, ASR-1, ASR-2 -->

本文档系统梳理 Space Fractions 系统的架构视图映射、组件划分与接口协议规范。

---

## 1. 架构基准输入

- **`Architecture_Documentation.md`**：系统功能需求（FR）、非功能质量属性（NFR/ASR）、组件划分、API 契约及运维模型。
- **`Architecture_View.md`**：涵盖 13 个 PlantUML 架构图表，覆盖 11 类标准软件架构视图（用例图、类图、对象图、状态机、活动图、时序图、协作图、包图、组件图、部署图、容器图）。

---

## 2. 核心组件划分与工程映射

| 架构逻辑组件 | 工程实现路径 | 核心业务职责与技术契约 |
|---|---|---|
| **GameComponent** | `services/game-service` | 答题会话创建、单题答案比对、得分实时累加、结算报告生成 |
| **QuestionComponent** | `services/question-service` | 种子题库管理、管理员 CRUD API、题库检索与标准答案核验 |
| **UserComponent** | `services/user-service` | 免注册访客会话分配、管理员登录鉴权、Bearer Token 生成与校验 |
| **WebUI / Gateway** | `public/` & 聚合入口 | 单页前端界面承载、静态资源分发、跨域与统一路由代理 |

---

## 3. 架构设计决策与技术权衡 (Design Trade-offs)

1. **服务解耦与运行模式**：严格遵循微服务架构的边界划分规范，业务逻辑高度内聚；在开发及检验环境中，通过轻量级 HTTP 监听机制降低对外部复杂容器网络的依赖。
2. **轻量化原生技术栈**：全部基于 Node.js 原生标准库实现，避免引入外部第三方重型框架，保障极高的启动速度与跨平台一致性。
3. **数据一致性保障**：采用基于文件系统的原子写入协议（Write-to-temp then rename），在保证轻量化的同时达成数据持久化与服务重启自愈契约。
