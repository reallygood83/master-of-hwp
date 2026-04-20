import { WasmBridge } from '@/core/wasm-bridge';
import type { DocumentInfo } from '@/core/types';
import { EventBus } from '@/core/event-bus';
import { CanvasView } from '@/view/canvas-view';
import { InputHandler } from '@/engine/input-handler';
import { Toolbar } from '@/ui/toolbar';
import { MenuBar } from '@/ui/menu-bar';
import { loadWebFonts } from '@/core/font-loader';
import { CommandRegistry } from '@/command/registry';
import { CommandDispatcher } from '@/command/dispatcher';
import type { EditorContext, CommandServices } from '@/command/types';
import { fileCommands } from '@/command/commands/file';
import { editCommands } from '@/command/commands/edit';
import { viewCommands } from '@/command/commands/view';
import { formatCommands } from '@/command/commands/format';
import { insertCommands } from '@/command/commands/insert';
import { tableCommands } from '@/command/commands/table';
import { pageCommands } from '@/command/commands/page';
import { toolCommands } from '@/command/commands/tool';
import { ContextMenu } from '@/ui/context-menu';
import { CommandPalette } from '@/ui/command-palette';
import { CellSelectionRenderer } from '@/engine/cell-selection-renderer';
import { TableObjectRenderer } from '@/engine/table-object-renderer';
import { TableResizeRenderer } from '@/engine/table-resize-renderer';
import { Ruler } from '@/view/ruler';

const wasm = new WasmBridge();
const eventBus = new EventBus();

if (import.meta.env.DEV) {
  (window as any).__wasm = wasm;
  (window as any).__eventBus = eventBus;
}
let canvasView: CanvasView | null = null;
let inputHandler: InputHandler | null = null;
let toolbar: Toolbar | null = null;
let ruler: Ruler | null = null;

const registry = new CommandRegistry();

function getContext(): EditorContext {
  return {
    hasDocument: wasm.pageCount > 0,
    hasSelection: inputHandler?.hasSelection() ?? false,
    inTable: inputHandler?.isInTable() ?? false,
    inCellSelectionMode: inputHandler?.isInCellSelectionMode() ?? false,
    inTableObjectSelection: inputHandler?.isInTableObjectSelection() ?? false,
    inPictureObjectSelection: inputHandler?.isInPictureObjectSelection() ?? false,
    inField: inputHandler?.isInField() ?? false,
    isEditable: true,
    canUndo: inputHandler?.canUndo() ?? false,
    canRedo: inputHandler?.canRedo() ?? false,
    zoom: canvasView?.getViewportManager().getZoom() ?? 1.0,
    showControlCodes: wasm.getShowControlCodes(),
  };
}

const commandServices: CommandServices = {
  eventBus,
  wasm,
  getContext,
  getInputHandler: () => inputHandler,
  getViewportManager: () => canvasView?.getViewportManager() ?? null,
};

const dispatcher = new CommandDispatcher(registry, commandServices, eventBus);
registry.registerAll(fileCommands);
registry.registerAll(editCommands);
registry.registerAll(viewCommands);
registry.registerAll(formatCommands);
registry.registerAll(insertCommands);
registry.registerAll(tableCommands);
registry.registerAll(pageCommands);
registry.registerAll(toolCommands);

const sbMessage = () => document.getElementById('sb-message')!;
const sbPage = () => document.getElementById('sb-page')!;
const sbSection = () => document.getElementById('sb-section')!;
const sbZoomVal = () => document.getElementById('sb-zoom-val')!;

