'use strict';

// Requirement coverage: [FR-1] [ASR-1] [ASR-2] [FR-DERIVED-1] [FR-DERIVED-2] [FR-DERIVED-3]

const test = require('node:test');
const assert = require('node:assert/strict');

const {
  createApp,
  DEFAULT_SEED_QUESTIONS,
  GAME_STATES,
  QUESTION_COUNT_PER_GAME,
  MAX_SCORE,
  ValidationError,
  NotFoundError,
  ConflictError,
  UnauthorizedError,
  InMemoryQuestionRepository,
  Game,
  UserComponent,
  AdminComponent,
} = require('../src/domain');

test('seed data contains at least one full game of valid questions', () => {
  assert.ok(
    DEFAULT_SEED_QUESTIONS.length >= QUESTION_COUNT_PER_GAME,
    'seed data must provide enough questions for a full game',
  );

  const repository = new InMemoryQuestionRepository(DEFAULT_SEED_QUESTIONS);
  assert.equal(repository.count(), DEFAULT_SEED_QUESTIONS.length);

  for (const question of repository.list()) {
    assert.equal(question.options.length, 4);
    assert.ok(Number.isInteger(question.correctIndex));
    assert.ok(question.correctIndex >= 0 && question.correctIndex < 4);
    assert.ok(question.prompt.length > 0);
    assert.ok(question.category.length > 0);
  }
});

test('createApp wires the logical components', () => {
  const app = createApp({ adminToken: 'secret' });
  assert.ok(app.gameComponent);
  assert.ok(app.questionComponent);
  assert.ok(app.userComponent);
  assert.ok(app.adminComponent);
});

test('correct answers accumulate points and the final answer ends the game', () => {
  const app = createApp({ adminToken: 'secret' });
  const game = app.gameComponent.start('guest_flow');

  assert.equal(game.status, GAME_STATES.PLAYING);
  assert.equal(game.questions.length, QUESTION_COUNT_PER_GAME);
  assert.equal(game.score, 0);

  let lastResult;
  for (let i = 0; i < QUESTION_COUNT_PER_GAME; i += 1) {
    const question = game.questions[game.currentIndex];
    lastResult = game.answer(question.correctIndex);
  }

  assert.equal(game.status, GAME_STATES.GAME_OVER);
  assert.equal(game.score, MAX_SCORE);
  assert.equal(lastResult.gameOver, true);
  assert.throws(() => game.answer(0), ValidationError);
});

test('a wrong answer does not change the score', () => {
  const app = createApp({ adminToken: 'secret' });
  const game = app.gameComponent.start('guest_wrong');
  const question = game.questions[game.currentIndex];
  const wrongIndex = (question.correctIndex + 1) % 4;

  const result = game.answer(wrongIndex);

  assert.equal(result.correct, false);
  assert.equal(game.score, 0);
});

test('answers reject out-of-range or non-integer selections', () => {
  const game = new Game({
    id: 'g1',
    guestId: 'guest_1',
    questions: DEFAULT_SEED_QUESTIONS.slice(0, QUESTION_COUNT_PER_GAME),
  });

  assert.throws(() => game.answer(-1), ValidationError);
  assert.throws(() => game.answer(4), ValidationError);
  assert.throws(() => game.answer('1'), ValidationError);
});

test('pause and resume transition between game states', () => {
  const app = createApp({ adminToken: 'secret' });
  const game = app.gameComponent.start('guest_pause');

  game.pause();
  assert.equal(game.status, GAME_STATES.PAUSED);
  assert.throws(() => game.answer(0), /paused/);

  game.resume();
  assert.equal(game.status, GAME_STATES.PLAYING);
  game.answer(0);
});

test('reset starts a fresh game with the same guest id', () => {
  const app = createApp({ adminToken: 'secret' });
  const first = app.gameComponent.start('guest_reset');
  first.answer(first.questions[first.currentIndex].correctIndex);

  const reset = app.gameComponent.reset(first.id);

  assert.equal(reset.id, first.id);
  assert.equal(reset.guestId, 'guest_reset');
  assert.equal(reset.status, GAME_STATES.PLAYING);
  assert.equal(reset.score, 0);
});

test('game view does not leak the correct index of the current question', () => {
  const app = createApp({ adminToken: 'secret' });
  const game = app.gameComponent.start('guest_view');
  const view = game.toView();

  assert.ok(view.currentQuestion);
  assert.equal(view.currentQuestion.correctIndex, undefined);
  assert.equal(view.currentQuestion.options.length, 4);
});

test('QuestionComponent supports create, read, update and delete', () => {
  const app = createApp({ adminToken: 'secret' });

  const created = app.questionComponent.create({
    prompt: '1/2 + 1/2 = ?',
    options: ['1/4', '1', '2/2', '1/2'],
    correctIndex: 1,
    category: 'addition',
  });

  assert.equal(created.prompt, '1/2 + 1/2 = ?');
  assert.equal(app.questionComponent.get(created.id).id, created.id);

  const updated = app.questionComponent.update(created.id, { category: 'mixed' });
  assert.equal(updated.category, 'mixed');
  assert.equal(updated.prompt, '1/2 + 1/2 = ?');

  assert.equal(app.questionComponent.remove(created.id), true);
  assert.throws(() => app.questionComponent.get(created.id), NotFoundError);
});

test('question validation rejects invalid shapes', () => {
  const app = createApp({ adminToken: 'secret' });

  assert.throws(
    () =>
      app.questionComponent.create({
        prompt: '',
        options: ['a', 'b', 'c', 'd'],
        correctIndex: 0,
        category: 'x',
      }),
    ValidationError,
  );

  assert.throws(
    () =>
      app.questionComponent.create({
        prompt: 'p',
        options: ['a', 'b', 'c'],
        correctIndex: 0,
        category: 'x',
      }),
    ValidationError,
  );

  assert.throws(
    () =>
      app.questionComponent.create({
        prompt: 'p',
        options: ['a', 'b', 'c', 'd'],
        correctIndex: 4,
        category: 'x',
      }),
    ValidationError,
  );
});

test('creating a question with a duplicate id is rejected', () => {
  const app = createApp({ adminToken: 'secret' });
  const question = {
    id: 'dup',
    prompt: 'p',
    options: ['a', 'b', 'c', 'd'],
    correctIndex: 0,
    category: 'x',
  };

  app.questionComponent.create(question);
  assert.throws(() => app.questionComponent.create(question), ConflictError);
});

test('AdminComponent authorizes only the configured token', () => {
  const admin = new AdminComponent({ token: 'secret-token' });

  assert.equal(admin.authorize('secret-token'), true);
  assert.throws(() => admin.authorize('wrong-token'), UnauthorizedError);
  assert.throws(() => admin.authorize(''), UnauthorizedError);
});

test('UserComponent creates unique guest identities', () => {
  const users = new UserComponent();
  const first = users.createGuest();
  const second = users.createGuest();

  assert.equal(first.role, 'guest');
  assert.equal(second.role, 'guest');
  assert.ok(first.guestId.startsWith('guest_'));
  assert.notEqual(first.guestId, second.guestId);
});

test('pick returns all available questions when fewer than requested', () => {
  const repository = new InMemoryQuestionRepository([DEFAULT_SEED_QUESTIONS[0]]);
  assert.equal(repository.pick(QUESTION_COUNT_PER_GAME).length, 1);
});

test('starting a game with no questions throws a validation error', () => {
  const app = createApp({ seedQuestions: [] });
  assert.throws(() => app.gameComponent.start('guest_empty'), /No questions available/);
});
