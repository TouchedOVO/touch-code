> 🌐 [English](README.md) | **简体中文**

# Space Fractions（六年级分数智能练习系统）

Space Fractions 是一款面向小学六年级学生的 Web 端分数运算学习系统，由 **SpaceCode Agent** 依据 `Architecture_Documentation.md` 与 `Architecture_View.md` 自动化生成。

学生用户可通过浏览器完成系统向导、主菜单选择、10 道分数运算题目作答以及练习成绩结算；系统同时提供基于安全令牌的管理员 REST 接口，用于题库的维护管理。

---

## 1. 系统架构与服务边界

本系统在代码实现层面完整继承并落实了架构设计中定义的三大核心业务服务边界，并在单机环境下通过轻量级服务架构进行协同，确保零外部依赖即可完成全流程运行与测试：

| 服务模块 | 默认端口 | 职责定位 |
|---|---:|---|
| **`question-service`** | 4001 | 题库管理、管理员 CRUD 接口、内部标准答案校验查询 |
| **`game-service`** | 4002 | 答题会话生命周期、单题答案判定、计分结算与最终报告 |
| **`user-service`** | 4003 | 免注册学生访客会话管理、管理员认证与 Bearer Token 鉴权 |

在单机演示模式下，`gateway-service` 将作为聚合接入层（监听端口 3000），负责托管前端静态单页应用并执行 API 请求的反向代理。

---

## 2. 核心特性

- **零外部依赖**：基于 Node.js 原生标准库（`node:http`）实现，无需执行 `npm install` 引入第三方重型框架。
- **全键盘与无障碍支持**：遵循 Web 无障碍规范（WCAG 2.1 AA），具备良好的 Tab 键焦点流转与高对比度显示。
- **高可靠文件持久化**：采用具备原子写入能力（临时文件写入 + 原子重命名）的文件存储引擎，支持服务重启后的数据恢复。
- **内置基准测试集**：配套提供 19 项 Node.js 单元测试、集成测试与端到端测试，开箱即测。

---

## 3. 快速启动与运行

### 3.1 运行前置条件
- Node.js ≥ 20.0.0

### 3.2 启动各微服务
```powershell
# 启动题目服务
node services/question-service/src/index.js

# 启动游戏服务
node services/game-service/src/index.js

# 启动用户服务
node services/user-service/src/index.js
```

### 3.3 执行自动化测试
```powershell
# 运行单元与集成测试
node --test tests/unit/http.test.js tests/unit/schema.test.js tests/unit/persistence.test.js `
  services/question-service/tests/questions.test.js `
  services/game-service/tests/game.test.js `
  services/user-service/tests/auth.test.js

# 运行业务端到端测试
node --test tests/e2e/flow.test.js
```

---

## 4. 架构设计与选型参考

- [系统架构摘要 (architecture-summary.md)](docs/architecture-summary.md)
- [架构设计假设与技术选型记录 (ASSUMPTIONS.md)](docs/ASSUMPTIONS.md)
