> 🌐 **English** | [简体中文](README.zh-CN.md)

# Space Fractions

Space Fractions is a web-based, interactive learning tool for sixth-grade
students to practice fraction-solving skills. Players answer 10 fraction
questions, earn 10 points per correct answer, and see a final score out of
100. Administrators can manage the question bank through a token-protected
REST API.

The project is implemented with Node.js only, using its built-in `http`
module for the REST API. The three documented service boundaries (Game,
Question, User) are preserved as separate modules but run inside one Node.js
process so the application can be verified without external cloud services.
This deliberate modular-monolith deviation is documented in
[`docs/ASSUMPTIONS.md`](docs/ASSUMPTIONS.md).

## Features

- Interactive browser UI with menu, gameplay, score/result, and help views.
- Keyboard-operable interface with visible focus, semantic labels, and
  accessible contrast.
- 10-question sessions; correct answers award 10 points, wrong answers award 0.
- Guest sessions — students do not need to register.
- Durable JSON file persistence for questions and completed scores with
  atomic writes and restart recovery.
- Admin question CRUD protected by a constant-time token comparison.
- Defensive security headers and centralized error handling.

## Directory structure

```
.
├── package.json
├── README.md
├── .env.example
├── data/
│   ├── seed-questions.json   # Seed sixth-grade fraction questions
│   └── scores.json           # Persisted completed scores (created at runtime)
├── docs/
│   └── ASSUMPTIONS.md
├── public/
│   ├── index.html            # Browser UI shell
│   ├── styles.css            # Responsive, accessible styles
│   └── app.js                # Browser-side game logic
├── src/
│   ├── config.js             # Environment configuration
│   ├── app.js                # App factory and service wiring
│   ├── http.js               # Zero-dependency HTTP router and helpers
│   ├── server.js             # Server entry point
│   ├── domain/
│   │   ├── fraction.js       # Fraction arithmetic and question generation
│   │   └── game.js           # Game state machine and scoring rules
│   ├── repositories/
│   │   ├── file-store.js     # Atomic JSON file store
│   │   ├── question.repository.js
│   │   └── score.repository.js
│   ├── services/
│   │   ├── question.service.js
│   │   ├── game.service.js
│   │   └── user.service.js
│   ├── routes/
│   │   ├── question.routes.js
│   │   ├── game.routes.js
│   │   └── user.routes.js
│   └── middleware/
│       ├── auth.js
│       └── error-handler.js
└── test/
    ├── helpers/test-app.js
    ├── fraction.test.js
    ├── game.api.test.js
    ├── question.api.test.js
    ├── security.test.js
    ├── persistence-restart.test.js
    └── performance.test.js
```

## Requirements

- Node.js 18, 19, or 20.
- `npm` (bundled with Node.js).
- No external database or message broker is required. Data is stored in JSON
  files under `data/`.

## Installation

```bash
npm install
```

There are no third-party runtime dependencies. `npm install` is optional and
is only needed to regenerate a lockfile if one is later added.

## Running the application

```bash
npm start
```

Then open <http://localhost:3000> in a browser.

Configuration is read from environment variables; see `.env.example`. The
default admin token is `dev-admin-token` and should be overridden in any real
deployment:

```bash
ADMIN_TOKEN='replace-with-a-strong-secret' npm start
```

On first boot the question repository creates `data/questions.json` from
`data/seed-questions.json`. Completed scores are appended to
`data/scores.json`.

## Running the tests

```bash
npm test
```

The test suite uses the Node.js built-in test runner and covers:

- `test/fraction.test.js` — fraction arithmetic and question generation.
- `test/game.api.test.js` — full game flow, scoring, and game over.
- `test/question.api.test.js` — admin question CRUD.
- `test/security.test.js` — token enforcement, headers, input handling.
- `test/persistence-restart.test.js` — restart recovery for questions and scores.
- `test/performance.test.js` — representative latency thresholds.

Each test file contains a `Covers:` comment mapping it to requirement IDs.

## Manual verification flow

1. Run `npm install` and `npm test`; all tests should pass.
2. Run `npm start` and open <http://localhost:3000>.
3. From the UI, start a game, answer ten questions, and verify the final score.
4. Open Help and verify keyboard-only navigation (Tab, Enter, Escape).
5. Create/update/delete a question through the admin API:

   ```bash
   curl -X POST http://localhost:3000/api/questions \
     -H 'Authorization: Bearer dev-admin-token' \
     -H 'Content-Type: application/json' \
     -d '{"text":"1/4 + 1/4 = ?","options":["1/2","1/4","1/8","2/4"],"answerIndex":0}'
   ```

6. Restart the server and confirm the created question and completed scores
   are recovered from `data/questions.json` and `data/scores.json`.
7. Attempt the same admin operation without the token and confirm a 401
   response.

## API summary

Public endpoints:

- `POST /api/users/guest` — create a guest ID.
- `GET /api/users/:guestId/scores` — list persisted scores for a guest.
- `GET /api/help` — help content.
- `POST /api/games` — start a game with `{ "guestId": "..." }`.
- `GET /api/games/:id` — current game state and current question.
- `POST /api/games/:id/answer` — submit `{ "selectedIndex": 0-3 }`.
- `GET /api/games/:id/score` — current or final score.
- `POST /api/games/:id/pause` and `POST /api/games/:id/resume` — state control.

Admin endpoints (require `Authorization: Bearer <ADMIN_TOKEN>`):

- `GET /api/questions`
- `POST /api/questions`
- `GET /api/questions/:id`
- `PUT /api/questions/:id`
- `DELETE /api/questions/:id`

## Assumptions and limitations

- A game is 10 questions, +10 points per correct answer, no timer.
- Students do not register; a guest ID is generated on first play.
- In-progress games are held in memory and are not resumed across restarts.
  Completed scores and questions are durable.
- PostgreSQL is not required to run the demo; the persistence layer uses JSON
  files with an interface that could be replaced by a database adapter.
- Redis, RabbitMQ, Elasticsearch, Kubernetes, Istio, Vault, and Terraform are
  intentionally excluded from the demo dependencies.

See [`docs/ASSUMPTIONS.md`](docs/ASSUMPTIONS.md) for the full list of
assumptions, document conflicts, and diagram-parsing warnings.
