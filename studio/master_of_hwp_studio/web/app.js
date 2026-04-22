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
        <button class="chip-btn replace-btn" title="선택 영역을 이 내용으로 교체">🔄 대치</button>
        <button class="chip-btn cursor-insert-btn" title="커서 위치에 이 내용을 삽입 (기존 내용 유지)">➕ 커서 삽입</button>
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
  const replaceBtn = card.querySelector('.replace-btn');
  const cursorInsertBtn = card.querySelector('.cursor-insert-btn');

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

  // 🔄 대치: 선택 영역 전체를 AI 결과로 교체. 선택이 없으면 전체 문단 교체.
  //          (HWP 5.0 이든 HWPX 든, 표 셀 안이든, 에디터가 네이티브로 처리)
  replaceBtn.addEventListener('click', async () => {
    replaceBtn.disabled = true;
    const origLabel = replaceBtn.textContent;
    replaceBtn.textContent = '대치 중...';
    try {
      await applyEditToEditor(preview, { mode: 'replace', isTable });
      state.saved = false;
      els.saveBtn.disabled = false;
      document.getElementById('saveAsBtn').disabled = false;
      addBubble('system', `✓ ${preview.selection ? '선택 영역' : `문단 ${preview.paragraph_index}`} 대치 완료`);
      replaceBtn.textContent = '✓ 대치됨';
      await reloadDocument();
    } catch (err) {
      addBubble('error', `대치 실패: ${err.message || err}`);
      replaceBtn.textContent = origLabel;
      replaceBtn.disabled = false;
    }
  });

  // ➕ 커서 삽입: 선택 영역 / 커서 위치에 **추가**. 기존 텍스트는 보존.
  cursorInsertBtn.addEventListener('click', async () => {
    cursorInsertBtn.disabled = true;
    const origLabel = cursorInsertBtn.textContent;
    cursorInsertBtn.textContent = '삽입 중...';
    try {
      await applyEditToEditor(preview, { mode: 'cursor-insert', isTable });
      state.saved = false;
      els.saveBtn.disabled = false;
      document.getElementById('saveAsBtn').disabled = false;
      addBubble('system', '✓ 커서 위치에 삽입 완료');
      cursorInsertBtn.textContent = '✓ 삽입됨';
      await reloadDocument();
    } catch (err) {
      addBubble('error', `삽입 실패: ${err.message || err}`);
      cursorInsertBtn.textContent = origLabel;
      cursorInsertBtn.disabled = false;
    }
  });

  card.querySelector('.cancel-btn').addEventListener('click', () => card.remove());
}

/**
 * 프리뷰 제안을 rhwp 에디터에 반영한다. 항상 에디터 API만 사용 (Python 백엔드 bypass).
 * 에디터는 HWP 5.0 / HWPX / 표 셀 내부를 모두 네이티브로 편집한다.
 *
 * @param {object} preview   AI 제안 페이로드 (selection / paragraph_index / content / table 등)
 * @param {object} opts
 * @param {'replace'|'cursor-insert'} opts.mode
 * @param {boolean} opts.isTable
 */
/**
 * 문서가 열려있지 않은 빈 노트 상태에서 AI로 텍스트만 생성하고
 * 프리뷰 카드로 보여준다. 사용자는 ➕ 커서 삽입 버튼으로 에디터에 넣는다.
 *
 * @param {string} text 사용자 지시 원문
 */
async function runBlankGenerate(text) {
  const provider = currentProvider();
  const thinking = addBubble('ai', `${provider} 생각 중...`);
  const res = await api('/api/ai/preview', {
    provider,
    instruction: text,
    task_type: 'insert',
    attachments: state.attachments || [],
  });
  thinking.remove();
  if (!res.ok) {
    addBubble('error', `AI 호출 실패: ${res.message || ''}`);
    return;
  }
  // 빈 노트 모드는 paragraph/selection 없으므로 커서 삽입만 의미가 있음
  addPreviewCard({
    ...res.data,
    title: 'AI 제안 (빈 노트)',
    blank_mode: true,
  });
}

