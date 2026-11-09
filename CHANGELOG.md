> 🌐 **English** | [简体中文](CHANGELOG.zh-CN.md)

# Changelog

## 1.0.0 — 2026-11-09

Initial public release.

### Added

- PySide6 desktop application with API key handling, input validation, progress, logs, file inventory,
  validation results, report preview, stop/cancel and open-output actions.
- DeepSeek-V4-Pro Responses API provider with function calling, reasoning effort, bounded retries,
  token/cost accounting and secret redaction.
- Markdown + PlantUML parser (13 blocks, 11 view types), Pydantic requirement model, conflict and
  assumption tracking.
- Bounded plan → execute → observe → verify agent loop with 8 tools, workspace path policy, atomic
  writes, JSON-schema validation and completion gating.
- Delivery validator, static checks, approved test runner, repair loop, traceability CSV and
  machine-readable run manifest.
- Built-in zero-dependency Space Fractions sample (33 files, 16 Node tests) for offline Mock runs.
- PyInstaller one-file/one-dir build script, icon, version metadata and Windows CI workflow.
  CI run [#6](https://github.com/TouchedOVO/touch-code/actions/runs/42640206235) passes Python tests,
  Node 22 tests, EXE build, smoke test and uploads the `SpaceCodeAgent-windows-x64` artifact.
- 84 pytest tests covering parsing, security, tools, provider retries, cancellation, budgets,
  repair-on-rejection, Mock end-to-end and GUI smoke.
- Browser UI + persistence contracts, per-requirement `Covers:` test evidence and a real T14
  browser E2E under `docs/evidence/t14-real/`.

### Known limitations

- A real `deepseek-v4-pro` run is included under `docs/evidence/t14-real/`. It generated a browser UI,
  restart-safe question/score persistence and 27/27 passing tests, with one automatic repair round.
- The generated demo uses a modular monolith, `node:http` and file-backed JSON persistence instead of
  deployed microservices and a PostgreSQL cluster; see the generated `ASSUMPTIONS.md` (major deviation).
- T15 clean-runner job removes Python/Qt and runs the EXE smoke, GUI launch and full Mock generation
  with generated tests; manual double-click on a desktop VM remains optional.
- Session-resume UI, diff preview and streaming reasoning display are not implemented.
