'use strict';

/**
 * Minimal zero-dependency HTTP layer.
 *
 * Space Fractions originally targeted Express.js, but the local verification
 * environment runs `node --test` without installing npm packages. This module
 * provides the small subset of the Express API that the application and tests
 * rely on (use/get/post/put/delete, request.params/body/get, response
 * status/set/json/end) using only Node's built-in `http` module.
 *
 * Keeping this layer self-contained removes the runtime dependency on Express
 * while preserving the same route and middleware structure. See
 * docs/ASSUMPTIONS.md for the deliberate deviation.
 */

const http = require('http');
const fs = require('fs');
const path = require('path');

const MIME_TYPES = Object.freeze({
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.ico': 'image/x-icon',
  '.txt': 'text/plain; charset=utf-8'
});

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function joinPath(base, child) {
  if (!child || child === '/') return base || '/';
  if (!base || base === '/') return child.startsWith('/') ? child : `/${child}`;
  const left = base.endsWith('/') ? base.slice(0, -1) : base;
  const right = child.startsWith('/') ? child : `/${child}`;
  return `${left}${right}`;
}

function matchesPrefix(pathname, prefix) {
  if (!prefix || prefix === '/') return true;
  return pathname === prefix || pathname.startsWith(`${prefix}/`);
}

function compilePath(pattern) {
  const keys = [];
  let source = pattern
    .split('/')
    .map((part) => {
      if (part.startsWith(':')) {
        keys.push(part.slice(1));
        return '([^/]+)';
      }
      return escapeRegExp(part);
    })
    .join('/');

  if (pattern !== '/') source += '/?';
  return { keys, regex: new RegExp(`^${source}$`) };
}

function extractParams(match, keys) {
  const params = {};
  keys.forEach((key, index) => {
    params[key] = decodeURIComponent(match[index + 1]);
  });
  return params;
}

function parseByteSize(value) {
  const text = String(value || '64kb').trim().toLowerCase();
  const match = text.match(/^(\d+)(b|kb|mb)?$/);
  if (!match) return 64 * 1024;
  const amount = Number(match[1]);
  const unit = match[2] || 'b';
  if (unit === 'kb') return amount * 1024;
  if (unit === 'mb') return amount * 1024 * 1024;
  return amount;
}

function decorateRequest(rawReq) {
  const url = new URL(rawReq.url, 'http://localhost');
  rawReq.path = url.pathname;
  rawReq.query = url.searchParams;
  rawReq.params = {};
  rawReq.body = undefined;
  rawReq.get = function getHeader(name) {
    const key = String(name).toLowerCase();
    return rawReq.headers[key] === undefined ? '' : rawReq.headers[key];
  };
  return rawReq;
}

class Response {
  constructor(rawReq, rawRes) {
    this.req = rawReq;
    this.raw = rawRes;
    this.statusCode = 200;
    this.headersSent = false;
    this._headers = {};
  }

  status(code) {
    this.statusCode = code;
    return this;
  }

  set(headers) {
    Object.keys(headers).forEach((key) => {
      this._headers[key.toLowerCase()] = headers[key];
    });
    return this;
  }

  get(name) {
    return this._headers[String(name).toLowerCase()];
  }

  json(payload) {
    this.set({ 'content-type': 'application/json; charset=utf-8' });
    this.end(JSON.stringify(payload));
  }

  send(body) {
    if (Buffer.isBuffer(body) || typeof body === 'string') {
      if (!this.get('content-type')) {
        this.set({ 'content-type': 'text/html; charset=utf-8' });
      }
      this.end(body);
      return;
    }
    if (body && typeof body === 'object') {
      this.json(body);
      return;
    }
    this.end();
  }

  end(body) {
    if (this.headersSent) return;
    if (body === undefined || body === null) {
      this.raw.writeHead(this.statusCode, this._headers);
      this.raw.end();
    } else {
      this.raw.writeHead(this.statusCode, this._headers);
      this.raw.end(body);
    }
    this.headersSent = true;
  }
}

class Router {
  constructor() {
    this.layers = [];
    this.isRouter = true;
  }

  _addMiddleware(prefix, fn) {
    this.layers.push({ kind: 'middleware', prefix, fn });
    return this;
  }

  _addRouter(prefix, router) {
    this.layers.push({ kind: 'router', prefix, router });
    return this;
  }

  use(target, maybeHandler) {
    if (typeof target === 'function') {
      return this._addMiddleware('', target);
    }
    if (target && target.isRouter) {
      return this._addRouter('', target);
    }
    if (typeof target === 'string') {
      if (maybeHandler && maybeHandler.isRouter) {
        return this._addRouter(target, maybeHandler);
      }
      if (typeof maybeHandler === 'function') {
        return this._addMiddleware(target, maybeHandler);
      }
    }
    throw new TypeError('use() expects a middleware function, a Router, or a path and one of those.');
  }

  _route(method, pattern, handler) {
    this.layers.push({ kind: 'route', method: method.toUpperCase(), pattern, handler });
    return this;
  }

  get(pattern, handler) {
    return this._route('GET', pattern, handler);
  }

  post(pattern, handler) {
    return this._route('POST', pattern, handler);
  }

  put(pattern, handler) {
    return this._route('PUT', pattern, handler);
  }

  delete(pattern, handler) {
    return this._route('DELETE', pattern, handler);
  }
}

