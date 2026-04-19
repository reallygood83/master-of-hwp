const state = { documentId: '' };

const els = {
  readinessText: document.getElementById('readinessText'),
  saveText: document.getElementById('saveText'),
  sessionText: document.getElementById('sessionText'),
  outputPane: document.getElementById('outputPane'),
  pathInput: document.getElementById('pathInput'),
  readonlyToggle: document.getElementById('readonlyToggle'),
  paragraphIndex: document.getElementById('paragraphIndex'),
  replaceText: document.getElementById('replaceText'),
  insertText: document.getElementById('insertText'),
  savePath: document.getElementById('savePath'),
  refreshStatus: document.getElementById('refreshStatus'),
  openBtn: document.getElementById('openBtn'),
  textBtn: document.getElementById('textBtn'),
  structureBtn: document.getElementById('structureBtn'),
  replaceBtn: document.getElementById('replaceBtn'),
  insertBtn: document.getElementById('insertBtn'),
  saveBtn: document.getElementById('saveBtn'),
  validateBtn: document.getElementById('validateBtn'),
  clearBtn: document.getElementById('clearBtn'),
};

function renderOutput(label, payload) {
  els.outputPane.textContent = `${label}\n\n${JSON.stringify(payload, null, 2)}`;
}

async function postJson(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return await res.json();
}

function updateSessionText() {
  els.sessionText.textContent = state.documentId ? `열린 문서: ${state.documentId}` : '열린 문서 없음';
}

async function refreshStatus() {
  const res = await fetch('/api/status');
  const payload = await res.json();
  const integration = payload.integration?.data || {};
  const save = payload.save?.data || {};
  els.readinessText.textContent = integration.ready
    ? `읽기 준비 완료 · command preview ${integration.command_preview?.length || 0}개 요소`
    : '읽기 엔진 준비 안 됨';
  els.saveText.textContent = save.ready
    ? '저장 엔진 준비 완료'
    : '저장 엔진은 부분 지원 상태';
  renderOutput('STATUS', payload);
}

async function openDocument() {
  const payload = await postJson('/api/open', {
    path: els.pathInput.value,
    readonly: els.readonlyToggle.checked,
  });
  state.documentId = payload.data?.document_id || '';
  updateSessionText();
  renderOutput('OPEN_DOCUMENT', payload);
}

async function extractText() {
  const payload = await postJson('/api/text', {
    document_id: state.documentId,
    path: state.documentId ? '' : els.pathInput.value,
  });
  renderOutput('EXTRACT_TEXT', payload);
}

async function extractStructure() {
  const payload = await postJson('/api/structure', {
    document_id: state.documentId,
    path: state.documentId ? '' : els.pathInput.value,
  });
  renderOutput('EXTRACT_STRUCTURE', payload);
}

async function replaceParagraph() {
  const payload = await postJson('/api/replace', {
    document_id: state.documentId,
    paragraph_index: Number(els.paragraphIndex.value),
    new_text: els.replaceText.value,
  });
  renderOutput('REPLACE_PARAGRAPH', payload);
}

async function insertParagraph() {
  const payload = await postJson('/api/insert', {
    document_id: state.documentId,
    after_paragraph_index: Number(els.paragraphIndex.value),
    text: els.insertText.value,
  });
  renderOutput('INSERT_PARAGRAPH', payload);
}

async function saveDocument() {
  const payload = await postJson('/api/save', {
    document_id: state.documentId,
    output_path: els.savePath.value,
  });
  renderOutput('SAVE_AS', payload);
}

async function validateDocument() {
  const payload = await postJson('/api/validate', {
    path: els.savePath.value,
  });
  renderOutput('VALIDATE_DOCUMENT', payload);
}

els.refreshStatus.addEventListener('click', refreshStatus);
els.openBtn.addEventListener('click', openDocument);
els.textBtn.addEventListener('click', extractText);
els.structureBtn.addEventListener('click', extractStructure);
els.replaceBtn.addEventListener('click', replaceParagraph);
els.insertBtn.addEventListener('click', insertParagraph);
els.saveBtn.addEventListener('click', saveDocument);
els.validateBtn.addEventListener('click', validateDocument);
els.clearBtn.addEventListener('click', () => {
  els.outputPane.textContent = '아직 실행 결과가 없습니다.';
});

updateSessionText();
refreshStatus();
