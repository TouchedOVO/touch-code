/**
 * REST client for the game service.
 * Covers: FR-1, FR-DERIVED-1
 */

export function createApi(baseUrl = 'http://127.0.0.1:4002') {
  const root = String(baseUrl).replace(/\/$/, '');

  async function request(path, options = {}) {
    let response;
    try {
      response = await fetch(`${root}${path}`, {
        ...options,
        headers: { 'content-type': 'application/json', ...(options.headers || {}) },
      });
    } catch (error) {
      throw new Error(`网络连接失败：${error.message}`);
    }
    let payload = {};
    try {
      payload = await response.json();
    } catch {
      payload = {};
    }
    if (!response.ok) {
      const message = payload.message || payload.error || `HTTP ${response.status}`;
      throw new Error(message);
    }
    return payload;
  }

  return {
    createGame: () => request('/games', { method: 'POST' }),
    getGame: (gameId) => request(`/games/${encodeURIComponent(gameId)}`),
    submitAnswer: (gameId, body) => request(
      `/games/${encodeURIComponent(gameId)}/answers`,
      { method: 'POST', body: JSON.stringify(body) },
    ),
    getResult: (gameId) => request(`/games/${encodeURIComponent(gameId)}/result`),
  };
}

export function scoreMessage(score) {
  if (score >= 90) return '分数核心完全修复，船员们为你欢呼！';
  if (score >= 60) return '核心已稳定，还有少量能量损耗。再试一次冲击满分吧。';
  return '核心仍在报警。回顾错题，再来一次一定更好。';
}
