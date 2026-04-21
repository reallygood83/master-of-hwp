/* master-of-hwp simplified GUI
 * Chat-driven workflow. Left: real rhwp editor. Right: AI provider panel.
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
  lastQuotedSelectionKey: null,
};

function selectionKey(sel) {
  if (!sel?.hasSelection || !sel.start || !sel.end) return null;
  return [
    sel.start.sectionIndex, sel.start.paragraphIndex, sel.start.charOffset,
    sel.end.sectionIndex, sel.end.paragraphIndex, sel.end.charOffset,
  ].join(':');
}

const $ = (id) => document.getElementById(id);
const els = {
  fileName: $('fileName'),
  statusDot: $('statusDot'),
  openBtn: $('openBtn'),
  saveBtn: $('saveBtn'),
  providerSelect: $('providerSelect'),
  editorFrame: $('editorFrame'),
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
  newChatBtn: $('newChatBtn'),
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

function currentProvider() {
  return els.providerSelect?.value || 'claude';
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

function renderTablePreviewHtml(table) {
  if (!table || !Array.isArray(table.cells)) return '';
  const rows = table.cells.map((row, rIdx) => {
    const tag = rIdx === 0 ? 'th' : 'td';
    const cellsHtml = row.map((c) => `<${tag}>${escapeHtml(String(c ?? ''))}</${tag}>`).join('');
    return `<tr>${cellsHtml}</tr>`;
  }).join('');
  return `<table class="hwp-table-preview">${rows}</table>`;
}

function addPreviewCard(preview) {
  const providerLabel = preview.provider || currentProvider();
  const label = preview.selection ? '선택 영역' : `문단 ${preview.paragraph_index}`;
  const isTable = preview.content_type === 'table' && preview.table;
  const typeChip = isTable ? ' · <span class="type-chip">표</span>' : '';
  const card = document.createElement('div');
  card.className = 'preview-card';
  const bodyHtml = isTable
    ? renderTablePreviewHtml(preview.table)
    : escapeHtml(preview.content || '');
  card.innerHTML = `
    <div class="card-head">
      <div class="title">${escapeHtml(preview.title || 'AI 제안')} · ${label} · ${escapeHtml(providerLabel)}${typeChip}</div>
      <div class="card-actions">
        <button class="chip-btn copy-btn" title="클립보드로 복사">📋 복사</button>
        <button class="chip-btn insert-btn" title="문서에 바로 삽입">📥 삽입</button>
      </div>
    </div>
    <div class="content ${isTable ? 'content-table' : ''}">${bodyHtml}</div>
    <div class="row tertiary">
      <button class="btn link cancel-btn">닫기</button>
    </div>
  `;
  els.chatLog.appendChild(card);
  els.chatLog.scrollTop = els.chatLog.scrollHeight;

  const copyBtn = card.querySelector('.copy-btn');
  const insertBtn = card.querySelector('.insert-btn');

  copyBtn.addEventListener('click', async () => {
    try {
      const textPayload = isTable
        ? preview.table.cells.map((row) => row.join('\t')).join('\n')
        : (preview.content || '');
      await navigator.clipboard.writeText(textPayload);
      const orig = copyBtn.textContent;
      copyBtn.textContent = '✓ 복사됨';
      copyBtn.disabled = true;
      setTimeout(() => { copyBtn.textContent = orig; copyBtn.disabled = false; }, 1500);
    } catch (err) {
      addBubble('error', `복사 실패: ${err.message}`);
    }
  });

  insertBtn.addEventListener('click', async () => {
    insertBtn.disabled = true;
    insertBtn.textContent = '삽입 중...';
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
      let editorOk = true;
      try {
        if (preview.selection?.hasSelection) {
          if (isTable) {
            // 표 형태 결과: 선택 영역을 삭제 후 그 위치에 HWP 네이티브 표를 생성
            await sendEditorRequest('applyEditTable', {
              section: preview.selection.start.sectionIndex,
              startPara: preview.selection.start.paragraphIndex,
              endPara: preview.selection.end.paragraphIndex,
              startChar: preview.selection.start.charOffset,
              endChar: preview.selection.end.charOffset,
              table: preview.table,
            });
          } else {
            // 전체 start/end 포지션(파셀 컨텍스트 포함) 전달 — main.ts가 cell-aware 처리
            await sendEditorRequest('applyEdit', {
              section: preview.selection.start.sectionIndex,
              start: preview.selection.start,
              end: preview.selection.end,
              startPara: preview.selection.start.paragraphIndex,
              endPara: preview.selection.end.paragraphIndex,
              startChar: preview.selection.start.charOffset,
              endChar: preview.selection.end.charOffset,
              newText: preview.content || '',
            });
          }
        } else {
          const para = state.structure?.paragraphs?.[preview.paragraph_index];
          const section = Number(para?.section_index ?? 0);
          const wasmPara = Number(para?.source_paragraph_index ?? preview.paragraph_index);
          const charCount = Number(para?.char_count ?? String(para?.text || '').length);
          if (isTable) {
            // 문단 모드 + 표: insert면 문단 끝에, rewrite/summarize면 기존 문단 통째로 교체
            const rewriteMode = preview.task_type !== 'insert';
            await sendEditorRequest('applyEditTable', {
              section,
              startPara: wasmPara,
              endPara: wasmPara,
              startChar: rewriteMode ? 0 : charCount,
              endChar: rewriteMode ? charCount : charCount,
              table: preview.table,
            });
          } else if (preview.task_type === 'insert') {
            // append a new paragraph after the target paragraph
            await sendEditorRequest('applyEdit', {
              section,
              startPara: wasmPara,
              endPara: wasmPara,
              startChar: charCount,
              endChar: charCount,
              newText: '\n' + (preview.content || ''),
            });
          } else {
            // rewrite/summarize → replace the whole paragraph
            await sendEditorRequest('applyEdit', {
              section,
              startPara: wasmPara,
              endPara: wasmPara,
              startChar: 0,
              endChar: charCount,
              newText: preview.content || '',
            });
          }
        }
      } catch (err) {
        editorOk = false;
        addBubble('error', `에디터 반영 실패: ${err.message}`);
      }
      if (editorOk) {
        addBubble('system', `✓ ${preview.selection ? '선택 영역' : `문단 ${preview.paragraph_index}`}에 삽입됨`);
      }
      await reloadDocument();
      insertBtn.textContent = editorOk ? '✓ 삽입됨' : '⚠ 부분 실패';
    } else {
      addBubble('error', `삽입 실패: ${res.message || '알 수 없는 오류'}`);
      insertBtn.textContent = '📥 삽입';
      insertBtn.disabled = false;
    }
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
    console.log('[rhwp-selection]', msg.payload);
    state.selection = msg.payload?.hasSelection ? msg.payload : null;
    if (state.selection?.start?.paragraphIndex !== undefined) {
      state.selectedIndex = state.selection.start.paragraphIndex;
    }
    if (!state.selection) state.lastQuotedSelectionKey = null;
    updateSelInfo();
  }
});

els.editorFrame.addEventListener('load', async () => {
  try {
    await sendEditorRequest('ready');
    state.editorReady = true;
    startSelectionPolling();
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
  const node = els.selInfo;
  node.classList.remove('sel-active', 'sel-para', 'sel-empty');
  if (state.selection?.hasSelection && state.selection.text) {
    const txt = String(state.selection.text).replace(/\n/g, ' ');
    const preview = txt.length > 50 ? txt.slice(0, 50) + '…' : txt;
    const len = txt.length;
    node.textContent = `✓ 드래그 선택됨 (${len}자) · "${preview}"`;
    node.title = txt;
    node.classList.add('sel-active');
    return;
  }
  node.title = '';
  if (state.selectedIndex == null) {
    node.textContent = '⭘ 선택 없음 — 텍스트를 드래그하거나 문단을 클릭하세요';
    node.classList.add('sel-empty');
  } else {
    node.textContent = `문단 ${state.selectedIndex + 1} 선택됨`;
    node.classList.add('sel-para');
  }
}

// 주기적 재조회 — push 이벤트 유실 및 셀선택 모드 상태 변화 보강.
// 에디터가 ready이고 값이 달라진 경우만 state를 갱신해 깜박임 방지.
let __selPollHandle = null;
function startSelectionPolling() {
  if (__selPollHandle) return;
  __selPollHandle = setInterval(async () => {
    if (!state.editorReady) return;
    try {
      const live = await sendEditorRequest('getSelection');
      const curKey = state.selection ? selectionKey(state.selection) : null;
      const liveKey = live?.hasSelection ? selectionKey(live) : null;
      if (curKey !== liveKey) {
        state.selection = live?.hasSelection ? live : null;
        if (state.selection?.start?.paragraphIndex !== undefined) {
          state.selectedIndex = state.selection.start.paragraphIndex;
        }
        updateSelInfo();
      }
    } catch { /* 에디터 준비 전이면 무시 */ }
  }, 800);
}

