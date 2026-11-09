'use strict';

// Covers: ASR-1
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { createQuestionStore } = require('../../services/question-service/src/store');
const { SEED_QUESTIONS } = require('../../services/question-service/src/questions');

function tempStorePath(t) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'space-fractions-'));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  return path.join(dir, 'questions.json');
}

test('admin edits survive a store restart', (t) => {
  const persistPath = tempStorePath(t);
  const first = createQuestionStore(SEED_QUESTIONS, { persistPath });
  const created = first.create({
    prompt: '1/5 + 2/5 = ?',
    options: ['3/5', '3/10', '2/5', '1/5'],
    answerIndex: 0,
    difficulty: 'easy',
  });
  first.update(created.id, { prompt: '1/5 + 2/5 = ? (updated)' });

  const second = createQuestionStore(SEED_QUESTIONS, { persistPath });
  const loaded = second.get(created.id, true);
  assert.ok(loaded, 'created question must be readable after restart');
  assert.match(loaded.prompt, /updated/);
  assert.equal(second.count(), SEED_QUESTIONS.length + 1);
});

test('deleted questions stay deleted after restart', (t) => {
  const persistPath = tempStorePath(t);
  const first = createQuestionStore(SEED_QUESTIONS, { persistPath });
  assert.equal(first.remove('q-001'), true);

  const second = createQuestionStore(SEED_QUESTIONS, { persistPath });
  assert.equal(second.get('q-001'), null);
  assert.equal(second.count(), SEED_QUESTIONS.length - 1);
});

test('invalid persistence file fails loudly instead of silently resetting', (t) => {
  const persistPath = tempStorePath(t);
  fs.writeFileSync(persistPath, JSON.stringify({ version: 1 }), 'utf8');
  assert.throws(() => createQuestionStore(SEED_QUESTIONS, { persistPath }), /invalid persistence/);
});
