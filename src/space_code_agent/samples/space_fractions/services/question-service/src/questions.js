'use strict';

/**
 * Seed question bank for sixth-grade fraction practice.
 *
 * Covers: FR-DERIVED-2
 * Each question has exactly four options and one zero-based answer index.
 */

const SEED_QUESTIONS = [
  {
    id: 'q-001',
    prompt: '1/2 + 1/4 = ?',
    options: ['3/4', '2/6', '1/6', '2/4'],
    answerIndex: 0,
    difficulty: 'easy',
  },
  {
    id: 'q-002',
    prompt: '2/3 + 1/6 = ?',
    options: ['3/9', '1/2', '5/6', '3/6'],
    answerIndex: 2,
    difficulty: 'easy',
  },
  {
    id: 'q-003',
    prompt: '3/4 - 1/2 = ?',
    options: ['1/2', '1/4', '2/2', '5/4'],
    answerIndex: 1,
    difficulty: 'easy',
  },
  {
    id: 'q-004',
    prompt: '5/6 - 1/3 = ?',
    options: ['2/3', '1/2', '4/3', '1/6'],
    answerIndex: 1,
    difficulty: 'medium',
  },
  {
    id: 'q-005',
    prompt: '2/5 + 1/10 = ?',
    options: ['1/2', '3/15', '2/50', '3/10'],
    answerIndex: 0,
    difficulty: 'medium',
  },
  {
    id: 'q-006',
    prompt: '7/8 - 3/8 = ?',
    options: ['4/16', '10/8', '5/8', '1/2'],
    answerIndex: 3,
    difficulty: 'easy',
  },
  {
    id: 'q-007',
    prompt: '1/3 + 1/6 = ?',
    options: ['2/9', '1/9', '1/2', '2/6'],
    answerIndex: 2,
    difficulty: 'easy',
  },
  {
    id: 'q-008',
    prompt: '3/5 - 1/4 = ?',
    options: ['7/20', '2/1', '1/20', '2/9'],
    answerIndex: 0,
    difficulty: 'hard',
  },
  {
    id: 'q-009',
    prompt: '2/7 + 3/7 = ?',
    options: ['5/7', '5/14', '6/7', '1/7'],
    answerIndex: 0,
    difficulty: 'easy',
  },
  {
    id: 'q-010',
    prompt: '9/10 - 2/5 = ?',
    options: ['7/5', '1/5', '4/5', '1/2'],
    answerIndex: 3,
    difficulty: 'medium',
  },
  {
    id: 'q-011',
    prompt: '1/4 + 1/8 = ?',
    options: ['2/12', '3/8', '1/2', '2/8'],
    answerIndex: 1,
    difficulty: 'medium',
  },
  {
    id: 'q-012',
    prompt: '5/6 - 1/6 = ?',
    options: ['1/6', '3/6', '2/3', '5/6'],
    answerIndex: 2,
    difficulty: 'easy',
  },
];

module.exports = { SEED_QUESTIONS };