async function initialize(): Promise<void> {
  const msg = sbMessage();
  try {
    msg.textContent = '웹폰트 로딩 중...';
    await loadWebFonts([]);
    msg.textContent = 'WASM 로딩 중...';
    await wasm.initialize();
    msg.textContent = 'HWP 파일을 선택해주세요.';

    const container = document.getElementById('scroll-container')!;
    canvasView = new CanvasView(container, wasm, eventBus);

    ruler = new Ruler(
      document.getElementById('h-ruler') as HTMLCanvasElement,
      document.getElementById('v-ruler') as HTMLCanvasElement,
      container,
      eventBus,
      wasm,
      canvasView.getVirtualScroll(),
      canvasView.getViewportManager(),
    );

    inputHandler = new InputHandler(
      container, wasm, eventBus,
      canvasView.getVirtualScroll(),
      canvasView.getViewportManager(),
    );

    toolbar = new Toolbar(document.getElementById('style-bar')!, wasm, eventBus, dispatcher);
    toolbar.setEnabled(false);

    // 메뉴바(파일/편집/보기/입력/서식/쪽/표/도구) 드롭다운 활성화
    const menuBarEl = document.getElementById('menu-bar');
    if (menuBarEl) new MenuBar(menuBarEl, eventBus, dispatcher);

    // 아이콘 툴바(오려두기/복사하기/붙이기 등)의 data-cmd 버튼을 디스패처에 연결
    const iconToolbarEl = document.getElementById('icon-toolbar');
    iconToolbarEl?.addEventListener('click', (e) => {
      const btn = (e.target as HTMLElement).closest('[data-cmd]') as HTMLElement | null;
      if (!btn || btn.classList.contains('disabled')) return;
      const cmd = btn.dataset.cmd;
      if (cmd) dispatcher.dispatch(cmd, { anchorEl: btn });
    });

    // 파일 열기 숨김 input 연결 (메뉴 '파일 > 열기' → #file-input.click() → 여기서 처리)
    const fileInput = document.getElementById('file-input') as HTMLInputElement | null;
    fileInput?.addEventListener('change', async () => {
      const f = fileInput.files?.[0];
      if (!f) return;
      try {
        const buf = await f.arrayBuffer();
        const docInfo = wasm.loadDocument(new Uint8Array(buf), f.name);
        await initializeDocument(docInfo, `${f.name} — ${docInfo.pageCount}페이지`);
      } catch (err: any) {
        sbMessage().textContent = `파일 열기 실패: ${err?.message ?? err}`;
        console.error('[file:open]', err);
      } finally {
        fileInput.value = '';
      }
    });

    inputHandler.setDispatcher(dispatcher);
    inputHandler.setContextMenu(new ContextMenu(dispatcher, registry));
    inputHandler.setCommandPalette(new CommandPalette(registry, dispatcher));
    inputHandler.setCellSelectionRenderer(new CellSelectionRenderer(container, canvasView.getViewportManager()));
    inputHandler.setTableObjectRenderer(new TableObjectRenderer(container, canvasView.getViewportManager()));
    inputHandler.setTableResizeRenderer(new TableResizeRenderer(container, canvasView.getVirtualScroll()));
    inputHandler.setPictureObjectRenderer(null as any);

    eventBus.on('document-changed', () => updateStatusBar());
    eventBus.on('current-page-changed', (page: any) => {
      if (typeof page === 'number') currentPageNum = page;
      else if (page && typeof page.page === 'number') currentPageNum = page.page;
      updateStatusBar();
    });
    eventBus.on('selection-changed', () => emitSelectionChanged());
    eventBus.on('cursor-moved', () => emitSelectionChanged());

    updateStatusBar();
  } catch (err: any) {
    msg.textContent = `초기화 실패: ${err.message || String(err)}`;
    console.error(err);
  }
}

let currentPageNum = 0;
function updateStatusBar(): void {
  const pc = Math.max(1, wasm.pageCount);
  sbPage().textContent = `${Math.min(pc, currentPageNum + 1)}/${pc}`;
  sbSection().textContent = `섹션 ${(wasm as any).currentSection !== undefined ? ((wasm as any).currentSection + 1) : 1}`;
  sbZoomVal().textContent = `${Math.round((canvasView?.getViewportManager().getZoom() ?? 1) * 100)}%`;
}