async function applyEditToEditor(preview, { mode, isTable }) {
  const newText = preview.content || '';

  // 0) 빈 노트 모드: 문서 컨텍스트 없이 에디터 현재 위치에 삽입.
  //    에디터가 파일을 열지 않은 상태라면 먼저 빈 새 문서를 생성해서
  //    applyEdit 이 작동할 기반을 만든다.
  if (preview.blank_mode) {
    // 에디터가 아무 문서도 안 들고 있으면 자동으로 새 문서 생성.
    if (!state.path && !state.structure) {
      try {
        await sendEditorRequest('newDocument');
        state.saved = true;
        state.selection = null;         // 이전 문서의 선택은 버림 (stale 인덱스 방지)
        state.selectedIndex = null;
        els.saveBtn.disabled = false;
      document.getElementById('saveAsBtn').disabled = false;
        if (!els.saveBtn.dataset.outputPath) {
          els.saveBtn.dataset.outputPath = defaultSavePath('새 문서.hwp');
        }
        els.fileName.textContent = '새 문서.hwp';
        addBubble('system', '✓ 빈 새 문서 자동 생성');
      } catch (err) {
        throw new Error(`새 문서 생성 실패: ${err.message || err}`);
      }
    }

    // 에디터의 현재 커서 위치를 실시간으로 조회. 셀 안이면 parentParaIndex,
    // controlIndex, cellIndex, cellParaIndex 같은 셀 컨텍스트를 **반드시**
    // 그대로 넘겨야 에디터가 본문이 아니라 해당 셀 안에 텍스트를 넣는다.
    // getSelection 은 선택이 없을 때 start 를 반환 안 하므로, getCursor 로 보강.
    let liveStart = null;
    try {
      const live = await sendEditorRequest('getSelection');
      liveStart = live?.start || null;
    } catch {
      /* ignore */
    }
    if (!liveStart) {
      try {
        liveStart = await sendEditorRequest('getCursor');
      } catch {
        /* ignore */
      }
    }
    const target = liveStart
      ? {
          sectionIndex: Number(liveStart.sectionIndex ?? 0),
          paragraphIndex: Number(liveStart.paragraphIndex ?? 0),
          charOffset: Number(liveStart.charOffset ?? 0),
        }
      : { sectionIndex: 0, paragraphIndex: 0, charOffset: 0 };

    // 표 결과 → 네이티브 HWP 표 생성 경로 (셀 안/밖 동일하게 동작)
    if (isTable) {
      return sendEditorRequest('applyEditTable', {
        section: target.sectionIndex,
        startPara: target.paragraphIndex,
        endPara: target.paragraphIndex,
        startChar: target.charOffset,
        endChar: target.charOffset,
        table: preview.table,
      });
    }

    // 셀 안이면 start/end 객체를 통째로 전달 → main.ts 의 inCell 분기 사용.
    // 에디터가 내부적으로 \n 를 splitParagraphInCell 로 처리하므로 여러 문단도 OK.
    if (liveStart && liveStart.parentParaIndex !== undefined) {
      const cellEnd = {
        sectionIndex: liveStart.sectionIndex,
        paragraphIndex: liveStart.paragraphIndex,
        charOffset: liveStart.charOffset,
        parentParaIndex: liveStart.parentParaIndex,
        controlIndex: liveStart.controlIndex,
        cellIndex: liveStart.cellIndex,
        cellParaIndex: liveStart.cellParaIndex ?? liveStart.paragraphIndex,
      };
      return sendEditorRequest('applyEdit', {
        section: target.sectionIndex,
        start: liveStart,
        end: cellEnd,
        startPara: target.paragraphIndex,
        endPara: target.paragraphIndex,
        startChar: target.charOffset,
        endChar: target.charOffset,
        newText,
      });
    }

    // 본문 영역: 단순 삽입
    return sendEditorRequest('applyEdit', {
      section: target.sectionIndex,
      startPara: target.paragraphIndex,
      endPara: target.paragraphIndex,
      startChar: target.charOffset,
      endChar: target.charOffset,
      newText,
    });
  }

  // --- 문서가 열린 상태: 항상 에디터의 실시간 커서/선택을 기준으로 결정 ---
  // (state.structure / preview.paragraph_index 같은 서버/캐시 값은 셀 컨텍스트를
  //  잃어버려서 신뢰 불가. 에디터가 유일한 source of truth.)

  let live = null;
  let cursor = null;
  try {
    live = await sendEditorRequest('getSelection');
  } catch {
    /* 선택 조회 실패 시 기본값 */
  }
  try {
    // 선택 영역이 없어도 현재 커서 위치는 알아야 한다 (셀 컨텍스트 포함).
    cursor = await sendEditorRequest('getCursor');
  } catch {
    /* 구 버전 에디터는 getCursor 미지원 — 무시 */
  }

  // 우선순위: 실제 선택 > 커서. 둘 다 없으면 null.
  const liveStart = live?.start || cursor || null;
  const liveEnd = live?.end || liveStart;
  const hasLiveSelection = !!(live?.hasSelection && live?.text);
  const inCell = !!(liveStart && liveStart.parentParaIndex !== undefined);
  const isMultiParagraph = /\r|\n/.test(newText);

  // 테이블 결과: rhwp 의 createTable 은 본문 레벨만 지원 → 중첩 표 생성 불가.
  // 커서가 기존 표 셀 안이면, 기존 표 바로 뒤(본문)에 새 표를 삽입한다.
  if (isTable) {
    if (inCell && liveStart) {
      const afterTableBody = Number(liveStart.parentParaIndex) + 1;
      addBubble('system', 'ℹ 표 안에는 중첩 표를 못 만들어 기존 표 바로 뒤에 삽입했습니다.');
      return sendEditorRequest('applyEditTable', {
        section: Number(liveStart.sectionIndex ?? 0),
        startPara: afterTableBody,
        endPara: afterTableBody,
        startChar: 0,
        endChar: 0,
        table: preview.table,
      });
    }
    const start = liveStart || { sectionIndex: 0, paragraphIndex: 0, charOffset: 0 };
    return sendEditorRequest('applyEditTable', {
      section: Number(start.sectionIndex ?? 0),
      startPara: Number(start.paragraphIndex ?? 0),
      endPara: Number(start.paragraphIndex ?? 0),
      startChar: Number(start.charOffset ?? 0),
      endChar: Number(start.charOffset ?? 0),
      table: preview.table,
    });
  }

  // 셀 안 (단일 or 다중 문단 모두) → inCell 경로 사용.
  // 에디터의 applyEdit 이 newText 에 \n 이 포함되면 splitParagraphInCell 으로
  // 문단을 나눠 셀 구조를 보존한 채 다중 문단 삽입을 처리한다.
  if (inCell) {
    const endPos =
      mode === 'replace' && hasLiveSelection && liveEnd?.parentParaIndex !== undefined
        ? liveEnd
        : liveStart;
    return sendEditorRequest('applyEdit', {
      section: Number(liveStart.sectionIndex ?? 0),
      start: liveStart,
      end: endPos,
      startPara: Number(liveStart.paragraphIndex ?? 0),
      endPara: Number(endPos.paragraphIndex ?? 0),
      startChar: Number(liveStart.charOffset ?? 0),
      endChar: Number(endPos.charOffset ?? 0),
      newText,
    });
  }

  // 본문 (셀 아닌 곳) — 커서 삽입: 선택이 없으면 현재 커서에 삽입
  if (mode === 'cursor-insert' || !hasLiveSelection) {
    const start = liveStart || { sectionIndex: 0, paragraphIndex: 0, charOffset: 0 };
    return sendEditorRequest('applyEdit', {
      section: Number(start.sectionIndex ?? 0),
      startPara: Number(start.paragraphIndex ?? 0),
      endPara: Number(start.paragraphIndex ?? 0),
      startChar: Number(start.charOffset ?? 0),
      endChar: Number(start.charOffset ?? 0),
      newText,
    });
  }

  // 본문 + replace 모드 + 실제 선택 있음 → 선택 범위 교체
  return sendEditorRequest('applyEdit', {
    section: Number(liveStart.sectionIndex ?? 0),
    startPara: Number(liveStart.paragraphIndex ?? 0),
    endPara: Number(liveEnd.paragraphIndex ?? 0),
    startChar: Number(liveStart.charOffset ?? 0),
    endChar: Number(liveEnd.charOffset ?? 0),
    newText,
  });
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
      document.getElementById('saveAsBtn').disabled = false;
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

async function saveDocument({ promptPath = false } = {}) {
  if (!state.documentId && !state.editorReady) return;
  let out = els.saveBtn.dataset.outputPath;
  if (!out) {
    // 기본 경로: 서버에 홈/Downloads 요청 (Mac/Windows/Linux 공통)
    try {
      const res = await api('/api/default-save-dir', {});
      const dir = res?.data?.path || state.defaultSaveDir || '';
      const baseName = state.path
        ? (state.path.split(/[\\/]/).pop() || '새 문서.hwp').replace(
            /\.(hwp|hwpx)$/i,
            '.edited.$1',
          )
        : '새 문서.hwp';
      if (dir) {
        const sep = dir.includes('\\') ? '\\' : '/';
        out = dir.replace(/[\\/]$/, '') + sep + baseName;
      } else {
        out = suggestOutputPath(state.path || '새 문서.hwp');
      }
    } catch {
      out = suggestOutputPath(state.path || '새 문서.hwp');
    }
  }
  if (promptPath) {
    const picked = await pickSavePath(out);
    if (!picked) {
      addBubble('system', '저장 취소됨.');
      return;
    }
    out = picked;
  }
  els.saveBtn.dataset.outputPath = out;
  addBubble('system', `💾 저장 중: ${out}`);

  // 에디터가 편집 소스이므로, 현재 바이트를 에디터에서 받아온다.
  // (Python 측 document 세션은 읽기 전용으로 취급.)
  let payload = { document_id: state.documentId, path: out };
  if (state.editorReady) {
    try {
      const exported = await sendEditorRequest('exportBytes');
      if (exported?.base64) {
        payload = { ...payload, base64: exported.base64 };
      }
    } catch (err) {
      addBubble('system', `ℹ 에디터 bytes 가져오기 실패, 원본 그대로 저장: ${err.message || err}`);
    }
  }

  const res = await api('/api/save', payload);
  if (res.ok) {
    state.saved = true;
    const size = res.data?.size || res.data?.bytes_len || '?';
    addBubble('system', `✓ 저장 완료: ${res.data?.saved_path || out} (${size} bytes)`);
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
  }

  const hasRealSelection = !!(state.selection?.hasSelection && state.selection.text && state.selection.text.trim());

  // 선택/타겟이 없으면 **순수 생성 모드** 로 바로 진입.
  // (과거엔 need_index/need_selection 로 거부했지만, 사용자는 선택 없이도
  // AI 초안을 받고 싶어할 수 있다. 생성된 내용은 프리뷰 카드 → 커서 삽입/대치 버튼으로 반영.)
  if (paragraphIndex == null && !hasRealSelection) {
    return { type: 'ai_generate', instruction: t };
  }

  if (/뒤에|다음에|이후에|추가|삽입|insert/.test(t)) {
    if (hasRealSelection) return { type: 'ai_selection_insert', paragraphIndex, instruction: t };
    return { type: 'ai_insert', paragraphIndex, instruction: t };
  }
  if (/요약|summar/i.test(t)) {
    if (hasRealSelection) return { type: 'ai_selection_summarize', paragraphIndex, instruction: t };
    return { type: 'ai_summarize', paragraphIndex, instruction: t };
  }
  if (hasRealSelection) return { type: 'ai_selection_rewrite', paragraphIndex, instruction: t };
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

  // 순수 생성 모드: 선택도 문단 타겟도 없음.
  //   - 문서가 안 열려있으면 → 빈 노트 모드 (자동 새 문서)
  //   - 문서가 열려있으면 → 에디터 현재 커서 위치 기준 삽입
  if (intent.type === 'ai_generate') {
    await runBlankGenerate(text);
    return;
  }
  if (!state.documentId && intent.type === 'save') {
    addBubble('ai', '먼저 편집한 내용이 있어야 저장할 수 있습니다.');
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
  const attachments = state.attachments || [];
  const payload = selectionMode
    ? {
        provider,
        document_id: state.documentId,
        selection: state.selection,
        task_type: taskType,
        instruction: intent.instruction,
        attachments,
      }
    : {
        provider,
        document_id: state.documentId,
        paragraph_index: intent.paragraphIndex,
        task_type: taskType,
        instruction: intent.instruction,
        attachments,
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
  await browseTo(path || defaultBrowseStart());
}
function closeModal() { els.modal.classList.add('hidden'); }

async function browseTo(path) {
  // In attachment mode, show all file types (images, PDFs, etc.)
  const allFiles = state.fileModalMode === 'pick-for-attachment';
  const res = await api('/api/browse', { path, all_files: allFiles });
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
      } else if (state.fileModalMode === 'pick-for-template') {
        handleFilePickedForTemplate(entry.path);
      } else if (state.fileModalMode === 'pick-for-attachment') {
        handleFilePickedForAttachment(entry.path);
      } else {
        closeModal();
        openDocumentByPath(entry.path);
      }
    });
    els.fileList.appendChild(row);
  }
}

