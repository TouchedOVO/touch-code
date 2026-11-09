> 🌐 **English** | [简体中文](CONTRIBUTING.zh-CN.md)

﻿# Contributing

Thanks for your interest in SpaceCode Agent.

## Development setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e ".[dev]"
```

Optional: Node.js ≥ 20 to run the generated sample project's tests.

## Before opening a pull request

```powershell
python -m pytest tests -q
```

Please also run the sample tests if you changed anything under
`src/space_code_agent/samples/space_fractions`:

```powershell
cd src\space_code_agent\samples\space_fractions
node --test tests/unit/http.test.js tests/unit/schema.test.js tests/unit/persistence.test.js `
  services\question-service\tests\questions.test.js `
  services\game-service\tests\game.test.js `
  services\user-service\tests\auth.test.js
node --test tests\e2e\flow.test.js
```

## Guidelines

- Keep the controller/UI separation: blocking work belongs in the worker thread, not the GUI thread.
- Any new file operation must go through `WorkspacePolicy`; do not bypass path checks.
- Any new tool must declare a JSON schema and return structured errors, never raise raw exceptions to
  the agent loop.
- Never log API keys or raw request headers. Use `SecretRedactor` for user-visible text.
- Add tests for security-relevant changes (path traversal, overwrite protection, approval, budgets).
- Keep generated sample code zero-dependency unless a dependency is clearly justified.
- Update `docs/` when behavior, limits or test counts change.

## Commit messages

Conventional prefixes are appreciated: `feat:`, `fix:`, `test:`, `docs:`, `build:`, `refactor:`.

## License

By contributing, you agree that your contributions are licensed under the MIT License.
