'use strict';

const path = require('path');

const DEFAULT_DATA_DIR = path.join(__dirname, '..', 'data');

function loadConfig(overrides = {}) {
  const dataDir = process.env.DATA_DIR || DEFAULT_DATA_DIR;

  const config = {
    port: Number(process.env.PORT) || 3000,
    host: process.env.HOST || '0.0.0.0',
    adminToken: process.env.ADMIN_TOKEN || 'dev-admin-token',
    dataDir,
    questionsFile: process.env.QUESTIONS_FILE || path.join(dataDir, 'questions.json'),
    scoresFile: process.env.SCORES_FILE || path.join(dataDir, 'scores.json'),
    seedQuestionsFile: process.env.SEED_QUESTIONS_FILE || path.join(dataDir, 'seed-questions.json'),
    maxBodySize: '64kb'
  };

  return { ...config, ...overrides };
}

module.exports = loadConfig();
module.exports.loadConfig = loadConfig;