function ensureDefaultParagraphSelection() {
  // Intentionally a no-op: auto-defaulting to paragraph 0 silently targets the
  // document title when a user asks to rewrite something they thought they had
  // selected. Require explicit drag-selection or a "문단 N" mention instead.
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
  addBubble('system', `✓ ${els.fileName.textContent} 열림`);

  if (state.editorReady) {
    try {
      await loadIntoEditor(state.path);
    } catch (err) {
      addBubble('error', `에디터 로드 실패: ${err.message}`);
    }
  } else {
    addBubble('system', 'ℹ 한글의 달인 준비 대기 중 — 잠시 후 다시 시도합니다.');
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
  let paragraphIndexSource = null; // 'explicit' | 'selection' | 'click'
  if (paraMatch) {
    paragraphIndex = parseInt(paraMatch[1] || paraMatch[2], 10) - 1;
    paragraphIndexSource = 'explicit';
  } else if (state.selection?.hasSelection) {
    paragraphIndex = state.selection.start.paragraphIndex;
    paragraphIndexSource = 'selection';
  } else if (state.selectedIndex != null) {
    paragraphIndex = state.selectedIndex;
    paragraphIndexSource = 'click';
  }

  const hasRealSelection = !!(state.selection?.hasSelection && state.selection.text && state.selection.text.trim());
  const mentionsSelection = /드래그|선택(?:한|된)?|이\s*부분|여기(?:에)?|표시한|하이라이트|highlighted|selected|selection/i.test(t);
  const mentionsContentArea = /이\s*(?:내용|글|문장|표|행|열|셀|칸|항목|부분)|여기\s*(?:내용|글|부분)|위\s*(?:내용|표|글)/i.test(t);
  if ((mentionsSelection || mentionsContentArea) && !hasRealSelection) {
    return { type: 'need_selection' };
  }
  // Silently editing paragraph 0 when the user never picked a target is how we used to
  // hallucinate unrelated content. Force an explicit pick if nothing is targeted.
  if (paragraphIndex == null) {
    return { type: 'need_index' };
  }

  if (/뒤에|다음에|이후에|추가|삽입|insert/.test(t)) {
    if (hasRealSelection) return { type: 'ai_selection_insert', paragraphIndex, instruction: t };
    if (paragraphIndex == null) return { type: 'need_index' };
    return { type: 'ai_insert', paragraphIndex, instruction: t };
  }
  if (/요약|summar/i.test(t)) {
    if (hasRealSelection) return { type: 'ai_selection_summarize', paragraphIndex, instruction: t };
    if (paragraphIndex == null) return { type: 'need_index' };
    return { type: 'ai_summarize', paragraphIndex, instruction: t };
  }
  if (hasRealSelection) return { type: 'ai_selection_rewrite', paragraphIndex, instruction: t };
  if (paragraphIndex == null) return { type: 'need_index' };
  return { type: 'ai_rewrite', paragraphIndex, instruction: t };
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

function addQuoteBubble(text) {
  const preview = String(text).slice(0, 200).replace(/\s+/g, ' ').trim();
  if (!preview) return;
  const div = document.createElement('div');
  div.className = 'bubble quote';
  div.textContent = `" ${preview}${text.length > 200 ? '…' : ''} "`;
  els.chatLog.appendChild(div);
  els.chatLog.scrollTop = els.chatLog.scrollHeight;
}

async function handleChat(text) {
  // submit 시점 실시간 재조회 — 드래그 후 포커스/클릭으로 선택이 해제됐거나,
  // push 이벤트가 유실된 경우 대비.
  try {
    if (state.editorReady) {
      const live = await sendEditorRequest('getSelection');
      if (live?.hasSelection && live.text && String(live.text).trim()) {
        state.selection = live;
        if (live.start?.paragraphIndex !== undefined) {
          state.selectedIndex = live.start.paragraphIndex;
        }
        updateSelInfo();
      }
    }
  } catch (err) {
    console.warn('[handleChat] getSelection 재조회 실패', err);
  }

  if (state.selection?.hasSelection && state.selection.text) {
    const key = selectionKey(state.selection);
    if (key && key !== state.lastQuotedSelectionKey) {
      addQuoteBubble(state.selection.text);
      state.lastQuotedSelectionKey = key;
    }
  }
  addBubble('user', `${currentProvider().toUpperCase()} · ${text}`);
  const intent = parseIntent(text);
  if (!intent) return;

  if (intent.type === 'need_index') {
    addBubble('ai', '어느 문단이나 선택 영역을 대상으로 할까요? 문단을 클릭하거나 텍스트를 드래그해 주세요.');
    return;
  }
  if (intent.type === 'need_selection') {
    const sel = state.selection;
    const diag = sel
      ? `현재 selection: hasSelection=${!!sel.hasSelection}, text="${String(sel.text || '').slice(0, 30)}", start=${JSON.stringify(sel.start)}`
      : '현재 selection: (null) — 편집기에서 선택 이벤트가 도착하지 않았습니다';
    addBubble('ai', `⚠ "드래그한 부분"이라고 하셨는데 실제 선택 텍스트가 감지되지 않았어요.\n${diag}\n\n편집기에서 텍스트를 다시 드래그해 주세요. (Cmd+Shift+R로 강제 새로고침 후 재시도해 보세요.)`);
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

  const provider = currentProvider();
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
  const thinking = addBubble('ai', `${provider} 생각 중...`);
  const endpoint = selectionMode ? '/api/ai/preview-selection' : '/api/ai/preview';
  const payload = selectionMode
    ? {
        provider,
        document_id: state.documentId,
        selection: state.selection,
        task_type: taskType,
        instruction: intent.instruction,
      }
    : {
        provider,
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

const helpModal = document.getElementById('helpModal');
const helpBtn = document.getElementById('helpBtn');
const helpClose = document.getElementById('helpClose');
if (helpBtn && helpModal && helpClose) {
  const openHelp = () => helpModal.classList.remove('hidden');
  const closeHelp = () => helpModal.classList.add('hidden');
  helpBtn.addEventListener('click', openHelp);
  helpClose.addEventListener('click', closeHelp);
  helpModal.addEventListener('click', (e) => { if (e.target === helpModal) closeHelp(); });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !helpModal.classList.contains('hidden')) closeHelp();
  });
}
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

els.newChatBtn?.addEventListener('click', () => {
  state.lastQuotedSelectionKey = null;
  els.chatText.value = '';
  showEmptyChat();
});
// Enter handling with IME (Korean composition) protection.
// Pressing Enter while a hangul syllable is mid-composition would otherwise
// leave the last jamo/syllable in the textarea and cause the next submit to
// fire with just that stray character ("줘" bug).
els.chatText.addEventListener('keydown', (e) => {
  if (e.key !== 'Enter' || e.shiftKey) return;
  if (e.isComposing || e.keyCode === 229) return; // IME mid-composition
  e.preventDefault();
  els.chatForm.dispatchEvent(new Event('submit'));
});

showEmptyChat();
updateSelInfo();
getStatus();
