-- Space Fractions — optional PostgreSQL schema
-- Covers: ASR-1, FR-DERIVED-2
-- The demo runs with in-memory repositories; this DDL documents the durable design.

CREATE TABLE IF NOT EXISTS questions (
    id           SERIAL PRIMARY KEY,
    prompt       TEXT        NOT NULL,
    options      JSONB       NOT NULL,
    answer_index INTEGER     NOT NULL CHECK (answer_index BETWEEN 0 AND 3),
    difficulty   TEXT        NOT NULL DEFAULT 'easy'
                             CHECK (difficulty IN ('easy', 'medium', 'hard')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS games (
    id             TEXT        PRIMARY KEY,
    status         TEXT        NOT NULL DEFAULT 'active'
                               CHECK (status IN ('active', 'finished', 'abandoned')),
    score          INTEGER     NOT NULL DEFAULT 0 CHECK (score >= 0),
    total_questions INTEGER    NOT NULL CHECK (total_questions > 0),
    current_index  INTEGER     NOT NULL DEFAULT 0,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at    TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS game_questions (
    game_id       TEXT    NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    position      INTEGER NOT NULL,
    question_id   INTEGER NOT NULL REFERENCES questions(id),
    answer_index  INTEGER NOT NULL,
    PRIMARY KEY (game_id, position)
);

CREATE TABLE IF NOT EXISTS game_answers (
    game_id       TEXT    NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    position      INTEGER NOT NULL,
    question_id   INTEGER NOT NULL REFERENCES questions(id),
    choice_index  INTEGER NOT NULL,
    correct       BOOLEAN NOT NULL,
    answered_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (game_id, position)
);

CREATE TABLE IF NOT EXISTS users (
    id            BIGSERIAL   PRIMARY KEY,
    username      TEXT        NOT NULL UNIQUE,
    password_hash TEXT        NOT NULL,
    role          TEXT        NOT NULL DEFAULT 'student'
                              CHECK (role IN ('student', 'admin')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_game_answers_game ON game_answers(game_id);
CREATE INDEX IF NOT EXISTS idx_questions_difficulty ON questions(difficulty);
