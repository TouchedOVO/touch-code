'use strict';

(function () {
  const state = {
    guestId: null,
    gameId: null,
    currentQuestion: null,
    answered: false
  };

  const viewEls = {
    menu: document.getElementById('view-menu'),
    game: document.getElementById('view-game'),
    score: document.getElementById('view-score'),
    help: document.getElementById('view-help')
  };

  function $(selector) {
    return document.querySelector(selector);
  }

  function showView(name) {
    Object.values(viewEls).forEach((el) => el.classList.add('hidden'));
    viewEls[name].classList.remove('hidden');
    window.scrollTo(0, 0);
  }

  async function api(path, options = {}) {
    const response = await fetch(path, {
      headers: { 'Content-Type': 'application/json' },
      ...options
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.message || data.error || `Request failed (${response.status})`);
    }
    return data;
  }

  async function ensureGuest() {
    if (state.guestId) return state.guestId;
    try {
      const stored = window.localStorage.getItem('space-fractions-guest');
      if (stored) {
        state.guestId = stored;
        return stored;
      }
    } catch (err) {
      // localStorage may be unavailable; fall back to a session-only guest.
    }
    const data = await api('/api/users/guest', { method: 'POST', body: JSON.stringify({}) });
    state.guestId = data.guestId;
    try {
      window.localStorage.setItem('space-fractions-guest', state.guestId);
    } catch (err) {
      // Ignore storage failures; the guest still works for this page load.
    }
    return state.guestId;
  }

  async function startGame() {
    setGameMessage('Loading mission…');
    try {
      const guestId = await ensureGuest();
      const data = await api('/api/games', {
        method: 'POST',
        body: JSON.stringify({ guestId })
      });
      state.gameId = data.game.id;
      state.answered = false;
      renderQuestion(data.question, data.game);
      showView('game');
    } catch (err) {
      alert(`Could not start the game: ${err.message}`);
      showView('menu');
    }
  }

  function renderQuestion(question, game) {
    state.currentQuestion = question;
    state.answered = false;
    $('#progress').textContent = `Question ${game.currentIndex + 1} of ${game.totalQuestions}`;
    $('#score').textContent = `Score: ${game.score}`;
    $('#question-text').textContent = question.text;
    $('#feedback').textContent = '';
    $('#next-question').classList.add('hidden');

    const optionsEl = $('#options');
    optionsEl.innerHTML = '';
    question.options.forEach((option, index) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'option-btn';
      button.textContent = option;
      button.dataset.index = String(index);
      button.setAttribute('aria-label', `Option ${index + 1}: ${option}`);
      button.addEventListener('click', () => chooseAnswer(index));
      optionsEl.appendChild(button);
    });
    focusFirstOption();
  }

  function focusFirstOption() {
    const first = $('#options .option-btn');
    if (first) first.focus();
  }

  function setGameMessage(message) {
    $('#feedback').textContent = message;
  }

  async function chooseAnswer(index) {
    if (state.answered || !state.gameId) return;
    state.answered = true;
    setGameMessage('Checking…');
    const buttons = Array.from(document.querySelectorAll('#options .option-btn'));
    buttons.forEach((button) => (button.disabled = true));

    try {
      const result = await api(`/api/games/${state.gameId}/answer`, {
        method: 'POST',
        body: JSON.stringify({ selectedIndex: index })
      });
      markAnswer(buttons, index, result.correctIndex, result.correct);
      $('#score').textContent = `Score: ${result.score}`;
      setGameMessage(
        result.correct
          ? 'Correct! +10 points.'
          : `Not quite. The correct answer was option ${result.correctIndex + 1}.`
      );

      if (result.completed) {
        $('#next-question').classList.add('hidden');
        window.setTimeout(() => showScore(), 1100);
      } else {
        const nextButton = $('#next-question');
        nextButton.classList.remove('hidden');
        nextButton.onclick = loadNextQuestion;
        nextButton.focus();
      }
    } catch (err) {
      setGameMessage(`Error: ${err.message}`);
      state.answered = false;
      buttons.forEach((button) => (button.disabled = false));
    }
  }

  function markAnswer(buttons, selectedIndex, correctIndex, correct) {
    buttons.forEach((button, index) => {
      button.disabled = true;
      if (index === correctIndex) button.classList.add('correct');
      else if (index === selectedIndex && !correct) button.classList.add('wrong');
    });
  }

  async function loadNextQuestion() {
    try {
      const data = await api(`/api/games/${state.gameId}`);
      state.answered = false;
      renderQuestion(data.question, data.game);
    } catch (err) {
      setGameMessage(`Error: ${err.message}`);
    }
  }

  async function showScore() {
    try {
      const data = await api(`/api/games/${state.gameId}/score`);
      $('#final-score').textContent = `${data.score} / ${data.total}`;
      $('#score-message').textContent = scoreMessage(data.score, data.total);
      showView('score');
    } catch (err) {
      alert(`Could not load the score: ${err.message}`);
      showView('menu');
    }
  }

  function scoreMessage(score, total) {
    const ratio = total === 0 ? 0 : score / total;
    if (ratio >= 1) return 'Perfect score! You are a fraction commander!';
    if (ratio >= 0.7) return 'Great work! Keep practicing to reach 100.';
    if (ratio >= 0.4) return 'Good effort! Review the help page for tips.';
    return 'Keep trying! Check the help page and try another mission.';
  }

  async function loadHelp() {
    try {
      const data = await api('/api/help');
      const container = $('#help-content');
      container.innerHTML = '';
      const title = document.createElement('h3');
      title.textContent = data.title;
      container.appendChild(title);
      (data.sections || []).forEach((section) => {
        const heading = document.createElement('h4');
        heading.textContent = section.heading;
        const body = document.createElement('p');
        body.textContent = section.body;
        container.appendChild(heading);
        container.appendChild(body);
      });
    } catch (err) {
      $('#help-content').textContent = `Could not load help: ${err.message}`;
    }
    showView('help');
  }

  function bindEvents() {
    $('#start-game').addEventListener('click', startGame);
    $('#show-help').addEventListener('click', loadHelp);
    $('#help-menu').addEventListener('click', () => showView('menu'));
    $('#score-menu').addEventListener('click', () => showView('menu'));
    $('#play-again').addEventListener('click', startGame);
    $('#quit-game').addEventListener('click', () => showView('menu'));

    document.querySelectorAll('[data-view]').forEach((button) => {
      button.addEventListener('click', () => {
        if (button.dataset.view === 'menu') showView('menu');
        if (button.dataset.view === 'help') loadHelp();
      });
    });

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && !viewEls.menu.classList.contains('hidden')) return;
      if (event.key === 'Escape') {
        showView('menu');
      }
    });
  }

  bindEvents();
  showView('menu');
})();
