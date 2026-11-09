# Space Fractions

<!-- Requirement coverage: [FR-1] [NFR-1] [ASR-1] [ASR-2] [FR-DERIVED-1] [FR-DERIVED-2] [FR-DERIVED-3] -->

A web-based, interactive learning tool designed to improve fraction-solving
skills for sixth-grade students. Players answer a fixed set of 10 single-choice
fraction arithmetic questions, earn 10 points per correct answer, and view their
score at the end of the round.

This repository implements the **backend REST API and domain model**. It is a
zero-dependency Node.js modular monolith; a future browser client can consume the
JSON endpoints below.

## Features

- **Play Game (FR-1):** create a guest session, receive 10 questions, and submit
  answers one at a time.
- **View Score (FR-DERIVED-1):** inspect the current score and game state at any
  time; final score is shown after game over.
- **Update Questions (FR-DERIVED-2):** admin-only create, read, update and delete
  for sixth-grade fraction questions.
- **View Help (FR-DERIVED-3):** a public help endpoint describes how to play.
- **Security (ASR-2):** correct answers are hidden until answered; admin routes
  use a bearer token with a timing-safe comparison; request bodies are size-capped.
- **Performance (NFR-1):** built on `node:http` with in-memory state and small
  JSON payloads.
- **Data durability (ASR-1):** seed questions ship in source; admin edits are
  in-memory in this demo, with a repository seam for an optional PostgreSQL adapter.

## Directory structure

```
.
├── README.md
├── package.json
├── .env.example
├── requirements.json
├── requirements.md
├── requirements-traceability.json
├── docs/
│   ├── ASSUMPTIONS.md            # assumptions, conflicts, deviations
│   ├── architecture-summary.md   # normalized architecture views
│   ├── requirements.md
│   └── requirements-traceability.md
├── src/
│   ├── index.js                  # HTTP server and REST routes
│   └── domain.js                 # Game/Question/User/Admin domain logic
└── tests/
    ├── domain.test.js            # unit tests
    └── e2e/
        └── flow.test.js          # end-to-end HTTP tests
```

## Requirements

- Node.js **20 or newer** (`node --version` should print `v20.x` or later).
- No npm install step is required; there are **zero runtime dependencies**.

## Installation and run

```bash
# 1. (Optional) check the Node version
node --version

# 2. Start the server
npm start
```

The server listens on `http://127.0.0.1:3000` by default. Override the port and
admin token with environment variables:

```bash
PORT=8080 ADMIN_TOKEN='your-strong-token' npm start
```

When `ADMIN_TOKEN` is not set, the server falls back to `dev-admin-token` so the
demo works out of the box. **Do not use that fallback outside local development.**

## Test commands

```bash
# Run all automated tests
npm test

# Syntax-check every JavaScript file
npm run check
```

The test suite uses the built-in `node:test` runner; no dependencies are needed.

## API quick reference

Public endpoints:

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/health` | Service health. |
| `GET` | `/api/help` | How-to-play text (View Help). |
| `POST` | `/api/games` | Start a game; returns `guestId` and first question. |
| `GET` | `/api/games/:id` | View game state and score. |
| `POST` | `/api/games/:id/answers` | Body `{ "selectedIndex": 0..3 }`; answers current question. |
| `POST` | `/api/games/:id/pause` | Pause the game. |
| `POST` | `/api/games/:id/resume` | Resume a paused game. |
| `POST` | `/api/games/:id/reset` | Start a new round with the same guest ID. |

Admin endpoints (require `Authorization: Bearer <ADMIN_TOKEN>`):

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/questions` | List all questions. |
| `POST` | `/api/questions` | Create a question. |
| `PUT` | `/api/questions/:id` | Update a question. |
| `DELETE` | `/api/questions/:id` | Delete a question. |

A question object has the shape:

```json
{
  "id": "q_...",
  "prompt": "1/2 + 1/4 = ?",
  "options": ["2/6", "3/4", "1/3", "2/4"],
  "correctIndex": 1,
  "category": "addition"
}
```

Player-facing game responses **never include `correctIndex` for the current
question**; the answer result reveals correctness only after submission.

## Assumptions and limitations

The implementation follows the assumptions and deviations recorded in
[`docs/ASSUMPTIONS.md`](docs/ASSUMPTIONS.md). The most important points:

- Each game has exactly **10 questions**, `+10` per correct answer, max `100`, no
  timer.
- Students do **not** register; a guest ID is generated per session.
- The project is a **modular monolith**, not distributed microservices. This is a
  documented deviation from the original architecture input.
- Persistence is **in-memory**. The optional PostgreSQL adapter is **not
  implemented**; the repository interface is the extension seam.
- Redis, RabbitMQ, Elasticsearch, Kubernetes, Istio, Vault and Terraform are
  optional extensions and are **not implemented**.
- The deliverable is the REST API plus domain model; a full browser UI is not
  included.
