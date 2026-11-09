# Assumptions, Deviations and Document Conflicts

<!-- Requirement coverage: [FR-1] [NFR-1] [ASR-1] [ASR-2] [FR-DERIVED-1] [FR-DERIVED-2] [FR-DERIVED-3] -->

This file records every assumption, default value, documented conflict and major
architectural deviation used while implementing **Space Fractions**. It is part of
the deliverable and should be read together with `README.md` and
`docs/architecture-summary.md`.

## 1. Registered assumptions (from the architecture input)

| ID | Assumption | Implementation impact |
| --- | --- | --- |
| A1 | The game is played by 1000 concurrent users. | The server keeps per-game state in process memory. For a local demo this is sufficient; a production deployment would need a shared/session store. See deviation D-01. |
| A2 | The game is played for 1 hour per session. | Sessions are not time-limited in code because the game has a fixed question count and no countdown (`ASM-01`). A 1-hour session simply means the user can finish and replay within that window. |
| ASM-01 | Each game has exactly 10 fraction questions; +10 points for a correct answer, 0 for a wrong answer, maximum 100, no timer. | Implemented in `src/domain.js` via `QUESTION_COUNT_PER_GAME`, `POINTS_PER_CORRECT` and `MAX_SCORE`. |
| ASM-02 | Students do not register; a guest ID is generated at session start and the score is only for the current round. Administrators log in with an environment-configured token. | Implemented as `UserComponent.createGuest()` and `AdminComponent.authorize()`. Admin token comes from `ADMIN_TOKEN`. |
| ASM-03 | Questions are sixth-grade fraction arithmetic single-choice questions (4 options). Seed data is provided and admins can create/update/delete. | Implemented as `DEFAULT_SEED_QUESTIONS` plus admin CRUD routes. |
| ASM-04 | Start/end animation uses CSS transitions and text scenes, no external images/video. | The API returns state for the UI to animate. A minimal text-based help scene is returned by `GET /api/help`. |
| ASM-05 | Accessibility: keyboard operable, semantic markup, visible focus, color contrast >= 4.5:1. | No HTML shell is shipped in this backend-focused deliverable; the API responses are plain JSON. Any future UI must satisfy this. Recorded here so the constraint is not lost. |
| ASM-06 | Keep `Game`/`Question`/`User` service boundaries, run them as REST + in-process repositories. PostgreSQL is an optional adapter. Redis/RabbitMQ/Elasticsearch/Kubernetes/Istio/Vault/Terraform are **not** demo dependencies. | Implemented as a modular monolith. See deviation D-01. |

## 2. Parsing warnings from the architecture input

These warnings were present in the normalized input and are intentionally not
silently ignored.

| ID | Warning | How it is handled |
| --- | --- | --- |
| W-001 | `ObjectDiagram` used participant notation (closer to a sequence diagram). | Object instances `game1`, `question1`, `user1`, `admin1` are treated as object semantics and documented in `docs/architecture-summary.md`. |
| W-002 | `CollaborationDiagram1` used sequence-message notation (`->>`). | Treated as a collaboration between `User`, `Game` and `Question`. |
| W-003 | `CollaborationDiagram2` used sequence-message notation (`->>`). | Treated as a collaboration between `Admin` and `Question`. |
| W-004 | The traceability matrix contained only 3 sample rows and could not cover every FR/NFR/ASR. | A complete requirement-to-component/file matrix is provided in `docs/architecture-summary.md`. |
| W-005 | The test matrix was empty (no component coverage entered for Unit/Integration/Contract/E2E/Chaos). | Tests were implemented and mapped below; Chaos testing is explicitly out of scope for the demo. |
| W-006 | `ASR-2` (security) was referenced in the quality-attribute/test table but had no definition or trace row. | A working definition and acceptance criteria are provided in `docs/architecture-summary.md`. |
| W-007 | The technical stack listed Redis/RabbitMQ/Elasticsearch/Kubernetes/Istio/Vault/Terraform without business constraints. | Treated as optional extensions and excluded from the demo dependency set. See deviation D-01. |

## 3. Document conflicts

