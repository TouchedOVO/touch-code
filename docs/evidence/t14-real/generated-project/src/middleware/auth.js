'use strict';

const crypto = require('crypto');

/**
 * Constant-time token comparison so that an attacker cannot infer the admin
 * token character by character from response timing.
 */
function tokensEqual(a, b) {
  const hashA = crypto.createHash('sha256').update(String(a)).digest();
  const hashB = crypto.createHash('sha256').update(String(b)).digest();
  return crypto.timingSafeEqual(hashA, hashB);
}

/**
 * Admin authentication middleware (ASR-2).
 *
 * Accepts either `Authorization: Bearer <token>` or the `x-admin-token`
 * header. The token itself is supplied through the ADMIN_TOKEN environment
 * variable and never hard-coded into source or committed secrets.
 */
function requireAdmin(config) {
  const expected = String(config.adminToken || '');
  return function adminGuard(req, res, next) {
    const authorization = req.get('authorization') || '';
    const bearer = authorization.startsWith('Bearer ') ? authorization.slice(7).trim() : '';
    const token = bearer || req.get('x-admin-token') || '';

    if (!token || !tokensEqual(token, expected)) {
      return res.status(401).json({
        error: 'Unauthorized',
        message: 'A valid admin token is required.'
      });
    }
    next();
  };
}

module.exports = { requireAdmin, tokensEqual };
