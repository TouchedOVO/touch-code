'use strict';

const config = require('./config');
const { createApp } = require('./app');

const app = createApp();

const server = app.listen(config.port, config.host, () => {
  console.log(`Space Fractions listening on http://localhost:${config.port}`);
  console.log(`Questions file: ${config.questionsFile}`);
  console.log(`Scores file: ${config.scoresFile}`);
});

server.on('error', (err) => {
  console.error('Failed to start server:', err);
  process.exit(1);
});
