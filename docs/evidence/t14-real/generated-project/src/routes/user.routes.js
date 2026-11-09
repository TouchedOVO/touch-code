'use strict';

const { Router } = require('../http');

/**
 * Guest sessions, score history (FR-DERIVED-1) and help (FR-DERIVED-3)
 * endpoints exposed by the UserComponent boundary.
 */
function userRoutes({ userService }) {
  const router = new Router();

  router.post('/users/guest', (req, res) => {
    res.status(201).json(userService.createGuest());
  });

  router.get('/users/:guestId/scores', (req, res) => {
    res.json(userService.getScores(req.params.guestId));
  });

  router.get('/help', (req, res) => {
    res.json(userService.getHelp());
  });

  return router;
}

module.exports = userRoutes;
