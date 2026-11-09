'use strict';

/**
 * Minimal identity boundary for the demo.
 *
 * Covers: ASR-2
 * The architecture document recommends OAuth2; this demo implements a small
 * HMAC-signed bearer-token flow for admins and anonymous guest sessions.
 * It is intentionally not a production identity provider.
 */

const crypto = require('node:crypto');

function createAuthService({
  adminUser = process.env.ADMIN_USER || 'admin',
  adminPassword = process.env.ADMIN_PASSWORD || 'space-fractions',
  secret = process.env.AUTH_SECRET || 'dev-only-secret',
  ttlSeconds = 3600,
  now = () => Date.now(),
} = {}) {
  function sign(encoded) {
    return crypto.createHmac('sha256', secret).update(encoded).digest('base64url');
  }

  function issue(username, role) {
    const payload = {
      sub: username,
      role,
      iat: now(),
      exp: now() + ttlSeconds * 1000,
    };
    const encoded = Buffer.from(JSON.stringify(payload)).toString('base64url');
    return `${encoded}.${sign(encoded)}`;
  }

  function verify(token) {
    if (!token || typeof token !== 'string') return null;
    const parts = token.split('.');
    if (parts.length !== 2) return null;
    const [encoded, signature] = parts;
    const expected = sign(encoded);
    const given = Buffer.from(signature);
    const wanted = Buffer.from(expected);
    if (given.length !== wanted.length || !crypto.timingSafeEqual(given, wanted)) {
      return null;
    }
    try {
      const payload = JSON.parse(Buffer.from(encoded, 'base64url').toString('utf8'));
      if (!payload || typeof payload.exp !== 'number' || payload.exp <= now()) return null;
      return payload;
    } catch {
      return null;
    }
  }

  function login(username, password) {
    if (username === adminUser && password === adminPassword) {
      return {
        token: issue(adminUser, 'admin'),
        role: 'admin',
        user: { username: adminUser, role: 'admin' },
      };
    }
    return null;
  }

  function guest() {
    const username = `guest-${crypto.randomBytes(4).toString('hex')}`;
    return {
      token: issue(username, 'student'),
      role: 'student',
      user: { username, role: 'student' },
    };
  }

  return { login, guest, verify, ttlSeconds };
}

module.exports = { createAuthService };
