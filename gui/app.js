/* master-of-hwp simplified GUI
 * Chat-driven workflow. Left: real rhwp editor. Right: Claude panel.
 */

const state = {
  documentId: '',
  path: '',
  selectedIndex: null,
  structure: null,
  saved: true,
  editorReady: false,
  editorReqId: 0,
  pendingEditorReqs: new Map(),
  selection: null,
};

const $ = (id) => document.getElementById(id);
const els = {
  fileName: $('fileName'),
  statusDot: $('statusDot'),
  openBtn: $('openBtn'),
  saveBtn: $('saveBtn'),
  editorFrame: $('editorFrame'),
  editorHint: $('editorHint'),
  docMeta: $('docMeta'),
  selInfo: $('selInfo'),
  chatLog: $('chatLog'),
  chatForm: $('chatForm'),
  chatText: $('chatText'),
  modal: $('modal'),
  modalClose: $('modalClose'),
  fileList: $('fileList'),
  pathInput: $('pathInput'),
  upBtn: $('upBtn'),
  goBtn: $('goBtn'),
};

async function api(path, body) {
  try {
    const res = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}),
    });
    return await res.json();
  } catch (err) {
    return { ok: false, message: String(err) };
  }
}

async function getStatus() {
  try {
    const res = await fetch('/api/status');
    const payload = await res.json();
    const ready = Boolean(payload.integration?.data?.ready);
    els.statusDot.classList.toggle('on', ready);
    els.statusDot.classList.toggle('off', !ready);
    els.statusDot.title = ready ? '서버 준비 완료' : '서버 연결됨 (읽기 엔진 부분 지원)';
    return true;
  } catch {
    els.statusDot.classList.remove('on');
    els.statusDot.classList.add('off');
    els.statusDot.title = '서버 응답 없음';
    return false;
  }
}

function showEmptyChat() {
  els.chatLog.innerHTML = `
    <div class="chat-empty">
      자연어로 문서를 수정해 보세요.
      <span class="ex">예: "드래그한 부분을 공식 문서체로 바꿔줘"</span>
      <span class="ex">예: "선택한 부분을 요약해줘"</span>
      <span class="ex">예: "문단 5 뒤에 결론 추가해줘" · "저장"</span>
    </div>
  `;
}

function addBubble(role, text) {
  const div = document.createElement('div');
  div.className = `bubble ${role}`;
  div.textContent = text;
  els.chatLog.appendChild(div);
  els.chatLog.scrollTop = els.chatLog.scrollHeight;
  return div;
}

function addPreviewCard(preview) {
  const label = preview.selection ? '선택 영역' : `문단 ${preview.paragraph_index}`;
  const card = document.createElement('div');
  card.className = 'preview-card';
  card.innerHTML = `
    <div class="title">${escapeHtml(preview.title || 'AI 제안')} · ${label}</div>
    <div class="content">${escapeHtml(preview.content || '')}</div>
    <div class="row">
      <button class="btn primary apply-btn">적용</button>
      <button class="btn cancel-btn">취소</button>
    </div>
  `;
  els.chatLog.appendChild(card);
  els.chatLog.scrollTop = els.chatLog.scrollHeight;

  card.querySelector('.apply-btn').addEventListener('click', async () => {
    card.querySelector('.apply-btn').disabled = true;
    const endpoint = preview.selection ? '/api/ai/apply-selection' : '/api/ai/apply';
    const payload = preview.selection
      ? {
          document_id: state.documentId,
          selection: preview.selection,
          content: preview.content,
        }
      : {
          document_id: state.documentId,
          task_type: preview.task_type,
          paragraph_index: preview.paragraph_index,
          content: preview.content,
        };
    const res = await api(endpoint, payload);
    if (res.ok) {
      state.saved = false;
      els.saveBtn.disabled = false;
      addBubble('system', `✓ ${preview.selection ? '선택 영역' : `문단 ${preview.paragraph_index}`}에 적용됨`);
      await reloadDocument();
    } else {
      addBubble('error', `적용 실패: ${res.message || '알 수 없는 오류'}`);
    }
    card.remove();
  });
  card.querySelector('.cancel-btn').addEventListener('click', () => card.remove());
}

