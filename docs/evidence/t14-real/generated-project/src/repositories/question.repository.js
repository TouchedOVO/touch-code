'use strict';

const JsonFileStore = require('./file-store');

/**
 * Persistent question repository.
 *
 * On first boot, an empty or missing questions file is seeded from the
 * supplied seed questions so that a brand-new deployment has playable content.
 */
class QuestionRepository {
  constructor({ filePath, seed = [] }) {
    this.store = new JsonFileStore(filePath, { initialValue: [] });
    this.seed = seed;
    this.questions = this._load();
  }

  _load() {
    let data = this.store.read();
    if (!Array.isArray(data)) data = [];
    if (data.length === 0 && this.seed.length > 0) {
      data = this.seed.map((q) => ({ ...q }));
      this.store.write(data);
    }
    return data;
  }

  findAll() {
    return this.questions.map((q) => ({ ...q }));
  }

  findById(id) {
    const found = this.questions.find((q) => q.id === id);
    return found ? { ...found } : null;
  }

  count() {
    return this.questions.length;
  }

  create(question) {
    if (question.id && this.findById(question.id)) {
      throw new Error(`Question with id ${question.id} already exists.`);
    }
    const record = {
      ...question,
      id: question.id || this._nextId()
    };
    this.questions.push(record);
    this._persist();
    return { ...record };
  }

  update(id, patch) {
    const index = this.questions.findIndex((q) => q.id === id);
    if (index === -1) return null;
    const next = { ...this.questions[index], ...patch, id };
    this.questions[index] = next;
    this._persist();
    return { ...next };
  }

  remove(id) {
    const index = this.questions.findIndex((q) => q.id === id);
    if (index === -1) return null;
    const [removed] = this.questions.splice(index, 1);
    this._persist();
    return { ...removed };
  }

  _nextId() {
    return `q-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
  }

  _persist() {
    this.store.write(this.questions);
  }
}

module.exports = QuestionRepository;
