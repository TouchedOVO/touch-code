'use strict';

// Covers: FR-1, FR-DERIVED-1
const test = require('node:test');
const assert = require('node:assert/strict');
const { createGame, submitAnswer, publicState, result } = require('../src/game');

function questions(count = 10) {
  return Array.from({ length: count }, (_, index) => ({
    id: `q-${String(index + 1).padStart(3, '0')}`,
    prompt: `question ${index + 1}`,
    options: ['a', 'b', 'c', 'd'],
    answerIndex: index % 4,
    difficulty: 'easy',
  }));
}

test('correct answers accumulate ten points each and finish the game', () => {
  const game = createGame({ id: 'g-1', questions: questions(10) });
  let outcome;
  for (let index = 0; index < 10; index += 1) {
    outcome = submitAnswer(game, {
      questionId: game.questions[index].id,
      choiceIndex: game.questions[index].answerIndex,
    });
  }
  assert.equal(outcome.score, 100);
  assert.equal(outcome.correct, true);
  assert.equal(outcome.finished, true);
  assert.equal(game.status, 'finished');
  assert.equal(result(game).correctCount, 10);
  assert.equal(result(game).maxScore, 100);
});

test('wrong answers do not add points and reveal the correct index', () => {
  const game = createGame({ id: 'g-2', questions: questions(2) });
  const first = game.questions[0];
  const wrongIndex = (first.answerIndex + 1) % 4;
  const outcome = submitAnswer(game, { questionId: first.id, choiceIndex: wrongIndex });
  assert.equal(outcome.correct, false);
  assert.equal(outcome.correctIndex, first.answerIndex);
  assert.equal(outcome.score, 0);
  assert.equal(outcome.answeredCount, 1);
});

test('answers must be submitted in order', () => {
  const game = createGame({ id: 'g-3', questions: questions(3) });
  assert.throws(
    () => submitAnswer(game, { questionId: game.questions[1].id, choiceIndex: 0 }),
    (error) => error.code === 'out_of_order',
  );
});

test('finished games reject further answers', () => {
  const game = createGame({ id: 'g-4', questions: questions(1) });
  submitAnswer(game, { questionId: game.questions[0].id, choiceIndex: 0 });
  assert.throws(
    () => submitAnswer(game, { questionId: game.questions[0].id, choiceIndex: 0 }),
    (error) => error.code === 'game_finished',
  );
});

test('public state never leaks answerIndex', () => {
  const game = createGame({ id: 'g-5', questions: questions(2) });
  const state = publicState(game);
  assert.equal(state.currentQuestion.answerIndex, undefined);
  assert.equal(JSON.stringify(state).includes('answerIndex'), false);
});
