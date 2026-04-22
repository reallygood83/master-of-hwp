<div align="center">

# 한글의 달인 · master-of-hwp

**AI가 한컴오피스 문서(.hwp / .hwpx)를 읽고, 이해하고, 편집하는 오픈소스 플랫폼**

[![PyPI](https://img.shields.io/pypi/v/master-of-hwp.svg?style=for-the-badge&logo=pypi&logoColor=white)](https://pypi.org/project/master-of-hwp/)
[![Studio](https://img.shields.io/pypi/v/master-of-hwp-studio.svg?label=studio&style=for-the-badge&logo=pypi&logoColor=white&color=7c3aed)](https://pypi.org/project/master-of-hwp-studio/)
[![Python](https://img.shields.io/pypi/pyversions/master-of-hwp.svg?style=for-the-badge&logo=python&logoColor=white)](https://pypi.org/project/master-of-hwp/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

<br />

<a href="https://www.youtube.com/@%EB%B0%B0%EC%9B%80%EC%9D%98%EB%8B%AC%EC%9D%B8-p5v" target="_blank">
  <img src="https://img.shields.io/badge/YouTube-배움의_달인-FF0000?style=for-the-badge&logo=youtube&logoColor=white" alt="YouTube 배움의 달인" />
</a>
&nbsp;
<a href="https://x.com/reallygood83" target="_blank">
  <img src="https://img.shields.io/badge/X-@reallygood83-000000?style=for-the-badge&logo=x&logoColor=white" alt="X @reallygood83" />
</a>
&nbsp;
<a href="https://github.com/reallygood83/master-of-hwp" target="_blank">
  <img src="https://img.shields.io/badge/GitHub-star-181717?style=for-the-badge&logo=github&logoColor=white" alt="GitHub star" />
</a>

<br /><br />

**[English](README.en.md)** · **[CHANGELOG](CHANGELOG.md)** · **[로드맵](docs/ROADMAP.md)** · **[아키텍처](docs/ARCHITECTURE.md)** · **[기여하기](CONTRIBUTING.md)**

</div>

---

## 🎯 왜 이 프로젝트인가

한국의 공공·교육·업무 현장은 아직도 한글 문서(`.hwp` / `.hwpx`)를 표준으로 씁니다. 하지만 대부분의 AI 도구는 HWP를 직접 다루지 못하고, DOCX로 변환해 편집한 뒤 돌려놓는 과정에서 **서식·표·문단 속성이 망가집니다**.

**한글의 달인(master-of-hwp)** 은 이 문제를 해결합니다:

- ✅ **진짜 포맷 유지** — 변환 없이 원본 HWP/HWPX를 그대로 열고 저장
- ✅ **구조 이해** — 섹션·문단·표의 구조를 AI에 그대로 노출
- ✅ **AI-네이티브 편집** — "3번째 문단을 공식 문체로 바꿔줘" 같은 자연어 지시로 수정
- ✅ **라운드트립 보장** — 편집 → 저장 → 재로딩 후에도 구조 훼손 없음

---

## 🚀 30초 시작

### 📘 개발자용 — Python 라이브러리

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

### 🎨 일반 사용자용 — Studio (WYSIWYG GUI)

```bash
pip install master-of-hwp-studio
mohwp studio
```

→ 브라우저 자동 실행 → **rhwp WYSIWYG 에디터 + AI 작업 패널** 한 화면에서 사용.

```bash
mohwp mcp-config   # Claude Desktop 연동 설정 스니펫 출력
```

---

## ✨ 주요 기능

| 기능 | 상세 |
|---|---|
| **문서 열기** | `.hwp` / `.hwpx` 파일을 네이티브 포맷 그대로 로드 |
| **구조 분석** | 섹션·문단·표·셀을 JSON으로 반환 (`summary()`, `section_tables` 등) |
| **문단/셀 편집** | `replace_paragraph`, `replace_table_cell_paragraph` 불변 API |
| **AI 자연어 편집** | `doc.ai_edit("내용을 공식체로")` — Claude/Codex/API 모두 지원 |
| **멀티모달** | 이미지·PDF 첨부 → Claude Code CLI/Codex CLI가 Read/인식 |
| **템플릿 라이브러리** | 자주 쓰는 양식 저장/불러오기 (`~/.mohwp/templates/`) |
| **왕복 재현율** | `fidelity.harness` 로 바이트 레벨 검증 |
| **MCP 서버** | Claude Desktop 에서 `open_document`, `find_paragraphs`, `replace_paragraph` 등 도구 호출 |

---

## 🧠 AI 제공자

| 제공자 | 사용 방식 | 우선순위 |
|---|---|---|
| **Claude Code CLI** | `claude -p "prompt"` (구독 사용, API 키 불필요) | 🥇 1순위 |
| **Claude API** | `ANTHROPIC_API_KEY` 환경변수 | 🥈 2순위 |
| **Codex CLI** | `codex exec` (ChatGPT Plus/Pro 구독) | 🥇 1순위 |
| **OpenAI API** | `OPENAI_API_KEY` 환경변수 | 🥈 2순위 |
| **Rule-based** | 위 어떤 것도 없을 때 폴백 | 🥉 항상 가능 |

---

## 🏗 아키텍처

```
┌──────────────────────────────────────────┐
│  사용자 (교사 · 공무원 · 개발자)         │
└────────────┬─────────────────────────────┘
             │
    ┌────────┴────────┐
    ▼                 ▼
┌──────────┐    ┌──────────────────┐
│ Claude   │    │ 한글의 달인 Studio│
│ Desktop  │    │ (mohwp studio)   │
└────┬─────┘    └────────┬─────────┘
     │ MCP              │ HTTP
     ▼                   ▼
┌────────────────────────────────┐
│  master-of-hwp Core API        │
│  (HwpDocument, ai_edit, ...)   │
└────────────┬───────────────────┘
             │
   ┌─────────┴─────────┐
   ▼                   ▼
┌────────────┐   ┌──────────────────┐
│ olefile +  │   │ rhwp (Rust+WASM) │
│ zipfile    │   │ WYSIWYG 에디터   │
└────────────┘   └──────────────────┘
```

- **Python Core** — HWP 5.0 (CFBF) + HWPX (OOXML) 파싱, 편집 프리미티브
- **rhwp** — [edwardkim/rhwp](https://github.com/edwardkim/rhwp) 의 Rust + WebAssembly WYSIWYG 편집 엔진 (번들 포함)
- **Studio** — 웹 GUI + MCP 서버 통합 (`mohwp` CLI)

---

## 📦 패키지

| 이름 | 용도 | 설치 |
|---|---|---|
| [`master-of-hwp`](https://pypi.org/project/master-of-hwp/) | Python Core API | `pip install master-of-hwp` |
| [`master-of-hwp`](https://pypi.org/project/master-of-hwp/)`[ai]` | + AI provider SDK | `pip install "master-of-hwp[ai]"` |
| [`master-of-hwp-studio`](https://pypi.org/project/master-of-hwp-studio/) | GUI + MCP + rhwp 번들 | `pip install master-of-hwp-studio` |

---

## 🛣 로드맵

- **v0.1** ✅ — 읽기 API + HWPX 문단 편집 + fidelity
- **v0.2** ✅ — 표 셀 편집 · 자연어 편집 루프 · CLI provider · Studio GUI · rhwp 번들 · 템플릿 라이브러리 · 멀티모달 첨부
- **v0.3** — HWP 5.0 완전 쓰기 (CFBF resize writer) · 문단 삽입/삭제 · 표 추가/삭제
- **v0.4** — Agentic edit loop (intent → locate → apply → verify → rollback)
- **v1.0** — API 호환성 계약 고정

세부: [docs/ROADMAP.md](docs/ROADMAP.md)

---

## 🤝 기여하기

**이 프로젝트는 커뮤니티 기여를 환영합니다.**

- 🐛 **버그 리포트 / 기능 요청**: [Issues](https://github.com/reallygood83/master-of-hwp/issues)
- 💻 **코드 기여**: fork → branch → PR ([CONTRIBUTING.md](CONTRIBUTING.md))
- 💬 **질문 / 토론**: [Discussions](https://github.com/reallygood83/master-of-hwp/discussions)

도움 주시면 좋은 영역:
- HWP 5.0 CFBF 쓰기 엔진 (v0.3)
- 문단/표 삽입·삭제 연산
- 추가 LLM provider (Gemini, 로컬 Ollama)
- Windows/Linux 인스톨러
- 접근성(a11y) 개선

작은 기여도 환영합니다 — 문서 오탈자, 번역, 샘플 파일 모두 가치 있습니다.

---

## 🙏 감사의 말

이 프로젝트는 [**edwardkim/rhwp**](https://github.com/edwardkim/rhwp) (by [@edwardkim](https://github.com/edwardkim)) 의 Rust + WebAssembly HWP 파싱/렌더링 엔진을 기반으로 합니다. `master-of-hwp-studio` 의 WYSIWYG 에디터는 rhwp 가 있기에 가능합니다. rhwp 도 같이 ⭐ 눌러주세요.

---

## 📄 라이선스

MIT — [LICENSE](LICENSE) 참고.

---

<div align="center">

**만든 사람** — 배움의 달인

<a href="https://www.youtube.com/@%EB%B0%B0%EC%9B%80%EC%9D%98%EB%8B%AC%EC%9D%B8-p5v" target="_blank">📺 YouTube</a>
&nbsp;·&nbsp;
<a href="https://x.com/reallygood83" target="_blank">𝕏 @reallygood83</a>
&nbsp;·&nbsp;
<a href="https://github.com/reallygood83" target="_blank">GitHub</a>

*도움이 되셨다면 ⭐ 한 번 눌러주시면 큰 힘이 됩니다.*

</div>