function sendEditorRequest(method, params = {}) {
  if (!els.editorFrame?.contentWindow) {
    return Promise.reject(new Error('에디터 frame이 준비되지 않음'));
  }
  state.editorReqId += 1;
  const id = `req-${state.editorReqId}`;
  return new Promise((resolve, reject) => {
    state.pendingEditorReqs.set(id, { resolve, reject });
    els.editorFrame.contentWindow.postMessage(
      { type: 'rhwp-request', id, method, params },
      '*',
    );
    setTimeout(() => {
      if (state.pendingEditorReqs.has(id)) {
        state.pendingEditorReqs.delete(id);
        reject(new Error('에디터 응답 시간 초과'));
      }
    }, 15000);
  });
}

window.addEventListener('message', (event) => {
  const msg = event.data;
  if (!msg) return;
  if (msg.type === 'rhwp-response' && msg.id) {
    const pending = state.pendingEditorReqs.get(msg.id);
    if (!pending) return;
    state.pendingEditorReqs.delete(msg.id);
    if (msg.error) pending.reject(new Error(msg.error));
    else pending.resolve(msg.result);
    return;
  }

  if (msg.type === 'rhwp-selection') {
    state.selection = msg.payload?.hasSelection ? msg.payload : null;
    if (state.selection?.start?.paragraphIndex !== undefined) {
      state.selectedIndex = state.selection.start.paragraphIndex;
    }
    updateSelInfo();
  }
});

els.editorFrame.addEventListener('load', async () => {
  try {
    await sendEditorRequest('ready');
    state.editorReady = true;
  } catch {
    state.editorReady = false;
  }
});

function base64ToArrayBuffer(base64) {
  const bin = atob(base64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i += 1) out[i] = bin.charCodeAt(i);
  return out.buffer;
}

async function loadIntoEditor(path) {
  const res = await api('/api/file-bytes', { path });
  if (!res.ok) throw new Error(res.message || '파일 바이트 로드 실패');
  const buffer = base64ToArrayBuffer(res.data.base64);
  await sendEditorRequest('loadFile', { data: buffer, fileName: res.data.file_name });
}

function updateMeta(structure) {
  state.structure = structure;
  els.docMeta.textContent = `문단 ${structure.paragraph_count ?? 0}개 · 표 ${structure.table_count ?? 0}개`;
  updateSelInfo();
}

function updateSelInfo() {
  if (state.selection?.hasSelection && state.selection.text) {
    const preview = String(state.selection.text).slice(0, 40).replace(/\n/g, ' ');
    els.selInfo.textContent = `선택됨 · ${preview}`;
    return;
  }
  if (state.selectedIndex == null) {
    els.selInfo.textContent = '선택된 문단 없음';
  } else {
    els.selInfo.textContent = `문단 ${state.selectedIndex + 1} 선택됨`;
  }
}

function ensureDefaultParagraphSelection() {
  if (state.selectedIndex != null) return;
  const paragraphCount = Number(state.structure?.paragraph_count || 0);
  if (paragraphCount > 0) {
    state.selectedIndex = 0;
    updateSelInfo();
  }
}

