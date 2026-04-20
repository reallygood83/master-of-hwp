# master-of-hwp

> ⚠️ **Phase 0 — Core API 추출 중 (v0.0.x)**
> 에디터(rhwp-studio)는 **Feature Freeze** 상태입니다. 현재 모든 에너지는 파이썬 Core API(`master_of_hwp`)의 PyPI 배포 가능한 수준까지의 안정화에 집중되어 있습니다.
> 자세한 방향은 [docs/ROADMAP.md](docs/ROADMAP.md)와 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)에서 확인하세요.

---

> **AI가 한컴오피스 문서(.hwp / .hwpx)를 읽고, 구조를 이해하고, 안전하게 편집·저장하도록 돕는 오픈소스 플랫폼**

`master-of-hwp`는 Claude Code·Claude Desktop·기타 MCP 호환 AI 클라이언트가 한국어 공공/교육/업무용 한글 문서를 **실제 파일 포맷 그대로** 읽고 수정할 수 있게 해 주는 오픈소스 프로젝트입니다. 핵심 편집 엔진으로는 Rust + WebAssembly 기반의 [`@rhwp/core`](https://www.npmjs.com/package/@rhwp/core) 라이브러리를 사용하고, Python으로 작성된 [FastMCP](https://github.com/jlowin/fastmcp) 서버가 이를 감싸 AI가 호출 가능한 도구로 노출합니다.

---

## 🎯 왜 이 프로젝트인가

한국 공공·교육 현장은 여전히 한글 문서(`.hwp` / `.hwpx`)를 사실상의 표준으로 사용합니다. 하지만 대부분의 AI 도구는 HWP 포맷을 직접 다루지 못하고, DOCX로 변환해 편집한 뒤 다시 돌려놓는 과정에서 **서식·표·문단 속성이 손상**되는 일이 빈번합니다.

`master-of-hwp`는 다음 문제를 해결합니다.

- **진짜 포맷 유지** — 변환 없이 원본 HWP/HWPX를 그대로 열고 저장합니다.
- **표·문단 구조 이해** — 단순 텍스트가 아니라 섹션·문단·표의 구조를 AI에 노출합니다.
- **AI-네이티브 편집** — Claude 등 LLM이 자연어로 "3번째 문단을 이렇게 바꿔줘"라고 지시하면 실제 원본 문서에 반영됩니다.
- **라운드트립 보장** — 편집 → 저장 → 재로딩 후에도 동일한 구조를 유지하는 것이 검증된 파이프라인입니다.

---

## ✨ 주요 기능

| 기능 | 설명 |
|------|------|
| **문서 열기** | `.hwp`, `.hwpx`, `.txt`, `.md` 파일을 세션에 로드하고 `document_id` 발급 |
| **텍스트 추출** | 문서 본문 텍스트 추출 (표 포함/제외 선택, 최대 글자수 제한) |
| **구조 추출** | 섹션·문단·표 구조를 JSON으로 반환 (행/열/셀 수, 페이지 위치 포함) |
| **문단 교체** | 특정 문단 인덱스의 내용을 새 텍스트로 안전 교체 |
| **문단 삽입** | 지정 문단 뒤에 새 문단 삽입 |
| **원본 포맷 저장** | 편집한 문서를 `.hwp` / `.hwpx` 포맷으로 재저장 (라운드트립 편집 재생) |
| **문서 검증** | 저장된 파일이 실제 유효한 한글 문서인지 WASM 엔진으로 재파싱 검증 |
| **워크스페이스 가드** | 허용된 디렉터리 밖의 파일 접근을 차단하는 보안 검사 |

---

## 🏗 아키텍처

```
┌──────────────────────────────┐
│  MCP Client                  │
│  (Claude Code / Desktop 등)  │
└─────────────┬────────────────┘
              │ MCP (stdio / JSON-RPC)
              ▼
┌──────────────────────────────┐
│  FastMCP Server (Python)     │
│  server.py                   │
│  └─ tools/                   │
│     ├─ open_document         │
│     ├─ extract_document_text │
│     ├─ extract_document_…    │
│     ├─ replace_paragraph_…   │
│     ├─ insert_paragraph_…    │
│     ├─ save_as               │
│     └─ validate_document     │
└─────────────┬────────────────┘
              │ 서브프로세스 호출
              ▼
┌──────────────────────────────┐
│  Node.js Bridges             │
│  bridges/rhwp_extract.mjs    │
│  bridges/rhwp_save.mjs       │
└─────────────┬────────────────┘
              │ wasm-bindgen
              ▼
┌──────────────────────────────┐
│  @rhwp/core (Rust + WASM)    │
│  실제 HWP/HWPX 파싱·편집·저장 │
└──────────────────────────────┘
```

### 왜 이런 구조인가?

- **rhwp**는 Rust로 작성된 HWP/HWPX 실제 포맷 라이브러리지만, 현재 공식 바인딩은 Node.js(WASM)뿐입니다.
- Python 서버에서 직접 WASM을 로드하면 의존성이 복잡해지고, 오히려 **서브프로세스 경계**가 안정성·격리·에러 처리에 유리합니다.
- Node 브리지는 한 번 호출당 한 작업만 수행하고 JSON으로 결과/에러를 반환합니다. Python 쪽은 이를 타입드 객체로 감싸고, 세션(DocumentStore)과 워크스페이스 가드를 책임집니다.
- 편집은 **세션에 연산 기록(`OperationRecord` 리스트)** 으로 누적되고, `save_as` 호출 시 원본 파일 + 연산 리스트를 브리지에 넘겨 **원본 위에서 연산을 재생(replay)** 하는 방식으로 포맷 충실도를 최대화합니다.

---

## 📦 설치

### 요구 사항

- **Python 3.11 이상** (FastMCP 3.2+ 의존성)
- **Node.js 20 이상** (WASM 로딩용)
- macOS / Linux / WSL 기준으로 검증 (Windows 네이티브는 미검증)

### 1) Python 가상환경 및 의존성

```bash
cd mcp-server
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

`pyproject.toml`의 `fastmcp>=3.2.0`이 설치됩니다.

### 2) Node 브리지 의존성

```bash
cd mcp-server/bridges
npm install
```

`@rhwp/core` WASM 패키지가 `node_modules/@rhwp/core/rhwp_bg.wasm` 경로에 설치됩니다. 브리지 스크립트가 이 경로를 직접 읽어 사용합니다.

---

## 🚀 실행

### MCP 서버 단독 실행 (stdio)

```bash
cd mcp-server
source .venv/bin/activate
python server.py
```

### Claude Code / Desktop에 등록

`~/.claude/settings.json` 또는 클라이언트의 MCP 설정에 다음과 같이 추가합니다 (경로는 환경에 맞게 수정).

```json
{
  "mcpServers": {
    "master-of-hwp": {
      "command": "/absolute/path/to/master-of-hwp/mcp-server/.venv/bin/python",
      "args": ["/absolute/path/to/master-of-hwp/mcp-server/server.py"]
    }
  }
}
```

클라이언트를 재시작하면 `health_check`, `open_document`, `extract_document_text` 등의 도구가 노출됩니다.

---

## 🛠 제공 MCP 도구

| 도구 | 역할 |
|------|------|
| `health_check` | 서버 상태·구현된 도구 목록 반환 |
| `rhwp_integration_status` | rhwp 실제 연동이 활성화된 환경인지 보고 |
| `rhwp_save_status` | HWP/HWPX 저장 브리지가 준비되었는지 보고 |
| `open_document(path, readonly=True)` | 문서를 열고 `document_id` 발급 |
| `extract_document_text(path/document_id, include_tables, max_chars)` | 본문 텍스트 추출 |
| `extract_document_structure(path/document_id, include_tables, max_chars)` | 섹션·문단·표 구조 JSON 반환 |
| `replace_paragraph_text(document_id, paragraph_index, new_text)` | 문단 교체 연산을 세션에 기록 |
| `insert_paragraph_after(document_id, after_paragraph_index, text)` | 문단 뒤 새 문단 삽입 연산 기록 |
| `save_as(document_id, output_path)` | 기록된 연산을 재생하여 `.hwp`/`.hwpx`/`.txt`/`.md` 로 저장 |
| `validate_document(path)` | 저장된 파일을 다시 로드하여 유효성 확인 |

모든 도구는 `{ok, ...}` 형태의 일관된 응답 포맷을 사용하며, 실패 시 `ok: false`와 `error_code`·`message`가 포함됩니다.

---

## 🧪 테스트

```bash
cd mcp-server
source .venv/bin/activate
pytest
```

- 단위 테스트 + rhwp 브리지 통합 테스트(실제 WASM 호출) 포함
- `pyproject.toml`의 `integration` 마커로 실제 브리지를 요구하는 테스트를 구분
- 실제 공공문서 샘플(`samples/public-official/table-vpos-01.hwpx`)을 이용한 표 구조 추출 검증 포함

---

## 📂 디렉터리 구조

```
master-of-hwp/
├── mcp-server/                   # FastMCP 서버 (Python)
│   ├── server.py                 # MCP 엔트리 포인트
│   ├── adapters/rhwp_adapter.py  # rhwp 브리지 호출 래퍼
│   ├── tools/                    # 개별 MCP 도구 구현
│   ├── document_store.py         # 세션·연산 기록 저장소
│   ├── config.py                 # 워크스페이스·브리지 설정
│   ├── bridges/                  # Node.js 브리지
│   │   ├── rhwp_extract.mjs
│   │   ├── rhwp_save.mjs
│   │   └── package.json
│   ├── tests/                    # pytest 스위트
│   └── pyproject.toml
├── gui/                          # (실험) 로컬 GUI 프로토타입
├── samples/                      # 공개 샘플 문서
├── outputs/                      # 테스트·실행 산출물 (git 제외)
└── README.md                     # (이 파일)
```

---

## 🔐 보안 & 안전성

- **워크스페이스 가드**: 서버는 허용된 디렉터리 밖의 경로 접근을 `Path.relative_to` 기반으로 차단합니다.
- **읽기 전용 기본값**: `open_document`는 기본값이 `readonly=True`입니다. 편집 의도가 명시적이어야 연산이 기록됩니다.
- **원본 우선**: 편집은 원본을 덮어쓰지 않고, 별도 `output_path`로 저장되는 것이 기본 패턴입니다.
- **서브프로세스 격리**: Node 브리지 호출은 실패 시 JSON 에러 코드(`BRIDGE_*`)로 반환되며, Python 쪽이 이를 MCP 에러로 변환합니다.

---

## 🗺 개발 현황

현재 **Phase 1 (읽기 + 텍스트 편집 PoC)** 완료, **Phase 2 (라운드트립 저장)** 의 핵심 시나리오가 실제 한컴 샘플에서 검증된 상태입니다.

- ✅ HWP/HWPX 실파일 열기 및 텍스트·구조 추출
- ✅ 문단 단위 편집(교체/삽입) 및 원본 포맷 재저장
- ✅ 실 공공문서 샘플 기반 표 구조 인식 (행/열/페이지 위치)
- ✅ pytest 기반 통합 테스트 자동화
- 🚧 표 셀 단위 편집, 스타일·서식 보존 검증 확대
- 🚧 이미지·수식 등 고급 오브젝트 대응

---

## 🤝 기여

이슈와 PR을 환영합니다. 한국 공공·교육 현장의 실제 문서 샘플(민감정보 제거 후)이나 실패 케이스 제보가 특히 큰 도움이 됩니다.

1. 이슈로 재현 가능한 샘플과 기대 동작을 설명해 주세요.
2. PR은 가능한 한 작게 나눠 주시고, 관련 테스트를 함께 첨부해 주세요.
3. 커밋 메시지는 Conventional Commits(`feat:`, `fix:`, `docs:` …) 형식을 따릅니다.

---

## 📜 라이선스 & 크레딧

- 본 저장소의 Python·Node 코드: MIT License (별도 명시가 없는 한)
- **[@rhwp/core](https://www.npmjs.com/package/@rhwp/core)** — HWP/HWPX 파싱·편집의 핵심 엔진. 해당 패키지의 자체 라이선스를 따릅니다.
- **[FastMCP](https://github.com/jlowin/fastmcp)** — MCP 서버 프레임워크.

한국 공공·교육 현장에서 AI가 더 쉽게, 더 안전하게 일할 수 있기를 바라며 만들고 있습니다. 🇰🇷
