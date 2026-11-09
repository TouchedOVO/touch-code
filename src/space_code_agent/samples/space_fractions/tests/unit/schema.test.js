'use strict';

// Covers: ASR-1
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const schema = fs.readFileSync(path.join(__dirname, '..', '..', 'sql', 'init.sql'), 'utf8');

test('durable schema defines the core tables and constraints', () => {
  for (const table of ['questions', 'games', 'game_questions', 'game_answers', 'users']) {
    assert.match(
      schema,
      new RegExp(`CREATE TABLE IF NOT EXISTS ${table}\\s*\\(`),
      `missing table ${table}`,
    );
  }
  assert.match(schema, /answer_index INTEGER\s+NOT NULL CHECK/);
  assert.match(schema, /REFERENCES games\(id\) ON DELETE CASCADE/);
  assert.match(schema, /CREATE INDEX IF NOT EXISTS idx_game_answers_game/);
});

test('schema keeps secrets out and documents role boundaries', () => {
  assert.equal(schema.includes('password_plain'), false);
  assert.match(schema, /password_hash TEXT\s+NOT NULL/);
  assert.match(schema, /CHECK \(role IN \('student', 'admin'\)\)/);
});