async function openDocumentByPath(path) {
  addBubble('system', `📂 ${path} 여는 중...`);
  const res = await api('/api/open', { path, readonly: false });
  if (!res.ok) {
    addBubble('error', `열기 실패: ${res.message || '알 수 없는 오류'}`);
    return;
  }
  state.documentId = res.data.document_id;
  state.path = res.data.path;
  state.saved = true;
  state.selection = null;
  els.fileName.textContent = state.path.split('/').pop();
  els.saveBtn.disabled = false;
  els.saveBtn.dataset.outputPath = suggestOutputPath(state.path);
  if (els.editorHint) {
    els.editorHint.classList.add('hidden');
    els.editorHint.style.display = 'none';
  }
  addBubble('system', `✓ ${els.fileName.textContent} 열림`);

  if (state.editorReady) {
    try {
      await loadIntoEditor(state.path);
    } catch (err) {
      addBubble('error', `에디터 로드 실패: ${err.message}`);
    }
  } else {
    addBubble('system', 'ℹ rhwp 에디터 준비 대기 중 — 잠시 후 다시 시도합니다.');
    setTimeout(() => {
      if (state.editorReady && state.path) loadIntoEditor(state.path).catch(() => {});
    }, 1500);
  }
  await reloadDocument();
}

async function reloadDocument() {
  if (!state.documentId) return;
  const res = await api('/api/structure', { document_id: state.documentId });
  if (res.ok) {
    updateMeta(res.data);
    ensureDefaultParagraphSelection();
  } else {
    addBubble('error', `구조 로드 실패: ${res.message || ''}`);
  }
}

function suggestOutputPath(inputPath) {
  const idx = inputPath.lastIndexOf('.');
  if (idx < 0) return inputPath + '.edited';
  return inputPath.slice(0, idx) + '.edited' + inputPath.slice(idx);
}

async function saveDocument() {
  if (!state.documentId) return;
  const out = els.saveBtn.dataset.outputPath || suggestOutputPath(state.path);
  addBubble('system', `💾 저장 중: ${out}`);
  const res = await api('/api/save', {
    document_id: state.documentId,
    output_path: out,
  });
  if (res.ok) {
    state.saved = true;
    addBubble('system', `✓ 저장 완료 (${res.data?.bytes_len || '?'} bytes)`);
  } else {
    addBubble('error', `저장 실패: ${res.message || ''}`);
  }
}

