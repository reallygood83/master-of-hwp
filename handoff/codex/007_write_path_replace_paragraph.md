---
id: 007
from: claude
to: codex
status: pending
created: 2026-04-21
priority: high
size: large
---

# Write Path Spike: replace_paragraph + 왕복 재현율 하네스

## 배경 / 진행 상태

Read path 완료:
- #001~#002 섹션 카운트 ✅
- #003~#004 섹션 텍스트 ✅
- #005 문단 열거 ✅
- #006 표 열거 ✅

이제 **write path**를 엽니다. ROADMAP.md Phase 1의 `Idempotent 연산 6종`
목표에서 가장 기초가 되는 `replace_paragraph` 를 스파이크합니다.

> **이번 작업은 의도적으로 큽니다.** (유저 요청: "작업량을 좀 많이줘")
> 세 개의 독립적인 제출물이 포함됩니다 — 필요하면 부분 진행이라도 OK.

## 목적

1. **쓰기 프리미티브**: 특정 문단 텍스트를 교체하고 다시 유효한 바이트로 직렬화.
2. **왕복 재현율 하네스**: 파싱 → 재직렬화 무(無)편집 시 재파싱 가능한지 수치로 증명.
3. **인덱스 불변성**: 편집 후 재파싱해도 다른 섹션/문단의 내용이 보존됨.

## 세 개의 제출물

### 제출물 1: 저수준 write 프리미티브 (두 포맷)

#### HWP5 — `master_of_hwp/adapters/hwp5_reader.py`

```python
def replace_paragraph(
    raw_bytes: bytes,
    section_index: int,
    paragraph_index: int,
    new_text: str,
) -> bytes:
    """Return new raw bytes with the specified paragraph replaced.

    The rest of the document (other paragraphs, control blocks,
    non-BodyText storages, headers) is preserved byte-for-byte
    wherever possible.
    """
```

**구현 전략:**
- `_open_compound_file` 로 OleFileIO 열기
- 해당 `BodyText/SectionN` 스트림만 꺼내서 DEFLATE 해제
- PARA_TEXT 레코드를 순회하면서 N번째 것만 새 UTF-16LE 바이트로 교체
  - 기존 레코드 헤더의 tag/level 유지, size 필드만 새 페이로드 길이로 재계산
  - 페이로드 새 길이가 0xFFF 이상이면 extended size 헤더(+4 bytes) 재구성
  - 기존 레코드의 **control block** 구조는 그대로 유지 (새 텍스트는 제어문자 없다고 가정)
- 수정된 스트림을 다시 raw DEFLATE로 압축 (`zlib.compressobj(wbits=-15)`)
- OleFileIO는 스트림 교체 API가 제한적이므로 **전체 compound file 재조립**:
  - 옵션 A: `olefile` + 직접 CFBF 재작성 — 너무 큼, 범위 밖
  - 옵션 B (권장): 해당 스트림만 in-place로 교체하는 바이트 수준 패치
    - olefile의 내부 sector layout을 이용해 section 스트림의 sector 체인을 찾고,
    - 새 압축 데이터가 기존 sector 수 이하면 패치, 초과하면 FAT 확장 필요 (범위 밖)
  - 옵션 C (현실적): **동일 길이 보존이 어려우면 이 스파이크에서는 실패로 처리**
    - `raise Hwp5FormatError("In-place resize required; write path pending richer CFBF writer")`
    - 왕복 재현율 하네스에서 이 경우를 `xfail`로 표시

**최소 성공 조건:** 새 텍스트가 기존 UTF-16LE 바이트 길이와 **동일한 경우**
라도 in-place 교체가 동작하면 합격. 다른 모든 케이스는 명시적 실패 OK.

#### HWPX — `master_of_hwp/adapters/hwpx_reader.py`

```python
def replace_paragraph(
    raw_bytes: bytes,
    section_index: int,
    paragraph_index: int,
    new_text: str,
) -> bytes:
    """Return new raw bytes with the specified paragraph replaced."""
```

**구현 전략 (HWPX가 훨씬 쉽다):**
- `zipfile.ZipFile` 로 열고 모든 엔트리를 메모리에 복사
- 대상 `Contents/sectionN.xml` 파싱
- N번째 `<p>` element를 찾아서 자식 `<t>` 요소들 내용 재작성
  - 기존 `<t>` 하나가 있으면 `.text = new_text` 로 교체하고 나머지 `<t>` 는 제거
  - `<t>` 가 하나도 없으면 새로 만들어 추가 (첫 `<run>` 안에)
  - 기타 `<t>` 이외의 서식/컨트롤 요소는 그대로 유지
