'use strict';

// Covers: FR-1, FR-DERIVED-1, ASR-2
const crypto = require('node:crypto');
const { createRouter, readJson, sendJson } = require('../../../lib/http');
const { createGame, submitAnswer, publicState, result } = require('./game');

function createGameApp({
  questionClient,
  games = new Map(),
  questionCount = 10,
  idFactory = () => `game-${crypto.randomUUID()}`,
} = {}) {
  if (!questionClient || typeof questionClient.fetchQuestions !== 'function') {
    throw new Error('questionClient.fetchQuestions is required');
  }
  const router = createRouter();

  router.get('/health', (req, res) => {
    sendJson(res, 200, { service: 'game-service', status: 'ok', activeGames: games.size });
  });

  router.post('/games', async (req, res) => {
    try {
      const questions = await questionClient.fetchQuestions(questionCount);
      const game = createGame({ id: idFactory(), questions });
      games.set(game.id, game);
      sendJson(res, 201, {
        gameId: game.id,
        totalQuestions: game.totalQuestions,
        score: game.score,
        currentQuestion: publicState(game).currentQuestion,
      });
    } catch (error) {
      sendJson(res, error.statusCode || 502, {
        error: error.code || 'game_creation_failed',
        message: error.message,
      });
    }
  });

  router.get('/games/:id', (req, res) => {
    const game = games.get(req.params.id);
    if (!game) {
      sendJson(res, 404, { error: 'game_not_found' });
      return;
    }
    sendJson(res, 200, publicState(game));
  });

  router.post('/games/:id/answers', async (req, res) => {
    const game = games.get(req.params.id);
    if (!game) {
      sendJson(res, 404, { error: 'game_not_found' });
      return;
    }
    try {
      const body = await readJson(req);
      const outcome = submitAnswer(game, {
        questionId: body.questionId,
        choiceIndex: body.choiceIndex,
      });
      sendJson(res, 200, outcome);
    } catch (error) {
      sendJson(res, error.statusCode || 400, {
        error: error.code || 'invalid_answer',
        message: error.message,
      });
    }
  });

  router.get('/games/:id/result', (req, res) => {
    const game = games.get(req.params.id);
    if (!game) {
      sendJson(res, 404, { error: 'game_not_found' });
      return;
    }
    if (game.status !== 'finished') {
      sendJson(res, 409, { error: 'game_not_finished', message: 'answer all questions first' });
      return;
    }
    sendJson(res, 200, result(game));
  });

  router.get('/games', (req, res) => {
    sendJson(res, 200, {
      games: [...games.values()].map((game) => ({
        gameId: game.id,
        status: game.status,
        score: game.score,
      })),
    });
  });

  return router.handle;
}

module.exports = { createGameApp };
