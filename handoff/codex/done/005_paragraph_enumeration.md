---
id: 005
from: claude
to: codex
status: done
created: 2026-04-21
priority: high
---

# 문단 단위 열거 (HWP5 + HWPX)

## 배경 / 진행 상태

- #001 HWP5 섹션 카운트 ✅
- #002 HWPX 섹션 카운트 ✅
- #003 HWP5 섹션 텍스트 추출 ✅
- #004 HWPX 섹션 텍스트 추출 ✅
- #005 **이 작업** — 섹션 안의 **문단(paragraph) 리스트** 열거

ROADMAP.md Phase 1의 `paragraphs` 목표를 해금합니다.

## 목적

각 섹션을 **문단들의 리스트**로 노출. 현재 `extract_section_texts`는 전체
섹션을 하나의 문자열로 돌려주지만, 편집/치환 연산은 문단 경계 인식이
필요합니다.

## In-Scope

### 1. HWP5 쪽 — `master_of_hwp/adapters/hwp5_reader.py`

```python
def extract_section_paragraphs(raw_bytes: bytes) -> list[list[str]]:
    """Return paragraphs per section.

    Returns:
        Outer list: one entry per BodyText/SectionN stream (count == count_sections).
        Inner list: one string per paragraph (one PARA_TEXT record = one paragraph).
    """
```

- 현재 `_extract_section_stream_text`가 PARA_TEXT 페이로드를 전부 concat하는데,
  이걸 PARA_TEXT 레코드 단위로 끊어서 리스트로 반환
- 문단 내 control-block 처리 로직(현재 `_decode_para_text`)은 그대로 재사용
- 문단 끝의 `\r` 은 포함하지 말 것 (문단 경계는 리스트 구조 자체가 표현)

### 2. HWPX 쪽 — `master_of_hwp/adapters/hwpx_reader.py`

```python
def extract_section_paragraphs(raw_bytes: bytes) -> list[list[str]]:
    """Return paragraphs per section.

    Returns:
        Outer list: one entry per section XML part (count == count_sections).
        Inner list: one string per <p> element — all <t> text joined.
    """
```

- 현재 `_extract_text_from_section_xml` 이 모든 `<p>` 를 `\n`으로 join 하는데,
  이걸 `<p>` 단위로 끊어서 리스트로 반환
- `<p>` 안의 `<t>` 순회 로직(`_iter_paragraph_text_nodes`) 은 그대로 재사용
- 빈 `<p>` 는 `""` 로 유지 (제거하지 말 것 — layout intent 보존)

### 3. 테스트

- `tests/unit/test_hwp5_reader.py`:
  - 실 샘플 → outer len == count_sections
  - 각 섹션의 paragraph들을 concat하면 기존 extract_section_texts 와 일치
    (단, 문단 끝 `\r` 차이만큼 정규화 필요할 수 있음 — 그냥 스모크 체크로 충분)

- `tests/unit/test_hwpx_reader.py`:
  - 빈 바이트 → `ValueError`
  - 실 샘플 → outer len == count_sections
  - `"\n".join(paragraphs)` 가 기존 `extract_section_texts` 결과와 정확히 일치

## Out-of-Scope

- 문단 메타데이터 (스타일, 들여쓰기, 정렬 등)
- 문자 런(run) 단위 분리
- `HwpDocument` 수정 — Claude가 후속 커밋에서 통합 property 추가

## 인수 기준

- [ ] 두 어댑터 모두에 `extract_section_paragraphs` 추가
- [ ] 외측 리스트 길이 == `count_sections(raw_bytes)` 항상
- [ ] 모든 공개 심볼에 타입 힌트 + docstring
- [ ] `ruff`, `black`, `mypy strict`, `pytest` 전부 통과 (현재 41 → 44+ passed)
- [ ] 외부 runtime 의존성 추가 금지

## 구현 힌트 (참고용)

### HWP5

```python
def extract_section_paragraphs(raw_bytes: bytes) -> list[list[str]]:
    if not raw_bytes:
        raise ValueError("HWP raw_bytes must not be empty.")
    try:
        with _open_compound_file(raw_bytes) as compound_file:
            section_names = _list_section_streams(compound_file)
            return [
                _extract_section_stream_paragraphs(
                    compound_file.openstream(["BodyText", name]).read()
                )
                for name in section_names
            ]
    except OSError as exc:
        raise Hwp5FormatError(...) from exc
    except OleFileError as exc:
        raise Hwp5FormatError(...) from exc


def _extract_section_stream_paragraphs(raw_section: bytes) -> list[str]:
    decompressed = _decompress_section(raw_section)
    return [
        _decode_para_text(payload).rstrip("\r")  # strip trailing \r if present
        for tag_id, _level, payload in _iter_records(decompressed)
        if tag_id == _PARA_TEXT_TAG_ID
    ]
```

### HWPX

```python
def extract_section_paragraphs(raw_bytes: bytes) -> list[list[str]]:
    # Same shape as extract_section_texts, but instead of "\n".join(paragraphs)
    # return the list itself.
    ...


def _paragraphs_from_section_xml(xml_bytes: bytes) -> list[str]:
    try:
        root = ElementTree.fromstring(xml_bytes)
    except ElementTree.ParseError as exc:
        raise HwpxFormatError(...) from exc
    return [
        "".join(text for text in _iter_paragraph_text_nodes(p) if text)
        for p in root.iter()
        if _local_name(p.tag) == "p"
    ]
```

선택: `extract_section_texts` 를 `extract_section_paragraphs` 위에서
`["\n".join(ps) for ps in extract_section_paragraphs(...)]` 로 재구현
하는 것도 환영. 하지만 필수는 아님 (중복 zipfile open 피하려면 private
helper 공유).

## 완료 후 할 일

1. `git mv handoff/codex/005_*.md handoff/codex/done/`
2. `handoff/review/005_review_paragraph_enumeration.md` 생성
3. 커밋: `feat(adapters): enumerate paragraphs per section (spike #005)`
4. 트레일러: `Confidence / Scope-risk / Reversibility / Directive / Tested / Not-tested`
5. `git push origin main`

## 스타일 가이드

- 두 어댑터의 기존 스타일 유지
- 새 예외 만들지 말고 기존 `Hwp5FormatError` / `HwpxFormatError` 재사용
- Private helper는 `_name` 접두사
