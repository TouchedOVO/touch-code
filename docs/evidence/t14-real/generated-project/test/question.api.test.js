'use strict';

// Covers: FR-DERIVED-2, ASR-2

const test = require('node:test');
const assert = require('node:assert/strict');

const {
  ADMIN_TOKEN,
  createTestApp,
  startServer,
  closeServer,
  getJson,
  postJson,
  putJson,
  deleteJson
} = require('./helpers/test-app');

const validQuestion = {
  text: '5/8 + 1/8 = ?',
  options: ['3/4', '1/2', '6/8', '5/16'],
  answerIndex: 0,
  explanation: '5/8 + 1/8 = 6/8 = 3/4.'
};

test('admin question list requires a valid token', async () => {
  const { app, cleanup } = createTestApp();
  const { server, baseUrl } = await startServer(app);

  try {
    const noToken = await getJson(baseUrl, '/api/questions');
    assert.equal(noToken.status, 401, 'missing token is rejected');

    const wrongTokenResponse = await fetch(`${baseUrl}/api/questions`, {
      headers: { Authorization: 'Bearer wrong-token' }
    });
    assert.equal(wrongTokenResponse.status, 401, 'wrong token is rejected');

    const validResponse = await fetch(`${baseUrl}/api/questions`, {
      headers: { Authorization: `Bearer ${ADMIN_TOKEN}` }
    });
    assert.equal(validResponse.status, 200, 'valid token is accepted');
  } finally {
    await closeServer(server);
    cleanup();
  }
});

test('admin can create, read, update and delete a question', async () => {
  const { app, cleanup, config } = createTestApp();
  const { server, baseUrl } = await startServer(app);
  const token = config.adminToken || ADMIN_TOKEN;

  try {
    const listBefore = await getJson(baseUrl, '/api/questions');
    assert.equal(listBefore.status, 401, 'list is protected before auth');

    const created = await postJson(baseUrl, '/api/questions', validQuestion, token);
    assert.equal(created.status, 201);
    assert.match(created.body.question.id, /^q-/);
    assert.equal(created.body.question.text, validQuestion.text);
    assert.equal(created.body.question.answerIndex, 0);

    const id = created.body.question.id;
    const fetched = await getJson(baseUrl, `/api/questions/${id}`);
    assert.equal(fetched.status, 401, 'single question is also protected');

    const updated = await putJson(
      baseUrl,
      `/api/questions/${id}`,
      { text: '5/8 + 1/8 = ?', options: ['3/4', '1/2', '6/8', '5/16'], answerIndex: 1 },
      token
    );
    assert.equal(updated.status, 200);
    assert.equal(updated.body.question.answerIndex, 1);

    const removed = await deleteJson(baseUrl, `/api/questions/${id}`, token);
    assert.equal(removed.status, 204);

    const afterDelete = await getJson(baseUrl, '/api/questions');
    assert.equal(afterDelete.status, 401, 'list still protected');
    const list = await fetch(`${baseUrl}/api/questions`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    const listBody = await list.json();
    assert.equal(list.status, 200);
    assert.equal(listBody.questions.some((q) => q.id === id), false);
  } finally {
    await closeServer(server);
    cleanup();
  }
});

test('question creation without token is rejected and nothing is written', async () => {
  const { app, cleanup } = createTestApp();
  const { server, baseUrl } = await startServer(app);

  try {
    const created = await postJson(baseUrl, '/api/questions', validQuestion);
    assert.equal(created.status, 401);
    assert.equal(app.locals.services.questionService.count(), 10);
  } finally {
    await closeServer(server);
    cleanup();
  }
});

test('invalid question payloads return 400 with details', async () => {
  const { app, cleanup, config } = createTestApp();
  const { server, baseUrl } = await startServer(app);
  const token = config.adminToken || ADMIN_TOKEN;

  try {
    const invalid = await postJson(
      baseUrl,
      '/api/questions',
      { text: 'bad', options: ['1/2', '1/3'], answerIndex: 0 },
      token
    );
    assert.equal(invalid.status, 400);
    assert.ok(Array.isArray(invalid.body.details));
    assert.ok(invalid.body.details.length > 0);
  } finally {
    await closeServer(server);
    cleanup();
  }
});