function parseIntent(text) {
  const t = text.trim();
  if (!t) return null;
  if (/^(저장|save)[\s!.?]*$/i.test(t) || /저장\s*해/.test(t)) {
    return { type: 'save' };
  }

  const paraMatch = t.match(/(?:문단|para(?:graph)?)\s*(\d+)|(\d+)\s*(?:번째|번)\s*문단/i);
  let paragraphIndex = null;
  if (paraMatch) {
    paragraphIndex = parseInt(paraMatch[1] || paraMatch[2], 10) - 1;
  } else if (state.selection?.hasSelection) {
    paragraphIndex = state.selection.start.paragraphIndex;
  } else if (state.selectedIndex != null) {
    paragraphIndex = state.selectedIndex;
  } else if (Number(state.structure?.paragraph_count || 0) > 0) {
    paragraphIndex = 0;
    state.selectedIndex = 0;
    updateSelInfo();
  }

  if (/뒤에|다음에|이후에|추가|삽입|insert/.test(t)) {
    if (state.selection?.hasSelection) return { type: 'ai_selection_insert', paragraphIndex, instruction: t };
    if (paragraphIndex == null) return { type: 'need_index' };
    return { type: 'ai_insert', paragraphIndex, instruction: t };
  }
  if (/요약|summar/i.test(t)) {
    if (state.selection?.hasSelection) return { type: 'ai_selection_summarize', paragraphIndex, instruction: t };
    if (paragraphIndex == null) return { type: 'need_index' };
    return { type: 'ai_summarize', paragraphIndex, instruction: t };
  }
  if (state.selection?.hasSelection) return { type: 'ai_selection_rewrite', paragraphIndex, instruction: t };
  if (paragraphIndex == null) return { type: 'need_index' };
  return { type: 'ai_rewrite', paragraphIndex, instruction: t };
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

async function handleChat(text) {
  addBubble('user', text);
  const intent = parseIntent(text);
  if (!intent) return;

  if (intent.type === 'need_index') {
    addBubble('ai', '어느 문단이나 선택 영역을 대상으로 할까요? 문단을 클릭하거나 텍스트를 드래그해 주세요.');
    return;
  }
  if (!state.documentId && intent.type !== 'save') {
    addBubble('ai', '먼저 📂 열기로 문서를 불러와 주세요.');
    return;
  }
  if (intent.type === 'save') {
    await saveDocument();
    return;
  }

  const selectionMode = intent.type.startsWith('ai_selection_');
  const taskMap = {
    ai_rewrite: 'rewrite',
    ai_summarize: 'summarize',
    ai_insert: 'insert',
    ai_selection_rewrite: 'rewrite',
    ai_selection_summarize: 'summarize',
    ai_selection_insert: 'insert',
  };
  const taskType = taskMap[intent.type];
  const thinking = addBubble('ai', '생각 중...');
  const endpoint = selectionMode ? '/api/ai/preview-selection' : '/api/ai/preview';
  const payload = selectionMode
    ? {
        document_id: state.documentId,
        selection: state.selection,
        task_type: taskType,
        instruction: intent.instruction,
      }
    : {
        document_id: state.documentId,
        paragraph_index: intent.paragraphIndex,
        task_type: taskType,
        instruction: intent.instruction,
      };
  const res = await api(endpoint, payload);
  thinking.remove();
  if (!res.ok) {
    addBubble('error', `AI 호출 실패: ${res.message || ''}`);
    return;
  }
  addPreviewCard(res.data);
}

async function openModal(path) {
  els.modal.classList.remove('hidden');
  await browseTo(path || '/Users/moon');
}
function closeModal() { els.modal.classList.add('hidden'); }

async function browseTo(path) {
  const res = await api('/api/browse', { path });
  if (!res.ok) {
    els.fileList.innerHTML = `<div class="file-row"><span class="ic">⚠</span><span class="name">${escapeHtml(res.message || '')}</span></div>`;
    return;
  }
  const { current_path, parent_path, entries } = res.data;
  els.pathInput.value = current_path;
  els.fileList.innerHTML = '';

  if (parent_path && parent_path !== current_path) {
    const up = document.createElement('div');
    up.className = 'file-row';
    up.innerHTML = `<span class="ic">⬆</span><span class="name">상위 폴더</span>`;
    up.addEventListener('click', () => browseTo(parent_path));
    els.fileList.appendChild(up);
  }

  for (const entry of entries) {
    const row = document.createElement('div');
    row.className = 'file-row';
    const icon = entry.type === 'dir' ? '📁' : '📄';
    row.innerHTML = `
      <span class="ic">${icon}</span>
      <span class="name">${escapeHtml(entry.name)}</span>
      <span class="hint">${entry.type === 'dir' ? '' : (entry.path.split('.').pop())}</span>
    `;
    row.addEventListener('click', () => {
      if (entry.type === 'dir') {
        browseTo(entry.path);
      } else {
        closeModal();
        openDocumentByPath(entry.path);
      }
    });
    els.fileList.appendChild(row);
  }
}

els.openBtn.addEventListener('click', () => openModal(els.pathInput.value));
els.modalClose.addEventListener('click', closeModal);
els.modal.addEventListener('click', (e) => { if (e.target === els.modal) closeModal(); });
els.saveBtn.addEventListener('click', saveDocument);
els.upBtn.addEventListener('click', () => {
  const parts = els.pathInput.value.split('/').filter(Boolean);
  parts.pop();
  browseTo('/' + parts.join('/'));
});
els.goBtn.addEventListener('click', () => browseTo(els.pathInput.value));
els.pathInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') browseTo(els.pathInput.value);
});

els.chatForm.addEventListener('submit', (e) => {
  e.preventDefault();
  const text = els.chatText.value.trim();
  if (!text) return;
  els.chatText.value = '';
  handleChat(text);
});
els.chatText.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    els.chatForm.dispatchEvent(new Event('submit'));
  }
});

showEmptyChat();
updateSelInfo();
getStatus();