- 수정된 XML을 `ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)`
- 새 ZIP을 `zipfile.ZipFile(output, "w", ZIP_DEFLATED)` 로 재구성
  - 엔트리 순서 보존
  - 수정된 section XML만 교체, 나머지는 원본 바이트 그대로 `writestr`
- HWPX 쪽은 `xml_declaration=True` + UTF-8 인코딩이 중요 (한글 보존)

### 제출물 2: 왕복 재현율 하네스

#### 새 파일: `master_of_hwp/fidelity.py`

```python
"""Round-trip fidelity harness for HwpDocument.

Given raw_bytes, checks that various transformations (identity, no-op
replace) produce documents that re-parse to equivalent structure.
"""

from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class FidelityReport:
    sections_match: bool
    paragraphs_match: bool
    tables_match: bool
    edited_paragraph_applied: bool
    byte_size_delta: int  # bytes_after - bytes_before


def verify_identity_roundtrip(raw_bytes: bytes, source_format: SourceFormat) -> FidelityReport:
    """Parse then (conceptually) re-emit with no edits, verify equality."""
    ...


def verify_replace_roundtrip(
    raw_bytes: bytes,
    source_format: SourceFormat,
    section_index: int,
    paragraph_index: int,
    new_text: str,
) -> FidelityReport:
    """Apply replace_paragraph, re-parse result, verify invariants.

    Invariants:
        - sections_count unchanged
        - total paragraph count unchanged
        - all paragraphs except the edited one unchanged
        - edited paragraph text == new_text
        - tables_match (structure-level)
    """
    ...
```

구현은 기존 `extract_*` 함수들을 재사용. 순수 pure-Python, 외부 의존성 없음.

### 제출물 3: 테스트

`tests/unit/test_write_path.py` 신규 파일:

- `test_hwpx_replace_paragraph_noop_same_length()`:
  기존 문단 텍스트로 교체 → 왕복 검증 통과
- `test_hwpx_replace_paragraph_shorter()`:
  실 샘플의 한 문단을 더 짧은 한글로 교체 → 재파싱 시 해당 문단만 변경
- `test_hwpx_replace_paragraph_longer()`:
  더 긴 한글로 교체 → 다른 문단 불변
- `test_hwpx_replace_paragraph_out_of_range_raises()`:
  존재하지 않는 section/paragraph 인덱스 → `HwpxFormatError` 또는 `IndexError`
- `test_hwp5_replace_paragraph_same_length()`:
  HWP5 쪽은 same-length 케이스만 통과하면 OK (xfail 나머지)
- `test_hwp5_replace_paragraph_different_length_xfails()`:
  다른 길이 교체는 현재 스파이크 범위 밖 — `pytest.xfail`

## 인수 기준

- [ ] 두 어댑터에 `replace_paragraph` 추가 (HWP5는 제한적이어도 OK)
- [ ] `master_of_hwp/fidelity.py` 모듈 신규
- [ ] `tests/unit/test_write_path.py` 신규 (최소 5개 테스트, xfail 포함 OK)
- [ ] 전 품질 게이트 통과 (현재 50 → 55+ passed, xfail은 pass로 카운트됨)
- [ ] 외부 runtime 의존성 추가 금지 — stdlib + 기존 olefile만

## Out-of-Scope

- `HwpDocument.replace_paragraph` 통합 property — Claude가 후속 commit에서
- `insert_paragraph` / `delete_paragraph` — 후속 스파이크
- 표 셀 편집 — 후속 스파이크
- HWP5의 CFBF sector reallocation — 별도 스파이크

## 구현 힌트

### HWPX replace (핵심 코드 스케치)