// ---------- OS-agnostic default paths (cached from server) -----------------
state.defaultSaveDir = '';
state.homeDir = '';
(async () => {
  try {
    const res = await api('/api/default-save-dir', {});
    if (res?.ok) {
      state.defaultSaveDir = res.data.path || '';
      state.homeDir = res.data.home || '';
    }
  } catch { /* ignore — keep empty defaults */ }
})();

function defaultBrowseStart() {
  return state.homeDir || state.defaultSaveDir || '';
}

function defaultSavePath(filename = '새 문서.hwp') {
  const dir = state.defaultSaveDir || state.homeDir || '';
  if (!dir) return filename; // 최후 수단
  const sep = dir.includes('\\') ? '\\' : '/';
  return dir.replace(/[\\/]$/, '') + sep + filename;
}

els.openBtn.addEventListener('click', () => openModal(els.pathInput.value || defaultBrowseStart()));

// ---------- Attachments (multimodal / file references for CLI providers) ----
state.attachments = [];

function renderAttachmentChips() {
  const bar = document.getElementById('attachmentsBar');
  if (!bar) return;
  bar.innerHTML = '';
  if (!state.attachments.length) {
    bar.classList.add('hidden');
    return;
  }
  bar.classList.remove('hidden');
  state.attachments.forEach((p, idx) => {
    const name = p.split('/').pop() || p;
    const chip = document.createElement('span');
    chip.className = 'attach-chip';
    const isImage = /\.(png|jpe?g|gif|webp|bmp)$/i.test(name);
    chip.innerHTML = `
      <span>${isImage ? '🖼' : '📄'}</span>
      <span class="chip-name" title="${escapeHtml(p)}">${escapeHtml(name)}</span>
      <button class="chip-remove" data-idx="${idx}" title="제거">✕</button>
    `;
    chip.querySelector('.chip-remove').addEventListener('click', () => {
      state.attachments.splice(idx, 1);
      renderAttachmentChips();
    });
    bar.appendChild(chip);
  });
}

