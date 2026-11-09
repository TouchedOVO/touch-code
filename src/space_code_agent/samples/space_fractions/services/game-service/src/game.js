'use strict';

/**
 * Game domain: rounds, answer validation and scoring.
 *
 * Covers: FR-1, FR-DERIVED-1
 * Pure functions over a game object; no HTTP or persistence dependencies.
 */

const QUESTION_POINTS = 10;

function gameError(code, message, statusCode = 409) {
  const error = new Error(message);
  error.code = code;
  error.statusCode = statusCode;
  return error;
}

function publicQuestion(question) {
  if (!question) return null;
  const { answerIndex, ...rest } = question;
  return { ...rest, options: [...rest.options] };
}

function createGame({ id, questions }) {
  if (!id) throw new Error('game id is required');
  if (!Array.isArray(questions) || questions.length === 0) {
    throw new Error('questions must be a non-empty array');
  }
  const normalized = questions.map((question) => {
    if (!question || !question.id || !Array.isArray(question.options)) {
      throw new Error('invalid question payload');
    }
    if (!Number.isInteger(question.answerIndex)) {
      throw new Error('question answerIndex is required on the server side');
    }
    return {
      id: String(question.id),
      prompt: String(question.prompt),
      options: question.options.map(String),
      answerIndex: question.answerIndex,
      difficulty: question.difficulty || 'easy',
    };
  });
  return {
    id: String(id),
    questions: normalized,
    totalQuestions: normalized.length,
    currentIndex: 0,
    score: 0,
    correctCount: 0,
    answers: [],
    status: 'active',
    createdAt: new Date().toISOString(),
  };
}

function currentQuestion(game) {
  if (game.status !== 'active') return null;
  return publicQuestion(game.questions[game.currentIndex]);
}

function submitAnswer(game, { questionId, choiceIndex }) {
  if (game.status !== 'active') {
    throw gameError('game_finished', 'this game is already finished');
  }
  const question = game.questions[game.currentIndex];
  if (!question) {
    throw gameError('game_finished', 'no questions remaining');
  }
  if (String(questionId) !== question.id) {
    throw gameError(
      'out_of_order',
      `expected question ${question.id} but received ${questionId}`,
    );
  }
  const choice = Number(choiceIndex);
  if (!Number.isInteger(choice) || choice < 0 || choice >= question.options.length) {
    throw gameError('invalid_choice', 'choiceIndex must be a valid option index', 400);
  }
  const correct = choice === question.answerIndex;
  if (correct) {
    game.score += QUESTION_POINTS;
    game.correctCount += 1;
  }
  game.answers.push({
    questionId: question.id,
    prompt: question.prompt,
    choiceIndex: choice,
    correct,
    correctIndex: question.answerIndex,
  });
  game.currentIndex += 1;
  if (game.currentIndex >= game.totalQuestions) {
    game.status = 'finished';
    game.finishedAt = new Date().toISOString();
  }
  return {
    correct,
    correctIndex: question.answerIndex,
    score: game.score,
    answeredCount: game.answers.length,
    totalQuestions: game.totalQuestions,
    finished: game.status === 'finished',
    nextQuestion: currentQuestion(game),
  };
}

function publicState(game) {
  return {
    gameId: game.id,
    score: game.score,
    correctCount: game.correctCount,
    answeredCount: game.answers.length,
    totalQuestions: game.totalQuestions,
    status: game.status,
    currentQuestion: currentQuestion(game),
    answers: game.answers.map((answer) => ({
      questionId: answer.questionId,
      correct: answer.correct,
      choiceIndex: answer.choiceIndex,
    })),
  };
}

function result(game) {
  return {
    gameId: game.id,
    status: game.status,
    score: game.score,
    correctCount: game.correctCount,
    totalQuestions: game.totalQuestions,
    maxScore: game.totalQuestions * QUESTION_POINTS,
    breakdown: game.answers.map((answer) => ({
      questionId: answer.questionId,
      prompt: answer.prompt,
      choiceIndex: answer.choiceIndex,
      correctIndex: answer.correctIndex,
      correct: answer.correct,
    })),
  };
}

module.exports = {
  QUESTION_POINTS,
  createGame,
  submitAnswer,
  publicState,
  publicQuestion,
  result,
};
