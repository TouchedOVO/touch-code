'use strict';

// Requirement coverage: [FR-1] [ASR-1] [ASR-2] [FR-DERIVED-1] [FR-DERIVED-2] [FR-DERIVED-3]

/**
 * Space Fractions — domain logic.
 *
 * The architecture requested separate Game / Question / User / Admin service
 * boundaries. This modular monolith preserves those boundaries as explicit
 * classes with narrow responsibilities while keeping the demo dependency-free.
 */

const crypto = require('node:crypto');

const QUESTION_COUNT_PER_GAME = 10;
const POINTS_PER_CORRECT = 10;
const MAX_SCORE = 100;
const OPTION_COUNT = 4;

const GAME_STATES = Object.freeze({
  PLAYING: 'playing',
  PAUSED: 'paused',
  GAME_OVER: 'gameover',
});

class ValidationError extends Error {
  constructor(message) {
    super(message);
    this.name = 'ValidationError';
  }
}

class NotFoundError extends Error {
  constructor(message) {
    super(message);
    this.name = 'NotFoundError';
  }
}

class ConflictError extends Error {
  constructor(message) {
    super(message);
    this.name = 'ConflictError';
  }
}

class UnauthorizedError extends Error {
  constructor(message) {
    super(message);
    this.name = 'UnauthorizedError';
  }
}

function randomId(prefix) {
  return `${prefix}_${crypto.randomUUID()}`;
}

function randomGuestId() {
  return `guest_${crypto.randomUUID()}`;
}

function cloneQuestion(question) {
  return {
    id: question.id,
    prompt: question.prompt,
    options: [...question.options],
    correctIndex: question.correctIndex,
    category: question.category,
  };
}

/**
 * Validate a question shape. A partial `base` is allowed so updates can reuse
 * the same validation path.
 */
function normaliseQuestion(input, base = {}) {
  const prompt = input.prompt !== undefined ? input.prompt : base.prompt;
  const options = input.options !== undefined ? input.options : base.options;
  const correctIndex =
    input.correctIndex !== undefined ? input.correctIndex : base.correctIndex;
  const category = input.category !== undefined ? input.category : base.category;

  if (typeof prompt !== 'string' || prompt.trim() === '') {
    throw new ValidationError('question.prompt must be a non-empty string');
  }

  if (!Array.isArray(options) || options.length !== OPTION_COUNT) {
    throw new ValidationError(
      `question.options must be an array of exactly ${OPTION_COUNT} strings`,
    );
  }

  const trimmedOptions = options.map((option) => {
    if (typeof option !== 'string' || option.trim() === '') {
      throw new ValidationError('question.options must contain only non-empty strings');
    }
    return option.trim();
  });

  if (
    !Number.isInteger(correctIndex) ||
    correctIndex < 0 ||
    correctIndex >= OPTION_COUNT
  ) {
    throw new ValidationError(
      `question.correctIndex must be an integer between 0 and ${OPTION_COUNT - 1}`,
    );
  }

  if (typeof category !== 'string' || category.trim() === '') {
    throw new ValidationError('question.category must be a non-empty string');
  }

  return {
    prompt: prompt.trim(),
    options: trimmedOptions,
    correctIndex,
    category: category.trim(),
  };
}

function createQuestion(input = {}) {
  if (
    input.id !== undefined &&
    (typeof input.id !== 'string' || input.id.trim() === '')
  ) {
    throw new ValidationError('question.id must be a non-empty string when provided');
  }

  const id = input.id !== undefined ? input.id : randomId('q');
  const normalised = normaliseQuestion(input);
  return { id, ...normalised };
}

/**
 * In-memory question store. This is the seam for an optional PostgreSQL adapter:
 * any replacement should expose list/get/add/update/remove/count/pick.
 */
class InMemoryQuestionRepository {
  constructor(seed = []) {
    this._questions = new Map();
    for (const item of seed) {
      const question = createQuestion(item);
      if (this._questions.has(question.id)) {
        throw new ConflictError(`Duplicate seed question id: ${question.id}`);
      }
      this._questions.set(question.id, question);
    }
  }