async function pickAttachment() {
  state.fileModalMode = 'pick-for-attachment';
  await openModal(els.pathInput.value || defaultBrowseStart());
}

function handleFilePickedForAttachment(path) {
  state.fileModalMode = null;
  closeModal();
  if (!state.attachments.includes(path)) {
    state.attachments.push(path);
    renderAttachmentChips();
    addBubble('system', `📎 첨부됨: ${path.split('/').pop()}`);
  }
}

document.getElementById('attachBtn')?.addEventListener('click', pickAttachment);

async function createNewDocument() {
  if (!state.editorReady) {
    addBubble('error', '에디터가 아직 준비되지 않았습니다. 잠시 후 다시 시도하세요.');
    return false;
  }
  try {
    await sendEditorRequest('newDocument');
    state.documentId = null;
    state.path = '';
    state.selection = null;
    state.selectedIndex = null;
    state.structure = null;
    state.saved = true;
    state.lastQuotedSelectionKey = null;
    els.fileName.textContent = '새 문서.hwp';
    els.saveBtn.disabled = false;
      document.getElementById('saveAsBtn').disabled = false;
    els.saveBtn.dataset.outputPath = defaultSavePath('새 문서.hwp');
    updateSelInfo();
    addBubble('system', '✓ 빈 새 문서를 열었습니다. AI로 내용을 작성해 보세요.');
    return true;
  } catch (err) {
    addBubble('error', `새 문서 생성 실패: ${err.message || err}`);
    return false;
  }
}

