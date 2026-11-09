'use strict';

// Covers: FR-DERIVED-1, FR-DERIVED-3

const test = require('node:test');
const assert = require('node:assert/strict');

const {
  createTestApp,
  startServer,
  closeServer,
  getJson,
  postJson
} = require('./helpers/test-app');

test('help endpoint returns keyboard and scoring guidance for students', async () => {
  const { app, cleanup } = createTestApp();
  const { server, baseUrl } = await startServer(app);

  try {
    const help = await getJson(baseUrl, '/api/help');
    assert.equal(help.status, 200);
    assert.ok(help.body.title);
    assert.ok(Array.isArray(help.body.sections));
    assert.ok(help.body.sections.length >= 3);

    const bodyText = help.body.sections
      .map((section) => `${section.heading} ${section.body}`)
      .join(' ');
    assert.match(bodyText, /10/);
    assert.match(bodyText, /100/);
    assert.match(bodyText, /Tab|keyboard/i);
  } finally {
    await closeServer(server);
    cleanup();
  }
});

test('guest creation returns an id and score history is empty before play', async () => {
  const { app, cleanup } = createTestApp();
  const { server, baseUrl } = await startServer(app);

  try {
    const guest = await postJson(baseUrl, '/api/users/guest', {});
    assert.equal(guest.status, 201);
    assert.match(guest.body.guestId, /^guest-/);

    const scores = await getJson(baseUrl, `/api/users/${guest.body.guestId}/scores`);
    assert.equal(scores.status, 200);
    assert.equal(scores.body.guestId, guest.body.guestId);
    assert.deepEqual(scores.body.scores, []);
  } finally {
    await closeServer(server);
    cleanup();
  }
});

test('completed scores are returned for a guest', async () => {
  const { app, cleanup } = createTestApp();
  const { server, baseUrl } = await startServer(app);

  try {
    const guest = await postJson(baseUrl, '/api/users/guest', {});
    const created = await postJson(baseUrl, '/api/games', { guestId: guest.body.guestId });
    const gameId = created.body.game.id;
    const gameService = app.locals.services.gameService;
    const questionService = app.locals.services.questionService;

    for (let step = 0; step < 10; step += 1) {
      const game = gameService.getGame(gameId);
      const question = questionService.getQuestion(game.questionIds[game.currentIndex]);
      await postJson(baseUrl, `/api/games/${gameId}/answer`, {
        selectedIndex: question.answerIndex
      });
    }

    const scores = await getJson(baseUrl, `/api/users/${guest.body.guestId}/scores`);
    assert.equal(scores.status, 200);
    assert.equal(scores.body.scores.length, 1);
    assert.equal(scores.body.scores[0].score, 100);
    assert.equal(scores.body.scores[0].total, 100);
  } finally {
    await closeServer(server);
    cleanup();
  }
});
