'use strict';

// Covers: FR-1
const { startServer } = require('../../../lib/http');
const { createQuestionClient } = require('./questionClient');
const { createGameApp } = require('./index');

const port = Number(process.env.PORT || process.env.PORT_GAME || 4002);
const questionServiceUrl = process.env.QUESTION_SERVICE_URL || 'http://127.0.0.1:4001';
const serviceToken = process.env.SERVICE_TOKEN || 'dev-service-token';

const app = createGameApp({
  questionClient: createQuestionClient({ baseUrl: questionServiceUrl, serviceToken }),
});

startServer(app, { port })
  .then(({ url }) => {
    // eslint-disable-next-line no-console
    console.log(`game-service listening on ${url} (questions: ${questionServiceUrl})`);
  })
  .catch((error) => {
    // eslint-disable-next-line no-console
    console.error('game-service failed to start:', error);
    process.exitCode = 1;
  });