document.getElementById('newDocBtn')?.addEventListener('click', createNewDocument);

// ---------- Template library -----------------------------------------------

const templatesModal = document.getElementById('templatesModal');
const templatesBtn = document.getElementById('templatesBtn');
const templatesClose = document.getElementById('templatesClose');
const templatesList = document.getElementById('templatesList');
const templateSaveCurrentBtn = document.getElementById('templateSaveCurrentBtn');

async function fetchTemplates() {
  try {
    const res = await api('/api/templates/list', {});
    return res.ok ? (res.data.templates || []) : [];
  } catch {
    return [];
  }
}

function formatTemplateDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}

async function renderTemplates() {
  templatesList.innerHTML = '<div class="templates-empty">불러오는 중…</div>';
  const templates = await fetchTemplates();
  if (!templates.length) {
    templatesList.innerHTML = '<div class="templates-empty">저장된 템플릿이 없습니다.<br>현재 문서를 편집한 뒤 위 버튼으로 저장해 보세요.</div>';
    return;
  }
  templatesList.innerHTML = '';
  for (const t of templates) {
    const row = document.createElement('div');
    row.className = 'template-item';
    const extHint = (t.original_filename || t.path || '').toLowerCase().endsWith('.hwpx') ? 'HWPX' : 'HWP';
    row.innerHTML = `
      <div class="icon">📋</div>
      <div class="meta">
        <div class="tname">${escapeHtml(t.name)}</div>
        ${t.description ? `<div class="tdesc">${escapeHtml(t.description)}</div>` : ''}
        <div class="tmeta">${formatTemplateDate(t.created_at)} · ${extHint}${t.original_filename ? ' · ' + escapeHtml(t.original_filename) : ''}</div>
      </div>
      <div class="tactions">
        <button class="chip-btn load-t" title="이 템플릿 불러오기">📂 불러오기</button>
        <button class="chip-btn delete-t" title="삭제">🗑</button>
      </div>
    `;
    row.querySelector('.load-t').addEventListener('click', async () => {
      templatesModal.classList.add('hidden');
      await openDocumentByPath(t.path);
    });
    row.querySelector('.delete-t').addEventListener('click', async (ev) => {
      ev.stopPropagation();
      if (!window.confirm(`'${t.name}' 템플릿을 삭제할까요?`)) return;
      const res = await api('/api/templates/delete', { id: t.id });
      if (res.ok) {
        row.remove();
        if (!templatesList.children.length) renderTemplates();
      } else {
        addBubble('error', `템플릿 삭제 실패: ${res.message || ''}`);
      }
    });
    templatesList.appendChild(row);
  }
}

