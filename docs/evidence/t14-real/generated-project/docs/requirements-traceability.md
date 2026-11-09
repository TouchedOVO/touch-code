# Requirements Traceability

This matrix maps each requirement from the architecture input to the files that
implement or verify it.

| Requirement | Component(s) | Implementation / verification files |
| --- | --- | --- |
| FR-1 — Play game | `GameComponent`, `QuestionComponent`, `UserComponent` | `src/domain.js`, `src/index.js`, `tests/domain.test.js`, `tests/e2e/flow.test.js` |
| NFR-1 — Performance | `GameComponent` | `src/domain.js`, `src/index.js`, `tests/e2e/flow.test.js` |
| ASR-1 — Data durability | `QuestionComponent` | `src/domain.js`, `tests/domain.test.js` |
| ASR-2 — Security | `GameComponent`, `AdminComponent` | `src/domain.js`, `src/index.js`, `.env.example`, `tests/domain.test.js`, `tests/e2e/flow.test.js` |
| FR-DERIVED-1 — View Score | `GameComponent`, `UserComponent` | `src/domain.js`, `src/index.js`, `tests/domain.test.js`, `tests/e2e/flow.test.js` |
| FR-DERIVED-2 — Update Questions | `QuestionComponent`, `AdminComponent` | `src/domain.js`, `src/index.js`, `tests/domain.test.js`, `tests/e2e/flow.test.js` |
| FR-DERIVED-3 — View Help | `UserComponent` | `src/domain.js`, `src/index.js`, `tests/e2e/flow.test.js` |

See `docs/architecture-summary.md` for the normalized diagram mappings and
`docs/ASSUMPTIONS.md` for assumptions, conflicts and deviations.
