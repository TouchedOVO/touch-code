/**
 * Student UI state machine: intro → menu → game → result.
 * Covers: FR-1, FR-DERIVED-1, FR-DERIVED-3
 */

import { createApi, scoreMessage } from './api.js';

const api = createApi(window.__GAME_API_BASE__ || 'http://127.0.0.1:4002');

const screens = new Map(
  [...document.querySelectorAll('[data-screen]')].map((element) => [element.dataset.screen, element]),
);

const elements = {
  scoreChip: document.getElementById('score-chip'),
  question: document.getElementById('question-title'),
  options: document.getElementById('options'),
  progressLabel: document.getElementById('progress-label'),
  progress: document.getElementById('progress'),
  progressBar: document.getElementById('progress-bar'),
  feedback: document.getElementById('feedback'),
  next: document.getElementById('next-btn'),
  resultTitle: document.getElementById('result-title'),
  resultScore: document.getElementById('result-score'),
  resultMessage: document.getElementById('result-message'),
  errorMessage: document.getElementById('error-message'),
};

const state = {
  screen: 'intro',
  gameId: null,
  currentQuestion: null,
  nextQuestion: null,
  score: 0,
  answered: 0,
  total: 10,
  busy: false,
};

function showScreen(name) {
  for (const [key, screen] of screens) {
    const active = key === name;
    screen.hidden = !active;
    screen.classList.toggle('screen--active', active);
  }
  state.screen = name;
  const heading = screens.get(name)?.querySelector('h2');
  if (heading) {
    heading.setAttribute('tabindex', '-1');
    heading.focus({ preventScroll: true });
  }
}

function updateScore() {
  elements.scoreChip.hidden = state.screen !== 'game';
  elements.scoreChip.textContent = `得分 ${state.score}`;
}

function updateProgress() {
  const answered = state.answered;
  elements.progressLabel.textContent = `第 ${Math.min(answered + 1, state.total)} / ${state.total} 题`;
  elements.progress.setAttribute('aria-valuenow', String(answered));
  elements.progressBar.style.width = `${(answered / state.total) * 100}%`;
}

function renderQuestion(question) {
  state.currentQuestion = question;
  state.nextQuestion = null;
  state.busy = false;
  elements.question.textContent = question.prompt;
  elements.feedback.textContent = '';
  elements.next.hidden = true;
  elements.options.replaceChildren();

  question.options.forEach((option, index) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'option';
    button.dataset.index = String(index);
    button.innerHTML = `<span class="option__key" aria-hidden="true">${String.fromCharCode(65 + index)}</span><span>${option}</span>`;
    button.addEventListener('click', () => choose(index));
    elements.options.appendChild(button);
  });

  updateProgress();
  updateScore();
}

async function choose(index) {
  if (state.busy || !state.currentQuestion || !state.gameId) return;
  state.busy = true;
  for (const button of elements.options.querySelectorAll('button')) {
    button.disabled = true;
  }

  try {
    const outcome = await api.submitAnswer(state.gameId, {
      questionId: state.currentQuestion.id,
      choiceIndex: index,
    });

    state.score = outcome.score;
    state.answered = outcome.answeredCount;
    updateScore();
    updateProgress();

    for (const button of elements.options.querySelectorAll('button')) {
      const buttonIndex = Number(button.dataset.index);
      if (buttonIndex === outcome.correctIndex) button.classList.add('option--correct');
      if (buttonIndex === index && !outcome.correct) button.classList.add('option--wrong');
    }

    elements.feedback.textContent = outcome.correct
      ? '答对了！+10 分'
      : `答错了，正确答案是 ${String.fromCharCode(65 + outcome.correctIndex)}。`;
    elements.feedback.classList.toggle('feedback--ok', outcome.correct);
    elements.feedback.classList.toggle('feedback--bad', !outcome.correct);

    if (outcome.finished) {
      setTimeout(loadResult, 950);
      return;
    }
    state.nextQuestion = outcome.nextQuestion;
    elements.next.hidden = false;
    elements.next.focus({ preventScroll: true });
  } catch (error) {
    showError(error.message);
  } finally {
    state.busy = false;
  }
}

async function startGame() {
  try {
    showScreen('menu');
    const game = await api.createGame();
    state.gameId = game.gameId;
    state.score = game.score || 0;
    state.answered = 0;
    state.total = game.totalQuestions || 10;
    elements.scoreChip.hidden = false;
    showScreen('game');
    renderQuestion(game.currentQuestion);
  } catch (error) {
    showError(error.message);
  }
}

async function loadResult() {
  try {
    const result = await api.getResult(state.gameId);
    elements.resultTitle.textContent = result.score >= 60 ? '返航成功' : '任务待重试';
    elements.resultScore.textContent = `${result.score} / ${result.maxScore}`;
    elements.resultMessage.textContent = scoreMessage(result.score);
    showScreen('result');
  } catch (error) {
    showError(error.message);
  }
}

function showError(message) {
  elements.errorMessage.textContent = message || '请确认游戏服务已启动。';
  showScreen('error');
}

function nextQuestion() {
  if (state.nextQuestion) {
    renderQuestion(state.nextQuestion);
  }
}

document.getElementById('enter-btn').addEventListener('click', () => showScreen('menu'));
document.getElementById('next-btn').addEventListener('click', nextQuestion);
document.getElementById('again-btn').addEventListener('click', startGame);
document.getElementById('retry-btn').addEventListener('click', startGame);

document.addEventListener('click', (event) => {
  const action = event.target.closest('[data-action]')?.dataset.action;
  if (!action) return;
  if (action === 'start') startGame();
  if (action === 'help') showScreen('help');
  if (action === 'menu') showScreen('menu');
});

showScreen('intro');
