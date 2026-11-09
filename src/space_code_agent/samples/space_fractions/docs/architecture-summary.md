> 🌐 **English** | [简体中文](architecture-summary.zh-CN.md)

# Architecture Summary

<!-- Covers: FR-1, FR-DERIVED-1, FR-DERIVED-2, FR-DERIVED-3, NFR-1, ASR-1, ASR-2 -->

## Source documents

- `Architecture_Documentation.md` — requirements, components, APIs, data, security, operations.
- `Architecture_View.md` — 13 PlantUML blocks covering 11 view types (use case, class, object,
  state, activity, sequence ×2, collaboration ×2, package, component, deployment, container).

## Component boundaries

| Component | Implemented as | Responsibilities |
|---|---|---|
| GameComponent | `services/game-service` | round creation, answer validation, scoring, result |
| QuestionComponent | `services/question-service` | question bank, admin CRUD, internal answer lookup |
| UserComponent | `services/user-service` | guest sessions, admin login, token verification |
| AdminComponent | `apps/web/admin.html` + question-service admin API | maintain questions |
| Student UI | `apps/web` | intro, menu, question flow, score, help, result |

## Runtime flows

1. **Play a round**: web → game-service `POST /games` → question-service
   `GET /internal/questions` → game holds server-side answers → web renders the first
   question.
2. **Submit an answer**: web → game-service `POST /games/:id/answers`; the service compares
   the choice with the stored answer index, adds 10 points when correct, advances the
   round, and returns the next question.
3. **View score**: after ten answers, web → game-service `GET /games/:id/result` and renders
   score plus per-question breakdown.
4. **Admin updates questions**: admin page → user-service login (admin role) → question-service
   admin endpoints with a bearer token.
5. **Help**: static help screen in the student UI.

## Data and durability

- The question bank persists to `data/questions.json` using a same-directory temp file + atomic
  rename; admin edits survive a service restart. A dedicated restart test covers this.
- Game rounds and guest sessions are in-memory; they are intentionally transient.
- `sql/init.sql` defines equivalent PostgreSQL tables (`questions`, `games`, `game_answers`,
  `users`) for teams that want a database-backed deployment. ASR-1 is satisfied at the application
  level by the JSON store in this demo, with PostgreSQL as an optional adapter.

## Security

- All question payloads are validated (4 unique options, answer index in range).
- Public question endpoints strip `answerIndex`; only the internal service-token endpoint
  returns answers.
- Admin endpoints require a bearer token; user-service issues HMAC-SHA256 signed tokens with
  expiry and constant-time signature comparison.
- No secrets are committed; `.env.example` contains placeholders only.
- Error responses avoid stack traces and never echo secrets.

## Deliberate deviations from the source architecture

See `docs/ASSUMPTIONS.md` (ASM-06). In short: microservice boundaries are preserved, but
Redis, RabbitMQ, Elasticsearch, Kubernetes, Istio, Vault, Terraform and a live PostgreSQL
cluster are out of scope for a runnable teaching demo. Express.js is replaced by `node:http`
so the project has zero runtime dependencies and can be tested offline.
