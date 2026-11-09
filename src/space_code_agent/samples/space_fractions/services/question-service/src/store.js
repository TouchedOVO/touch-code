'use strict';

// Covers: FR-DERIVED-2, ASR-1
const { SEED_QUESTIONS } = require('./questions');

function validationError(message) {
  const error = new Error(message);
  error.statusCode = 400;
  return error;
}

function validateQuestion(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) {
    throw validationError('question must be an object');
  }
  const prompt = typeof input.prompt === 'string' ? input.prompt.trim() : '';
  if (prompt.length < 3) {
    throw validationError('prompt must contain at least 3 characters');
  }
  if (!Array.isArray(input.options) || input.options.length !== 4) {
    throw validationError('options must contain exactly 4 entries');
  }
  const options = input.options.map((option) => String(option).trim());
  if (options.some((option) => option.length === 0)) {
    throw validationError('options must not be empty');
  }
  if (new Set(options).size !== options.length) {
    throw validationError('options must be unique');
  }
  const answerIndex = Number(input.answerIndex);
  if (!Number.isInteger(answerIndex) || answerIndex < 0 || answerIndex >= options.length) {
    throw validationError('answerIndex must be an integer between 0 and 3');
  }
  const difficulty = input.difficulty === undefined ? 'easy' : String(input.difficulty);
  if (!['easy', 'medium', 'hard'].includes(difficulty)) {
    throw validationError('difficulty must be easy, medium or hard');
  }
  return { prompt, options, answerIndex, difficulty };
}

function clone(question) {
  return { ...question, options: [...question.options] };
}

function publicView(question) {
  const { answerIndex, ...rest } = question;
  return { ...rest, options: [...rest.options] };
}

function shuffle(items) {
  const copy = [...items];
  for (let i = copy.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}

function createQuestionStore(seed = SEED_QUESTIONS) {
  let questions = seed.map(clone);
  let counter = questions.length;

  function find(id) {
    return questions.find((question) => question.id === id);
  }

  return {
    count() {
      return questions.length;
    },
    all(includeAnswers = false) {
      return questions.map((question) => (includeAnswers ? clone(question) : publicView(question)));
    },
    get(id, includeAnswers = false) {
      const question = find(String(id));
      if (!question) return null;
      return includeAnswers ? clone(question) : publicView(question);
    },
    random(count = 10, includeAnswers = false) {
      const requested = Number.isInteger(Number(count)) ? Number(count) : 10;
      const size = Math.min(Math.max(requested, 1), questions.length);
      return shuffle(questions).slice(0, size).map((question) => (
        includeAnswers ? clone(question) : publicView(question)
      ));
    },
    create(input) {
      const valid = validateQuestion(input);
      counter += 1;
      const question = { id: `q-${String(counter).padStart(3, '0')}`, ...valid };
      questions.push(question);
      return clone(question);
    },
    update(id, patch) {
      const existing = find(String(id));
      if (!existing) return null;
      const merged = { ...existing, ...patch, id: existing.id };
      const valid = validateQuestion(merged);
      Object.assign(existing, valid);
      return clone(existing);
    },
    remove(id) {
      const index = questions.findIndex((question) => question.id === String(id));
      if (index < 0) return false;
      questions.splice(index, 1);
      return true;
    },
    reset() {
      questions = seed.map(clone);
      counter = questions.length;
    },
  };
}

module.exports = { createQuestionStore, validateQuestion, publicView, SEED_QUESTIONS };
