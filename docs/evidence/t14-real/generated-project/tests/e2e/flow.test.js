'use strict';

// Requirement coverage: [FR-1] [NFR-1] [ASR-2] [FR-DERIVED-1] [FR-DERIVED-2] [FR-DERIVED-3]

const test = require('node:test');
const assert = require('node:assert/strict');

const { createServer } = require('../../src/index');
const { DEFAULT_SEED_QUESTIONS } = require('../../src/domain');

async function startServer(t) {
  const server = createServer({
    adminToken: 'test-admin-token',
    seedQuestions: DEFAULT_SEED_QUESTIONS,
  });

  await new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolve);
  });

  t.after(() => new Promise((resolve) => server.close(resolve)));

  const address = server.address();
  return `http://127.0.0.1:${address.port}`;
}

async function requestJson(baseUrl, path, options = {}) {
  const response = await fetch(`${baseUrl}${path}`, options);
  const text = await response.text();
  let body = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }
  return { status: response.status, body };
}

test('health and help endpoints are public', async (t) => {
  const baseUrl = await startServer(t);

  const health = await requestJson(baseUrl, '/api/health');
  assert.equal(health.status, 200);
  assert.equal(health.body.status, 'ok');

  const help = await requestJson(baseUrl, '/api/help');
  assert.equal(help.status, 200);
  assert.equal(help.body.title, 'How to play Space Fractions');
});

test('a full game flow ends with a score and supports reset', async (t) => {
  const baseUrl = await startServer(t);

  const created = await requestJson(baseUrl, '/api/games', { method: 'POST' });
  assert.equal(created.status, 201);

  let game = created.body.game;
  assert.equal(game.status, 'playing');
  assert.equal(game.totalQuestions, 10);
  assert.equal(game.score, 0);
  assert.ok(game.guestId.startsWith('guest_'));
  assert.equal(game.currentQuestion.correctIndex, undefined);
  assert.equal(game.currentQuestion.options.length, 4);

  for (let i = 0; i < 10; i += 1) {
    const answer = await requestJson(baseUrl, `/api/games/${game.id}/answers`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ selectedIndex: 0 }),
    });
    assert.equal(answer.status, 200);
    game = answer.body.game;
  }

  assert.equal(game.status, 'gameover');
  assert.equal(game.totalQuestions, 10);
  assert.equal(typeof game.score, 'number');
  assert.ok(game.score >= 0 && game.score <= 100);
  assert.equal(game.currentQuestion, null);

  const viewed = await requestJson(baseUrl, `/api/games/${game.id}`);
  assert.equal(viewed.status, 200);
  assert.equal(viewed.body.game.status, 'gameover');
  assert.equal(viewed.body.game.score, game.score);

  const reset = await requestJson(baseUrl, `/api/games/${game.id}/reset`, {
    method: 'POST',
  });
  assert.equal(reset.status, 200);
  assert.equal(reset.body.game.status, 'playing');
  assert.equal(reset.body.game.score, 0);
  assert.equal(reset.body.game.guestId, game.guestId);
});

test('admin question endpoints enforce auth and support CRUD', async (t) => {
  const baseUrl = await startServer(t);

  const denied = await requestJson(baseUrl, '/api/questions');
  assert.equal(denied.status, 401);

  const authHeaders = {
    'Content-Type': 'application/json',
    Authorization: 'Bearer test-admin-token',
  };

  const list = await requestJson(baseUrl, '/api/questions', { headers: authHeaders });
  assert.equal(list.status, 200);
  assert.ok(list.body.count >= 10);

  const created = await requestJson(baseUrl, '/api/questions', {
    method: 'POST',
    headers: authHeaders,
    body: JSON.stringify({
      prompt: '1/2 + 1/2 = ?',
      options: ['1/4', '1', '2/2', '1/2'],
      correctIndex: 1,
      category: 'addition',
    }),
  });
  assert.equal(created.status, 201);
  const id = created.body.question.id;

  const updated = await requestJson(baseUrl, `/api/questions/${id}`, {
    method: 'PUT',
    headers: authHeaders,
    body: JSON.stringify({ category: 'mixed' }),
  });
  assert.equal(updated.status, 200);
  assert.equal(updated.body.question.category, 'mixed');
  assert.equal(updated.body.question.prompt, '1/2 + 1/2 = ?');

  const deleted = await fetch(`${baseUrl}/api/questions/${id}`, {
    method: 'DELETE',
    headers: { Authorization: 'Bearer test-admin-token' },
  });
  assert.equal(deleted.status, 204);

  const missing = await requestJson(baseUrl, `/api/questions/${id}`, {
    headers: authHeaders,
  });
  assert.equal(missing.status, 404);
});

test('invalid input and unknown routes return 4xx responses', async (t) => {
  const baseUrl = await startServer(t);

  const created = await requestJson(baseUrl, '/api/games', { method: 'POST' });
  assert.equal(created.status, 201);
  const game = created.body.game;

  const badAnswer = await requestJson(baseUrl, `/api/games/${game.id}/answers`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ selectedIndex: 9 }),
  });
  assert.equal(badAnswer.status, 400);

  const badJson = await requestJson(baseUrl, `/api/games/${game.id}/answers`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: 'not-json',
  });
  assert.equal(badJson.status, 400);

  const unknown = await requestJson(baseUrl, '/api/nope');
  assert.equal(unknown.status, 404);
});
