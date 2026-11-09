'use strict';

const fs = require('fs');
const path = require('path');

/**
 * Minimal durable JSON file store.
 *
 * Writes are performed atomically: the payload is written to a temporary file
 * in the same directory and then renamed over the target file. This avoids a
 * torn write if the process crashes mid-save and satisfies the ASR-1 data
 * durability requirement for the demo deployment.
 */
class JsonFileStore {
  constructor(filePath, options = {}) {
    this.filePath = filePath;
    this.initialValue = options.initialValue !== undefined ? options.initialValue : null;
  }

  read() {
    let raw;
    try {
      raw = fs.readFileSync(this.filePath, 'utf8');
    } catch (err) {
      if (err.code === 'ENOENT') return this.initialValue;
      throw err;
    }
    if (!raw.trim()) return this.initialValue;
    return JSON.parse(raw);
  }

  write(data) {
    const dir = path.dirname(this.filePath);
    fs.mkdirSync(dir, { recursive: true });
    const tmpPath = `${this.filePath}.${process.pid}.${Date.now()}.tmp`;
    fs.writeFileSync(tmpPath, JSON.stringify(data, null, 2));
    fs.renameSync(tmpPath, this.filePath);
  }

  update(mutator) {
    const current = this.read();
    const next = mutator(current);
    this.write(next);
    return next;
  }
}

module.exports = JsonFileStore;
