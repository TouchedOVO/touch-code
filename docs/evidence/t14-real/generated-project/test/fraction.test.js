'use strict';

// Covers: FR-1

const test = require('node:test');
const assert = require('node:assert/strict');

const {
  gcd,
  reduceFraction,
  parseFraction,
  formatFraction,
  addFractions,
  subtractFractions,
  multiplyFractions,
  divideFractions,
  generateFractionQuestion
} = require('../src/domain/fraction');

function seededRandom(seed) {
  let state = seed >>> 0;
  return function random() {
    state = (state * 1664525 + 1013904223) >>> 0;
    return state / 4294967296;
  };
}

test('gcd and reduceFraction normalise fractions', () => {
  assert.equal(gcd(12, 8), 4);
  assert.deepEqual(reduceFraction(6, 8), { numerator: 3, denominator: 4 });
  assert.deepEqual(reduceFraction(4, -8), { numerator: -1, denominator: 2 });
  assert.deepEqual(reduceFraction(0, 5), { numerator: 0, denominator: 1 });
  assert.throws(() => reduceFraction(1, 0), /Denominator cannot be zero/);
});

test('parseFraction accepts simple, mixed and whole-number forms', () => {
  assert.deepEqual(parseFraction('3/4'), { numerator: 3, denominator: 4 });
  assert.deepEqual(parseFraction('1 1/2'), { numerator: 3, denominator: 2 });
  assert.deepEqual(parseFraction('-2/4'), { numerator: -1, denominator: 2 });
  assert.deepEqual(parseFraction('5'), { numerator: 5, denominator: 1 });
  assert.throws(() => parseFraction('nope'), /Invalid fraction format/);
});

test('fraction arithmetic returns reduced results', () => {
  const a = parseFraction('1/2');
  const b = parseFraction('1/4');
  assert.deepEqual(addFractions(a, b), { numerator: 3, denominator: 4 });
  assert.deepEqual(subtractFractions(a, b), { numerator: 1, denominator: 4 });
  assert.deepEqual(multiplyFractions(parseFraction('2/3'), parseFraction('3/4')), {
    numerator: 1,
    denominator: 2
  });
  assert.deepEqual(divideFractions(parseFraction('3/5'), parseFraction('2/3')), {
    numerator: 9,
    denominator: 10
  });
  assert.throws(() => divideFractions(a, parseFraction('0')), /divide by zero/);
});

test('formatFraction renders canonical and mixed-number forms', () => {
  assert.equal(formatFraction({ numerator: 3, denominator: 4 }), '3/4');
  assert.equal(formatFraction({ numerator: 4, denominator: 8 }), '1/2');
  assert.equal(formatFraction({ numerator: 3, denominator: 2 }, { mixed: true }), '1 1/2');
  assert.equal(formatFraction({ numerator: 5, denominator: 1 }), '5');
});

test('generated questions have four unique options and a valid correct answer', () => {
  const random = seededRandom(42);
  for (let i = 0; i < 250; i += 1) {
    const question = generateFractionQuestion(random);
    assert.ok(question.text.includes('='), 'question text is a prompt');
    assert.equal(question.options.length, 4, 'exactly four options');
    assert.equal(new Set(question.options).size, 4, 'options are unique');
    assert.ok(
      Number.isInteger(question.answerIndex) &&
        question.answerIndex >= 0 &&
        question.answerIndex <= 3,
      'answerIndex is a valid option index'
    );
    assert.equal(question.options[question.answerIndex], question.answer, 'correct option matches');
  }
});

test('generated question answers are mathematically correct', () => {
  const random = seededRandom(7);
  for (let i = 0; i < 100; i += 1) {
    const question = generateFractionQuestion(random);
    const a = parseFraction(question.operandA);
    const b = parseFraction(question.operandB);
    let expected;
    if (question.operator === '+') expected = addFractions(a, b);
    else if (question.operator === '−') expected = subtractFractions(a, b);
    else if (question.operator === '×') expected = multiplyFractions(a, b);
    else expected = divideFractions(a, b);
    assert.equal(question.answer, formatFraction(expected));
  }
});
