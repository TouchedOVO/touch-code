'use strict';

/**
 * Minimal zero-dependency HTTP toolkit.
 *
 * Covers: FR-1, NFR-1
 * The architecture document recommends Express.js; this demo deliberately uses
 * node:http so the generated project can be verified without npm install.
 */

const http = require('node:http');

const MAX_BODY_BYTES = 1024 * 1024;

function sendJson(res, status, payload) {
  const body = JSON.stringify(payload);
  res.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'content-length': Buffer.byteLength(body),
    'cache-control': 'no-store',
  });
  res.end(body);
}

function sendText(res, status, text) {
  res.writeHead(status, {
    'content-type': 'text/plain; charset=utf-8',
    'content-length': Buffer.byteLength(text),
  });
  res.end(text);
}

function readJson(req, limit = MAX_BODY_BYTES) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    req.on('data', (chunk) => {
      size += chunk.length;
      if (size > limit) {
        const error = new Error('request body too large');
        error.statusCode = 413;
        reject(error);
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });
    req.on('end', () => {
      if (chunks.length === 0) {
        resolve({});
        return;
      }
      try {
        const parsed = JSON.parse(Buffer.concat(chunks).toString('utf8'));
        if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
          const error = new Error('JSON body must be an object');
          error.statusCode = 400;
          reject(error);
          return;
        }
        resolve(parsed);
      } catch {
        const error = new Error('invalid JSON body');
        error.statusCode = 400;
        reject(error);
      }
    });
    req.on('error', reject);
  });
}

function bearer(req) {
  const header = req.headers.authorization || '';
  const match = /^Bearer\s+(.+)$/i.exec(header);
  return match ? match[1].trim() : '';
}

function compile(pattern) {
  return pattern.split('/').filter((part) => part.length > 0);
}

function match(patternParts, pathParts) {
  if (patternParts.length !== pathParts.length) return null;
  const params = {};
  for (let i = 0; i < patternParts.length; i += 1) {
    const expected = patternParts[i];
    if (expected.startsWith(':')) {
      params[expected.slice(1)] = decodeURIComponent(pathParts[i]);
      continue;
    }
    if (expected !== pathParts[i]) return null;
  }
  return params;
}

function createRouter() {
  const routes = [];

  function add(method, pattern, handler) {
    routes.push({ method, parts: compile(pattern), handler });
  }

  async function handle(req, res) {
    res.setHeader('access-control-allow-origin', '*');
    res.setHeader('access-control-allow-headers', 'content-type, authorization, x-service-token');
    res.setHeader('access-control-allow-methods', 'GET, POST, PUT, DELETE, OPTIONS');
    if (req.method === 'OPTIONS') {
      res.writeHead(204);
      res.end();
      return;
    }
    const url = new URL(req.url, 'http://localhost');
    const pathParts = url.pathname.split('/').filter((part) => part.length > 0);
    for (const route of routes) {
      if (route.method !== req.method) continue;
      const params = match(route.parts, pathParts);
      if (params === null) continue;
      req.params = params;
      req.query = Object.fromEntries(url.searchParams.entries());
      try {
        await route.handler(req, res);
      } catch (error) {
        const status = error.statusCode || 500;
        sendJson(res, status, {
          error: status >= 500 ? 'internal_error' : 'request_error',
          message: status >= 500 ? 'unexpected server error' : error.message,
        });
      }
      return;
    }
    sendJson(res, 404, { error: 'not_found', path: url.pathname });
  }

  return {
    add,
    get: (pattern, handler) => add('GET', pattern, handler),
    post: (pattern, handler) => add('POST', pattern, handler),
    put: (pattern, handler) => add('PUT', pattern, handler),
    delete: (pattern, handler) => add('DELETE', pattern, handler),
    handle,
  };
}

function startServer(handler, { port = 0, host = '127.0.0.1' } = {}) {
  const server = http.createServer(handler);
  return new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, host, () => {
      server.removeListener('error', reject);
      const address = server.address();
      resolve({
        server,
        port: address.port,
        url: `http://${host}:${address.port}`,
      });
    });
  });
}

function stopServer(server) {
  return new Promise((resolve, reject) => {
    if (!server || !server.listening) {
      resolve();
      return;
    }
    server.close((error) => (error ? reject(error) : resolve()));
  });
}

function isJsonObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

module.exports = {
  sendJson,
  sendText,
  readJson,
  bearer,
  createRouter,
  startServer,
  stopServer,
  isJsonObject,
  MAX_BODY_BYTES,
};
