'use strict';

// Covers: FR-1, FR-DERIVED-1

const test = require('node:test');
const assert = require('node:assert/strict');

const {
  createTestApp,
  startServer,
  closeServer,
  postJson,
  getJson
} = require('./helpers/test-app');

test('full game flow awards 10 points per correct answer and reaches 100', async () => {
  const { app, cleanup } = createTestApp();
  const { server, baseUrl } = await startServer(app);

  try {
    const guest = await postJson(baseUrl, '/api/users/guest', {});
    assert.equal(guest.status, 201);
    assert.match(guest.body.guestId, /^guest-/);

    const created = await postJson(baseUrl, '/api/games', { guestId: guest.body.guestId });
    assert.equal(created.status, 201);
    assert.equal(created.body.game.status, 'PLAYING');
    assert.equal(created.body.game.totalQuestions, 10);
    assert.equal(created.body.game.score, 0);
    assert.ok(created.body.question.text);
    assert.equal(created.body.question.options.length, 4);
    assert.equal(created.body.question.answerIndex, undefined, 'answer must not leak to the player');

    const gameId = created.body.game.id;
    const gameService = app.locals.services.gameService;
    const questionService = app.locals.services.questionService;

    for (let step = 0; step < 10; step += 1) {
      const game = gameService.getGame(gameId);
      const questionId = game.questionIds[game.currentIndex];
      const question = questionService.getQuestion(questionId);
      const answer = await postJson(baseUrl, `/api/games/${gameId}/answer`, {
        selectedIndex: question.answerIndex
      });

      assert.equal(answer.status, 200);
      assert.equal(answer.body.correct, true, `step ${step + 1} should be correct`);
      assert.equal(answer.body.score, (step + 1) * 10);
      if (step < 9) {
        assert.equal(answer.body.completed, false);
        assert.ok(answer.body.nextQuestion, 'next question is provided until the end');
      } else {
        assert.equal(answer.body.completed, true);
        assert.equal(answer.body.finalScore, 100);
      }
    }

    const score = await getJson(baseUrl, `/api/games/${gameId}/score`);
    assert.equal(score.status, 200);
    assert.equal(score.body.score, 100);
    assert.equal(score.body.total, 100);
    assert.equal(score.body.completed, true);
    assert.equal(score.body.questionsAnswered, 10);

    const history = await getJson(baseUrl, `/api/users/${guest.body.guestId}/scores`);
    assert.equal(history.status, 200);
    assert.equal(history.body.scores.length, 1);
    assert.equal(history.body.scores[0].score, 100);
  } finally {
    await closeServer(server);
    cleanup();
  }
});

test('wrong answers earn zero points and still advance the game', async () => {
  const { app, cleanup } = createTestApp();
  const { server, baseUrl } = await startServer(app);

  try {
    const guest = await postJson(baseUrl, '/api/users/guest', {});
    const created = await postJson(baseUrl, '/api/games', { guestId: guest.body.guestId });
    const gameId = created.body.game.id;

    const game = app.locals.services.gameService.getGame(gameId);
    const question = app.locals.services.questionService.getQuestion(game.questionIds[0]);
    const wrongIndex = question.answerIndex === 0 ? 1 : 0;

    const answer = await postJson(baseUrl, `/api/games/${gameId}/answer`, {
      selectedIndex: wrongIndex
    });

    assert.equal(answer.body.correct, false);
    assert.equal(answer.body.correctIndex, question.answerIndex);
    assert.equal(answer.body.score, 0);
    assert.equal(answer.body.completed, false);
    assert.ok(answer.body.nextQuestion);
  } finally {
    await closeServer(server);
    cleanup();
  }
});

test('unknown games return 404', async () => {
  const { app, cleanup } = createTestApp();
  const { server, baseUrl } = await startServer(app);

  try {
    const score = await getJson(baseUrl, '/api/games/does-not-exist/score');
    assert.equal(score.status, 404);
    const answer = await postJson(baseUrl, '/api/games/does-not-exist/answer', { selectedIndex: 0 });
    assert.equal(answer.status, 404);
  } finally {
    await closeServer(server);
    cleanup();
  }
});
