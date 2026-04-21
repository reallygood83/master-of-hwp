---
id: 009
from: claude
to: codex
status: done
created: 2026-04-21
priority: high
size: medium
---

# HWPX 표 셀 편집

## 배경

v0.1.0 PyPI 배포 완료. 사용자(선생님)가 실제 필요하다고 지목한 기능 2가지:
1. **표 셀 내용 편집** ← 이번 작업
2. 자연어 편집 자동 루프 ← 다음 (#010)

실무 예시: 가정통신문 표에 학생별 이름/성적 자동 입력, 통계 보고서 수치 업데이트.

## 목적

HWPX 표의 **특정 셀 안 특정 문단**을 새 텍스트로 교체. 순수 함수 + 불변.
API 모양은 기존 `replace_paragraph` 와 대칭.

## In-Scope (3개 제출물)

### 1. `master_of_hwp/adapters/hwpx_reader.py`

```python
def replace_table_cell_paragraph(
    raw_bytes: bytes,
    section_index: int,
    table_index: int,
    row_index: int,
    cell_index: int,
    paragraph_index: int,
    new_text: str,
) -> bytes:
    """Return new raw bytes with the targeted table cell paragraph replaced.

    The rest of the document — other cells, other tables, non-table
    paragraphs, styles — is preserved byte-identical wherever possible
    (the ZIP is re-packed but target cell XML is the only section
    content change).
    """
```

**구현 전략 (기존 `replace_paragraph` 재사용):**

- `zipfile.ZipFile` 로 읽고 모든 엔트리 메모리 복사
- 대상 `Contents/sectionN.xml` 찾기 (`_list_section_part_names` 재사용)
- XML tree 순회하여 N번째 `<tbl>` → M번째 `<tr>` → K번째 `<tc>` → L번째 `<p>` 로 내려감
  - local name 비교 (`_local_name` 재사용)
  - 중첩 표 주의: `extract_section_tables` 와 동일한 "outer only" 정책 유지
- 기존 `_replace_p_in_section` 로직과 **동일한 `<p>` 변환** 적용
  - 첫 `<t>` 에 `new_text` 설정, 나머지 `<t>` 제거
  - `<t>` 없으면 새로 생성 (기존 정책)
- XML 재직렬화 + ZIP 재패킹

**새 helper 예상:**
```python
def _replace_p_in_table_cell(
    xml_bytes: bytes,
    table_index: int,
    row_index: int,
    cell_index: int,
    paragraph_index: int,
    new_text: str,
) -> bytes:
    ...
```

**에러:** 인덱스 범위 초과 → `IndexError`. 기타 → `HwpxFormatError`.

### 2. `master_of_hwp/core/document.py`

```python
def replace_table_cell_paragraph(
    self,
    section_index: int,
    table_index: int,
    row_index: int,
    cell_index: int,
    paragraph_index: int,
    new_text: str,
) -> Self:
    """Return a new HwpDocument with one table cell paragraph replaced.

    Only HWPX is supported in v0.2; HWP 5.0 raises NotImplementedError
    pending the richer write path (#012+).
    """
```

- HWPX → 어댑터 호출
- HWP 5.0 → `raise NotImplementedError("HWP 5.0 table cell editing pending v0.2.x")`

### 3. 테스트

#### `tests/unit/test_table_cell_write.py` (신규)

`table-vpos-01.hwpx` 샘플 기반:

- `test_replace_table_cell_paragraph_noop_same_length`:
  기존 셀 내용으로 교체 → 불변
- `test_replace_table_cell_paragraph_changes_target_cell`:
  셀 바꾼 후 `extract_section_tables` 로 확인
- `test_replace_table_cell_paragraph_preserves_other_cells`:
  바꾼 셀 외 모든 셀 불변 (지루하지만 중요)
- `test_replace_table_cell_paragraph_out_of_range_raises`:
  table_index / row_index / cell_index / paragraph_index 각각 초과 → `IndexError`

#### `tests/integration/test_document_table_edit.py` (신규)

- `HwpDocument.replace_table_cell_paragraph` 호출 성공 + 결과 검증
- HWP 5.0 경로 → `NotImplementedError`

## Out-of-Scope

- HWP 5.0 표 셀 편집 (HWP5 write path 전반이 제한적)
- 셀 **병합/분할** (structural change, 별도 스파이크)
- 셀 **삽입/삭제** (별도)
- 표 자체 추가/제거 (별도)
- 표 스타일 편집 (서식 레이어 - 훨씬 나중)

## 인수 기준

- [ ] 어댑터에 `replace_table_cell_paragraph` 추가
- [ ] 도메인 모델에 대응 메서드 추가
- [ ] 테스트 4+ 추가, 전 품질 게이트 통과 (현재 84 → 88+ passed)
- [ ] 외부 runtime 의존성 추가 금지

## 구현 힌트

### 중첩 표 대응

기존 `_tables_from_section_xml` 는 outer-only:
```python
for tbl in root.iter():
    if _local_name(tbl.tag) != "tbl":
        continue
    # ... 그 tbl 은 descendant tbl 은 수집 안 함
```

이 정책을 write 쪽에서도 **동일하게** 유지해야 함 (read 인덱스와 write 인덱스가 일치해야 함).

즉, `table_index` 는 "outer table 카운터". 내부 중첩 표는 write 대상 아님 (v0.2.x 이후).

### XML 재직렬화 + UTF-8 + xml_declaration

```python
ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)
```

HWPX는 UTF-8 XML이므로 이게 깨지면 한글 다 날아감. 기존 코드와 동일하게.

### ZIP 재패킹 시 원본 엔트리 순서/타임스탬프

순서 보존하되 타임스탬프는 현재 시간으로 OK (재생성 타임스탬프가 fidelity에 영향 안 줌 — 원래 `extract_section_tables` 결과가 일치하면 pass).

## 완료 후 할 일

1. `git mv handoff/codex/009_*.md handoff/codex/done/`
2. `handoff/review/009_review_table_cell_edit.md` 생성
3. 커밋: `feat(adapters,core): replace_table_cell_paragraph for HWPX (spike #009)`
4. 트레일러 필수: Confidence / Scope-risk / Reversibility / Directive / Tested / Not-tested
5. `git push origin main`

## 스타일

- 기존 HWPX write path 스타일 유지
- `_replace_p_in_section` 과 helper 공유 가능하면 공유 (중복 제거)
- Private helper는 `_name` 접두사
- 공개 심볼 타입 힌트 + docstring 100%
