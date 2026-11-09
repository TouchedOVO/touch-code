# T14 — Real DeepSeek-V4-Pro run

**Date:** 2026-11-09  
**Endpoint:** `https://api.deepseek.com`  
**Requested model:** `deepseek-v4-pro`  
**Returned model:** `deepseek-v4-pro`  
**Mode:** real API (not Mock)  
**Agent status:** `completed`  
**Functional acceptance:** **PARTIAL** — the generated project has no browser UI (see gaps below)

## Command

```powershell
$env:DEEPSEEK_API_KEY = "<user-level environment variable>"
python -m space_code_agent --run .\out\t14-real `
  --doc .\examples\inputs\Architecture_Documentation.md `
  --uml .\examples\inputs\Architecture_View.md --allow-tests
```

## Measured result

| Metric | Value |
|---|---|
| Agent steps / tool calls | 37 / 57 |
| Model requests | 37 |
| Input tokens | 1,370,537 (cached 1,296,512) |
| Output tokens | 58,339 (reasoning 31,703) |
| Total tokens | 1,428,876 |
| Estimated cost | **$0.081532** |
| Agent elapsed | 898.96 s |
| Generated files | 15 (including reports), 12 source/doc files |
| Static checks | structure/json/python/js/links/traceability all pass |
| Generated test suite | **19 / 19 passed** (Node.js 22, exit 0) |
| Traceability | 7/7 mapped, 7/7 verified (file/test mapping) |

## What was generated

```text
generated-project/
├── .env.example
├── package.json
├── README.md
├── requirements.json / requirements.md
├── requirements-traceability.json
├── docs/
│   ├── ASSUMPTIONS.md
│   ├── architecture-summary.md
│   ├── requirements.md / requirements.json
│   └── requirements-traceability.md
├── src/
│   ├── domain.js          # game/question/user/admin domain logic
│   └── index.js           # node:http REST API
└── tests/
    ├── domain.test.js
    └── e2e/flow.test.js
```

The REST API implements Play Game, View Score, Update Questions, View Help, pause/resume/reset,
and admin bearer-token protection. The generated test suite passes.

## Important gaps (why this is not a full pass)

1. **No browser UI was generated.** The generated README states it is a backend REST API and a
   future browser client can consume the endpoints. The task describes a web-based interactive
   learning tool; the UI/accessibility assumptions are therefore not implemented. Its own
   `docs/ASSUMPTIONS.md` records “No HTML shell is shipped in this backend-focused deliverable”.
2. **The planner failed twice** (one non-JSON response, one malformed JSON response), so the
   controller used the deterministic fallback plan. The implementation itself was still produced
   by the real model.
3. **Coverage numbers are file/test mappings**, not a manual functional certification. The
   validator found files and tests per requirement, but it cannot prove that every intended
   user-facing behavior exists.
4. The model chose a **modular monolith** and in-memory repositories instead of the documented
   microservice/cloud topology; this is explicitly recorded in the generated assumptions.

## Evidence files

| File | Content |
|---|---|
| `GENERATION_REPORT.md` | Sanitized report from the real run |
| `traceability_matrix.csv` | Requirement → file/test matrix |
| `run_manifest.json` | Machine-readable run record, tokens, tests, file hashes |
| `test-output.txt` | Independent `node --test` output (19 passed) |
| `run-events.log` | Sanitized agent event log |
| `generated-project/` | The files the real model wrote |

Absolute local paths, session IDs and credentials were replaced/removed before publication.
No API key is present in these files.
