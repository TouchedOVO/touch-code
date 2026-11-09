'use strict';

const fs = require('fs');
const path = require('path');

const defaultConfig = require('./config');
const { createApp: createHttpApp, jsonParser, staticFiles } = require('./http');
const QuestionRepository = require('./repositories/question.repository');
const ScoreRepository = require('./repositories/score.repository');
const QuestionService = require('./services/question.service');
const GameService = require('./services/game.service');
const UserService = require('./services/user.service');
const questionRoutes = require('./routes/question.routes');
const gameRoutes = require('./routes/game.routes');
const userRoutes = require('./routes/user.routes');
const { securityHeaders, notFound, errorHandler } = require('./middleware/error-handler');

function readSeedQuestions(filePath) {
  try {
    const raw = fs.readFileSync(filePath, 'utf8');
    const data = JSON.parse(raw);
    return Array.isArray(data) ? data : [];
  } catch (err) {
    if (err.code !== 'ENOENT') {
      console.warn(`Could not read seed questions from ${filePath}: ${err.message}`);
    }
    return [];
  }
}

/**
 * HTTP application factory.
 *
 * The three documented service boundaries (Game, Question, User) are wired as
 * separate modules but executed inside one Node.js process so the demo can run
 * without external cloud services. See docs/ASSUMPTIONS.md for the deliberate
 * modular-monolith deviation from the microservices style.
 *
 * The application uses the zero-dependency HTTP adapter in src/http.js instead
 * of Express so that `node --test` and `npm start` both work without an
 * `npm install` step in offline environments.
 */
function createApp(options = {}) {
  const config = { ...defaultConfig, ...(options.config || {}) };
  const seedQuestions = options.seedQuestions || readSeedQuestions(config.seedQuestionsFile);

  const questionRepository =
    options.questionRepository ||
    new QuestionRepository({ filePath: config.questionsFile, seed: seedQuestions });
  const scoreRepository =
    options.scoreRepository || new ScoreRepository({ filePath: config.scoresFile });

  const questionService = options.questionService || new QuestionService({ questionRepository });
  const gameService =
    options.gameService ||
    new GameService({ questionService, scoreRepository, random: options.random || Math.random });
  const userService = options.userService || new UserService({ scoreRepository });

  const app = createHttpApp();
  app.disable('x-powered-by');
  app.use(securityHeaders);
  app.use(jsonParser(config.maxBodySize));
  app.use(staticFiles(path.join(__dirname, '..', 'public')));

  app.get('/api/health', (req, res) => {
    res.json({ ok: true, service: 'space-fractions', questions: questionService.count() });
  });

  app.use('/api/questions', questionRoutes({ questionService, config }));
  app.use('/api/games', gameRoutes({ gameService }));
  app.use('/api', userRoutes({ userService }));

  app.use(notFound);
  app.error(errorHandler);

  app.locals.services = { questionService, gameService, userService };
  app.locals.repositories = { questionRepository, scoreRepository };

  return app;
}

module.exports = { createApp, readSeedQuestions };