async function saveCurrentAsTemplate() {
  if (!state.editorReady) {
    addBubble('error', '에디터가 준비되지 않았습니다.');
    return;
  }
  const name = window.prompt('템플릿 이름을 입력하세요:', state.path ? state.path.split('/').pop().replace(/\.(hwp|hwpx)$/i, '') : '새 템플릿');
  if (!name) return;
  const description = window.prompt('간단한 설명 (선택):', '') || '';
  let base64 = '';
  try {
    const exported = await sendEditorRequest('exportBytes');
    base64 = exported?.base64 || '';
  } catch (err) {
    addBubble('error', `바이트 내보내기 실패: ${err.message || err}`);
    return;
  }
  if (!base64) {
    addBubble('error', '에디터에서 문서를 가져올 수 없습니다.');
    return;
  }
  const res = await api('/api/templates/save', {
    name,
    description,
    base64,
    original_filename: state.path ? state.path.split('/').pop() : '',
  });
  if (res.ok) {
    addBubble('system', `✓ 템플릿 저장 완료: ${name}`);
    await renderTemplates();
  } else {
    addBubble('error', `템플릿 저장 실패: ${res.message || ''}`);
  }
}

/**
 * 디스크에 있는 기존 HWP/HWPX 파일을 선택해 바로 템플릿으로 저장한다.
 * 파일 브라우저 모달을 재활용하되, 파일을 클릭하면 "열기" 대신 "템플릿 저장"이
 * 동작하도록 state.fileModalMode를 임시로 바꾼다.
 */
