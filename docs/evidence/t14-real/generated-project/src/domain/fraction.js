'use strict';

/**
 * Sixth-grade fraction helpers: parsing, normalising, arithmetic and
 * multiple-choice question generation. All operations return reduced,
 * canonical fractions (denominator kept positive).
 */

function gcd(a, b) {
  let x = Math.abs(a);
  let y = Math.abs(b);
  while (y !== 0) {
    const t = y;
    y = x % y;
    x = t;
  }
  return x || 1;
}

function reduceFraction(numerator, denominator) {
  if (!Number.isFinite(numerator) || !Number.isFinite(denominator)) {
    throw new Error('Fraction parts must be finite numbers.');
  }
  if (denominator === 0) {
    throw new Error('Denominator cannot be zero.');
  }
  let n = numerator;
  let d = denominator;
  if (d < 0) {
    n = -n;
    d = -d;
  }
  const g = gcd(n, d);
  return { numerator: n / g, denominator: d / g };
}

function fractionFromParts(numerator, denominator) {
  return reduceFraction(numerator, denominator);
}

/**
 * Parse "3/4", "1 1/2", "-2/3" or a whole number into a canonical fraction.
 */
function parseFraction(input) {
  if (typeof input !== 'string') {
    throw new Error('Fraction must be a string.');
  }
  const text = input.trim();
  let match = text.match(/^(-?\d+)\s+(\d+)\s*\/\s*(\d+)$/);
  if (match) {
    const whole = Number(match[1]);
    const num = Number(match[2]);
    const den = Number(match[3]);
    if (den === 0) throw new Error('Denominator cannot be zero.');
    const sign = whole < 0 ? -1 : 1;
    return reduceFraction(sign * (Math.abs(whole) * den + num), den);
  }
  match = text.match(/^(-?\d+)\s*\/\s*(\d+)$/);
  if (match) {
    return reduceFraction(Number(match[1]), Number(match[2]));
  }
  match = text.match(/^(-?\d+)$/);
  if (match) {
    return reduceFraction(Number(match[1]), 1);
  }
  throw new Error(`Invalid fraction format: ${input}`);
}

function formatFraction(fraction, options = {}) {
  const { numerator, denominator } = reduceFraction(fraction.numerator, fraction.denominator);
  if (denominator === 1) return String(numerator);
  if (options.mixed && Math.abs(numerator) > denominator) {
    const whole = Math.trunc(numerator / denominator);
    const remainder = Math.abs(numerator % denominator);
    return remainder === 0 ? String(whole) : `${whole} ${remainder}/${denominator}`;
  }
  return `${numerator}/${denominator}`;
}

function addFractions(a, b) {
  return reduceFraction(
    a.numerator * b.denominator + b.numerator * a.denominator,
    a.denominator * b.denominator
  );
}

function subtractFractions(a, b) {
  return reduceFraction(
    a.numerator * b.denominator - b.numerator * a.denominator,
    a.denominator * b.denominator
  );
}

function multiplyFractions(a, b) {
  return reduceFraction(a.numerator * b.numerator, a.denominator * b.denominator);
}

function divideFractions(a, b) {
  if (b.numerator === 0) {
    throw new Error('Cannot divide by zero.');
  }
  return reduceFraction(a.numerator * b.denominator, a.denominator * b.numerator);
}

const OPERATORS = [
  { symbol: '+', name: 'addition', apply: addFractions },
  { symbol: '−', name: 'subtraction', apply: subtractFractions },
  { symbol: '×', name: 'multiplication', apply: multiplyFractions },
  { symbol: '÷', name: 'division', apply: divideFractions }
];

function shuffle(items, random) {
  const arr = items.slice();
  for (let i = arr.length - 1; i > 0; i -= 1) {
    const j = Math.floor(random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

function randomProperFraction(random) {
  // Denominator from 2 to 10, numerator from 1 to denominator - 1.
  const denominator = 2 + Math.floor(random() * 9);
  const numerator = 1 + Math.floor(random() * (denominator - 1));
  return { numerator, denominator };
}

function makeDistractor(answer, random) {
  const roll = random();
  if (roll < 0.34) {
    const numerator = answer.numerator + (random() < 0.5 ? -1 : 1);
    return reduceFraction(numerator, answer.denominator);
  }
  if (roll < 0.67) {
    return reduceFraction(answer.numerator, Math.max(1, answer.denominator - 1));
  }
  return reduceFraction(answer.numerator + 1, answer.denominator + 1);
}

function buildOptions(answer, random) {
  const correctLabel = formatFraction(answer);
  const labels = new Set([correctLabel]);

  let guard = 0;
  while (labels.size < 4 && guard < 200) {
    guard += 1;
    const candidate = makeDistractor(answer, random);
    const label = formatFraction(candidate);
    if (!labels.has(label)) labels.add(label);
  }

  const fallbacks = [
    { numerator: answer.numerator + 1, denominator: answer.denominator },
    { numerator: answer.numerator, denominator: answer.denominator + 1 },
    { numerator: answer.numerator + 1, denominator: answer.denominator + 1 },
    { numerator: answer.numerator, denominator: Math.max(1, answer.denominator - 1) }
  ];
  for (const fallback of fallbacks) {
    if (labels.size >= 4) break;
    const label = formatFraction(fallback);
    if (!labels.has(label)) labels.add(label);
  }

  let wholeFallback = 1;
  while (labels.size < 4) {
    labels.add(String(wholeFallback));
    wholeFallback += 1;
  }

  return shuffle(Array.from(labels), random);
}

/**
 * Generate a random fraction question with exactly four unique options.
 * Returns the canonical answer string plus a display-ready text prompt.
 */
function generateFractionQuestion(random = Math.random) {
  const operator = OPERATORS[Math.floor(random() * OPERATORS.length)];
  let a = randomProperFraction(random);
  let b = randomProperFraction(random);

  if (operator.name === 'subtraction' && a.numerator / a.denominator < b.numerator / b.denominator) {
    const tmp = a;
    a = b;
    b = tmp;
  }
  if (operator.name === 'division' && b.numerator === 0) {
    b = { numerator: 1, denominator: b.denominator };
  }

  const answer = operator.apply(a, b);
  const answerLabel = formatFraction(answer);
  const options = buildOptions(answer, random);
  const answerIndex = options.indexOf(answerLabel);

  return {
    text: `${formatFraction(a)} ${operator.symbol} ${formatFraction(b)} = ?`,
    options,
    answerIndex,
    answer: answerLabel,
    operator: operator.symbol,
    operandA: formatFraction(a),
    operandB: formatFraction(b)
  };
}

module.exports = {
  gcd,
  reduceFraction,
  fractionFromParts,
  parseFraction,
  formatFraction,
  addFractions,
  subtractFractions,
  multiplyFractions,
  divideFractions,
  generateFractionQuestion,
  OPERATORS
};