```python
def replace_paragraph(raw_bytes, section_index, paragraph_index, new_text):
    if not raw_bytes:
        raise ValueError("HWPX raw_bytes must not be empty.")

    # Read all entries
    with zipfile.ZipFile(BytesIO(raw_bytes)) as archive:
        entries = [(i.filename, archive.read(i.filename), i) for i in archive.infolist()]
        section_names = _list_section_part_names(archive)

    if not (0 <= section_index < len(section_names)):
        raise HwpxFormatError(f"section_index {section_index} out of range")
    target_name = section_names[section_index]

    # Modify target section XML
    for idx, (name, data, info) in enumerate(entries):
        if name == target_name:
            new_xml = _replace_p_in_section(data, paragraph_index, new_text)
            entries[idx] = (name, new_xml, info)
            break

    # Re-zip
    out = BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for name, data, info in entries:
            dst.writestr(info, data)
    return out.getvalue()


def _replace_p_in_section(xml_bytes, paragraph_index, new_text):
    root = ElementTree.fromstring(xml_bytes)
    p_elements = [e for e in root.iter() if _local_name(e.tag) == "p"]
    if not (0 <= paragraph_index < len(p_elements)):
        raise HwpxFormatError(...)
    p = p_elements[paragraph_index]

    # Replace text in first <t>, remove rest
    t_elements = [e for e in p.iter() if _local_name(e.tag) == "t"]
    if t_elements:
        t_elements[0].text = new_text
        for extra in t_elements[1:]:
            parent = _find_parent(p, extra)  # need parent tracking
            parent.remove(extra)
    # else: would need to create a <t> — for spike, raise if paragraph has no <t>

    return ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)
```

HINT: `ElementTree` 는 parent tracking이 없어서 `{child: parent}` 맵을 미리
만들거나 `lxml` 이면 쉬운데 stdlib 고수면 순회로 찾기. 가장 간단: 각 `<p>`
노드 안에서만 제거하면 되므로 `_remove_extra_t_from_p(p)` 로 스코프 제한.

### 왕복 재현율 검증 스니펫

```python
def verify_replace_roundtrip(raw_bytes, source_format, section_index, paragraph_index, new_text):
    from master_of_hwp.adapters import hwpx_reader, hwp5_reader
    if source_format is SourceFormat.HWPX:
        before = hwpx_reader.extract_section_paragraphs(raw_bytes)
        edited = hwpx_reader.replace_paragraph(raw_bytes, section_index, paragraph_index, new_text)
        after = hwpx_reader.extract_section_paragraphs(edited)
    elif source_format is SourceFormat.HWP:
        before = hwp5_reader.extract_section_paragraphs(raw_bytes)
        edited = hwp5_reader.replace_paragraph(raw_bytes, section_index, paragraph_index, new_text)
        after = hwp5_reader.extract_section_paragraphs(edited)

    return FidelityReport(
        sections_match=len(before) == len(after),
        paragraphs_match=(
            all(len(b) == len(a) for b, a in zip(before, after))
        ),
        tables_match=True,  # structure-level only for now
        edited_paragraph_applied=(
            after[section_index][paragraph_index] == new_text
        ),
        byte_size_delta=len(edited) - len(raw_bytes),
    )
```

## 완료 후 할 일

1. `git mv handoff/codex/007_*.md handoff/codex/done/`
2. `handoff/review/007_review_write_path.md` 생성 — 각 제출물 상태 명시
   (3개 다 완성 vs 부분 완성 — 부분이어도 괜찮음)
3. 커밋: `feat(adapters,core): write-path spike — replace_paragraph + fidelity harness (spike #007)`
4. 트레일러 필수: Confidence / Scope-risk / Reversibility / Directive / Tested / Not-tested
5. `git push origin main`

## 스타일 가이드

- 기존 스타일 유지
- 새 예외 만들지 말고 `Hwp5FormatError` / `HwpxFormatError` 재사용
- `IndexError` 는 인덱스 범위 위반에 한해 OK
- `replace_paragraph` 는 **pure function** — raw_bytes 입력에 대해 새 bytes 반환
  (입력 수정 금지)
- Private helper는 `_name` 접두사
- `fidelity.py` 는 sync API만 (async 필요 없음)

## 중요: 부분 진행 정책

이 스파이크는 일부러 큽니다. 모두 끝내지 못해도 **부분 진행 + 솔직한
리뷰 요청**이 최선의 결과입니다. 예컨대:

- HWPX replace_paragraph ✅, HWP5 xfail, fidelity harness ✅, 테스트 5개 → 합격
- HWPX replace_paragraph ✅, HWP5 skip, fidelity harness 부분, 테스트 3개 → 합격 (리뷰 요청에 명시)
- 전부 실패 → 커밋하지 말고 리뷰 요청에 차단 사유 명시

커밋 트레일러의 `Not-tested:` 필드에 무엇을 남겼는지 꼼꼼히 기록해주세요.
