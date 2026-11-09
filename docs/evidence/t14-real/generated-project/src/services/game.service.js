'use strict';

const {
  createGame,
  submitAnswer,
  pauseGame,
  resumeGame,
  getScore,
  pickQuestionIds,
  toPublicGame,
  QUESTIONS_PER_GAME,
  GAME_STATUS
} = require('../domain/game');

/**
 * Coordinates game sessions in memory and persists completed scores.
 *
 * Games are intentionally session-scoped; questions and finished scores are
 * durable (see ASR-1). This keeps the play path fast while still allowing
 * score recovery across process restarts.
 */
class GameService {
  constructor({ questionService, scoreRepository, random = Math.random }) {
    this.questionService = questionService;
    this.scoreRepository = scoreRepository;
    this.random = random;
    this.games = new Map();
  }

  createGame(guestId) {
    if (typeof guestId !== 'string' || !guestId.trim() || guestId.length > 128) {
      throw httpError(400, 'guestId is required and must be a string of at most 128 characters.');
    }

    const questions = this.questionService.listQuestions();
    if (questions.length < QUESTIONS_PER_GAME) {
      throw httpError(503, `At least ${QUESTIONS_PER_GAME} questions are required to start a game.`);
    }

    const id = `game-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
    const questionIds = pickQuestionIds(questions, QUESTIONS_PER_GAME, this.random);
    const game = createGame({ id, guestId: guestId.trim(), questionIds });
    this.games.set(id, game);
    return { ...game };
  }

  getGame(id) {
    const game = this.games.get(id);
    return game ? { ...game } : null;
  }

  getCurrentQuestion(id) {
    const game = this._requireGame(id);
    if (game.status === GAME_STATUS.GAME_OVER) return null;
    const questionId = game.questionIds[game.currentIndex];
    const question = this.questionService.getQuestionForGame(questionId);
    if (!question) {
      throw httpError(500, 'The current question could not be loaded.');
    }
    return {
      index: game.currentIndex,
      ...question
    };
  }

  submitAnswer(id, selectedIndex) {
    const game = this._requireGame(id);
    if (!Number.isInteger(selectedIndex) || selectedIndex < 0 || selectedIndex > 3) {
      throw httpError(400, 'selectedIndex must be an integer between 0 and 3.');
    }
    const questionId = game.questionIds[game.currentIndex];
    const question = this.questionService.getQuestion(questionId);
    if (!question) {
      throw httpError(500, 'The current question could not be loaded.');
    }

    const result = submitAnswer(game, selectedIndex, question);

    if (game.status === GAME_STATUS.GAME_OVER) {
      this.scoreRepository.save({
        gameId: game.id,
        guestId: game.guestId,
        score: game.score,
        total: game.totalQuestions * 10,
        finishedAt: game.finishedAt
      });
    }

    const response = {
      correct: result.correct,
      correctIndex: result.correctIndex,
      score: game.score,
      status: game.status,
      currentIndex: game.currentIndex,
      totalQuestions: game.totalQuestions,
      completed: result.completed
    };

    if (result.completed) {
      response.finalScore = game.score;
    } else {
      response.nextQuestion = this._questionView(game, game.currentIndex);
    }
    return response;
  }

  getScore(id) {
    const game = this._requireGame(id);
    return getScore(game);
  }

  pause(id) {
    const game = this._requireGame(id);
    pauseGame(game);
    return { ...game };
  }

  resume(id) {
    const game = this._requireGame(id);
    resumeGame(game);
    return { ...game };
  }

  _questionView(game, index) {
    const questionId = game.questionIds[index];
    const question = this.questionService.getQuestionForGame(questionId);
    return {
      index,
      ...question
    };
  }

  _requireGame(id) {
    const game = this.games.get(id);
    if (!game) throw httpError(404, 'Game not found.');
    return game;
  }
}

function httpError(status, message) {
  const error = new Error(message);
  error.status = status;
  return error;
}

module.exports = GameService;
module.exports.toPublicGame = toPublicGame;
