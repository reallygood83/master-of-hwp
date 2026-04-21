---
id: 008
from: claude
to: codex
status: done
created: 2026-04-21
priority: high
size: large
---

# v0.1 PyPI Release Prep (큰 작업)

## 배경 / 전략 피벗

Read path + HWPX replace_paragraph 까지 완성됐습니다. 이제 완벽주의로
더 파는 대신 **v0.1 을 PyPI 에 실제 배포**하는 방향으로 피벗합니다.

근거: 세상에 내놓으면 실제 사용자가 버그와 요구사항을 알려주고,
혼자 완벽주의로 만드는 것보다 10배 빠르게 좋아집니다.

## 목적

`pip install master-of-hwp` 로 설치 가능한 v0.1.0 배포.
현재 기능만 담고 "write path for HWPX, HWP5 write coming in v0.2"로 명시.

## In-Scope (6개 제출물)

### 1. `pyproject.toml` 업데이트

- version: `0.0.1` → `0.1.0`
- classifiers:
  - `Development Status :: 3 - Alpha` (pre-alpha → alpha)
  - `Programming Language :: Python :: 3.13` 추가
- `description` 1줄 갱신: "Read Korean HWP/HWPX documents in Python;
  edit paragraphs in HWPX. AI-friendly API."
- 불필요한 의존성 정리 (`fastmcp` 는 `mcp` extras 에 이미 있음, 확인)

### 2. `LICENSE` 파일 생성

MIT 라이선스 표준 텍스트. Copyright holder: "moon <jpmjkim23@gmail.com>".
현재 파일이 없음.

### 3. `CHANGELOG.md` 신규 파일 (Keep a Changelog 포맷)

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-04-21

### Added
- `HwpDocument.open(path)` — open .hwp / .hwpx files
- `HwpDocument.sections_count` — count sections
- `HwpDocument.section_texts` — plain text per section
- `HwpDocument.section_paragraphs` — paragraphs per section
- `HwpDocument.section_tables` — tables as nested lists [section][table][row][cell][para]
- `HwpDocument.replace_paragraph(section_index, paragraph_index, new_text)` — immutable edit (HWPX fully supported, HWP 5.0 same-length only)
- `master_of_hwp.fidelity.harness` — round-trip fidelity verification
- Type hints throughout; mypy strict clean
- Python 3.11+ support

### Known Limitations
- HWP 5.0 write path supports same-length paragraph replacement only; different-length edits pending v0.2
- Insert/delete operations not yet available
- Table cell editing not yet available
- AI editing loop planned for v0.3
```

### 4. `README.md` 전면 재작성

현재 README는 에디터/MCP 서버 중심. PyPI 랜딩페이지 관점으로 재작성:

필수 섹션:
- 한 줄 태그라인
- **30초 Quickstart** (pip install + 5줄 예제)
- API 요약 표 (메서드 → 설명)
- **Supported formats** 표 (read/write 매트릭스)
- **Roadmap** (v0.1 ✅ / v0.2 edit expansion / v0.3 AI)
- License / Contributing / Acknowledgments

기존 내용은 `docs/ARCHITECTURE.md` / `docs/ROADMAP.md` / `CONTRIBUTING.md`
가 이미 있으므로 README는 **얇게** 유지. 지금 README 너무 김.

예시 Quickstart:

```python
from master_of_hwp import HwpDocument

doc = HwpDocument.open("report.hwpx")
print(f"{doc.sections_count} sections")

for section_idx, paragraphs in enumerate(doc.section_paragraphs):
    for para_idx, text in enumerate(paragraphs):
        if text:
            print(f"§{section_idx}.{para_idx}: {text}")

# Edit the first paragraph
edited = doc.replace_paragraph(0, 0, "New intro text")
edited.path.write_bytes(edited.raw_bytes)  # or use Path manually
```

### 5. `examples/` 폴더 신규 (3개 스크립트)

파일:
- `examples/01_read_sections.py` — 섹션/문단 enumerate + 출력
- `examples/02_extract_tables.py` — 표 구조를 pretty-print
- `examples/03_edit_paragraph.py` — HWPX 문단 교체 + 저장

각 파일은 **실행 가능**해야 하고 샘플 파일 경로를 상대경로로 받음:
`python examples/01_read_sections.py samples/public-official/table-vpos-01.hwpx`

### 6. `.github/workflows/release.yml` 신규

태그 push (`v*.*.*`) 시 PyPI 배포. **Trusted Publishing** 방식 선호
(API 토큰보다 안전). 최소 구성:

```yaml
name: Release to PyPI

on:
  push:
    tags:
      - 'v*.*.*'

jobs:
  build-and-publish:
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write  # for trusted publishing
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install build
      - run: python -m build
      - uses: pypa/gh-action-pypi-publish@release/v1
```

실제 PyPI 등록은 사용자가 (PyPI.org 가서 프로젝트 claim + GitHub
trusted publisher 설정) 해야 하므로 README 또는 CONTRIBUTING에
이 단계를 문서화할 것.

## Out-of-Scope

- PyPI 업로드 자체는 수행하지 말 것 (사용자 수동 작업)
- `ci.yml` 수정은 필요한 경우만 (이미 mypy/pytest 돌고 있음)
- Sphinx / Read the Docs — v0.2 에서 고려
- `HwpDocument.replace_paragraph` integration — Claude가 이미 완료

## 인수 기준

- [ ] 6개 제출물 모두 생성/수정
- [ ] `python -m build` 이 dist/ 에 `.tar.gz` + `.whl` 생성 성공
  - 확인: `python -m build && ls dist/` 로 2개 파일 생기는지
- [ ] `python -m twine check dist/*` 통과 (설치 필요: `pip install twine`)
- [ ] README 의 Quickstart 예제가 실제로 동작 (실행 테스트)
- [ ] `ruff`, `black`, `mypy strict`, `pytest` 전부 유지 (현재 57+ passed)
- [ ] 외부 runtime 의존성 추가 금지

## 완료 후 할 일

1. `git mv handoff/codex/008_*.md handoff/codex/done/`
2. `handoff/review/008_review_release_prep.md` 생성
3. 커밋: `release(v0.1.0): PyPI-ready packaging, README, examples, CHANGELOG, release CI`
4. 트레일러: `Confidence / Scope-risk / Reversibility / Directive / Tested / Not-tested`
5. **git tag v0.1.0 은 만들지 말 것** — 사용자가 리뷰 후 수동 태깅
6. `git push origin main`

## 스타일 가이드

- 기존 mypy strict / ruff / black 설정 유지
- examples/ 스크립트는 단순하게 (주석 + `if __name__ == "__main__"`)
- README 예제는 실제 sample 파일 기준으로 작성
- CHANGELOG 는 Keep a Changelog 1.1.0 포맷 엄수
- 영어 README 가 PyPI landing 이므로 **영어로** 작성 (현재 한글 README는 그대로 두고 신규로 교체)
  - 혹은 README.md 는 영어, README.ko.md 는 한글로 분리 — 편한 쪽 선택

## 중요

이번 작업은 결과물이 **사용자에게 직접 보이는 공개물** 입니다.
단어 선택, 표기, 예제 출력이 프로젝트의 첫인상을 결정합니다.
정성 들여주세요.
