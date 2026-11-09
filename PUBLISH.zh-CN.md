> 🌐 [English](PUBLISH.md) | **简体中文**

# 项目发布指南 (Publishing Guide)

本项目源码目录已配置完善的排除规则，构建产物、Python 虚拟环境、本地输出工件及临时会话日志均已通过 `.gitignore` 过滤，具备直接推送到代码托管平台的独立完整性。

---

## 1. 提交前检查与安全审查

在初始化提交前，请核验工作区状态：

```powershell
git status --short
git ls-files --others --exclude-standard
```

确认未暂存任何 `.env` 文件、构建生成的 `*.exe`、`.agent_state/` 缓存、虚拟环境及开发机绝对路径信息。

使用 PowerShell 进行敏感凭据快速扫描：

```powershell
Select-String -Path (Get-ChildItem -Recurse -File -Include *.py,*.md,*.json,*.yml,*.yaml,*.ps1) `
  -Pattern 'sk-[A-Za-z0-9]{20,}|BEGIN (RSA|OPENSSH) PRIVATE KEY' -Encoding UTF8
```

> **注意**：仓库内所有匹配 `sk-` 的字符串均属于单元测试 Mock 数据，不含生产敏感信息。

---

## 2. 仓库初始化与本地提交

```powershell
git init -b main
git add .
git commit -m "feat: initial public release of SpaceCode Agent"
```

若尚未配置 Git 身份信息：

```powershell
git config user.name "Your Name"
git config user.email "you@example.com"
```

---

## 3. 推送至 GitHub 远程仓库

使用 GitHub CLI 创建并推送：

```powershell
gh repo create space-code-agent --public --source=. --remote=origin --push
```

或在 GitHub 创建空仓库后关联远程分支推送：

```powershell
git remote add origin https://github.com/<your-account>/space-code-agent.git
git push -u origin main
```

---

## 4. 构建发布制品 (Artifacts)

**请勿将编译后的二进制可执行文件 `SpaceCodeAgent.exe`（约 58~64 MiB）直接提交至 Git 历史版本中**。推荐本地按需打包，或通过 GitHub Actions 自动化构建生成 Release 制品：

```powershell
# 本地构建命令
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1 -Clean
```

公开发布时，请将生成的 `dist\SpaceCodeAgent.exe` 作为附件上传至 GitHub **Releases** 页面。

---

## 5. 建议的仓库配置

- **项目描述 (Description)**: `Architecture-document-driven code agent for Windows (DeepSeek-V4-Pro, PySide6)`
- **标签 (Topics)**: `code-agent`, `deepseek`, `pyside6`, `python`, `code-generation`, `plantuml`
- **安全功能**: 开启 GitHub **Private vulnerability reporting**（私密漏洞报告）。
- **自动化依赖检测**: 启用 Dependabot 检测 pip 与 GitHub Actions 依赖安全更新。
