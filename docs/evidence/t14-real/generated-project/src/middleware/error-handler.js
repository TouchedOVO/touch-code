'use strict';

/**
 * Security headers applied to every response (ASR-2). The strict CSP keeps the
 * static UI and API on the same origin and blocks third-party scripts/styles.
 */
function securityHeaders(req, res, next) {
  res.set({
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'Referrer-Policy': 'no-referrer',
    'Content-Security-Policy':
      "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
    'Cache-Control': 'no-store'
  });
  next();
}

function notFound(req, res) {
  res.status(404).json({
    error: 'Not Found',
    message: `No route for ${req.method} ${req.path}.`
  });
}

function errorHandler(err, req, res, next) {
  if (res.headersSent) {
    return next(err);
  }

  // Body parser errors from the built-in JSON parser in src/http.js.
  if (err.type === 'entity.parse.failed' || err.type === 'entity.too.large') {
    return res.status(400).json({
      error: 'Bad Request',
      message: 'Request body must be valid JSON and must not exceed the configured size limit.'
    });
  }

  const status = err.status || err.statusCode || 500;
  if (status >= 500) {
    // Log server faults but never leak stack traces to clients.
    console.error(`[${new Date().toISOString()}] ${req.method} ${req.path}`, err);
  }

  const payload = {
    error: err.name || 'Error',
    message: status >= 500 ? 'Internal server error.' : err.message
  };
  if (err.details && Array.isArray(err.details)) {
    payload.details = err.details;
  }
  res.status(status).json(payload);
}

module.exports = { securityHeaders, notFound, errorHandler };