  list() {
    return [...this._questions.values()].map(cloneQuestion);
  }

  get(id) {
    const question = this._questions.get(id);
    return question ? cloneQuestion(question) : null;
  }

  add(input) {
    const question = createQuestion(input);
    if (this._questions.has(question.id)) {
      throw new ConflictError(`Question already exists: ${question.id}`);
    }
    this._questions.set(question.id, question);
    return cloneQuestion(question);
  }

  update(id, patch = {}) {
    const existing = this._questions.get(id);
    if (!existing) return null;

    // The route id always wins so an update cannot move a question to a new key.
    const merged = { ...existing, ...patch, id };
    const updated = createQuestion(merged);
    this._questions.set(id, updated);
    return cloneQuestion(updated);
  }

  remove(id) {
    return this._questions.delete(id);
  }

  count() {
    return this._questions.size;
  }

  /**
   * Return up to `count` questions in a random order. If fewer questions exist,
   * all of them are returned (documented in ASSUMPTIONS.md).
   */
  pick(count) {
    const all = this.list();
    for (let i = all.length - 1; i > 0; i -= 1) {
      const j = crypto.randomInt(i + 1);
      [all[i], all[j]] = [all[j], all[i]];
    }
    return all.slice(0, Math.min(count, all.length));
  }
}

/**
 * GameComponent — starts games, applies answers and owns game state.
 */
class Game {
  constructor({ id, guestId, questions }) {
    this.id = id;
    this.guestId = guestId;
    this.status = GAME_STATES.PLAYING;
    this.questions = questions.map((question) => ({
      ...cloneQuestion(question),
      selectedIndex: null,
    }));
    this.currentIndex = 0;
    this.score = 0;
    this.startedAt = new Date().toISOString();
    this.endedAt = null;
  }

  get currentQuestion() {
    if (this.status !== GAME_STATES.PLAYING) return null;
    return this.questions[this.currentIndex] ?? null;
  }

  answer(selectedIndex) {
    if (this.status === GAME_STATES.GAME_OVER) {
      throw new ValidationError('Game is already over');
    }
    if (this.status === GAME_STATES.PAUSED) {
      throw new ValidationError('Game is paused; resume before answering');
    }
    if (
      !Number.isInteger(selectedIndex) ||
      selectedIndex < 0 ||
      selectedIndex >= OPTION_COUNT
    ) {
      throw new ValidationError(
        `selectedIndex must be an integer between 0 and ${OPTION_COUNT - 1}`,
      );
    }

    const question = this.currentQuestion;
    if (!question) {
      throw new ValidationError('No current question available');
    }

    const correct = selectedIndex === question.correctIndex;
    if (correct) this.score += POINTS_PER_CORRECT;
    question.selectedIndex = selectedIndex;

    const wasLastQuestion = this.currentIndex === this.questions.length - 1;
    if (wasLastQuestion) {
      this.status = GAME_STATES.GAME_OVER;
      this.endedAt = new Date().toISOString();
    } else {
      this.currentIndex += 1;
    }

    return {
      correct,
      correctIndex: question.correctIndex,
      score: this.score,
      gameOver: this.status === GAME_STATES.GAME_OVER,
    };
  }

  pause() {
    if (this.status !== GAME_STATES.PLAYING) {
      throw new ValidationError('Only a playing game can be paused');
    }
    this.status = GAME_STATES.PAUSED;
  }

  resume() {
    if (this.status !== GAME_STATES.PAUSED) {
      throw new ValidationError('Only a paused game can be resumed');
    }
    this.status = GAME_STATES.PLAYING;
  }

  toView() {
    const currentQuestion = this.currentQuestion;
    const results = this.questions
      .filter((question) => question.selectedIndex !== null)
      .map((question, index) => ({
        number: index + 1,
        prompt: question.prompt,
        selectedIndex: question.selectedIndex,
        correctIndex: question.correctIndex,
        correct: question.selectedIndex === question.correctIndex,
      }));

    return {
      id: this.id,
      guestId: this.guestId,
      status: this.status,
      currentIndex: this.currentIndex,
      totalQuestions: this.questions.length,
      score: this.score,
      maxScore: MAX_SCORE,
      startedAt: this.startedAt,
      endedAt: this.endedAt,
      currentQuestion: currentQuestion
        ? {
            number: this.currentIndex + 1,
            prompt: currentQuestion.prompt,
            options: [...currentQuestion.options],
            category: currentQuestion.category,
          }
        : null,
      results,
    };
  }
}

