'use strict';

// Covers: FR-1, FR-DERIVED-1, ASR-1
const path = require('node:path');
const { startServer } = require('../../../lib/http');
const { createQuestionStore } = require('./store');
const { createQuestionApp } = require('./index');

const port = Number(process.env.PORT || process.env.PORT_QUESTIONS || 4001);
const serviceToken = process.env.SERVICE_TOKEN || 'dev-service-token';
const adminToken = process.env.ADMIN_TOKEN || 'dev-admin-token';
const persistPath = process.env.QUESTION_DB_PATH
  || path.join(__dirname, '..', '..', '..', 'data', 'questions.json');

const store = createQuestionStore(undefined, { persistPath });
const app = createQuestionApp({ store, serviceToken, adminToken });

startServer(app, { port })
  .then(({ url }) => {
    // eslint-disable-next-line no-console
    console.log(`question-service listening on ${url} (${store.count()} questions)`);
  })
  .catch((error) => {
    // eslint-disable-next-line no-console
    console.error('question-service failed to start:', error);
    process.exitCode = 1;
  });
