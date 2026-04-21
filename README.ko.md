# master-of-hwp

[![PyPI](https://img.shields.io/pypi/v/master-of-hwp.svg)](https://pypi.org/project/master-of-hwp/)
[![Python](https://img.shields.io/pypi/pyversions/master-of-hwp.svg)](https://pypi.org/project/master-of-hwp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> 🎉 **v0.1.0 공개 (2026-04-21)** — `pip install master-of-hwp`
> 읽기 API 완성 + HWPX 문단 편집 기본기가 들어간 첫 PyPI 릴리스입니다.
> 영어 요약: [README.md](README.md). 릴리스 노트: [CHANGELOG.md](CHANGELOG.md).
> 로드맵: [docs/ROADMAP.md](docs/ROADMAP.md), 아키텍처: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## 🚀 30초 시작

```bash
pip install master-of-hwp
```

```python
from master_of_hwp import HwpDocument

doc = HwpDocument.open("보도자료.hwpx")
print(doc.summary())                         # 구조 요약 (AI 컨텍스트용)

for s, p, text in doc.find_paragraphs("보도"):
    print(f"§{s}.{p}: {text}")

edited = doc.replace_paragraph(0, 0, "새 문단 내용")
edited.path.with_suffix(".edited.hwpx").write_bytes(edited.raw_bytes)
```

---

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

## 📦 설치

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## 🧪 테스트

```bash
ruff check master_of_hwp tests
black --check master_of_hwp tests
mypy master_of_hwp
pytest
```

## 🤝 기여

[CONTRIBUTING.md](CONTRIBUTING.md)를 먼저 읽어 주세요.
