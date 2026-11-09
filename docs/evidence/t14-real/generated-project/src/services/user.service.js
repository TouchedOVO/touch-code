'use strict';

const crypto = require('crypto');

const HELP_CONTENT = Object.freeze({
  title: 'How to play Space Fractions',
  sections: [
    {
      heading: 'Goal',
      body: 'Solve 10 sixth-grade fraction questions. Each correct answer earns 10 points, so a perfect mission scores 100 points.'
    },
    {
      heading: 'Answering',
      body: 'Read the fraction problem, choose one of the four options, and press Enter or click the option button. The game shows whether your answer was correct before moving on.'
    },
    {
      heading: 'Keyboard access',
      body: 'Use Tab and Shift+Tab to move between buttons, Enter or Space to activate a button, and Escape to return to the menu. The current question and feedback are announced to screen readers.'
    },
    {
      heading: 'No account needed',
      body: 'You do not need to register. A guest ID is created on your first game and stored locally in your browser so your recent scores can be shown again.'
    },
    {
      heading: 'Scoring',
      body: 'Scores are only for the current round. Restarting the browser does not erase completed scores saved on the server, but an in-progress game is not resumed.'
    }
  ]
});

/**
 * Guest session handling, score lookup (FR-DERIVED-1) and help content
 * (FR-DERIVED-3) for the UserComponent boundary.
 */
class UserService {
  constructor({ scoreRepository }) {
    this.scoreRepository = scoreRepository;
  }

  createGuest() {
    return { guestId: `guest-${crypto.randomUUID()}` };
  }

  getScores(guestId) {
    if (typeof guestId !== 'string' || !guestId.trim() || guestId.length > 128) {
      throw httpError(400, 'guestId is required and must be a string of at most 128 characters.');
    }
    const scores = this.scoreRepository.findByGuestId(guestId.trim()).map((score) => ({
      gameId: score.gameId,
      score: score.score,
      total: score.total,
      finishedAt: score.finishedAt
    }));
    return { guestId: guestId.trim(), scores };
  }

  getHelp() {
    return {
      title: HELP_CONTENT.title,
      sections: HELP_CONTENT.sections.map((section) => ({ ...section }))
    };
  }
}

function httpError(status, message) {
  const error = new Error(message);
  error.status = status;
  return error;
}

module.exports = UserService;
