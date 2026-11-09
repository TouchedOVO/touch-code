'use strict';

// Requirement coverage: [FR-1] [NFR-1] [ASR-2] [FR-DERIVED-1] [FR-DERIVED-2] [FR-DERIVED-3]

/**
 * Space Fractions — HTTP entry point.
 *
 * Exposes the domain logic as a small REST API using only node:http.
 * `createServer` is exported so the end-to-end test can start an ephemeral
 * instance without binding to a fixed port.
 */

const http = require('node:http');
const { URL } = require('node:url');

const {
  createApp,
  ValidationError,
  NotFoundError,
  ConflictError,
  UnauthorizedError,
} = require('./domain');

const DEFAULT_PORT = 3000;
const MAX_BODY_BYTES = 64 * 1024;
const DEFAULT_ADMIN_TOKEN = 'dev-admin-token';

const GAME_ROUTE = /^\/api\/games\/([^/]+)$/;
const GAME_ACTION_ROUTE = /^\/api\/games\/([^/]+)\/(answers|pause|resume|reset)$/;
const QUESTION_ROUTE = /^\/api\/questions\/([^/]+)$/;

function sendJson(res, statusCode, payload) {
  const body = JSON.stringify(payload);
  res.writeHead(statusCode, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(body),
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff',
  });
  res.end(body);
}

function sendNoContent(res) {
  res.writeHead(204, {
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff',
  });
  res.end();
}

function sendError(res, error) {
  const statusCode = statusCodeFor(error);
  if (statusCode >= 500) {
    // Log unexpected errors server-side without leaking internals to clients.
    console.error(error);
  }
  sendJson(res, statusCode, {
    error: statusCode >= 500 ? 'Internal server error' : error.message,
  });
}

function statusCodeFor(error) {
  if (error instanceof ValidationError) return 400;
  if (error instanceof UnauthorizedError) return 401;
  if (error instanceof NotFoundError) return 404;
  if (error instanceof ConflictError) return 409;
  return 500;
}

function readJsonBody(req) {
  return new Promise((resolve, reject) => {
    let raw = '';
    let received = 0;

    req.on('data', (chunk) => {
      received += chunk.length;
      if (received > MAX_BODY_BYTES) {
        reject(new ValidationError('Request body is too large'));
        req.resume();
        return;
      }
      raw += chunk;
    });

    req.on('end', () => {
      if (raw.trim() === '') {
        resolve({});
        return;
      }
      try {
        resolve(JSON.parse(raw));
      } catch {
        reject(new ValidationError('Request body must be valid JSON'));
      }
    });

    req.on('error', reject);
  });
}

function requireAdmin(req, app) {
  const header = req.headers.authorization || '';
  const token = header.startsWith('Bearer ') ? header.slice(7) : header;
  app.adminComponent.authorize(token);
}

function decodeSegment(segment) {
  try {
    return decodeURIComponent(segment);
  } catch {
    throw new ValidationError('Path segment is not valid URL encoding');
  }
}

async function handleRequest(req, res, app) {
  const url = new URL(req.url, 'http://localhost');
  const path = url.pathname;
  const method = req.method.toUpperCase();

  if (method === 'GET' && path === '/') {
    return sendJson(res, 200, {
      service: 'space-fractions',
      description: 'Fraction-solving practice for sixth-grade students',
      health: '/api/health',
      help: '/api/help',
      startGame: 'POST /api/games',
    });
  }

  if (method === 'GET' && path === '/api/health') {
    return sendJson(res, 200, { status: 'ok', service: 'space-fractions' });
  }

  if (method === 'GET' && path === '/api/help') {
    return sendJson(res, 200, app.userComponent.help());
  }

  if (method === 'POST' && path === '/api/games') {
    const guest = app.userComponent.createGuest();
    const game = app.gameComponent.start(guest.guestId);
    return sendJson(res, 201, { game: game.toView() });
  }

  const gameAction = path.match(GAME_ACTION_ROUTE);
  if (gameAction) {
    const id = decodeSegment(gameAction[1]);
    const action = gameAction[2];

    if (method === 'POST' && action === 'answers') {
      const body = await readJsonBody(req);
      const { selectedIndex } = body;
      if (!Number.isInteger(selectedIndex)) {
        throw new ValidationError('selectedIndex must be an integer');
      }
      const result = app.gameComponent.answer(id, selectedIndex);
      return sendJson(res, 200, { result, game: app.gameComponent.view(id) });
    }

    if (method === 'POST' && action === 'pause') {
      return sendJson(res, 200, { game: app.gameComponent.pause(id) });
    }

    if (method === 'POST' && action === 'resume') {
      return sendJson(res, 200, { game: app.gameComponent.resume(id) });
    }

    if (method === 'POST' && action === 'reset') {
      const game = app.gameComponent.reset(id);
      return sendJson(res, 200, { game: game.toView() });
    }
  }

  const gameMatch = path.match(GAME_ROUTE);
  if (gameMatch && method === 'GET') {
    const id = decodeSegment(gameMatch[1]);
    return sendJson(res, 200, { game: app.gameComponent.view(id) });
  }

  if (method === 'GET' && path === '/api/questions') {
    requireAdmin(req, app);
    return sendJson(res, 200, {
      questions: app.questionComponent.list(),
      count: app.questionComponent.count(),
    });
  }

  if (method === 'POST' && path === '/api/questions') {
    requireAdmin(req, app);
    const body = await readJsonBody(req);
    const question = app.questionComponent.create(body);
    return sendJson(res, 201, { question });
  }

  const questionMatch = path.match(QUESTION_ROUTE);
  if (questionMatch) {
    const id = decodeSegment(questionMatch[1]);

    if (method === 'GET') {
      requireAdmin(req, app);
      return sendJson(res, 200, { question: app.questionComponent.get(id) });
    }

    if (method === 'PUT') {
      requireAdmin(req, app);
      const body = await readJsonBody(req);
      const question = app.questionComponent.update(id, body);
      return sendJson(res, 200, { question });
    }

    if (method === 'DELETE') {
      requireAdmin(req, app);
      app.questionComponent.remove(id);
      return sendNoContent(res);
    }
  }

  throw new NotFoundError(`Route not found: ${method} ${path}`);
}

function createServer({ adminToken = process.env.ADMIN_TOKEN || DEFAULT_ADMIN_TOKEN, seedQuestions } = {}) {
  const app = createApp({ adminToken, seedQuestions });

  return http.createServer((req, res) => {
    handleRequest(req, res, app).catch((error) => {
      sendError(res, error);
    });
  });
}

function start() {
  const port = Number(process.env.PORT || DEFAULT_PORT);
  const server = createServer();
  server.listen(port, () => {
    console.log(`Space Fractions listening on http://127.0.0.1:${port}`);
  });
  return server;
}

if (require.main === module) {
  start();
}

module.exports = {
  createServer,
  start,
  DEFAULT_PORT,
  DEFAULT_ADMIN_TOKEN,
  MAX_BODY_BYTES,
};