function getSelectionPayload(): { hasSelection: boolean; start?: any; end?: any; text?: string } {
  if (!inputHandler) {
    console.log('[getSelectionPayload] no inputHandler');
    return { hasSelection: false };
  }
  const cursor = (inputHandler as any).cursor;
  const inCellMode = cursor?.isInCellSelectionMode?.() ?? false;

  // Cell selection mode (F5 또는 셀 경계 가로지르는 드래그):
  // getSelectionOrdered()가 null이므로 별도 처리가 필요하다.
  if (inCellMode && cursor) {
    try {
      const range = cursor.getSelectedCellRange?.();
      const ctx = cursor.getCellTableContext?.();
      if (range && ctx) {
        const excluded: Set<string> = cursor.getExcludedCells?.() ?? new Set();
        const bboxes = wasm.getTableCellBboxes(ctx.sec, ctx.ppi, ctx.ci);
        // 범위 내 셀 bbox만 수집 (row,col 교차)
        const picked = bboxes.filter((b: any) => {
          if (excluded.has(`${b.row},${b.col}`)) return false;
          const rOk = b.row + b.rowSpan > range.startRow && b.row <= range.endRow;
          const cOk = b.col + b.colSpan > range.startCol && b.col <= range.endCol;
          return rOk && cOk;
        });
        if (picked.length === 0) {
          console.log('[getSelectionPayload] cell-mode: no cells picked');
          return { hasSelection: false };
        }
        picked.sort((a: any, b: any) => (a.row - b.row) || (a.col - b.col));
        const parts: string[] = [];
        for (const cell of picked) {
          try {
            const paraCount = wasm.getCellParagraphCount(ctx.sec, ctx.ppi, ctx.ci, cell.cellIdx);
            for (let p = 0; p < paraCount; p++) {
              const len = wasm.getCellParagraphLength(ctx.sec, ctx.ppi, ctx.ci, cell.cellIdx, p);
              if (len > 0) {
                parts.push(wasm.getTextInCell(ctx.sec, ctx.ppi, ctx.ci, cell.cellIdx, p, 0, len));
              }
            }
          } catch (err) {
            console.warn('[getSelectionPayload] cell read failed', cell, err);
          }
        }
        const text = parts.filter(Boolean).join('\n');
        if (!text) return { hasSelection: false };
        const first = picked[0];
        const last = picked[picked.length - 1];
        const startPos = {
          sectionIndex: ctx.sec,
          paragraphIndex: ctx.ppi,
          charOffset: 0,
          parentParaIndex: ctx.ppi,
          controlIndex: ctx.ci,
          cellIndex: first.cellIdx,
          cellParaIndex: 0,
        };
        const endPos = {
          sectionIndex: ctx.sec,
          paragraphIndex: ctx.ppi,
          charOffset: 0,
          parentParaIndex: ctx.ppi,
          controlIndex: ctx.ci,
          cellIndex: last.cellIdx,
          cellParaIndex: 0,
        };
        console.log('[getSelectionPayload] cell-mode payload text=', text.slice(0, 60));
        return { hasSelection: true, start: startPos, end: endPos, text };
      }
    } catch (err) {
      console.warn('[getSelectionPayload] cell-mode failed', err);
    }
  }

  const sel = inputHandler.getSelection();
  console.log('[getSelectionPayload] sel=', sel, 'cellSelectionMode=', inCellMode);
  if (!sel) return { hasSelection: false };
  const { start, end } = sel;
  if (start.sectionIndex !== end.sectionIndex) {
    console.log('[getSelectionPayload] different sections', start.sectionIndex, end.sectionIndex);
    return { hasSelection: false };
  }
  const sec = start.sectionIndex;

  // Selection lives inside a table cell — read text via getTextInCell instead of
  // the top-level getTextRange, which would otherwise return text from the wrong
  // paragraph (the table's container paragraph at the document root).
  const bothInCell = start.parentParaIndex !== undefined && end.parentParaIndex !== undefined;
  const sameCell = bothInCell
    && start.parentParaIndex === end.parentParaIndex
    && start.controlIndex === end.controlIndex
    && start.cellIndex === end.cellIndex;
  if (sameCell) {
    const ppi = start.parentParaIndex as number;
    const ci = start.controlIndex as number;
    const cellIdx = start.cellIndex as number;
    const sp = start.cellParaIndex ?? 0;
    const ep = end.cellParaIndex ?? sp;
    const readCellPara = (p: number, from: number, to: number): string => {
      try {
        const len = wasm.getCellParagraphLength(sec, ppi, ci, cellIdx, p);
        const f = Math.min(Math.max(0, from), len);
        const t = Math.min(Math.max(f, to), len);
        const count = t - f;
        if (count <= 0) return '';
        return wasm.getTextInCell(sec, ppi, ci, cellIdx, p, f, count);
      } catch (err) {
        console.warn('[getSelectionPayload] readCellPara failed', p, err);
        return '';
      }
    };
    if (sp === ep) {
      const count = end.charOffset - start.charOffset;
      if (count <= 0) return { hasSelection: false };
      const text = readCellPara(sp, start.charOffset, end.charOffset);
      if (!text) return { hasSelection: false };
      return { hasSelection: true, start, end, text };
    }
    if (ep < sp) return { hasSelection: false };
    const parts: string[] = [];
    parts.push(readCellPara(sp, start.charOffset, Number.MAX_SAFE_INTEGER));
    for (let p = sp + 1; p < ep; p++) {
      parts.push(readCellPara(p, 0, Number.MAX_SAFE_INTEGER));
    }
    parts.push(readCellPara(ep, 0, end.charOffset));
    const text = parts.join('\n');
    if (!text) return { hasSelection: false };
    return { hasSelection: true, start, end, text };
  }

  const sp = start.paragraphIndex;
  const ep = end.paragraphIndex;
  if (sp === ep) {
    const count = end.charOffset - start.charOffset;
    if (count <= 0) return { hasSelection: false };
    const text = wasm.getTextRange(sec, sp, start.charOffset, count);
    return { hasSelection: true, start, end, text };
  }
  if (ep < sp) return { hasSelection: false };
  const parts: string[] = [];
  const readPara = (p: number, from: number, to: number): string => {
    try {
      const len = wasm.getParagraphLength(sec, p);
      const f = Math.min(Math.max(0, from), len);
      const t = Math.min(Math.max(f, to), len);
      const count = t - f;
      if (count <= 0) return '';
      return wasm.getTextRange(sec, p, f, count);
    } catch (err) {
      console.warn('[getSelectionPayload] readPara failed', p, err);
      return '';
    }
  };
  parts.push(readPara(sp, start.charOffset, Number.MAX_SAFE_INTEGER));
  for (let p = sp + 1; p < ep; p++) {
    parts.push(readPara(p, 0, Number.MAX_SAFE_INTEGER));
  }
  parts.push(readPara(ep, 0, end.charOffset));
  const text = parts.join('\n');
  if (!text) return { hasSelection: false };
  return { hasSelection: true, start, end, text };
}

