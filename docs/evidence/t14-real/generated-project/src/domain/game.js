'use strict';

/**
 * Game state machine and scoring rules.
 *
 * A session always contains 10 questions. A correct answer earns 10 points
 * and a wrong answer earns 0, so the maximum score is 100. The state machine
 * follows the documented Playing -> Paused / Playing -> GameOver transitions.
 */

const GAME_STATUS = Object.freeze({
  PLAYING: 'PLAYING',
  PAUSED: 'PAUSED',
  GAME_OVER: 'GAME_OVER'
});

const QUESTIONS_PER_GAME = 10;
const POINTS_PER_CORRECT = 10;
const MAX_SCORE = QUESTIONS_PER_GAME * POINTS_PER_CORRECT;

function shuffle(items, random = Math.random) {
  const arr = items.slice();
  for (let i = arr.length - 1; i > 0; i -= 1) {
    const j = Math.floor(random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

function pickQuestionIds(questions, count = QUESTIONS_PER_GAME, random = Math.random) {
  return shuffle(questions, random).slice(0, count).map((q) => q.id);
}

function createGame({ id, guestId, questionIds, now = new Date() }) {
  if (!id) throw new Error('Game id is required.');
  if (!guestId) throw new Error('Guest id is required.');
  if (!Array.isArray(questionIds) || questionIds.length !== QUESTIONS_PER_GAME) {
    throw new Error(`A game requires exactly ${QUESTIONS_PER_GAME} questions.`);
  }

  return {
    id,
    guestId,
    status: GAME_STATUS.PLAYING,
    questionIds: questionIds.slice(),
    currentIndex: 0,
    answers: [],
    score: 0,
    totalQuestions: questionIds.length,
    startedAt: now.toISOString(),
    finishedAt: null,
    updatedAt: now.toISOString()
  };
}

function submitAnswer(game, selectedIndex, question, now = new Date()) {
  if (game.status === GAME_STATUS.GAME_OVER) {
    throw new Error('Game is already over.');
  }
  if (game.status === GAME_STATUS.PAUSED) {
    throw new Error('Game is paused; resume before answering.');
  }
  const currentQuestionId = game.questionIds[game.currentIndex];
  if (!question || question.id !== currentQuestionId) {
    throw new Error('Question does not match the current game position.');
  }
  if (!Number.isInteger(selectedIndex) || selectedIndex < 0 || selectedIndex > 3) {
    throw new Error('selectedIndex must be an integer between 0 and 3.');
  }

  const correct = question.answerIndex === selectedIndex;
  const earned = correct ? POINTS_PER_CORRECT : 0;

  game.score += earned;
  game.answers.push({
    questionId: currentQuestionId,
    selectedIndex,
    correct,
    earned
  });
  game.currentIndex += 1;

  if (game.currentIndex >= game.totalQuestions) {
    game.status = GAME_STATUS.GAME_OVER;
    game.finishedAt = now.toISOString();
  }
  game.updatedAt = now.toISOString();

  return {
    correct,
    correctIndex: question.answerIndex,
    earned,
    score: game.score,
    status: game.status,
    completed: game.status === GAME_STATUS.GAME_OVER
  };
}

function pauseGame(game, now = new Date()) {
  if (game.status !== GAME_STATUS.PLAYING) {
    throw new Error('Only a playing game can be paused.');
  }
  game.status = GAME_STATUS.PAUSED;
  game.updatedAt = now.toISOString();
  return game;
}

function resumeGame(game, now = new Date()) {
  if (game.status !== GAME_STATUS.PAUSED) {
    throw new Error('Only a paused game can be resumed.');
  }
  game.status = GAME_STATUS.PLAYING;
  game.updatedAt = now.toISOString();
  return game;
}

function getScore(game) {
  return {
    gameId: game.id,
    score: game.score,
    total: game.totalQuestions * POINTS_PER_CORRECT,
    status: game.status,
    completed: game.status === GAME_STATUS.GAME_OVER,
    questionsAnswered: game.answers.length
  };
}

function toPublicGame(game) {
  return {
    id: game.id,
    status: game.status,
    score: game.score,
    currentIndex: game.currentIndex,
    totalQuestions: game.totalQuestions,
    startedAt: game.startedAt,
    finishedAt: game.finishedAt
  };
}

module.exports = {
  GAME_STATUS,
  QUESTIONS_PER_GAME,
  POINTS_PER_CORRECT,
  MAX_SCORE,
  createGame,
  submitAnswer,
  pauseGame,
  resumeGame,
  getScore,
  pickQuestionIds,
  toPublicGame
};