async function saveFromFileAsTemplate() {
  // 템플릿 모달은 잠시 숨기고 파일 브라우저로 이동
  templatesModal.classList.add('hidden');
  state.fileModalMode = 'pick-for-template';
  await openModal(els.pathInput.value || defaultBrowseStart());
}

async function handleFilePickedForTemplate(path) {
  state.fileModalMode = null;
  closeModal();
  const filename = path.split('/').pop() || path;
  const defaultName = filename.replace(/\.(hwp|hwpx)$/i, '');
  const name = window.prompt('템플릿 이름을 입력하세요:', defaultName);
  if (!name) {
    templatesModal.classList.remove('hidden');
    return;
  }
  const description = window.prompt('간단한 설명 (선택):', '') || '';
  const res = await api('/api/templates/save', {
    name,
    description,
    source_path: path,
    original_filename: filename,
  });
  if (res.ok) {
    addBubble('system', `✓ 템플릿 저장 완료: ${name} (${filename})`);
  } else {
    addBubble('error', `템플릿 저장 실패: ${res.message || ''}`);
  }
  templatesModal.classList.remove('hidden');
  await renderTemplates();
}

if (templatesBtn && templatesModal && templatesClose) {
  const openTemplates = async () => {
    templatesModal.classList.remove('hidden');
    templateSaveCurrentBtn.disabled = !state.editorReady;
    await renderTemplates();
  };
  const closeTemplates = () => templatesModal.classList.add('hidden');
  templatesBtn.addEventListener('click', openTemplates);
  templatesClose.addEventListener('click', closeTemplates);
  templatesModal.addEventListener('click', (e) => { if (e.target === templatesModal) closeTemplates(); });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !templatesModal.classList.contains('hidden')) closeTemplates();
  });
  templateSaveCurrentBtn?.addEventListener('click', saveCurrentAsTemplate);
  document.getElementById('templateSaveFromFileBtn')?.addEventListener('click', saveFromFileAsTemplate);
}
els.modalClose.addEventListener('click', closeModal);
els.modal.addEventListener('click', (e) => { if (e.target === els.modal) closeModal(); });
els.saveBtn.addEventListener('click', () => saveDocument());
document.getElementById('saveAsBtn')?.addEventListener('click', () => saveDocument({ promptPath: true }));

// ---------- Save-as picker modal -------------------------------------------

const saveAsModal = document.getElementById('saveAsModal');
const saveAsClose = document.getElementById('saveAsClose');
const saveAsPathInput = document.getElementById('saveAsPathInput');
const saveAsUpBtn = document.getElementById('saveAsUpBtn');
const saveAsGoBtn = document.getElementById('saveAsGoBtn');
const saveAsFolderList = document.getElementById('saveAsFolderList');
const saveAsFilename = document.getElementById('saveAsFilename');
const saveAsConfirmBtn = document.getElementById('saveAsConfirmBtn');

