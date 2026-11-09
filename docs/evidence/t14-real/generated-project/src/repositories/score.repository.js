'use strict';

const JsonFileStore = require('./file-store');

/**
 * Persistent score repository used for View Score and restart recovery.
 */
class ScoreRepository {
  constructor({ filePath }) {
    this.store = new JsonFileStore(filePath, { initialValue: [] });
    this.scores = this._load();
  }

  _load() {
    const data = this.store.read();
    return Array.isArray(data) ? data : [];
  }

  save(record) {
    const stored = { ...record };
    this.scores.push(stored);
    this._persist();
    return { ...stored };
  }

  findByGuestId(guestId) {
    return this.scores
      .filter((s) => s.guestId === guestId)
      .map((s) => ({ ...s }))
      .sort((a, b) => String(a.finishedAt).localeCompare(String(b.finishedAt)));
  }

  findByGameId(gameId) {
    const found = this.scores.find((s) => s.gameId === gameId);
    return found ? { ...found } : null;
  }

  all() {
    return this.scores.map((s) => ({ ...s }));
  }

  _persist() {
    this.store.write(this.scores);
  }
}

module.exports = ScoreRepository;
