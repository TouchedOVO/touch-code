'use strict';

// Covers: NFR-1

const test = require('node:test');
const assert = require('node:assert/strict');

const {
  createTestApp,
  startServer,
  closeServer,
  postJson
} = require('./helpers/test-app');

/**
 * Representative latency threshold. The app has no database or network hop in
 * the test path, so these endpoints must complete far below the ceiling.
 */
const LATENCY_BUDGET_MS = 500;

async function measureLatency(callback) {
  const start = process.hrtime.bigint();
  await callback();
  const end = process.hrtime.bigint();
  return Number(end - start) / 1e6;
}

test('health and help endpoints respond within the latency budget', async () => {
  const { app, cleanup } = createTestApp();
  const { server, baseUrl } = await startServer(app);

  try {
    const health = await measureLatency(() => fetch(`${baseUrl}/api/health`).then((r) => r.json()));
    const help = await measureLatency(() => fetch(`${baseUrl}/api/help`).then((r) => r.json()));
    assert.ok(health < LATENCY_BUDGET_MS, `health took ${health.toFixed(2)}ms`);
    assert.ok(help < LATENCY_BUDGET_MS, `help took ${help.toFixed(2)}ms`);
  } finally {
    await closeServer(server);
    cleanup();
  }
});

test('game creation and a full answer loop stay within the latency budget', async () => {
  const { app, cleanup } = createTestApp();
  const { server, baseUrl } = await startServer(app);

  try {
    const guest = await postJson(baseUrl, '/api/users/guest', {});
    const created = await measureLatency(() =>
      postJson(baseUrl, '/api/games', { guestId: guest.body.guestId })
    );
    assert.ok(created < LATENCY_BUDGET_MS, `game creation took ${created.toFixed(2)}ms`);

    const createdGame = await postJson(baseUrl, '/api/games', { guestId: guest.body.guestId });
    const gameId = createdGame.body.game.id;
    const gameService = app.locals.services.gameService;
    const questionService = app.locals.services.questionService;

    for (let step = 0; step < 10; step += 1) {
      const game = gameService.getGame(gameId);
      const question = questionService.getQuestion(game.questionIds[game.currentIndex]);
      const latency = await measureLatency(() =>
        postJson(baseUrl, `/api/games/${gameId}/answer`, {
          selectedIndex: question.answerIndex
        })
      );
      assert.ok(latency < LATENCY_BUDGET_MS, `answer ${step + 1} took ${latency.toFixed(2)}ms`);
    }
  } finally {
    await closeServer(server);
    cleanup();
  }
});
