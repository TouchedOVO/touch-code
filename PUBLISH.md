# Publishing this repository to GitHub

This folder is already a clean, self-contained source tree. Binaries, virtual environments, local
outputs and session logs are excluded by `.gitignore`.

## 1. Review before publishing

```powershell
git status --short
git ls-files --others --exclude-standard
```

Make sure no `.env`, `*.exe`, `.agent_state/`, virtual environment or personal path is staged.

Quick secret scan (PowerShell):

```powershell
Select-String -Path (Get-ChildItem -Recurse -File -Include *.py,*.md,*.json,*.yml,*.yaml,*.ps1) `
  -Pattern 'sk-[A-Za-z0-9]{20,}|BEGIN (RSA|OPENSSH) PRIVATE KEY' -Encoding UTF8
```

The only `sk-` strings in this repo are clearly fake unit-test values.

## 2. Initialize and commit

```powershell
git init -b main
git add .
git commit -m "feat: initial public release of SpaceCode Agent"
```

If Git asks for an identity:

```powershell
git config user.name "Your Name"
git config user.email "you@example.com"
```

## 3. Create the GitHub repository

With GitHub CLI:

```powershell
gh repo create space-code-agent --public --source=. --remote=origin --push
```

Or manually create an empty public repository on GitHub, then:

```powershell
git remote add origin https://github.com/<your-account>/space-code-agent.git
git push -u origin main
```

## 4. Build artifacts

Do **not** commit `SpaceCodeAgent.exe` (about 58 MiB). Build it locally or let the
`Windows build` GitHub Action run and download the artifact:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1 -Clean
```

For a public download, attach `dist\SpaceCodeAgent.exe` to a GitHub **Release** rather than the source
tree.

## 5. Suggested repository settings

- Description: `Architecture-document-driven code agent for Windows (DeepSeek-V4-Pro, PySide6)`
- Topics: `code-agent`, `deepseek`, `pyside6`, `python`, `code-generation`, `plantuml`
- Enable **Private vulnerability reporting** (see `SECURITY.md`).
- Enable Dependabot for pip and GitHub Actions.
