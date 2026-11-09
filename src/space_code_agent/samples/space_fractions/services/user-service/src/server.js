'use strict';

// Covers: ASR-2
const { startServer } = require('../../../lib/http');
const { createAuthService } = require('./auth');
const { createUserApp } = require('./index');

const port = Number(process.env.PORT || process.env.PORT_USERS || 4003);
const auth = createAuthService();
const app = createUserApp({ auth });

startServer(app, { port })
  .then(({ url }) => {
    // eslint-disable-next-line no-console
    console.log(`user-service listening on ${url}`);
  })
  .catch((error) => {
    // eslint-disable-next-line no-console
    console.error('user-service failed to start:', error);
    process.exitCode = 1;
  });
