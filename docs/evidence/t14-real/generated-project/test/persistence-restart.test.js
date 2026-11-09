'use strict';

// Covers: ASR-1

const test = require('node:test');
const assert = require('node:assert/strict');

const { createApp } = require('../src/app');
const { createTestApp } = require('./helpers/test-app');

function completeGame(app, guestId) {
  const { gameService, questionService } = app.locals.services;
  const created = gameService.createGame(guestId);
  const gameId = created.id;

  for (let step = 0; step < 10; step += 1) {
    const game = gameService.getGame(gameId);
    const question = questionService.getQuestion(game.questionIds[game.currentIndex]);
    gameService.submitAnswer(gameId, question.answerIndex);
  }

  return gameId;
}

test('questions and scores survive a simulated process restart', () => {
  const first = createTestApp();
  const { config } = first;

  try {
    // 1. Admin changes question data and a player finishes a game.
    const newQuestion = first.app.locals.services.questionService.createQuestion({
      text: '1/4 + 1/4 = ?',
      options: ['1/2', '1/4', '1/8', '2/4'],
      answerIndex: 0,
      explanation: '1/4 + 1/4 = 2/4 = 1/2.'
    });

    const guestId = 'guest-persist-test';
    const gameId = completeGame(first.app, guestId);
    const finished = first.app.locals.services.gameService.getGame(gameId);
    assert.equal(finished.score, 100);

    // 2. Simulate restart: build a fresh app from the same on-disk files.
    const restarted = createApp({
      config,
      seedQuestions: []
    });

    try {
      const reloadedQuestions = restarted.locals.services.questionService.listQuestions();
      assert.ok(
        reloadedQuestions.some((q) => q.id === newQuestion.id),
        'created question is still present after restart'
      );

      const reloadedScore = restarted.locals.services.userService.getScores(guestId);
      assert.equal(reloadedScore.scores.length, 1);
      assert.equal(reloadedScore.scores[0].gameId, gameId);
      assert.equal(reloadedScore.scores[0].score, 100);
    } finally {
      // The repositories read from disk; no close hook is required.
    }
  } finally {
    first.cleanup();
  }
});

test('seed questions are written to the questions file on first boot', () => {
  const context = createTestApp();
  try {
    const questions = context.app.locals.services.questionService.listQuestions();
    assert.ok(questions.length >= 10);
    questions.forEach((question) => {
      assert.ok(question.id);
      assert.ok(question.text);
      assert.equal(question.options.length, 4);
      assert.ok(Number.isInteger(question.answerIndex));
    });
  } finally {
    context.cleanup();
  }
});

test('empty data files are treated as empty collections, not crashes', () => {
  const context = createTestApp();
  const fs = require('fs');
  const path = require('path');

  try {
    fs.writeFileSync(context.config.scoresFile, '[]');
    fs.writeFileSync(context.config.questionsFile, '[]');

    const restarted = createApp({ config: context.config, seedQuestions: [] });
    try {
      assert.equal(restarted.locals.services.questionService.count(), 0);
      assert.deepEqual(restarted.locals.services.userService.getScores('anyone').scores, []);
    } finally {
      // Nothing to close.
    }
  } finally {
    context.cleanup();
  }
});
