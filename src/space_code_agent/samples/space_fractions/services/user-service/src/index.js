'use strict';

// Covers: ASR-2
const { createRouter, readJson, sendJson, bearer } = require('../../../lib/http');

function createUserApp({ auth } = {}) {
  if (!auth) throw new Error('auth service is required');
  const router = createRouter();

  router.get('/health', (req, res) => {
    sendJson(res, 200, { service: 'user-service', status: 'ok' });
  });

  router.post('/sessions', async (req, res) => {
    try {
      const body = await readJson(req);
      if (typeof body.username !== 'string' || typeof body.password !== 'string') {
        sendJson(res, 400, { error: 'invalid_credentials', message: 'username and password are required' });
        return;
      }
      const session = auth.login(body.username, body.password);
      if (!session) {
        sendJson(res, 401, { error: 'invalid_credentials', message: 'invalid username or password' });
        return;
      }
      sendJson(res, 200, session);
    } catch (error) {
      sendJson(res, error.statusCode || 400, { error: 'bad_request', message: error.message });
    }
  });

  router.post('/guests', (req, res) => {
    sendJson(res, 201, auth.guest());
  });

  router.get('/me', (req, res) => {
    const payload = auth.verify(bearer(req));
    if (!payload) {
      sendJson(res, 401, { error: 'unauthorized', message: 'valid bearer token required' });
      return;
    }
    sendJson(res, 200, { user: { username: payload.sub, role: payload.role }, expiresAt: payload.exp });
  });

  return router.handle;
}

module.exports = { createUserApp };