| ID | Severity | Conflict | Resolution |
| --- | --- | --- | --- |
| C-001 | medium | The architecture document claimed 11 PlantUML diagrams but 13 code blocks were parsed. | All diagram names are preserved in `docs/architecture-summary.md`; the count discrepancy has no runtime impact. |
| C-002 | medium | `ASR-2` (security) was referenced in the quality-attribute table but never formally defined. | Security is defined as: no correct answers leaked before answering, admin endpoints protected by a bearer token, timing-safe token comparison, request body size limits, and no secrets in responses. |
| C-003 | high | The test matrix was empty. | Implemented unit and end-to-end tests (`tests/domain.test.js`, `tests/e2e/flow.test.js`). |
| C-004 | low | `ObjectDiagram` uses participant syntax. | Normalized to object semantics; not reproduced as a runtime artifact. |
| C-005 | low | `CollaborationDiagram1` uses sequence-message syntax. | Normalized to collaboration semantics. |
| C-006 | low | `CollaborationDiagram2` uses sequence-message syntax. | Normalized to collaboration semantics. |
| C-007 | low | Sequence and collaboration diagrams have duplicate versions. | Only the two message flows (`User -> Game -> Question`, `Admin -> Question`) are implemented; duplicates are documentation noise. |
| C-008 | high | Heavy components (Redis/RabbitMQ/Elasticsearch/Kubernetes/Istio/Vault/Terraform) were recommended without business constraints or an operations budget. | All are declared optional extensions and are **not implemented**. |

## 4. Major architectural deviation

### D-01: Microservices -> modular monolith

The architecture input requested a microservices style with cloud-based
infrastructure. The approved implementation plan deliberately falls back to a
**modular monolith**:

- One Node.js process exposes a REST API built with `node:http`.
- `GameComponent`, `QuestionComponent`, `UserComponent` and `AdminComponent`
  are separate modules/classes with explicit boundaries inside `src/domain.js`.
- Persistence is in-memory. The `InMemoryQuestionRepository` is the seam where a
  future PostgreSQL adapter could be plugged in by implementing the same methods.
- No Redis, RabbitMQ, Elasticsearch, Kubernetes, Istio, Vault or Terraform are
  required or used.

**Reason:** the business rules for a sixth-grade fraction game do not require a
distributed system, and a zero-dependency implementation can be run and verified
on an ordinary development machine. This deviation is visible in the code layout,
`README.md`, this file, and the delivery summary.

### D-02: Optional PostgreSQL adapter is not implemented

The approved plan lists "in-memory with optional PostgreSQL adapter". The adapter
is intentionally left as a documented extension point rather than shipped code,
because shipping a working PostgreSQL client would add a runtime dependency and
require a running database for the test suite. The repository interface is the
only persistence boundary and is isolated in `src/domain.js`.

## 5. Defaults

| Item | Default | Notes |
| --- | --- | --- |
| Port | `3000` | Override with `PORT`. |
| Admin token | `dev-admin-token` when `ADMIN_TOKEN` is unset | Demo-only fallback so `npm start` works out of the box. Never use it outside local development. |
| Questions per game | `10` | `QUESTION_COUNT_PER_GAME` in `src/domain.js`. |
| Points per correct answer | `10` | Max score is `100`. |
| Question option count | `4` | Enforced by validation. |
| Body size limit | `64 KiB` | Protects the in-process server from oversized requests. |

## 6. Explicitly out of scope / not implemented

- Persistent database storage (PostgreSQL adapter) — not implemented; repository seam provided.
- User registration, passwords, sessions, OAuth — students use guest IDs by design.
- Countdown timers, leaderboards, multiplayer/competitive mode — not in the accepted requirements.
- A full HTML/CSS/JavaScript client application — this deliverable is the REST API plus domain model.
- Chaos testing and load testing — not implemented for the demo.
- Redis/RabbitMQ/Elasticsearch/Kubernetes/Istio/Vault/Terraform — optional extensions, not implemented.

## 7. Test execution status

The automated tests in `tests/domain.test.js` and `tests/e2e/flow.test.js` were
run with `node --test` (`run_tests` profile `node`). Result: **19/19 passed**
(15 unit/domain tests + 4 end-to-end HTTP tests), exit code 0.
