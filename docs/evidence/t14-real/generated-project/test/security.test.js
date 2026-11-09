'use strict';

// Covers: ASR-2

const test = require('node:test');
const assert = require('node:assert/strict');

const {
  ADMIN_TOKEN,
  createTestApp,
  startServer,
  closeServer,
  getJson,
  postJson,
  deleteJson
} = require('./helpers/test-app');

async function rawGet(baseUrl, path) {
  const response = await fetch(`${baseUrl}${path}`);
  return response;
}

test('admin endpoints reject missing, malformed and wrong tokens', async () => {
  const { app, cleanup, config } = createTestApp();
  const { server, baseUrl } = await startServer(app);

  try {
    const missing = await getJson(baseUrl, '/api/questions');
    assert.equal(missing.status, 401);

    const wrong = await fetch(`${baseUrl}/api/questions`, {
      headers: { Authorization: 'Bearer definitely-wrong' }
    });
    assert.equal(wrong.status, 401);

    const xToken = await fetch(`${baseUrl}/api/questions`, {
      headers: { 'x-admin-token': config.adminToken || ADMIN_TOKEN }
    });
    assert.equal(xToken.status, 200);

    const malformed = await postJson(baseUrl, '/api/questions', {
      text: '1/2 + 1/2 = ?',
      options: ['1', '1/4', '1/2', '2'],
      answerIndex: 0
    });
    assert.equal(malformed.status, 401);
  } finally {
    await closeServer(server);
    cleanup();
  }
});

test('responses include defensive security headers and no powered-by header', async () => {
  const { app, cleanup } = createTestApp();
  const { server, baseUrl } = await startServer(app);

  try {
    const response = await rawGet(baseUrl, '/api/health');
    assert.equal(response.headers.get('x-powered-by'), null);
    assert.equal(response.headers.get('x-content-type-options'), 'nosniff');
    assert.equal(response.headers.get('x-frame-options'), 'DENY');
    assert.equal(response.headers.get('referrer-policy'), 'no-referrer');
    assert.match(response.headers.get('content-security-policy') || '', /default-src 'self'/);
    assert.equal(response.headers.get('cache-control'), 'no-store');
  } finally {
    await closeServer(server);
    cleanup();
  }
});

test('invalid JSON bodies are rejected with a controlled error', async () => {
  const { app, cleanup, config } = createTestApp();
  const { server, baseUrl } = await startServer(app);

  try {
    const response = await fetch(`${baseUrl}/api/questions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${config.adminToken || ADMIN_TOKEN}`
      },
      body: '{"not valid json'
    });
    assert.equal(response.status, 400);
    const body = await response.json();
    assert.equal(body.error, 'Bad Request');
  } finally {
    await closeServer(server);
    cleanup();
  }
});

test('game question payloads never expose the correct answer index', async () => {
  const { app, cleanup } = createTestApp();
  const { server, baseUrl } = await startServer(app);

  try {
    const guest = await postJson(baseUrl, '/api/users/guest', {});
    const game = await postJson(baseUrl, '/api/games', { guestId: guest.body.guestId });
    assert.equal(game.status, 201);
    assert.equal(game.body.question.answerIndex, undefined);
    assert.equal(game.body.question.answer, undefined);
    assert.ok(Array.isArray(game.body.question.options));
  } finally {
    await closeServer(server);
    cleanup();
  }
});

test('admin delete without token does not remove questions', async () => {
  const { app, cleanup } = createTestApp();
  const { server, baseUrl } = await startServer(app);

  try {
    const question = app.locals.services.questionService.listQuestions()[0];
    const result = await deleteJson(baseUrl, `/api/questions/${question.id}`);
    assert.equal(result.status, 401);
    assert.ok(app.locals.services.questionService.getQuestion(question.id));
  } finally {
    await closeServer(server);
    cleanup();
  }
});