/** 저장 경로 선택 모달 — 폴더 클릭으로 이동, 파일명 입력 → 최종 full path 반환. */
async function pickSavePath(defaultPath) {
  return new Promise((resolve) => {
    const lastSlash = defaultPath.lastIndexOf('/');
    const initialDir = lastSlash >= 0 ? defaultPath.slice(0, lastSlash) : defaultPath;
    const initialName = lastSlash >= 0 ? defaultPath.slice(lastSlash + 1) : defaultPath;
    saveAsFilename.value = initialName;

    let currentDir = initialDir;

    async function browse(dir) {
      currentDir = dir;
      saveAsPathInput.value = dir;
      saveAsFolderList.innerHTML = '<div class="file-row"><span class="name">로딩 중…</span></div>';
      const res = await api('/api/browse', { path: dir });
      if (!res.ok) {
        saveAsFolderList.innerHTML = `<div class="file-row"><span class="ic">⚠</span><span class="name">${escapeHtml(res.message || '')}</span></div>`;
        return;
      }
      const { current_path, parent_path, entries } = res.data;
      currentDir = current_path;
      saveAsPathInput.value = current_path;
      saveAsFolderList.innerHTML = '';
      if (parent_path && parent_path !== current_path) {
        const up = document.createElement('div');
        up.className = 'file-row';
        up.innerHTML = `<span class="ic">⬆</span><span class="name">상위 폴더</span>`;
        up.addEventListener('click', () => browse(parent_path));
        saveAsFolderList.appendChild(up);
      }
      // 폴더만 표시 (파일은 숨김, 사용자는 파일명 input으로 타이핑)
      for (const entry of entries) {
        if (entry.type !== 'dir') continue;
        const row = document.createElement('div');
        row.className = 'file-row';
        row.innerHTML = `<span class="ic">📁</span><span class="name">${escapeHtml(entry.name)}</span>`;
        row.addEventListener('click', () => browse(entry.path));
        saveAsFolderList.appendChild(row);
      }
      if (!entries.some((e) => e.type === 'dir')) {
        const empty = document.createElement('div');
        empty.className = 'file-row';
        empty.innerHTML = `<span class="name" style="color:var(--text-subtle);font-style:italic">이 폴더에는 하위 폴더가 없습니다. 여기에 저장하려면 파일명을 입력하고 '저장'을 누르세요.</span>`;
        saveAsFolderList.appendChild(empty);
      }
    }

    function finish(fullPath) {
      cleanup();
      resolve(fullPath);
    }

    function cleanup() {
      saveAsModal.classList.add('hidden');
      saveAsClose.removeEventListener('click', onCancel);
      saveAsModal.removeEventListener('click', onBackdrop);
      saveAsUpBtn.removeEventListener('click', onUp);
      saveAsGoBtn.removeEventListener('click', onGo);
      saveAsConfirmBtn.removeEventListener('click', onConfirm);
      saveAsPathInput.removeEventListener('keydown', onPathKey);
      saveAsFilename.removeEventListener('keydown', onNameKey);
    }
    function onCancel() { finish(null); }
    function onBackdrop(e) { if (e.target === saveAsModal) finish(null); }
    function onUp() {
      // OS-agnostic: split on either separator, drop last segment, rejoin
      // using the separator present in the original path. Windows C:\… works.
      const isWindows = currentDir.includes('\\') && currentDir.match(/^[A-Za-z]:/);
      const parts = currentDir.split(/[\\/]/).filter(Boolean);
      parts.pop();
      if (isWindows && parts.length) {
        browse(parts.join('\\'));
      } else {
        browse('/' + parts.join('/'));
      }
    }
    function onGo() { browse(saveAsPathInput.value); }
    function onPathKey(e) { if (e.key === 'Enter') { e.preventDefault(); onGo(); } }
    function onNameKey(e) { if (e.key === 'Enter') { e.preventDefault(); onConfirm(); } }
    function onConfirm() {
      const name = saveAsFilename.value.trim();
      if (!name) return;
      const sep = currentDir.includes('\\') && /^[A-Za-z]:/.test(currentDir) ? '\\' : '/';
      const full = currentDir.replace(/[\\/]$/, '') + sep + name;
      finish(full);
    }

    saveAsClose.addEventListener('click', onCancel);
    saveAsModal.addEventListener('click', onBackdrop);
    saveAsUpBtn.addEventListener('click', onUp);
    saveAsGoBtn.addEventListener('click', onGo);
    saveAsConfirmBtn.addEventListener('click', onConfirm);
    saveAsPathInput.addEventListener('keydown', onPathKey);
    saveAsFilename.addEventListener('keydown', onNameKey);

    saveAsModal.classList.remove('hidden');
    browse(initialDir);
    setTimeout(() => saveAsFilename.focus(), 100);
  });
}

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
  const raw = els.pathInput.value;
  const isWindows = raw.includes('\\') && /^[A-Za-z]:/.test(raw);
  const parts = raw.split(/[\\/]/).filter(Boolean);
  parts.pop();
  if (isWindows && parts.length) {
    browseTo(parts.join('\\'));
  } else {
    browseTo('/' + parts.join('/'));
  }
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
