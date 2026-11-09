'use strict';

const { Router } = require('../http');
const { toPublicGame } = require('../domain/game');

/**
 * Play Game and View Score endpoints.
 *
 * The current question is projected without its answer index so players cannot
 * read the solution from the API response.
 */
function gameRoutes({ gameService }) {
  const router = new Router();

  router.post('/', (req, res) => {
    const guestId = req.body && req.body.guestId;
    const game = gameService.createGame(guestId);
    const question = gameService.getCurrentQuestion(game.id);
    res.status(201).json({ game: toPublicGame(game), question });
  });

  router.get('/:id', (req, res) => {
    const game = gameService.getGame(req.params.id);
    if (!game) {
      return res.status(404).json({ error: 'Not Found', message: 'Game not found.' });
    }
    const question = gameService.getCurrentQuestion(game.id);
    res.json({ game: toPublicGame(game), question });
  });

  router.post('/:id/answer', (req, res) => {
    const selectedIndex = req.body && req.body.selectedIndex;
    const result = gameService.submitAnswer(req.params.id, selectedIndex);
    res.json(result);
  });

  router.get('/:id/score', (req, res) => {
    const score = gameService.getScore(req.params.id);
    if (!score) {
      return res.status(404).json({ error: 'Not Found', message: 'Game not found.' });
    }
    res.json(score);
  });

  router.post('/:id/pause', (req, res) => {
    const game = gameService.pause(req.params.id);
    res.json({ game: toPublicGame(game) });
  });

  router.post('/:id/resume', (req, res) => {
    const game = gameService.resume(req.params.id);
    res.json({ game: toPublicGame(game) });
  });

  return router;
}

module.exports = gameRoutes;
