# ASSUMPTIONS

<!-- Covers: FR-1, FR-DERIVED-1, FR-DERIVED-2, FR-DERIVED-3, NFR-1, ASR-1, ASR-2 -->

This file records every assumption, ambiguity and deliberate deviation. None of the
statements below should be mistaken for requirements explicitly present in the source
documents.

## Document assumptions (verbatim)

- **A1**: The game will be played by 1000 users concurrently.
- **A2**: The game will be played for 1 hour per session.

## Agent assumptions

- **ASM-01 (gameplay)**: Ten questions per round; each correct answer is worth 10 points,
  each wrong answer 0; maximum score 100; no timer. The source document does not define
  question count or scoring.
- **ASM-02 (identity)**: Students play anonymously as guests. Admins log in with credentials
  from environment variables and receive a short-lived HMAC-signed bearer token. This is a
  minimal identity boundary, **not** full OAuth2.
- **ASM-03 (content)**: Questions are sixth-grade fraction addition/subtraction multiple
  choice with exactly four unique options. The seed bank contains 12 questions; each round
  samples 10.
- **ASM-04 (UI)**: Intro and ending scenes use CSS transitions and text instead of external
  movie/video assets. No external media is bundled.
- **ASM-05 (accessibility)**: Keyboard-operable controls, semantic landmarks, visible focus
  outlines, ARIA live feedback, and a minimum 4.5:1 contrast target.
- **ASM-06 (architecture — major deviation)**: The source document specifies a cloud-native
  microservices architecture with Redis, RabbitMQ, Elasticsearch, Kubernetes, Istio, Vault,
  Terraform, Prometheus and a live PostgreSQL cluster. This demo keeps the
  Game/Question/User service boundaries and REST contracts, but:
  - persistence is in-memory (`sql/init.sql` documents the PostgreSQL equivalent);
  - Express.js is replaced by `node:http` to achieve zero runtime dependencies;
  - the listed infrastructure components are **not deployed** and are treated as optional
    extensions;
  - this project must not be described as production-ready.

## Source-document conflicts

- The architecture document claims 11 PlantUML diagrams; the view file actually contains
  **13** blocks (sequence and collaboration each have two versions). The 13 parsed blocks are
  authoritative.
- `ASR-2` (security) is referenced by the QA coverage table but has no formal definition or
  acceptance metric. It is interpreted as input validation, token-protected admin endpoints,
  no secret leakage, and least-privilege service tokens.
- The traceability matrix contains only three sample rows (FR-1, NFR-1, ASR-1); the remaining
  derived requirements were reconstructed by the Agent and are marked `diagram-derived`.
- The test matrix in the document is empty. This project supplies unit, integration and
  end-to-end tests instead; their real execution status is reported by the Agent.
- `ObjectDiagram` uses `participant` notation and the collaboration diagrams use sequence
  arrows. Semantics were extracted defensively; syntax irregularities are recorded as
  low-severity conflicts.

## Open questions

- Expected concurrent user growth and session length (beyond A1/A2).
- Whether student scores must persist across sessions or devices.
- Whether a real OAuth2 provider and managed PostgreSQL are mandatory for evaluation.