class GameComponent {
  constructor({ questionComponent, questionCount = QUESTION_COUNT_PER_GAME, idGenerator } = {}) {
    if (
      !Number.isInteger(questionCount) ||
      questionCount < 1 ||
      questionCount > MAX_SCORE / POINTS_PER_CORRECT
    ) {
      throw new ValidationError(
        `questionCount must be an integer between 1 and ${MAX_SCORE / POINTS_PER_CORRECT}`,
      );
    }
    this.questionComponent = questionComponent;
    this.questionCount = questionCount;
    this.idGenerator = idGenerator || ((prefix) => randomId(prefix));
    this.games = new Map();
  }

  start(guestId) {
    const questions = this.questionComponent.pick(this.questionCount);
    if (questions.length === 0) {
      throw new ValidationError('No questions available to start a game');
    }
    const game = new Game({
      id: this.idGenerator('g'),
      guestId,
      questions,
    });
    this.games.set(game.id, game);
    return game;
  }

  get(id) {
    const game = this.games.get(id);
    if (!game) throw new NotFoundError(`Game not found: ${id}`);
    return game;
  }

  view(id) {
    return this.get(id).toView();
  }

  answer(id, selectedIndex) {
    return this.get(id).answer(selectedIndex);
  }

  pause(id) {
    this.get(id).pause();
    return this.view(id);
  }

  resume(id) {
    this.get(id).resume();
    return this.view(id);
  }

  reset(id) {
    const existing = this.get(id);
    const questions = this.questionComponent.pick(this.questionCount);
    if (questions.length === 0) {
      throw new ValidationError('No questions available to reset a game');
    }
    const game = new Game({
      id: existing.id,
      guestId: existing.guestId,
      questions,
    });
    this.games.set(game.id, game);
    return game;
  }
}

/**
 * QuestionComponent — question management and persistence boundary.
 */
class QuestionComponent {
  constructor(repository) {
    this.repository = repository;
  }

  list() {
    return this.repository.list();
  }

  count() {
    return this.repository.count();
  }

  get(id) {
    const question = this.repository.get(id);
    if (!question) throw new NotFoundError(`Question not found: ${id}`);
    return question;
  }

  create(input) {
    return this.repository.add(input);
  }

  update(id, patch) {
    const question = this.repository.update(id, patch);
    if (!question) throw new NotFoundError(`Question not found: ${id}`);
    return question;
  }

  remove(id) {
    if (!this.repository.remove(id)) {
      throw new NotFoundError(`Question not found: ${id}`);
    }
    return true;
  }

  pick(count) {
    return this.repository.pick(count);
  }
}

/**
 * UserComponent — guest identity and player-facing help.
 */
class UserComponent {
  createGuest() {
    return {
      guestId: randomGuestId(),
      role: 'guest',
    };
  }

  help() {
    return {
      title: 'How to play Space Fractions',
      steps: [
        'Start a game to receive 10 fraction questions.',
        'Choose one of the four answers for each question.',
        'Earn 10 points for each correct answer, up to a maximum of 100.',
        'Your final score is displayed when the game is over.',
        'Use "reset" to play again with the same guest ID.',
      ],
      controls: [
        'Start game: POST /api/games',
        'Answer: POST /api/games/:id/answers',
        'View score: GET /api/games/:id',
      ],
    };
  }
}

function constantTimeEqual(left, right) {
  const a = Buffer.from(String(left));
  const b = Buffer.from(String(right));
  if (a.length !== b.length) return false;
  return crypto.timingSafeEqual(a, b);
}

/**
 * AdminComponent — authorization boundary for question management.
 */
class AdminComponent {
  constructor({ token = '', verify = constantTimeEqual } = {}) {
    this.token = String(token);
    this.verify = verify;
  }

