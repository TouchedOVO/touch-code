> 🌐 [English](CONTRIBUTING.md) | **简体中文**

# 贡献指南 (Contributing Guide)

感谢对 SpaceCode Agent 项目的关注与贡献。为保证代码质量与系统稳定性，请在提交代码前阅读并遵循以下规范。

---

## 1. 本地开发环境搭建

推荐在独立的 Python 虚拟环境中配置开发依赖：

```powershell
# 创建并激活虚拟环境
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 安装运行与开发依赖
pip install -r requirements.txt
pip install -e ".[dev]"
```

> **可选依赖**：若需在本地执行生成示例工程的自动化测试，需预先安装 Node.js ≥ 20。

---

## 2. 提交 Pull Request 前的质量检查

在提交 Pull Request 之前，必须确保本地所有测试用例均通过：

```powershell
python -m pytest tests -q
```

若变更涉及 `src/space_code_agent/samples/space_fractions` 目录下的示例工程代码，须执行对应的 Node.js 测试套件：

```powershell
cd src\space_code_agent\samples\space_fractions

# 单元测试与服务测试
node --test tests/unit/http.test.js tests/unit/schema.test.js tests/unit/persistence.test.js `
  services\question-service\tests\questions.test.js `
  services\game-service\tests\game.test.js `
  services\user-service\tests\auth.test.js

# 端到端测试
node --test tests\e2e\flow.test.js
```

---

## 3. 架构与编码规范

- **线程模型与 UI 解耦**：严格遵循 Controller 与 UI 的分离原则。所有 I/O 操作、模型推理及耗时计算必须交由 Worker 线程执行，严禁阻塞 GUI 主事件循环。
- **工作区安全边界**：所有文件读写与路径访问必须通过 `WorkspacePolicy` 校验，严禁绕过沙箱路径检查或直接进行非受控的文件操作。
- **工具调用契约**：新增工具必须声明标准 JSON Schema 参数规范，并统一返回结构化错误响应，严禁向外层的 Agent Loop 抛出未捕获的原始异常。
- **敏感信息脱敏**：禁止在日志、输出流中记录 API 密钥或原始 HTTP 请求头信息。所有面向前台展示或日志持久化的文本，均需通过 `SecretRedactor` 处理。
- **安全回归测试**：任何涉及路径穿越防御、文件覆盖保护、人工审批流程、Token 预算控制等核心安全逻辑的改动，必须包含完备的自动化测试。
- **零依赖约束**：生成的样例工程与内置示例代码须严格遵循零外部依赖原则，如确需引入第三方库，需在架构文档中提供完整的技术选型论据。
- **文档同步维护**：若功能实现、运行限制、预算阈值或测试用例集发生变更，必须同步修订 `docs/` 目录下的相关规范与状态文档。

---

## 4. 提交规范 (Commit Convention)

提交信息遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范，推荐前缀：

- `feat:` 新增功能
- `fix:` 缺陷修复
- `test:` 测试用例补充与调整
- `docs:` 文档变更
- `build:` 构建脚本或依赖调整
- `refactor:` 代码重构（不改变功能逻辑）

---

## 5. 开源许可

凡向本项目提交代码贡献，即代表同意将所贡献内容以 MIT 许可证授权发布。
