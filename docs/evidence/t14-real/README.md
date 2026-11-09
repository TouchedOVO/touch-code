# T14 — Real DeepSeek-V4-Pro run (browser UI + persistence)

**Date:** 2026-11-09  
**Endpoint:** `https://api.deepseek.com`  
**Requested / returned model:** `deepseek-v4-pro` / `deepseek-v4-pro`  
**Mode:** real API (not Mock)  
**Agent status:** `completed`  
**Functional acceptance:** **PASS** for browser UI, persistence, interactive flow and tests  
**Remaining external check:** T15 clean Windows VM (EXE), not covered by this evidence.

## Command

```powershell
$env:DEEPSEEK_API_KEY = "<user-level environment variable>"
python -m space_code_agent --run .\out\t14-real `
  --doc .\examples\inputs\Architecture_Documentation.md `
  --uml .\examples\inputs\Architecture_View.md --allow-tests --max-steps 80
```

## Measured result

| Metric | Value |
|---|---|
| Agent steps / tool calls / requests | 75 / 114 / 75 |
| Input / output / cached / reasoning tokens | 2,525,691 / 91,059 / 2,370,432 / 51,670 |
| Total tokens | **2,616,750** |
| Estimated cost | **$0.148089** |
| Agent elapsed / report wall time | 1,375.4 s / 1,720.1 s |
| Static checks | structure / JSON / Python / JS / links / traceability all pass |
| Delivery contracts | deliverables / JSON / traceability / **web_ui** / **persistence** all pass |
| Generated test suite | **27 / 27 passed** (Node 22, exit 0) |
| Traceability | 7/7 mapped, 7/7 verified with per-requirement `Covers:` evidence |
| Browser E2E | **PASS** — Edge headless: menu → help → 10 answers → result screen (10 / 100) |

## What the model produced

```text
generated-project/
├── README.md / package.json / .env.example
├── docs/ASSUMPTIONS.md
├── public/
│   ├── index.html        # intro, menu, question, score/result, help scenes
│   ├── app.js            # state machine + REST calls
│   └── styles.css        # responsive, keyboard/ARIA styles
├── src/
│   ├── app.js / server.js / http.js / config.js
│   ├── domain/fraction.js / game.js
│   ├── repositories/file-store.js / question.repository.js / score.repository.js
│   ├── routes/game.routes.js / question.routes.js / user.routes.js
│   └── services/game.service.js / question.service.js / user.service.js
├── data/seed-questions.json
└── test/                 # 27 tests incl. persistence-restart and API E2E
```

- **Browser UI** covers opening/menu, game play, score/result and help, and calls the REST API.
- **Persistence** uses a JSON file store with temp-file + rename; a restart test recreates the app from
  the same files and verifies questions and completed scores survive.
- **Tests** explicitly annotate `Covers:` requirement IDs, enabling per-requirement verification.

## Real-model behavior observed

1. First plan attempt referenced assumption IDs (`ASM-04`, `ASM-05`) in `requirement_ids`; the validator
   rejected it and the model’s second plan was accepted (9 tasks / 31 files).
2. First implementation used Express; tests failed with `Cannot find module 'express'` in the sandbox.
   The controller fed the failure back, and the model completed **repair round 1** by replacing Express
   with a zero-dependency `node:http` adapter, then all 27 tests passed.
3. The model explicitly documented deviations: modular monolith instead of deployed microservices;
   Express replaced; PostgreSQL/Redis/RabbitMQ/Elasticsearch/K8s/Istio/Vault/Terraform optional.

## Evidence files

| File | Content |
|---|---|
| `GENERATION_REPORT.md` | Sanitized report from the real run |
| `traceability_matrix.csv` | Requirement → file/test matrix |
| `run_manifest.json` | Tokens, statuses, checks, tests, file hashes |
| `test-output.txt` | Independent `node --test` output (27 passed) |
| `browser-e2e.json` | Browser E2E result (Edge/Playwright) |
| `browser-e2e.png` | Result screen screenshot |
| `run-events.txt` | Sanitized agent event log |
| `generated-project/` | Files written by the real model |

Absolute local paths, session IDs and credentials were removed/replaced. No API key is present.