function flattenLayers(router, basePrefix) {
  const flattened = [];
  router.layers.forEach((layer) => {
    if (layer.kind === 'route') {
      const fullPath = joinPath(basePrefix, layer.pattern);
      flattened.push({
        kind: 'route',
        method: layer.method,
        path: fullPath,
        compiled: compilePath(fullPath),
        handler: layer.handler
      });
    } else if (layer.kind === 'middleware') {
      flattened.push({
        kind: 'middleware',
        prefix: joinPath(basePrefix, layer.prefix),
        fn: layer.fn
      });
    } else if (layer.kind === 'router') {
      flattened.push(...flattenLayers(layer.router, joinPath(basePrefix, layer.prefix)));
    }
  });
  return flattened;
}

function createApp() {
  const app = new Router();
  app.locals = {};
  app.errorHandlers = [];
  app._compiled = null;

  app.error = function registerErrorHandler(handler) {
    app.errorHandlers.push(handler);
    return app;
  };

  app.disable = function noopDisable() {
    return app;
  };

  app._getLayers = function getLayers() {
    if (!app._compiled) {
      app._compiled = flattenLayers(app, '');
    }
    return app._compiled;
  };

  app.handle = async function handleRequest(rawReq, rawRes) {
    const req = decorateRequest(rawReq);
    const res = new Response(req, rawRes);
    const layers = app._getLayers();
    let index = 0;

    const runError = async (error) => {
      if (!app.errorHandlers.length) {
        if (!res.headersSent) {
          res.status(500).json({ error: 'Internal Server Error', message: 'Internal server error.' });
        }
        return;
      }
      const handler = app.errorHandlers[0];
      try {
        await handler(error, req, res, () => {});
      } catch (secondaryError) {
        console.error('Error handler failed:', secondaryError);
        if (!res.headersSent) {
          res.status(500).json({ error: 'Internal Server Error', message: 'Internal server error.' });
        }
      }
    };

    const next = async (error) => {
      if (error) {
        await runError(error);
        return;
      }

      while (index < layers.length) {
        const layer = layers[index];
        index += 1;

        if (layer.kind === 'middleware') {
          if (!matchesPrefix(req.path, layer.prefix)) continue;
          try {
            await layer.fn(req, res, next);
          } catch (err) {
            await next(err);
          }
          return;
        }

        if (layer.kind === 'route') {
          if (layer.method !== req.method) continue;
          const match = layer.compiled.regex.exec(req.path);
          if (!match) continue;
          req.params = extractParams(match, layer.compiled.keys);
          try {
            await layer.handler(req, res, next);
          } catch (err) {
            await next(err);
          }
          return;
        }
      }

      // No route or terminal middleware handled this request.
      if (!res.headersSent) {
        res.status(404).json({ error: 'Not Found', message: `No route for ${req.method} ${req.path}.` });
      }
    };

    await next(null);
  };

  app.listen = function listen(...args) {
    const server = http.createServer((req, res) => {
      app.handle(req, res).catch((error) => {
        console.error('Unhandled request failure:', error);
        if (!res.headersSent) {
          res.statusCode = 500;
          res.setHeader('Content-Type', 'application/json; charset=utf-8');
          res.end(JSON.stringify({ error: 'Internal Server Error', message: 'Internal server error.' }));
        }
      });
    });
    return server.listen(...args);
  };

  return app;
}

function jsonParser(maxSize) {
  const limit = parseByteSize(maxSize);

  return function parseJson(req, res, next) {
    if (!['POST', 'PUT', 'PATCH', 'DELETE'].includes(req.method)) {
      next();
      return;
    }
    const contentType = req.get('content-type') || '';
    if (!contentType.toLowerCase().includes('application/json')) {
      next();
      return;
    }

    let body = '';
    let received = 0;
    let tooLarge = false;

    req.on('data', (chunk) => {
      received += chunk.length;
      if (received > limit) {
        tooLarge = true;
        return;
      }
      body += chunk;
    });

    req.on('end', () => {
      if (tooLarge) {
        const error = new Error('Request body is too large.');
        error.type = 'entity.too.large';
        next(error);
        return;
      }
      if (!body.trim()) {
        req.body = {};
        next();
        return;
      }
      try {
        req.body = JSON.parse(body);
        next();
      } catch (parseError) {
        const error = new Error('Request body must be valid JSON.');
        error.type = 'entity.parse.failed';
        next(error);
      }
    });

    req.on('error', (streamError) => {
      next(streamError);
    });
  };
}

function staticFiles(rootDir) {
  const root = path.resolve(rootDir);

  return function serveStatic(req, res, next) {
    if (req.method !== 'GET' && req.method !== 'HEAD') {
      next();
      return;
    }

    let pathname;
    try {
      pathname = decodeURIComponent(req.path);
    } catch (err) {
      next();
      return;
    }

    if (pathname === '/') pathname = '/index.html';

    // `'.' + pathname` keeps the path relative to root even when pathname
    // starts with a slash, and path.resolve normalises traversal attempts.
    const filePath = path.resolve(root, `.${pathname}`);
    if (filePath !== root && !filePath.startsWith(`${root}${path.sep}`)) {
      next();
      return;
    }

    fs.readFile(filePath, (err, data) => {
      if (err) {
        if (err.code === 'ENOENT' || err.code === 'EISDIR') {
          next();
          return;
        }
        next(err);
        return;
      }
      const extension = path.extname(filePath).toLowerCase();
      res.set({ 'content-type': MIME_TYPES[extension] || 'application/octet-stream' });
      res.send(data);
    });
  };
}

module.exports = {
  createApp,
  Router,
  jsonParser,
  staticFiles,
  parseByteSize,
  compilePath
};
