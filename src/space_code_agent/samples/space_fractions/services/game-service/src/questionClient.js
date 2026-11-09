'use strict';

// Covers: FR-1, NFR-1
function createQuestionClient({
  baseUrl = process.env.QUESTION_SERVICE_URL || 'http://127.0.0.1:4001',
  serviceToken = process.env.SERVICE_TOKEN || 'dev-service-token',
  fetchImpl = globalThis.fetch,
} = {}) {
  async function fetchQuestions(count = 10) {
    const endpoint = `${baseUrl.replace(/\/$/, '')}/internal/questions?count=${count}`;
    let response;
    try {
      response = await fetchImpl(endpoint, {
        headers: { 'x-service-token': serviceToken },
        signal: AbortSignal.timeout(3000),
      });
    } catch (error) {
      const wrapped = new Error(`question-service unavailable: ${error.message}`);
      wrapped.code = 'question_service_unavailable';
      wrapped.statusCode = 502;
      throw wrapped;
    }
    if (!response.ok) {
      const wrapped = new Error(`question-service returned ${response.status}`);
      wrapped.code = 'question_service_error';
      wrapped.statusCode = 502;
      throw wrapped;
    }
    const payload = await response.json();
    if (!Array.isArray(payload.questions) || payload.questions.length === 0) {
      const wrapped = new Error('question-service returned no questions');
      wrapped.code = 'empty_question_bank';
      wrapped.statusCode = 502;
      throw wrapped;
    }
    return payload.questions;
  }

  return { fetchQuestions };
}

module.exports = { createQuestionClient };
