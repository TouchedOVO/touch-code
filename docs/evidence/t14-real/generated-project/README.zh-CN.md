> 🌐 [English](README.md) | **简体中文**

# Space Fractions（六年级分数智能练习系统）

Space Fractions 是一款面向六年级学生的 Web 端互动式分数运算练习系统。学生通过答题练习强化分数加减乘除技能，每套会话包含 10 道题目，每题答对计 10 分，满分为 100 分。系统配套提供基于令牌鉴权的管理员 REST API，支持题库的动态维护与管理。

本项目基于 Node.js 原生模块构建，采用内置的 `node:http` 实现 REST 服务与静态资源承载。在架构实现上，完整保留了架构文档中定义的“游戏 (Game)”、“题目 (Question)”和“用户 (User)”三大服务边界，并在单进程模块化单体架构（Modular Monolith）下协同运行，确保在无需外部云服务依赖的环境下即可独立部署与验收验证。具体的架构设计假设与技术选型决策详见 [`docs/ASSUMPTIONS.md`](docs/ASSUMPTIONS.md)。

---

## 核心特性 (Features)

- **交互式 Web 前端界面**：包含欢迎向导、功能主菜单、交互式答题面板、结算报告及帮助说明。
- **无障碍与全键盘交互**：支持 Tab 键焦点导向、高对比度色彩适配及语义化 ARIA 标签规范。
- **练习与计分机制**：每轮练习由 10 道随机分数单选题组成；答对单题计 10 分，答错计 0 分，满分 100 分。
- **免注册游客模式**：学生端支持一键生成临时游客凭证开启答题，简化操作门槛。
- **可靠的文件级状态持久化**：针对题库及答题记录提供基于原子化写入（临时文件 + 重命名）的 JSON 文件存储，支持服务异常重启后的数据自愈恢复。
- **题库管理 REST API**：提供基于 HTTP Bearer Token 鉴权的题目增删改查（CRUD）接口。
- **完备的自动化测试体系**：内置 27 项自动化测试用例，覆盖服务重启数据一致性验证与端到端核心交互链路。

---

## 快速上手与运行 (Quick Start)

### 1. 环境依赖
- Node.js ≥ 20.0.0（无需安装第三方 npm 外部依赖包）。

### 2. 启动服务
```bash
# 采用默认配置启动服务（监听端口 3000）
node src/server.js
```

服务启动后，在浏览器中访问：`http://localhost:3000`

### 3. 执行自动化测试
```bash
# 执行全部 27 项测试套件
node --test test/*.test.js
```

---

## REST API 接口规范

### 用户与认证
- `POST /api/users/guest`：生成免注册临时学生游客身份。

### 题目服务
- `GET /api/questions/random?count=10`：随机拉取 10 道分数运算题目。
- `POST /api/questions`：新增题目（需携带 `Authorization: Bearer <ADMIN_TOKEN>` 请求头）。
- `PUT /api/questions/:id`：修改题目（需管理员鉴权）。
- `DELETE /api/questions/:id`：删除题目（需管理员鉴权）。

### 答题与结算
- `POST /api/games/session`：初始化答题会话。
- `POST /api/games/session/:id/submit`：提交单题答案并实时计算得分。
- `GET /api/games/session/:id/result`：拉取练习结算报告与详细解析。

---

## 架构与选型说明

本系统的架构权衡、技术决策与需求追溯细节请参阅：
- [架构设计假设与选型记录 (ASSUMPTIONS.md)](docs/ASSUMPTIONS.md)
