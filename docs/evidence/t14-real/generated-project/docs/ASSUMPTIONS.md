# Assumptions and Deviations

This document records the assumptions, unspecified requirements, document
conflicts, and significant deviations that were resolved during
implementation of Space Fractions.

## Registered assumptions

| ID | Assumption | Implementation effect |
| --- | --- | --- |
| A1 | The game will be played by 1000 users concurrently. | The in-process game registry is O(1) per request and the static/API path is stateless except for files. A real 1000-user deployment would put the app behind multiple Node.js workers and a shared store; this demo verifies functional correctness, not load at that scale. |
| A2 | The game will be played for 1 hour per session. | No server-side timeout is enforced; a session is 10 questions regardless of wall-clock time. |
| ASM-01 | 10 questions per game, +10 correct / 0 wrong, max 100, no timer. | Implemented in `src/domain/game.js`. |
| ASM-02 | No student registration; guest ID generated at session start. Admin uses an environment-configured token. | Guest IDs come from `POST /api/users/guest`. Admin token comes from `ADMIN_TOKEN`. |
| ASM-03 | Sixth-grade fraction four-operation single-choice questions with 4 options; seeded data; admin CRUD. | Seed data in `data/seed-questions.json`; admin CRUD in `src/routes/question.routes.js`. |
| ASM-04 | Start/end animation via CSS transitions and text scenes, no external media. | Implemented in `public/styles.css` and view transitions in `public/app.js`. |
| ASM-05 | Accessibility: keyboard operation, semantic labels, visible focus, contrast >= 4.5:1. | Semantic sections/fieldset, `focus-visible`, skip link, ARIA live regions, and a high-contrast palette. |
| ASM-06 | Preserve Game/Question/User service boundaries; run as REST + in-process repositories. PostgreSQL optional adapter; Redis/RabbitMQ/Elasticsearch/Kubernetes/Istio/Vault/Terraform excluded. | Three service modules in one process; JSON file repositories. |

## Major deviation from the architecture document

The architecture document specifies a microservices style and cloud-based
infrastructure. This implementation deliberately ships a **modular monolith**
with separate Game, Question, and User service modules and REST route
boundaries inside a single Node.js process. Rationale: the document does not
provide business constraints or an operations budget for the recommended
heavy components, and the local verification environment cannot guarantee
PostgreSQL, Redis, RabbitMQ, Kubernetes, Istio, Vault, or Terraform are
available.

Consequences:

- The three service boundaries are kept as independently readable modules and
  route mount points (`src/services/*.js`, `src/routes/*.js`).
- Persistence uses a durable JSON file store with atomic rename-based writes
  instead of PostgreSQL.
- Deployment is a single `npm start` process instead of multiple cloud
  containers.
- The documented Express.js web framework is replaced by a small zero-dependency
  HTTP adapter (`src/http.js`) built on Node's `http` module. This keeps the
  REST routes and middleware structurally identical while allowing the test
  suite to run without an `npm install` step.

## Diagram parsing warnings (not silently ignored)

| ID | Warning | Handling |
| --- | --- | --- |
| W-001 | `ObjectDiagram` used participant notation (more like a sequence diagram). | Object semantics (`game1`, `question1`, `user1`, `admin1`) were extracted; the unusual notation is treated as source syntax only. |
| W-002 | `CollaborationDiagram1` used sequence message notation (`->>`). | Collaboration semantics (User, Game, Question) were extracted. |
| W-003 | `CollaborationDiagram2` used sequence message notation (`->>`). | Collaboration semantics (Admin, Question) were extracted. |
| W-004 | Traceability matrix has only 3 sample rows and cannot cover all FR/NFR/ASR. | Requirements were traced from the requirement list and per-test `Covers:` comments instead. |
| W-005 | Test matrix is empty (Unit/Integration/Contract/E2E/Chaos coverage not filled). | A concrete test suite was produced; coverage is documented in `README.md`. |
| W-006 | ASR-2 is referenced in quality/test tables but has no formal definition or trace row. | ASR-2 was interpreted as security: admin token auth, input validation, defensive headers, and no answer leakage. |
| W-007 | Redis/RabbitMQ/Elasticsearch/Kubernetes/Istio/Vault/Terraform appear without business constraints. | Treated as optional extensions and excluded from demo dependencies. |

## Document conflicts

| ID | Severity | Conflict | Resolution |
| --- | --- | --- | --- |
| C-001 | medium | Document claims 11 PlantUML diagrams; 13 code blocks were parsed. | The implementation is driven by the requirement list and component table, not by the diagram count. |
| C-002 | medium | ASR-2 (security) has no formal definition or acceptance metric. | Security is defined and tested as token authentication, validation, headers, and non-leakage of answers. |
| C-003 | high | Test matrix is empty. | A full automated test suite was authored (see `test/`). |
| C-004 | low | ObjectDiagram uses participant syntax. | See W-001. |
| C-005 | low | CollaborationDiagram1 uses sequence message syntax. | See W-002. |
| C-006 | low | CollaborationDiagram2 uses sequence message syntax. | See W-003. |
| C-007 | low | Multiple sequence/collaboration diagrams are highly duplicated. | No extra functionality was invented from the duplicates. |
| C-008 | high | Heavy components are recommended without business or budget constraints. | Excluded as optional; documented as a major deviation above. |

## Explicitly not implemented

- Microservice network separation (separate containers/processes per service).
- PostgreSQL, Redis, RabbitMQ, Elasticsearch, Kubernetes, Istio, Vault, and
  Terraform deployment artifacts.
- Authentication/authorization for students (guest-only by design).
- Resume of an in-progress game after a server restart. Completed scores and
  question data are durable; in-memory game state is intentionally
  session-scoped.
- A production admin UI. Administration is provided through the REST API.

## Security notes

- The default `ADMIN_TOKEN` is a development convenience only. Set a strong
  `ADMIN_TOKEN` before any non-local deployment.
- The `.env.example` file contains variable names only, never real secrets.
- Token comparison uses a constant-time SHA-256 digest comparison.
