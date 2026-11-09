'use strict';

// Covers: FR-1, NFR-1
const test = require('node:test');
const assert = require('node:assert/strict');
const { createRouter, readJson, sendJson, startServer, stopServer, bearer } = require('../../lib/http');

test('router matches path parameters and returns 404 JSON', async (t) => {
  const router = createRouter();
  router.get('/items/:id', (req, res) => sendJson(res, 200, { id: req.params.id, query: req.query }));
  const { server, url } = await startServer(router.handle);
  t.after(() => stopServer(server));

  const found = await fetch(`${url}/items/q-42?verbose=1`);
  assert.equal(found.status, 200);
  assert.deepEqual(await found.json(), { id: 'q-42', query: { verbose: '1' } });

  const missing = await fetch(`${url}/nope`);
  assert.equal(missing.status, 404);
  assert.equal((await missing.json()).error, 'not_found');
});

test('readJson rejects invalid JSON and preserves bearer tokens', async (t) => {
  const router = createRouter();
  router.post('/echo', async (req, res) => {
    const body = await readJson(req);
    sendJson(res, 200, { body, token: bearer(req) });
  });
  const { server, url } = await startServer(router.handle);
  t.after(() => stopServer(server));

  const ok = await fetch(`${url}/echo`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', authorization: 'Bearer abc123' },
    body: JSON.stringify({ hello: 'world' }),
  });
  const payload = await ok.json();
  assert.deepEqual(payload.body, { hello: 'world' });
  assert.equal(payload.token, 'abc123');

  const bad = await fetch(`${url}/echo`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: '{not-json',
  });
  assert.equal(bad.status, 400);
});