  authorize(candidate) {
    if (typeof candidate !== 'string' || !this.verify(candidate, this.token)) {
      throw new UnauthorizedError('Invalid or missing admin token');
    }
    return true;
  }
}

/**
 * Wires the logical components together into an in-process application facade.
 */
function createApp({ adminToken = '', seedQuestions = DEFAULT_SEED_QUESTIONS, questionCount } = {}) {
  const questionRepository = new InMemoryQuestionRepository(seedQuestions);
  const questionComponent = new QuestionComponent(questionRepository);
  const gameComponent = new GameComponent({ questionComponent, questionCount });
  const userComponent = new UserComponent();
  const adminComponent = new AdminComponent({ token: adminToken });

  return {
    questionComponent,
    gameComponent,
    userComponent,
    adminComponent,
  };
}

const DEFAULT_SEED_QUESTIONS = [
  {
    id: 'q_fr_add_1',
    prompt: '1/2 + 1/4 = ?',
    options: ['2/6', '3/4', '1/3', '2/4'],
    correctIndex: 1,
    category: 'addition',
  },
  {
    id: 'q_fr_sub_1',
    prompt: '3/5 - 1/5 = ?',
    options: ['4/5', '3/10', '2/5', '1/5'],
    correctIndex: 2,
    category: 'subtraction',
  },
  {
    id: 'q_fr_add_2',
    prompt: '1/3 + 1/6 = ?',
    options: ['2/9', '1/2', '1/6', '2/3'],
    correctIndex: 1,
    category: 'addition',
  },
  {
    id: 'q_fr_mul_1',
    prompt: '1/2 x 1/4 = ?',
    options: ['1/6', '2/6', '1/2', '1/8'],
    correctIndex: 3,
    category: 'multiplication',
  },
  {
    id: 'q_fr_div_1',
    prompt: '3/4 / 1/2 = ?',
    options: ['3/2', '3/8', '2/3', '4/6'],
    correctIndex: 0,
    category: 'division',
  },
  {
    id: 'q_fr_add_3',
    prompt: '2/3 + 1/6 = ?',
    options: ['3/9', '1/2', '5/6', '2/6'],
    correctIndex: 2,
    category: 'addition',
  },
  {
    id: 'q_fr_sub_2',
    prompt: '5/6 - 1/3 = ?',
    options: ['4/3', '5/18', '2/6', '1/2'],
    correctIndex: 3,
    category: 'subtraction',
  },
  {
    id: 'q_fr_mul_2',
    prompt: '2/5 x 3/4 = ?',
    options: ['6/9', '3/10', '5/8', '8/15'],
    correctIndex: 1,
    category: 'multiplication',
  },
  {
    id: 'q_fr_sub_3',
    prompt: '7/8 - 1/2 = ?',
    options: ['6/8', '7/16', '3/8', '1/2'],
    correctIndex: 2,
    category: 'subtraction',
  },
  {
    id: 'q_fr_div_2',
    prompt: '4/5 / 2/3 = ?',
    options: ['8/15', '5/6', '2/5', '6/5'],
    correctIndex: 3,
    category: 'division',
  },
  {
    id: 'q_fr_add_4',
    prompt: '1/4 + 3/8 = ?',
    options: ['5/8', '4/12', '3/8', '1/2'],
    correctIndex: 0,
    category: 'addition',
  },
  {
    id: 'q_fr_sub_4',
    prompt: '2/3 - 1/6 = ?',
    options: ['1/6', '1/2', '2/6', '3/6'],
    correctIndex: 1,
    category: 'subtraction',
  },
];

module.exports = {
  QUESTION_COUNT_PER_GAME,
  POINTS_PER_CORRECT,
  MAX_SCORE,
  OPTION_COUNT,
  GAME_STATES,
  DEFAULT_SEED_QUESTIONS,
  ValidationError,
  NotFoundError,
  ConflictError,
  UnauthorizedError,
  randomId,
  randomGuestId,
  constantTimeEqual,
  createQuestion,
  normaliseQuestion,
  InMemoryQuestionRepository,
  Game,
  GameComponent,
  QuestionComponent,
  UserComponent,
  AdminComponent,
  createApp,
};
