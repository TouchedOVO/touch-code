> 🌐 [English](SECURITY.md) | **简体中文**

# 安全策略 (Security Policy)

本项目高度重视软件系统的安全性。在开发、构建及使用 SpaceCode Agent 时，请遵循以下安全准则。

---

## 1. 漏洞反馈通道

若发现潜在的安全漏洞，**请勿通过公开 Issue 提交**。请使用 GitHub 官方提供的 [私密漏洞报告 (Private Vulnerability Reporting)](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities) 渠道进行反馈。

反馈时请附带：
- 漏洞影响版本；
- 最小化复现步骤（PoC）；
- 潜在安全威胁评估。

---

## 2. 凭据管理与脱敏规范

- **API 密钥安全**：严禁将真实的 DeepSeek API 密钥硬编码或提交至版本控制系统。SpaceCode Agent 仅在内存中临时驻留密钥，且在所有日志、交付报告与 `run_manifest.json` 导出中均通过 `SecretRedactor` 执行动态脱敏。
- **环境配置文件**：`.env.example` 仅作为模板保留占位符，禁止将包含真实凭据的 `.env` 文件提交至代码仓库。
- **泄漏应急响应**：若发生凭据意外泄露，请立即前往 [DeepSeek 开放平台](https://platform.deepseek.com/api_keys) 吊销并轮换该密钥。

---

## 3. 代码生成与执行安全模型

SpaceCode Agent 在用户显式指定的工作区目录（Workspace）内生成工程文件，并内置有限的测试命令调用能力（仅限白名单中的 `node --test`、`npm test`、`pytest`）。系统通过静态安全策略与沙箱路径规则进行约束，但并不等同于操作系统级内核沙箱（OS-level Sandbox）。

为确保宿主机环境安全，请遵循以下原则：
- **运行权限最小化**：严禁以操作系统管理员或高权限账号（Administrator / root）运行生成的工程代码。
- **人工审查机制**：在执行生成工程中的测试或构建脚本前，务必审查 `package.json` 中的 scripts 及对应测试代码。
- **命令受控执行**：外部命令执行能力默认处于禁用状态，仅在用户显式授权且充分信任生成产物时开启。

---

## 4. 版本支持策略

| 版本系列 | 维护状态 | 安全更新支持 |
|---|---|---|
| 1.x | 活跃维护中 | 支持 |

---

## 5. 样例工程安全范围

内置的 Space Fractions 演示工程仅作为教学与离线测试样例，其预设的开发 Token 与测试凭据均为占位符，严禁直接用于生产部署。
