'use strict';

// Covers: ASR-2
const test = require('node:test');
const assert = require('node:assert/strict');
const { startServer, stopServer } = require('../../../lib/http');
const { createAuthService } = require('../src/auth');
const { createUserApp } = require('../src/index');

test('admin login, /me and guest sessions', async (t) => {
  const auth = createAuthService({
    adminUser: 'admin',
    adminPassword: 'secret',
    secret: 'test-secret',
  });
  const { server, url } = await startServer(createUserApp({ auth }));
  t.after(() => stopServer(server));

  const bad = await fetch(`${url}/sessions`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ username: 'admin', password: 'wrong' }),
  });
  assert.equal(bad.status, 401);

  const login = await fetch(`${url}/sessions`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ username: 'admin', password: 'secret' }),
  });
  assert.equal(login.status, 200);
  const session = await login.json();
  assert.equal(session.role, 'admin');

  const me = await fetch(`${url}/me`, {
    headers: { authorization: `Bearer ${session.token}` },
  });
  assert.equal(me.status, 200);
  assert.equal((await me.json()).user.role, 'admin');

  const tampered = await fetch(`${url}/me`, {
    headers: { authorization: `Bearer ${session.token}x` },
  });
  assert.equal(tampered.status, 401);

  const guest = await fetch(`${url}/guests`, { method: 'POST' });
  assert.equal(guest.status, 201);
  const guestSession = await guest.json();
  assert.equal(guestSession.role, 'student');
  assert.match(guestSession.user.username, /^guest-[0-9a-f]{8}$/);
});

test('expired tokens are rejected', () => {
  let clock = 1_000_000;
  const auth = createAuthService({ secret: 's', ttlSeconds: 10, now: () => clock });
  const session = auth.login('admin', 'space-fractions');
  assert.ok(auth.verify(session.token));
  clock += 11_000;
  assert.equal(auth.verify(session.token), null);
});
