'use strict';

/**
 * Business rules for question management.
 *
 * Admin-created and admin-updated questions are validated here before they
 * reach the persistence layer. Game flow uses the "for game" projections so
 * that the correct answer index is never sent to a player.
 */
class QuestionService {
  constructor({ questionRepository }) {
    this.repository = questionRepository;
  }

  listQuestions() {
    return this.repository.findAll();
  }

  getQuestion(id) {
    return this.repository.findById(id);
  }

  getQuestionForGame(id) {
    const question = this.repository.findById(id);
    if (!question) return null;
    return {
      id: question.id,
      text: question.text,
      options: question.options.slice()
    };
  }

  getQuestionsForGame(ids) {
    return ids.map((id) => this.getQuestionForGame(id));
  }

  createQuestion(input) {
    const question = validateQuestionInput(input);
    return this.repository.create(question);
  }

  updateQuestion(id, input) {
    const existing = this.repository.findById(id);
    if (!existing) return null;
    const merged = {
      text: input && input.text !== undefined ? input.text : existing.text,
      options: input && input.options !== undefined ? input.options : existing.options,
      answerIndex: input && input.answerIndex !== undefined ? input.answerIndex : existing.answerIndex,
      explanation: input && input.explanation !== undefined ? input.explanation : existing.explanation
    };
    const question = validateQuestionInput(merged);
    return this.repository.update(id, question);
  }

  deleteQuestion(id) {
    return this.repository.remove(id);
  }

  count() {
    return this.repository.count();
  }
}

function validateQuestionInput(input) {
  const errors = [];
  if (!input || typeof input !== 'object') {
    errors.push('question body is required');
  }

  const text = input && input.text;
  if (typeof text !== 'string' || !text.trim()) {
    errors.push('text must be a non-empty string');
  }

  const options = input && input.options;
  if (!Array.isArray(options) || options.length !== 4) {
    errors.push('options must be an array of exactly 4 strings');
  } else {
    options.forEach((option, index) => {
      if (typeof option !== 'string' || !option.trim()) {
        errors.push(`options[${index}] must be a non-empty string`);
      }
    });
    const unique = new Set(options.map((option) => (typeof option === 'string' ? option.trim() : option)));
    if (unique.size !== options.length) {
      errors.push('options must be unique');
    }
  }

  const answerIndex = input && input.answerIndex;
  if (!Number.isInteger(answerIndex) || answerIndex < 0 || answerIndex > 3) {
    errors.push('answerIndex must be an integer between 0 and 3');
  }

  if (errors.length > 0) {
    const error = new Error(`Invalid question: ${errors.join('; ')}.`);
    error.status = 400;
    error.details = errors;
    throw error;
  }

  return {
    text: text.trim(),
    options: options.map((option) => option.trim()),
    answerIndex,
    explanation: typeof input.explanation === 'string' ? input.explanation.trim() : ''
  };
}

module.exports = QuestionService;
module.exports.validateQuestionInput = validateQuestionInput;
