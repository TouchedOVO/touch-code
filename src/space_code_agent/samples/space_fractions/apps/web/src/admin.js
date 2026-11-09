/**
 * Admin console for question CRUD.
 * Covers: FR-DERIVED-2, ASR-2
 */

const baseUrl = (window.__QUESTION_API_BASE__ || 'http://127.0.0.1:4001').replace(/\/$/, '');
const elements = {
  token: document.getElementById('token'),
  load: document.getElementById('load-btn'),
  status: document.getElementById('status'),
  form: document.getElementById('question-form'),
  formTitle: document.getElementById('form-title'),
  prompt: document.getElementById('prompt'),
  options: [0, 1, 2, 3].map((index) => document.getElementById(`opt-${index}`)),
  answer: document.getElementById('answer'),
  difficulty: document.getElementById('difficulty'),
  save: document.getElementById('save-btn'),
  cancel: document.getElementById('cancel-btn'),
  table: document.getElementById('question-table'),
  tbody: document.querySelector('#question-table tbody'),
};

let editingId = null;

function token() {
  return elements.token.value.trim();
}

function headers() {
  return { 'content-type': 'application/json', authorization: `Bearer ${token()}` };
}

function setStatus(message, kind = 'info') {
  elements.status.textContent = message;
  elements.status.style.color = kind === 'error' ? 'var(--bad)' : 'var(--muted)';
}

async function request(path, options = {}) {
  const response = await fetch(`${baseUrl}${path}`, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.message || payload.error || `HTTP ${response.status}`);
  }
  return payload;
}

function resetForm() {
  editingId = null;
  elements.form.reset();
  elements.formTitle.textContent = '新增题目';
  elements.cancel.hidden = true;
}

function renderQuestions(questions) {
  elements.tbody.replaceChildren();
  for (const question of questions) {
    const row = document.createElement('tr');
    const cells = [
      question.id,
      question.prompt,
      String.fromCharCode(65 + question.answerIndex),
      question.difficulty,
    ];
    for (const value of cells) {
      const cell = document.createElement('td');
      cell.textContent = value;
      row.appendChild(cell);
    }
    const actions = document.createElement('td');
    const edit = document.createElement('button');
    edit.type = 'button';
    edit.className = 'btn';
    edit.textContent = '编辑';
    edit.addEventListener('click', () => beginEdit(question));
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'btn';
    remove.textContent = '删除';
    remove.addEventListener('click', () => deleteQuestion(question.id));
    actions.append(edit, remove);
    row.appendChild(actions);
    elements.tbody.appendChild(row);
  }
  elements.table.hidden = questions.length === 0;
}

function beginEdit(question) {
  editingId = question.id;
  elements.formTitle.textContent = `编辑 ${question.id}`;
  elements.prompt.value = question.prompt;
  question.options.forEach((option, index) => {
    elements.options[index].value = option;
  });
  elements.answer.value = String(question.answerIndex);
  elements.difficulty.value = question.difficulty || 'easy';
  elements.cancel.hidden = false;
  elements.form.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

async function loadQuestions() {
  if (!token()) {
    setStatus('请先填写管理员令牌。', 'error');
    return;
  }
  try {
    setStatus('加载中…');
    const payload = await request('/admin/questions', { headers: headers() });
    renderQuestions(payload.questions);
    elements.form.hidden = false;
    setStatus(`已加载 ${payload.questions.length} 道题。`);
  } catch (error) {
    setStatus(`加载失败：${error.message}`, 'error');
  }
}

async function deleteQuestion(id) {
  if (!window.confirm(`确定删除 ${id}？`)) return;
  try {
    await request(`/questions/${encodeURIComponent(id)}`, { method: 'DELETE', headers: headers() });
    setStatus(`已删除 ${id}。`);
    await loadQuestions();
  } catch (error) {
    setStatus(`删除失败：${error.message}`, 'error');
  }
}

elements.form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const payload = {
    prompt: elements.prompt.value.trim(),
    options: elements.options.map((input) => input.value.trim()),
    answerIndex: Number(elements.answer.value),
    difficulty: elements.difficulty.value,
  };
  try {
    const path = editingId ? `/questions/${encodeURIComponent(editingId)}` : '/questions';
    const method = editingId ? 'PUT' : 'POST';
    await request(path, { method, headers: headers(), body: JSON.stringify(payload) });
    setStatus(editingId ? `已更新 ${editingId}。` : '已新增题目。');
    resetForm();
    await loadQuestions();
  } catch (error) {
    setStatus(`保存失败：${error.message}`, 'error');
  }
});

elements.load.addEventListener('click', loadQuestions);
elements.cancel.addEventListener('click', resetForm);
