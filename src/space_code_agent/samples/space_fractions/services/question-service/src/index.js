'use strict';

// Covers: FR-DERIVED-2, ASR-2
const { createRouter, readJson, sendJson, bearer } = require('../../../lib/http');

function authorized(req, expected) {
  if (!expected) return true;
  if (req.headers['x-service-token'] === expected) return true;
  return bearer(req) === expected;
}

function createQuestionApp({
  store,
  serviceToken = 'dev-service-token',
  adminToken = 'dev-admin-token',
} = {}) {
  if (!store) throw new Error('store is required');
  const router = createRouter();

  router.get('/health', (req, res) => {
    sendJson(res, 200, { service: 'question-service', status: 'ok', questions: store.count() });
  });

  router.get('/questions', (req, res) => {
    const count = Number(req.query.count || 10);
    if (!Number.isInteger(count) || count < 1 || count > 50) {
      sendJson(res, 400, { error: 'invalid_count', message: 'count must be between 1 and 50' });
      return;
    }
    sendJson(res, 200, { questions: store.random(count, false) });
  });

  router.get('/internal/questions', (req, res) => {
    if (!authorized(req, serviceToken)) {
      sendJson(res, 401, { error: 'unauthorized', message: 'service token required' });
      return;
    }
    const count = Number(req.query.count || 10);
    sendJson(res, 200, { questions: store.random(count, true) });
  });

  router.get('/admin/questions', (req, res) => {
    if (!authorized(req, adminToken)) {
      sendJson(res, 401, { error: 'unauthorized', message: 'admin token required' });
      return;
    }
    sendJson(res, 200, { questions: store.all(true) });
  });

  router.get('/questions/:id', (req, res) => {
    const question = store.get(req.params.id, false);
    if (!question) {
      sendJson(res, 404, { error: 'question_not_found' });
      return;
    }
    sendJson(res, 200, { question });
  });

  router.post('/questions', async (req, res) => {
    if (!authorized(req, adminToken)) {
      sendJson(res, 401, { error: 'unauthorized', message: 'admin token required' });
      return;
    }
    try {
      const body = await readJson(req);
      const question = store.create(body);
      sendJson(res, 201, { question });
    } catch (error) {
      sendJson(res, error.statusCode || 400, {
        error: 'invalid_question',
        message: error.message,
      });
    }
  });

  router.put('/questions/:id', async (req, res) => {
    if (!authorized(req, adminToken)) {
      sendJson(res, 401, { error: 'unauthorized', message: 'admin token required' });
      return;
    }
    try {
      const body = await readJson(req);
      const question = store.update(req.params.id, body);
      if (!question) {
        sendJson(res, 404, { error: 'question_not_found' });
        return;
      }
      sendJson(res, 200, { question });
    } catch (error) {
      sendJson(res, error.statusCode || 400, {
        error: 'invalid_question',
        message: error.message,
      });
    }
  });

  router.delete('/questions/:id', (req, res) => {
    if (!authorized(req, adminToken)) {
      sendJson(res, 401, { error: 'unauthorized', message: 'admin token required' });
      return;
    }
    const removed = store.remove(req.params.id);
    if (!removed) {
      sendJson(res, 404, { error: 'question_not_found' });
      return;
    }
    sendJson(res, 200, { deleted: true, id: req.params.id });
  });

  return router.handle;
}

module.exports = { createQuestionApp };
