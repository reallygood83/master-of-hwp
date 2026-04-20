---
id: 001
from: claude
to: codex
status: done
created: 2026-04-21
priority: high
---

# HWP 5.0 바이너리 포맷 파서 스파이크

## 목적

현재 `HwpDocument.open()`은 파일을 바이트로만 읽는다. 이 작업의 목표는 **HWP 5.0 바이너리 포맷**(Microsoft CFBF 기반)에서 **섹션/문단 수만 세는** 최소 파서를 작성하는 것이다. 전체 구조 해석은 추후 확장.

이것은 **스파이크(spike)** 다. 완벽한 파서가 아니라 "HWP 5.0의 내부에 접근 가능함"을 증명하고, `HwpDocument.sections_count` 속성의 근거 데이터를 만든다.

## In-Scope

1. `master_of_hwp/adapters/hwp5_reader.py` 신설
2. 다음 함수 구현:
   ```python
   def count_sections(raw_bytes: bytes) -> int:
       """Return the number of BodyText/Section streams in a HWP 5.0 file."""
   ```
3. `HwpDocument.open()`과 통합되는 선택적 속성 추가는 **하지 말 것** (Claude가 후속으로 수행)
4. 단위 테스트 `tests/unit/test_hwp5_reader.py` 최소 3 케이스:
   - 비어있는 바이트 → ValueError
   - 유효하지 않은 시그니처 → `Hwp5FormatError` (새 예외)
   - 샘플 파일(`samples/public-official/re-mixed-0tr.hwp`) → 양의 정수

## Out-of-Scope

- .hwpx (OOXML) 처리 — 이건 별도 어댑터
- 문단/표 내용 추출
- 쓰기/저장
- `HwpDocument` 수정

## 인수 기준

- [ ] `count_sections(raw_bytes)` 함수가 구현됨
- [ ] `Hwp5FormatError` 예외가 정의됨 (signature mismatch, corrupt CFBF 등)
- [ ] 모든 공개 심볼에 타입 힌트 + docstring
- [ ] 새 테스트 3개 전부 통과
- [ ] 기존 테스트 27개 전부 통과
- [ ] `ruff check master_of_hwp tests` 경고 0
- [ ] `black --check master_of_hwp tests` 통과

## 참고 자료

- HWP 5.0 공개 스펙: https://www.hancom.com/etc/hwpDownload.do
  - Compound File Binary Format (MS-CFB) 사용
  - "BodyText" 스토리지 아래 "Section0", "Section1", ... 스트림
- 기존 참고 구현:
  - `vendor/rhwp-main/` (Rust 파서)
  - `mcp-server/bridges/rhwp_extract.mjs` (node 바인딩)
- 외부 라이브러리 사용 가능:
  - `olefile` (CFBF 읽기) — 순수 파이썬, 의존성 낮음
  - → `pyproject.toml`의 dependencies에 추가 허용

## 테스트 요구사항

```python
# tests/unit/test_hwp5_reader.py
import pytest
from master_of_hwp.adapters.hwp5_reader import count_sections, Hwp5FormatError

def test_empty_bytes_raises():
    with pytest.raises((ValueError, Hwp5FormatError)):
        count_sections(b"")

def test_invalid_signature_raises():
    with pytest.raises(Hwp5FormatError):
        count_sections(b"NOT-A-HWP-FILE" * 100)

def test_real_sample_returns_positive(samples_dir):
    sample = samples_dir / "public-official" / "re-mixed-0tr.hwp"
    if not sample.exists():
        pytest.skip("sample missing")
    n = count_sections(sample.read_bytes())
    assert n >= 1
```

## 완료 후 할 일

1. 이 파일을 `handoff/codex/done/001_hwp_binary_parser_spike.md`로 이동
2. `git mv handoff/codex/001_*.md handoff/codex/done/`
3. 커밋 메시지: `feat(adapters): add minimal HWP 5.0 section counter (spike #001)`
4. `review/001_review_hwp5_reader.md` 파일 생성하여 Claude에게 리뷰 요청

## 스타일 가이드

- Python 3.11+ 기능 사용 가능
- `from __future__ import annotations` 사용
- 공개 함수는 반드시 docstring
- pure function 지향 — 전역 상태 없음
- 에러는 커스텀 예외로, 메시지에 맥락 포함
