'use strict';

/**
 * End-to-end flow across question, game and user services.
 * Covers: FR-1, FR-DERIVED-1, FR-DERIVED-2, FR-DERIVED-3, ASR-2
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const { startServer, stopServer } = require('../../lib/http');
const { createQuestionStore } = require('../../services/question-service/src/store');
const { createQuestionApp } = require('../../services/question-service/src/index');
const { SEED_QUESTIONS } = require('../../services/question-service/src/questions');
const { createGameApp } = require('../../services/game-service/src/index');
const { createQuestionClient } = require('../../services/game-service/src/questionClient');
const { createAuthService } = require('../../services/user-service/src/auth');
const { createUserApp } = require('../../services/user-service/src/index');

test('student can play a full round and admin can add a question', async (t) => {
  const questionService = await startServer(createQuestionApp({
    store: createQuestionStore(),
    serviceToken: 'svc-token',
    adminToken: 'admin-token',
  }));
  const gameService = await startServer(createGameApp({
    questionClient: createQuestionClient({
      baseUrl: questionService.url,
      serviceToken: 'svc-token',
    }),
    idFactory: () => 'game-e2e',
  }));
  const userService = await startServer(createUserApp({
    auth: createAuthService({
      adminUser: 'admin',
      adminPassword: 'test-password',
      secret: 'test-secret',
    }),
  }));

  t.after(async () => {
    await stopServer(gameService.server);
    await stopServer(questionService.server);
    await stopServer(userService.server);
  });

  const guestResponse = await fetch(`${userService.url}/guests`, { method: 'POST' });
  assert.equal(guestResponse.status, 201);
  const guest = await guestResponse.json();
  assert.equal(guest.role, 'student');

  const createdResponse = await fetch(`${gameService.url}/games`, { method: 'POST' });
  assert.equal(createdResponse.status, 201);
  const created = await createdResponse.json();
  assert.equal(created.gameId, 'game-e2e');
  assert.equal(created.totalQuestions, 10);

  const answers = new Map(SEED_QUESTIONS.map((question) => [question.id, question.answerIndex]));
  let question = created.currentQuestion;
  let score = 0;
  let answered = 0;
  for (let index = 0; index < 10; index += 1) {
    assert.ok(question, `question ${index} should exist`);
    const answerIndex = answers.get(question.id);
    assert.equal(typeof answerIndex, 'number', `seed answer for ${question.id}`);
    const submit = await fetch(`${gameService.url}/games/${created.gameId}/answers`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ questionId: question.id, choiceIndex: answerIndex }),
    });
    assert.equal(submit.status, 200);
    const outcome = await submit.json();
    assert.equal(outcome.correct, true);
    score = outcome.score;
    answered = outcome.answeredCount;
    question = outcome.nextQuestion;
  }
  assert.equal(score, 100);
  assert.equal(answered, 10);
  assert.equal(question, null);

  const finished = await fetch(`${gameService.url}/games/${created.gameId}`);
  assert.equal(finished.status, 200);
  assert.equal((await finished.json()).status, 'finished');

  const resultResponse = await fetch(`${gameService.url}/games/${created.gameId}/result`);
  assert.equal(resultResponse.status, 200);
  const result = await resultResponse.json();
  assert.equal(result.score, 100);
  assert.equal(result.maxScore, 100);
  assert.equal(result.breakdown.length, 10);
  assert.ok(result.breakdown.every((entry) => entry.correct));

  const loginResponse = await fetch(`${userService.url}/sessions`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ username: 'admin', password: 'test-password' }),
  });
  assert.equal(loginResponse.status, 200);
  const admin = await loginResponse.json();
  assert.equal(admin.role, 'admin');

  const me = await fetch(`${userService.url}/me`, {
    headers: { authorization: `Bearer ${admin.token}` },
  });
  assert.equal(me.status, 200);

  const newQuestion = {
    prompt: '2/9 + 4/9 = ?',
    options: ['6/9', '6/18', '2/9', '1/3'],
    answerIndex: 0,
    difficulty: 'easy',
  };
  const addResponse = await fetch(`${questionService.url}/questions`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', authorization: 'Bearer admin-token' },
    body: JSON.stringify(newQuestion),
  });
  assert.equal(addResponse.status, 201);
  const added = await addResponse.json();
  assert.equal(added.question.id, 'q-013');

  const adminList = await fetch(`${questionService.url}/admin/questions`, {
    headers: { authorization: 'Bearer admin-token' },
  });
  assert.equal(adminList.status, 200);
  assert.equal((await adminList.json()).questions.length, 13);

  const health = await fetch(`${questionService.url}/health`);
  assert.equal(health.status, 200);
});
