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
- 82 pytest tests covering parsing, security, tools, provider retries, cancellation, budgets,
  repair-on-rejection, Mock end-to-end and GUI smoke.

### Known limitations

- Real DeepSeek API end-to-end was not executed in the build environment because no API key was
  available; the report marks this as `not run`.
- The generated demo uses `node:http` instead of Express and in-memory repositories instead of a live
  PostgreSQL cluster; see the generated `ASSUMPTIONS.md` (major deviation).
- Session-resume UI, diff preview and streaming reasoning display are not implemented.
