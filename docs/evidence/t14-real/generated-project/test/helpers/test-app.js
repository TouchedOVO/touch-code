'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const { createApp } = require('../../src/app');

const ADMIN_TOKEN = 'test-admin-token';

function loadSeedQuestions() {
  const seedPath = path.join(__dirname, '..', '..', 'data', 'seed-questions.json');
  return JSON.parse(fs.readFileSync(seedPath, 'utf8'));
}

/**
 * Create an isolated HTTP app backed by a fresh temporary data directory.
 * Seed questions are copied in on first boot exactly like the real server.
 */
function createTestApp(options = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'space-fractions-'));
  const config = {
    adminToken: options.adminToken || ADMIN_TOKEN,
    questionsFile: path.join(dir, 'questions.json'),
    scoresFile: path.join(dir, 'scores.json'),
    maxBodySize: '64kb',
    ...(options.config || {})
  };

  const app = createApp({
    config,
    seedQuestions: options.seedQuestions || loadSeedQuestions(),
    random: options.random
  });

  function cleanup() {
    fs.rmSync(dir, { recursive: true, force: true });
  }

  return { app, config, cleanup, dir };
}

function startServer(app) {
  return new Promise((resolve) => {
    const server = app.listen(0, '127.0.0.1', () => {
      const address = server.address();
      resolve({ server, baseUrl: `http://127.0.0.1:${address.port}` });
    });
  });
}

function closeServer(server) {
  return new Promise((resolve, reject) => {
    server.close((err) => (err ? reject(err) : resolve()));
  });
}

async function getJson(baseUrl, path) {
  const response = await fetch(`${baseUrl}${path}`);
  const body = await response.json();
  return { status: response.status, body };
}

async function postJson(baseUrl, path, payload, token) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${baseUrl}${path}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload)
  });
  const text = await response.text();
  const body = text ? JSON.parse(text) : {};
  return { status: response.status, body };
}

async function putJson(baseUrl, path, payload, token) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${baseUrl}${path}`, {
    method: 'PUT',
    headers,
    body: JSON.stringify(payload)
  });
  const text = await response.text();
  const body = text ? JSON.parse(text) : {};
  return { status: response.status, body };
}

async function deleteJson(baseUrl, path, token) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${baseUrl}${path}`, {
    method: 'DELETE',
    headers
  });
  return { status: response.status, body: null };
}

module.exports = {
  ADMIN_TOKEN,
  loadSeedQuestions,
  createTestApp,
  startServer,
  closeServer,
  getJson,
  postJson,
  putJson,
  deleteJson
};
