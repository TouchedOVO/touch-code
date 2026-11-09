# Space Fractions — Architecture Summary

<!-- Requirement coverage: [FR-1] [NFR-1] [ASR-1] [ASR-2] [FR-DERIVED-1] [FR-DERIVED-2] [FR-DERIVED-3] -->

This document summarizes the implemented architecture, the normalized diagram
views, and requirement traceability for the **Space Fractions** project.

## 1. Architectural style

The original input requested a microservices style deployed on cloud
infrastructure. After the approved fallback plan, the project is implemented as a
**modular monolith**:

- Runtime: Node.js >= 20 (no third-party runtime dependencies).
- Web framework: built-in `node:http` (RESTful JSON API).
- Persistence: in-memory repositories with an optional PostgreSQL adapter seam.
- Testing: built-in `node:test`.

The `Game`, `Question`, `User` and `Admin` boundaries are preserved as separate
classes inside `src/domain.js`, so the logical component diagram is still valid
even though the physical deployment is a single process.

## 2. Component responsibilities

| Component | Responsibility | Implementation |
| --- | --- | --- |
| `GameComponent` | Starts games, selects questions, accepts answers, computes score, manages `Playing`/`Paused`/`GameOver` state. | `GameComponent` and `Game` in `src/domain.js`. |
| `QuestionComponent` | Stores and validates questions; exposes CRUD and random question selection. | `QuestionComponent` and `InMemoryQuestionRepository` in `src/domain.js`. |
| `UserComponent` | Creates guest identities and returns help content. | `UserComponent` in `src/domain.js`. |
| `AdminComponent` | Authenticates the admin token for protected question-management operations. | `AdminComponent` in `src/domain.js`. |

## 3. REST API surface

All routes are JSON unless noted.

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| `GET` | `/` | public | Service information. |
| `GET` | `/api/health` | public | Liveness check. |
| `GET` | `/api/help` | public | `View Help` (FR-DERIVED-3). |
| `POST` | `/api/games` | public | Create a guest session and start a game (FR-1). |
| `GET` | `/api/games/:id` | public | View game state and score (FR-DERIVED-1). |
| `POST` | `/api/games/:id/answers` | public | Submit an answer for the current question (FR-1). |
| `POST` | `/api/games/:id/pause` | public | Pause the game (`Paused` state). |
| `POST` | `/api/games/:id/resume` | public | Resume a paused game. |
| `POST` | `/api/games/:id/reset` | public | Start a fresh round with the same guest ID. |
| `GET` | `/api/questions` | admin | List all questions (FR-DERIVED-2). |
| `POST` | `/api/questions` | admin | Create a question (FR-DERIVED-2). |
| `PUT` | `/api/questions/:id` | admin | Update a question (FR-DERIVED-2). |
| `DELETE` | `/api/questions/:id` | admin | Delete a question (FR-DERIVED-2). |

Admin requests use `Authorization: Bearer <ADMIN_TOKEN>`.

## 4. Normalized diagram views

The PlantUML views from the input are mapped to concrete code elements.

### Use Case Diagram
- **Play Game** -> `POST /api/games` + `POST /api/games/:id/answers`.
- **View Score** -> `GET /api/games/:id`.
- **Update Questions** -> admin question CRUD routes.
- **View Help** -> `GET /api/help`.
- Actors: `EndUser` (guest), `Admin` (token-authenticated).

### Class Diagram
- `Game` (session, questions, score, state).
- `Question` (prompt, options, correctIndex, category).
- `User` (guest identity) and `Admin` (token authorization).

### Object Diagram
- `game1` -> a `Game` instance created by `POST /api/games`.
- `question1` -> a `Question` instance from the seed repository.
- `user1` -> a guest identity created by `UserComponent.createGuest()`.
- `admin1` -> an authorization check performed by `AdminComponent`.

> Parsing warning W-001: the source object diagram used participant notation;
> it was normalized to object semantics here.

