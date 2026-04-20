---
id: 006
from: claude
to: codex
status: done
created: 2026-04-21
priority: high
---

# 표(Table) 열거 (HWP5 + HWPX)

## 배경 / 진행 상태

- #001 HWP5 섹션 카운트 ✅
- #002 HWPX 섹션 카운트 ✅
- #003 HWP5 섹션 텍스트 ✅
- #004 HWPX 섹션 텍스트 ✅
- #005 HWP5 + HWPX 문단 열거 ✅
- #006 **이 작업** — HWP5 + HWPX **표(Table)** 열거

ROADMAP.md Phase 1의 `tables` 목표를 해금합니다. Read-path의 마지막
구조 항목입니다 (이후 write path로 넘어갑니다).

## 목적

각 섹션에서 표를 찾아내어 **행×열×셀텍스트** 형태로 노출.

## In-Scope

### 1. HWP5 쪽 — `master_of_hwp/adapters/hwp5_reader.py`

```python
def extract_section_tables(raw_bytes: bytes) -> list[list[list[list[str]]]]:
    """Return tables per section.

    Returns:
        Outermost list: one entry per BodyText/SectionN stream
            (len == count_sections).
        Level 2: one entry per table in that section.
        Level 3: rows.
        Level 4: cells, each as a list of paragraph strings
            (reusing the spike #005 paragraph contract).
    """
```

- HWP 5.0 record 구조에서 `TABLE` 레코드(`tag_id = 0x5B`, 91)를 찾고,
  그 아래의 `LIST_HEADER` + `PARA_HEADER`/`PARA_TEXT` 트리를 파싱
- 현재 `_iter_records`는 tag/level/payload를 내뱉는데 level은 **레코드
  depth**라서 같은 level의 인접 레코드를 한 table로 묶을 수 있음
- 구현이 복잡하면 **최소 구현**도 OK:
  1) table 레코드 카운트만 먼저 반환
  2) 셀 텍스트 추출은 "이 table에 소속된 다음 N개의 PARA_TEXT" 휴리스틱
  3) row/col 정확도는 `Not-tested:` 트레일러로 문서화
- 샘플이 안 맞으면 실패하더라도 "[[[]]]" 같은 빈 구조 반환 금지 → `[]`
  (= "이 섹션에 표 없음")

### 2. HWPX 쪽 — `master_of_hwp/adapters/hwpx_reader.py`

```python
def extract_section_tables(raw_bytes: bytes) -> list[list[list[list[str]]]]:
    # Same shape as above.
```

- HWPX는 훨씬 쉬움: local name이 `tbl`인 element를 찾고, 그 안의
  `tr` (또는 local name `tr`), `tc` (cell) 순으로 내려감
- 각 셀 안의 `<p>` 는 #005 의 `_iter_paragraph_text_nodes` 로직 재사용
- namespace는 항상 무시 (local name 비교)

### 3. 테스트

- `tests/unit/test_hwp5_reader.py`:
  - 빈 바이트 → `ValueError`
  - `re-mixed-0tr.hwp` 로 호출 → outer len == count_sections (표 없으면 `[[]]` OK)
  - 호출 성공 + 타입 일치면 통과 (정확도는 이번 스파이크 범위 밖)

- `tests/unit/test_hwpx_reader.py`:
  - 빈 바이트 → `ValueError`
  - `table-vpos-01.hwpx` (이름에 table 들어감!) → 적어도 하나의 표,
    표는 행≥1, 셀≥1 이어야 함
  - 셀 내 paragraph 스트링이 전부 `str`

## Out-of-Scope

- 셀 병합(merge/span) 처리 — 메타데이터는 나중에
- 표 스타일, 너비, 테두리
- 중첩 표(표 안의 표)는 best-effort

## 인수 기준

- [ ] 두 어댑터 모두에 `extract_section_tables` 추가
- [ ] 외측 리스트 길이 == `count_sections(raw_bytes)` 항상
- [ ] 모든 공개 심볼에 타입 힌트 + docstring
- [ ] `ruff`, `black`, `mypy strict`, `pytest` 전부 통과 (현재 46 → 50+ passed)
- [ ] 외부 runtime 의존성 추가 금지

## 구현 힌트 (참고용)

### HWP5 — 최소 구현 전략

```python
_TABLE_TAG_ID = 0x5B  # TABLE record

def extract_section_tables(raw_bytes: bytes) -> list[list[list[list[str]]]]:
    if not raw_bytes:
        raise ValueError("HWP raw_bytes must not be empty.")
    try:
        with _open_compound_file(raw_bytes) as cf:
            sections = _list_section_streams(cf)
            return [
                _extract_tables_from_section(
                    cf.openstream(["BodyText", name]).read()
                )
                for name in sections
            ]
    except OSError as exc:
        raise Hwp5FormatError(...) from exc
    except OleFileError as exc:
        raise Hwp5FormatError(...) from exc


def _extract_tables_from_section(raw_section: bytes) -> list[list[list[list[str]]]]:
    # Minimal: just count TABLE records and return empty [[[]]] per table.
    # Better: walk records by level to group rows/cells.
    ...
```

### HWPX

```python
def extract_section_tables(raw_bytes: bytes) -> list[list[list[list[str]]]]:
    if not raw_bytes:
        raise ValueError("HWPX raw_bytes must not be empty.")
    try:
        with zipfile.ZipFile(BytesIO(raw_bytes)) as archive:
            names = _list_section_part_names(archive)
            return [_tables_from_section_xml(archive.read(n)) for n in names]
    except zipfile.BadZipFile as exc:
        raise HwpxFormatError(...) from exc


def _tables_from_section_xml(xml_bytes: bytes) -> list[list[list[str]]]:
    root = ElementTree.fromstring(xml_bytes)
    tables = []
    for tbl in root.iter():
        if _local_name(tbl.tag) != "tbl":
            continue
        rows = []
        for tr in tbl.iter():
            if _local_name(tr.tag) != "tr":
                continue
            cells = []
            for tc in tr.iter():
                if _local_name(tc.tag) != "tc":
                    continue
                cell_paras = [
                    "".join(_iter_paragraph_text_nodes(p))
                    for p in tc.iter()
                    if _local_name(p.tag) == "p"
                ]
                cells.append(cell_paras)
            rows.append(cells)
        tables.append(rows)
    return tables
```

주의: `.iter()` 는 nested table을 중복 수집할 수 있음. 필요하면
**직계 자식만** (`list(element)` + 재귀) 로 바꾸는 게 안전.

## 완료 후 할 일

1. `git mv handoff/codex/006_*.md handoff/codex/done/`
2. `handoff/review/006_review_table_enumeration.md` 생성
3. 커밋: `feat(adapters): enumerate tables per section (spike #006)`
4. 트레일러: `Confidence / Scope-risk / Reversibility / Directive / Tested / Not-tested`
5. `git push origin main`

## 스타일 가이드

- 두 어댑터의 기존 스타일 유지
- 새 예외 만들지 말고 기존 에러 재사용
- Private helper는 `_name` 접두사
- HWP5 표 파싱이 애매하면 **최소 구현 + Not-tested 트레일러** 전략
