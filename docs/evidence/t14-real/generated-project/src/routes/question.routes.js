'use strict';

const { Router } = require('../http');
const { requireAdmin } = require('../middleware/auth');

/**
 * Admin-only question management endpoints.
 *
 * FR-DERIVED-2 (Update Questions) is implemented through create, update and
 * delete operations. ASR-2 is enforced by the admin token guard.
 */
function questionRoutes({ questionService, config }) {
  const router = new Router();

  router.use(requireAdmin(config));

  router.get('/', (req, res) => {
    res.json({ questions: questionService.listQuestions() });
  });

  router.post('/', (req, res) => {
    const question = questionService.createQuestion(req.body);
    res.status(201).json({ question });
  });

  router.get('/:id', (req, res) => {
    const question = questionService.getQuestion(req.params.id);
    if (!question) {
      return res.status(404).json({ error: 'Not Found', message: 'Question not found.' });
    }
    res.json({ question });
  });

  router.put('/:id', (req, res) => {
    const question = questionService.updateQuestion(req.params.id, req.body);
    if (!question) {
      return res.status(404).json({ error: 'Not Found', message: 'Question not found.' });
    }
    res.json({ question });
  });

  router.delete('/:id', (req, res) => {
    const removed = questionService.deleteQuestion(req.params.id);
    if (!removed) {
      return res.status(404).json({ error: 'Not Found', message: 'Question not found.' });
    }
    res.status(204).end();
  });

  return router;
}

module.exports = questionRoutes;