### State Diagram
- `Playing` -> default state after `POST /api/games`.
- `Paused` -> reached via `/pause`, left via `/resume`.
- `GameOver` -> reached after the final question is answered.

### Activity Diagram
- `play game` -> start + answer loop.
- `calculate score` -> `Game.answer()` adds `POINTS_PER_CORRECT` on correct answers.
- `display score` -> `GET /api/games/:id` returns `score` and `maxScore`.
- `game over` -> final answer flips status to `gameover`.
- `continue playing` -> `/reset` starts a new round with the same guest ID.

### Sequence / Collaboration Diagrams
- `SequenceDiagram1` / `CollaborationDiagram1`: `User -> Game -> Question`
  (request game, select questions, answer, calculate score).
- `SequenceDiagram2` / `CollaborationDiagram2`: `Admin -> Question`
  (authenticate, create/update/delete question).

> Parsing warnings W-002/W-003: collaboration diagrams used `->>` sequence
> notation; both were normalized to collaboration semantics.

### Package / Component / Deployment / Container Diagrams
- Package boundaries = component classes in `src/domain.js`.
- Component boundaries = `GameComponent`, `QuestionComponent`, `UserComponent`,
  `AdminComponent`.
- Deployment/container nodes `GameServer`, `QuestionServer`, `UserClient`,
  `AdminClient` collapse into one Node.js process in the modular-monolith
  deviation (D-01).

## 5. Quality attributes

### NFR-1 — Performance
- The API uses `node:http` directly with small JSON payloads and a handful of
  constant-time route matches.
- In-memory state avoids database round-trips for the demo.
- Acceptance target for the demo: a full 10-question game and admin CRUD complete
  correctly under the automated test suite.

### ASR-1 — Data durability
- Seed questions are embedded in source and remain available across restarts.
- Admin-created questions and game scores are in-memory only; durability beyond a
  process restart is **not implemented** and is the explicit reason for the
  optional PostgreSQL adapter seam.

### ASR-2 — Security (working definition)
- The correct answer index is never returned before the user answers the question.
- Admin routes require a bearer token checked with a timing-safe comparison.
- Request bodies are capped at 64 KiB and rejected when invalid.
- Responses include `X-Content-Type-Options: nosniff` and `Cache-Control: no-store`.
- Acceptance criteria: unauthenticated admin requests receive `401`; player-facing
  game responses contain no `correctIndex` for the current question.

## 6. Requirement traceability

| Requirement | Component(s) | Primary files |
| --- | --- | --- |
| FR-1 — Play game | `GameComponent`, `QuestionComponent`, `UserComponent` | `src/domain.js`, `src/index.js` |
| NFR-1 — Performance | `GameComponent` | `src/domain.js`, `src/index.js` |
| ASR-1 — Data durability | `QuestionComponent` | `src/domain.js` |
| ASR-2 — Security | `GameComponent`, `AdminComponent` | `src/domain.js`, `src/index.js` |
| FR-DERIVED-1 — View Score | `GameComponent`, `UserComponent` | `src/domain.js`, `src/index.js` |
| FR-DERIVED-2 — Update Questions | `QuestionComponent`, `AdminComponent` | `src/domain.js`, `src/index.js` |
| FR-DERIVED-3 — View Help | `UserComponent` | `src/domain.js`, `src/index.js` |

## 7. Test coverage map

| Test type | Coverage | Files |
| --- | --- | --- |
| Unit | Scoring, game state transitions, question validation/CRUD, admin auth, guest identity. | `tests/domain.test.js` |
| End-to-end | Full HTTP flow: health, help, start game, answer 10 questions, view score, reset, admin CRUD with and without token. | `tests/e2e/flow.test.js` |
| Contract | Implicitly covered by the end-to-end test asserting response shapes and status codes. | `tests/e2e/flow.test.js` |
| Chaos | Not implemented (explicitly out of scope for the demo). | — |
