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

    inputHandler.setDispatcher(dispatcher);
    inputHandler.setContextMenu(new ContextMenu(dispatcher, registry));
    inputHandler.setCommandPalette(new CommandPalette(registry, dispatcher));
    inputHandler.setCellSelectionRenderer(new CellSelectionRenderer(container, canvasView.getViewportManager()));
    inputHandler.setTableObjectRenderer(new TableObjectRenderer(container, canvasView.getViewportManager()));
    inputHandler.setTableResizeRenderer(new TableResizeRenderer(container, canvasView.getViewportManager()));
    inputHandler.setPictureObjectRenderer(null as any);

    eventBus.on('document-changed', () => updateStatusBar());
    eventBus.on('current-page-changed', () => updateStatusBar());
    eventBus.on('selection-changed', () => emitSelectionChanged());
    eventBus.on('cursor-moved', () => emitSelectionChanged());

    updateStatusBar();
  } catch (err: any) {
    msg.textContent = `초기화 실패: ${err.message || String(err)}`;
    console.error(err);
  }
}

function updateStatusBar(): void {
  sbPage().textContent = `${wasm.currentPage + 1}/${Math.max(1, wasm.pageCount)}`;
  sbSection().textContent = `섹션 ${wasm.currentSection + 1}`;
  sbZoomVal().textContent = `${Math.round((canvasView?.getViewportManager().getZoom() ?? 1) * 100)}%`;
}

function getSelectionPayload(): { hasSelection: boolean; start?: any; end?: any; text?: string } {
  if (!inputHandler) return { hasSelection: false };
  const sel = inputHandler.getSelection();
  if (!sel) return { hasSelection: false };
  const { start, end } = sel;
  if (start.sectionIndex !== end.sectionIndex) {
    return { hasSelection: false };
  }
  if (start.paragraphIndex !== end.paragraphIndex) {
    return { hasSelection: false };
  }
  const count = end.charOffset - start.charOffset;
  if (count <= 0) {
    return { hasSelection: false };
  }
  const text = wasm.getTextRange(start.sectionIndex, start.paragraphIndex, start.charOffset, count);
  return { hasSelection: true, start, end, text };
}

function emitSelectionChanged(): void {
  const payload = getSelectionPayload();
  window.parent?.postMessage({ type: 'rhwp-selection', payload }, '*');
}

async function initializeDocument(docInfo: DocumentInfo, title: string): Promise<void> {
  document.title = title;
  toolbar?.setEnabled(true);
  updateStatusBar();
  emitSelectionChanged();
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
      default:
        reply(undefined, `Unknown method: ${method}`);
    }
  } catch (err: any) {
    reply(undefined, err.message || String(err));
  }
});

loadFromUrlParam();
