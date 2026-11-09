'use strict';

// Covers: FR-DERIVED-2
const test = require('node:test');
const assert = require('node:assert/strict');
const { startServer, stopServer } = require('../../../lib/http');
const { createQuestionStore } = require('../src/store');
const { createQuestionApp } = require('../src/index');

async function withApp(t) {
  const store = createQuestionStore();
  const app = createQuestionApp({
    store,
    serviceToken: 'svc-token',
    adminToken: 'admin-token',
  });
  const { server, url } = await startServer(app);
  t.after(() => stopServer(server));
  return { store, url };
}

test('public question list hides answers and respects count', async (t) => {
  const { url } = await withApp(t);
  const response = await fetch(`${url}/questions?count=5`);
  assert.equal(response.status, 200);
  const payload = await response.json();
  assert.equal(payload.questions.length, 5);
  for (const question of payload.questions) {
    assert.equal(question.answerIndex, undefined);
    assert.equal(question.options.length, 4);
  }
  assert.equal(new Set(payload.questions.map((q) => q.id)).size, 5);
});

test('internal endpoint requires service token and includes answers', async (t) => {
  const { url } = await withApp(t);
  const denied = await fetch(`${url}/internal/questions?count=2`);
  assert.equal(denied.status, 401);

  const allowed = await fetch(`${url}/internal/questions?count=2`, {
    headers: { 'x-service-token': 'svc-token' },
  });
  assert.equal(allowed.status, 200);
  const payload = await allowed.json();
  assert.equal(payload.questions.length, 2);
  assert.equal(typeof payload.questions[0].answerIndex, 'number');
});

test('admin can create, update and delete a question', async (t) => {
  const { url } = await withApp(t);
  const payload = {
    prompt: '1/3 + 1/3 = ?',
    options: ['2/3', '1/6', '2/6', '1/3'],
    answerIndex: 0,
    difficulty: 'easy',
  };

  const denied = await fetch(`${url}/questions`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
  });
  assert.equal(denied.status, 401);

  const created = await fetch(`${url}/questions`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', authorization: 'Bearer admin-token' },
    body: JSON.stringify(payload),
  });
  assert.equal(created.status, 201);
  const createdBody = await created.json();
  assert.equal(createdBody.question.id, 'q-013');
  assert.equal(createdBody.question.answerIndex, 0);

  const updated = await fetch(`${url}/questions/q-013`, {
    method: 'PUT',
    headers: { 'content-type': 'application/json', authorization: 'Bearer admin-token' },
    body: JSON.stringify({ ...payload, prompt: '1/3 + 1/3 = ? (updated)' }),
  });
  assert.equal(updated.status, 200);
  assert.match((await updated.json()).question.prompt, /updated/);

  const deleted = await fetch(`${url}/questions/q-013`, {
    method: 'DELETE',
    headers: { authorization: 'Bearer admin-token' },
  });
  assert.equal(deleted.status, 200);
  const missing = await fetch(`${url}/questions/q-013`);
  assert.equal(missing.status, 404);
});

test('invalid question payload is rejected', async (t) => {
  const { url } = await withApp(t);
  const response = await fetch(`${url}/questions`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', authorization: 'Bearer admin-token' },
    body: JSON.stringify({ prompt: 'bad', options: ['a', 'a', 'b', 'c'], answerIndex: 9 }),
  });
  assert.equal(response.status, 400);
  assert.equal((await response.json()).error, 'invalid_question');
});