function emitSelectionChanged(): void {
  const payload = getSelectionPayload();
  window.parent?.postMessage({ type: 'rhwp-selection', payload }, '*');
}

async function initializeDocument(docInfo: DocumentInfo, title: string): Promise<void> {
  document.title = title;
  canvasView?.loadDocument();
  toolbar?.setEnabled(true);
  eventBus.emit('document-changed');
  updateStatusBar();
  emitSelectionChanged();
  sbMessage().textContent = title;
}

async function loadFromUrlParam() {
  const msg = sbMessage();
  const params = new URLSearchParams(location.search);
  const fileUrl = params.get('file');
  const fileName = params.get('name') || 'document.hwp';
  if (!fileUrl) return;
  try {
    let response;
    if (/^https?:/.test(fileUrl)) {
      response = await fetch(fileUrl, { mode: 'cors' });
    } else {
      response = await fetch(fileUrl);
    }
    if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    const buffer = await response.arrayBuffer();
    const data = new Uint8Array(buffer);
    const docInfo = wasm.loadDocument(data, fileName);
    await initializeDocument(docInfo, `${fileName} — ${docInfo.pageCount}페이지`);
  } catch (error) {
    const errMsg = `파일 로드 실패: ${error}`;
    msg.textContent = errMsg;
    console.error('[loadFromUrlParam]', error);
  }
}

initialize();

window.addEventListener('message', async (e) => {
  const msg = e.data;
  if (!msg || typeof msg !== 'object') return;

  if (msg.type === 'hwpctl-load' && msg.data) {
    try {
      const bytes = new Uint8Array(msg.data);
      const docInfo = wasm.loadDocument(bytes, msg.fileName || 'document.hwp');
      await initializeDocument(docInfo, `${msg.fileName || 'document'} — ${docInfo.pageCount}페이지`);
      e.source?.postMessage({ type: 'rhwp-response', id: msg.id, result: { pageCount: docInfo.pageCount } }, { targetOrigin: '*' });
    } catch (err: any) {
      e.source?.postMessage({ type: 'rhwp-response', id: msg.id, error: err.message || String(err) }, { targetOrigin: '*' });
    }
    return;
  }

  if (msg.type !== 'rhwp-request' || !msg.method) return;
  const { id, method, params } = msg;
  const reply = (result?: any, error?: string) => {
    e.source?.postMessage({ type: 'rhwp-response', id, result, error }, { targetOrigin: '*' });
  };

  try {
    switch (method) {
      case 'loadFile': {
        const bytes = new Uint8Array(params.data);
        const docInfo = wasm.loadDocument(bytes, params.fileName || 'document.hwp');
        await initializeDocument(docInfo, `${params.fileName || 'document'} — ${docInfo.pageCount}페이지`);
        reply({ pageCount: docInfo.pageCount });
        break;
      }
      case 'pageCount':
        reply(wasm.pageCount);
        break;
      case 'getPageSvg':
        reply(wasm.renderPageSvg(params.page ?? 0));
        break;
      case 'ready':
        reply(true);
        break;
      case 'getSelection':
        reply(getSelectionPayload());
        break;
      case 'setSelection': {
        if (!inputHandler) {
          reply(undefined, 'inputHandler not ready');
          break;
        }
        const sec = Number(params.section ?? params.sectionIndex ?? 0);
        const startPara = Number(params.startPara ?? params.paragraph ?? params.paragraphIndex ?? 0);
        const endPara = Number(params.endPara ?? startPara);
        const startChar = Number(params.startChar ?? params.charOffset ?? 0);
        const endChar = Number(params.endChar ?? startChar);
        const anchorPos = { sectionIndex: sec, paragraphIndex: startPara, charOffset: startChar };
        const focusPos = { sectionIndex: sec, paragraphIndex: endPara, charOffset: endChar };
        const ok = inputHandler.moveCursorTo(anchorPos);
        if (!ok) {
          reply(undefined, 'invalid anchor position');
          break;
        }
        const cursor = (inputHandler as any).cursor;
        if (cursor && typeof cursor.setAnchor === 'function' && typeof cursor.moveTo === 'function') {
          cursor.setAnchor();
          cursor.moveTo(focusPos);
        }
        eventBus.emit('selection-changed');
        const payload = getSelectionPayload();
        reply(payload);
        break;
      }
      case 'applyEdit': {
        if (!inputHandler) {
          reply(undefined, 'inputHandler not ready');
          break;
        }
        const sec = Number(params.section ?? params.sectionIndex ?? 0);
        const startPara = Number(params.startPara ?? params.paragraph ?? params.paragraphIndex ?? 0);
        const endPara = Number(params.endPara ?? startPara);
        const startChar = Number(params.startChar ?? params.charOffset ?? 0);
        const endChar = Number(params.endChar ?? (startChar + Number(params.length ?? 0)));
        const newText = String(params.newText ?? '');
        const start = params.start ?? null;
        const end = params.end ?? null;

        // 셀 안에서의 편집: start/end 모두 parentParaIndex가 있고 같은 셀이면 cell-aware API 사용.
        const inCell = start && end
          && start.parentParaIndex !== undefined
          && end.parentParaIndex !== undefined
          && start.parentParaIndex === end.parentParaIndex
          && start.controlIndex === end.controlIndex
          && start.cellIndex === end.cellIndex;

        let result: any = { ok: true };
        let resultError: string | null = null;
        try {
          // AI 편집을 SnapshotCommand로 감싸 히스토리 스택에 올린다 → Ctrl+Z 지원
          inputHandler.executeOperation({
            kind: 'snapshot',
            operationType: 'aiEdit',
            operation: (w) => {
              if (inCell) {
                const ppi = Number(start.parentParaIndex);
                const ci = Number(start.controlIndex);
                const cellIdx = Number(start.cellIndex);
                const sCellPara = Number(start.cellParaIndex ?? 0);
                const eCellPara = Number(end.cellParaIndex ?? sCellPara);
                const sOff = Number(start.charOffset ?? 0);
                const eOff = Number(end.charOffset ?? sOff);

                if (sCellPara === eCellPara) {
                  const count = Math.max(0, eOff - sOff);
                  if (count > 0) w.deleteTextInCell(sec, ppi, ci, cellIdx, sCellPara, sOff, count);
                  if (newText) w.insertTextInCell(sec, ppi, ci, cellIdx, sCellPara, sOff, newText);
                  result = { ok: true, inCell: true };
                  return {
                    sectionIndex: sec, paragraphIndex: ppi, charOffset: sOff + newText.length,
                    parentParaIndex: ppi, controlIndex: ci, cellIndex: cellIdx, cellParaIndex: sCellPara,
                  };
                }
                // 같은 셀·다른 문단: 역순으로 삭제 → 첫 문단 위치에 삽입
                const firstLen = w.getCellParagraphLength(sec, ppi, ci, cellIdx, sCellPara);
                const firstTail = Math.max(0, firstLen - sOff);
                if (firstTail > 0) w.deleteTextInCell(sec, ppi, ci, cellIdx, sCellPara, sOff, firstTail);
                for (let p = eCellPara; p > sCellPara; p--) {
                  const pLen = w.getCellParagraphLength(sec, ppi, ci, cellIdx, p);
                  const cnt = p === eCellPara ? Math.min(eOff, pLen) : pLen;
                  if (cnt > 0) w.deleteTextInCell(sec, ppi, ci, cellIdx, p, 0, cnt);
                }
                if (newText) w.insertTextInCell(sec, ppi, ci, cellIdx, sCellPara, sOff, newText);
                result = { ok: true, inCell: true, multiPara: true };
                return {
                  sectionIndex: sec, paragraphIndex: ppi, charOffset: sOff + newText.length,
                  parentParaIndex: ppi, controlIndex: ci, cellIndex: cellIdx, cellParaIndex: sCellPara,
                };
              }
              if (startPara === endPara) {
                const length = Math.max(0, endChar - startChar);
                const r = w.replaceText(sec, startPara, startChar, length, newText);
                result = r;
                return { sectionIndex: sec, paragraphIndex: startPara, charOffset: startChar + newText.length };
              }
              const del = w.deleteRange(sec, startPara, startChar, endPara, endChar);
              if (!del?.ok) {
                resultError = 'deleteRange failed';
                return { sectionIndex: sec, paragraphIndex: startPara, charOffset: startChar };
              }
              const ins = w.insertText(sec, del.paraIdx, del.charOffset, newText);
              result = { ok: true, deleted: del, inserted: ins };
              return { sectionIndex: sec, paragraphIndex: del.paraIdx, charOffset: del.charOffset + newText.length };
            },
          });
        } catch (err: any) {
          reply(undefined, err?.message || String(err));
          break;
        }
        if (resultError) {
          reply(undefined, resultError);
          break;
        }
        eventBus.emit('document-changed');
        emitSelectionChanged();
        reply(result);
        break;
      }
      case 'applyEditTable': {
        if (!inputHandler) {
          reply(undefined, 'inputHandler not ready');
          break;
        }
        const sec = Number(params.section ?? params.sectionIndex ?? 0);
        const startPara = Number(params.startPara ?? params.paragraph ?? params.paragraphIndex ?? 0);
        const endPara = Number(params.endPara ?? startPara);
        const startChar = Number(params.startChar ?? params.charOffset ?? 0);
        const endChar = Number(params.endChar ?? startChar);
        const table = params.table;
        if (!table || typeof table !== 'object') {
          reply(undefined, 'table payload missing');
          break;
        }
        const rows = Number(table.rows);
        const cols = Number(table.cols);
        const cells = table.cells;
        if (!Number.isFinite(rows) || !Number.isFinite(cols) || rows <= 0 || cols <= 0) {
          reply(undefined, 'table rows/cols invalid');
          break;
        }
        if (!Array.isArray(cells) || cells.length !== rows) {
          reply(undefined, 'table cells shape mismatch');
          break;
        }

        let result: any = null;
        let resultError: string | null = null;
        try {
          // 표 삽입을 SnapshotCommand로 감싸 히스토리 스택에 올린다 → Ctrl+Z 지원
          inputHandler.executeOperation({
            kind: 'snapshot',
            operationType: 'aiEditTable',
            operation: (w) => {
              // 1) 기존 선택 영역이 있으면 삭제해서 표를 그 자리에 끼워 넣는다.
              let insertPara = startPara;
              let insertChar = startChar;
              if (startPara === endPara && endChar > startChar) {
                const length = endChar - startChar;
                w.replaceText(sec, startPara, startChar, length, '');
              } else if (endPara > startPara) {
                const del = w.deleteRange(sec, startPara, startChar, endPara, endChar);
                if (del?.ok) {
                  insertPara = del.paraIdx;
                  insertChar = del.charOffset;
                }
              }

              // 2) 표 생성
              const created = w.createTable(sec, insertPara, insertChar, rows, cols);
              if (!created?.ok) {
                resultError = 'createTable failed';
                return { sectionIndex: sec, paragraphIndex: insertPara, charOffset: insertChar };
              }
              const ppi = created.paraIdx;
              const ci = created.controlIdx;

              // 2.5) 페이지 본문 폭에 맞춰 셀 폭 균등 조정 (HWPUNIT 단위)
              try {
                const pageDef = w.getPageDef(sec);
                const gutter = (pageDef as any).marginGutter ?? 0;
                const availableWidth = pageDef.width - pageDef.marginLeft - pageDef.marginRight - gutter;
                if (availableWidth > 0 && cols > 0) {
                  const tableProps = w.getTableProperties(sec, ppi, ci);
                  const currentWidth = tableProps.tableWidth ?? 0;
                  if (currentWidth === 0 || currentWidth > availableWidth) {
                    const targetCellWidth = Math.floor(availableWidth / cols);
                    for (let r = 0; r < rows; r++) {
                      for (let c = 0; c < cols; c++) {
                        const cellIdx = r * cols + c;
                        try {
                          w.setCellProperties(sec, ppi, ci, cellIdx, { width: targetCellWidth } as any);
                        } catch (cpErr) {
                          console.warn('[applyEditTable] setCellProperties width failed', cellIdx, cpErr);
                        }
                      }
                    }
                    try {
                      w.setTableProperties(sec, ppi, ci, { tableWidth: targetCellWidth * cols } as any);
                    } catch (tpErr) {
                      console.warn('[applyEditTable] setTableProperties failed', tpErr);
                    }
                  }
                }
              } catch (fitErr) {
                console.warn('[applyEditTable] fit-to-page failed', fitErr);
              }

              // 3) 셀 채우기
              for (let r = 0; r < rows; r++) {
                const row = cells[r];
                if (!Array.isArray(row)) continue;
                for (let c = 0; c < cols; c++) {
                  const raw = row[c];
                  const txt = raw === null || raw === undefined ? '' : String(raw);
                  if (!txt) continue;
                  const cellIdx = r * cols + c;
                  try {
                    w.insertTextInCell(sec, ppi, ci, cellIdx, 0, 0, txt);
                  } catch (cellErr) {
                    console.warn('[applyEditTable] insertTextInCell failed', r, c, cellErr);
                  }
                }
              }

              result = { ok: true, paragraphIndex: ppi, controlIndex: ci, rows, cols };
              // 커서를 첫 번째 셀 시작 위치로 이동
              return {
                sectionIndex: sec,
                paragraphIndex: ppi,
                charOffset: 0,
                parentParaIndex: ppi,
                controlIndex: ci,
                cellIndex: 0,
                cellParaIndex: 0,
              };
            },
          });
        } catch (err: any) {
          reply(undefined, `applyEditTable failed: ${err?.message || err}`);
          break;
        }
        if (resultError) {
          reply(undefined, resultError);
          break;
        }
        eventBus.emit('document-changed');
        emitSelectionChanged();
        reply(result);
        break;
      }
      default:
        reply(undefined, `Unknown method: ${method}`);
    }
  } catch (err: any) {
    reply(undefined, err.message || String(err));
  }
});

loadFromUrlParam();
