---
id: 002
from: claude
to: codex
status: pending
created: 2026-04-21
priority: high
---

# HWPX (OOXML/ZIP) 섹션 리더 스파이크

## 목적

HWP 5.0 바이너리 쪽은 spike #001에서 `count_sections()`를 확보했다. 이 작업은 동일한 계약을 **HWPX (OOXML/ZIP)** 포맷에서도 확보하는 것이 목표다. 이후 `HwpDocument.sections_count`는 `source_format`에 따라 두 어댑터로 분기될 것이다.

이것은 **스파이크(spike)** 다. 전체 OOXML 스펙 해석이 아니라 "HWPX의 내부에 접근 가능함"을 증명하고, 섹션 수를 센다.

## 배경: HWPX 구조

HWPX 파일은 ZIP 컨테이너다. 내부에 다음과 같은 구조를 가진다:

```
container.zip
├── mimetype                      → "application/hwp+zip" (또는 유사)
├── META-INF/
│   └── container.xml             → 루트 파트 선언
├── Contents/
│   ├── content.hpf               → package manifest (OPF 유사)
│   ├── header.xml                → 문서 header (style, bindata 등)
│   ├── section0.xml              ← 이게 섹션!
│   ├── section1.xml              ← 그리고 이것도
│   └── ... (sectionN.xml)
└── BinData/                      → 임베드된 이미지/오브젝트
```

즉 `Contents/` 디렉토리 안의 `section*.xml` 파일 수를 세면 된다.

단, 스펙마다 변형이 있을 수 있으므로:
- **1차 시도**: `Contents/section*.xml` 패턴 파일 카운트
- **fallback**: `Contents/content.hpf`를 XML 파싱해 `<spine>` 또는 `<manifest>`에서 `section` 참조 카운트
- 1차 시도로 0이 나오면 fallback 사용

## In-Scope

1. `master_of_hwp/adapters/hwpx_reader.py` 신설
2. 다음 함수 구현:
   ```python
   def count_sections(raw_bytes: bytes) -> int:
       """Return the number of section XML parts in a HWPX file."""
   ```
3. 새 예외 `HwpxFormatError(ValueError)` 정의
4. 단위 테스트 `tests/unit/test_hwpx_reader.py` 최소 3 케이스:
   - 비어있는 바이트 → ValueError
   - ZIP이 아닌 바이트 → `HwpxFormatError`
   - 실 샘플 (`samples/public-official/table-vpos-01.hwpx`) → 양의 정수

## Out-of-Scope

- .hwp 바이너리 처리 — Codex가 #001에서 완료했음
- 섹션 본문 파싱, 텍스트 추출
- 쓰기/저장
- `HwpDocument` 통합 — Claude가 #003에서 수행
- `master_of_hwp/adapters/__init__.py`의 re-export — Claude가 별도 커밋에서 처리

## 인수 기준

- [ ] `count_sections(raw_bytes)` 함수가 구현됨 (동일한 시그니처: `bytes -> int`)
- [ ] `HwpxFormatError` 예외가 정의됨
- [ ] 모든 공개 심볼에 타입 힌트 + docstring
- [ ] 새 테스트 3개 전부 통과
- [ ] 기존 테스트 30개 전부 통과
- [ ] `ruff check master_of_hwp tests` 경고 0
- [ ] `black --check master_of_hwp tests` 통과
- [ ] `python -c "from master_of_hwp.adapters.hwpx_reader import count_sections, HwpxFormatError"` 성공

## 계약 일관성 (중요)

`hwp5_reader.count_sections`와 **동일한 행동 규칙**을 따를 것:

- 빈 바이트 → `ValueError`
- 포맷 불일치 → 커스텀 Format 예외 (Hwp5FormatError ↔ HwpxFormatError)
- 섹션이 0개 → 포맷 예외 (빈 문서는 유효하지 않은 HWPX로 간주)
- 반환값은 항상 `int >= 1`

이 일관성 덕분에 `HwpDocument.sections_count`가 분기만 하면 되고, 에러 처리 방식이 통일된다.

## 의존성 허용

- 표준 라이브러리 `zipfile` 사용 (추가 패키지 불필요)
- 필요시 `xml.etree.ElementTree` 사용 (표준 라이브러리)
- **새 runtime 의존성 추가 금지** — pure stdlib로 충분해야 함

## 구현 힌트 (참고용, 강제 아님)

```python
from __future__ import annotations

import re
import zipfile
from io import BytesIO

_SECTION_PATTERN = re.compile(r"Contents/section\d+\.xml", re.IGNORECASE)


class HwpxFormatError(ValueError):
    """Raised when raw bytes are not a readable HWPX/ZIP document."""


def count_sections(raw_bytes: bytes) -> int:
    if not raw_bytes:
        raise ValueError("HWPX raw_bytes must not be empty.")
    try:
        with zipfile.ZipFile(BytesIO(raw_bytes)) as zf:
            names = zf.namelist()
    except zipfile.BadZipFile as exc:
        raise HwpxFormatError(f"Not a valid HWPX (ZIP) container: {exc}") from exc

    section_count = sum(1 for name in names if _SECTION_PATTERN.fullmatch(name))
    if section_count < 1:
        raise HwpxFormatError("HWPX container has no Contents/sectionN.xml entries.")
    return section_count
```

## 테스트 요구사항

```python
# tests/unit/test_hwpx_reader.py
import pytest
from master_of_hwp.adapters.hwpx_reader import count_sections, HwpxFormatError


@pytest.mark.unit
def test_empty_bytes_raises_value_error() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        count_sections(b"")


@pytest.mark.unit
def test_non_zip_raises_hwpx_format_error() -> None:
    with pytest.raises(HwpxFormatError):
        count_sections(b"NOT-A-ZIP-FILE" * 100)


@pytest.mark.unit
def test_real_sample_returns_positive_section_count(samples_dir) -> None:
    sample = samples_dir / "public-official" / "table-vpos-01.hwpx"
    if not sample.exists():
        pytest.skip("sample missing")
    assert count_sections(sample.read_bytes()) >= 1
```

## 완료 후 할 일

1. 이 파일을 `handoff/codex/done/002_hwpx_zip_reader.md`로 이동
2. `git mv handoff/codex/002_*.md handoff/codex/done/`
3. 커밋 메시지: `feat(adapters): add minimal HWPX section counter (spike #002)`
4. 필요시 `handoff/review/002_review_hwpx_reader.md` 생성하여 Claude에게 리뷰 요청

## 스타일 가이드

- Python 3.11+ 기능 사용 가능
- `from __future__ import annotations` 사용
- 공개 함수는 반드시 docstring
- pure function 지향 — 전역 상태 없음
- 에러는 커스텀 예외로, 메시지에 맥락 포함
- **`hwp5_reader.py`의 스타일/구조를 거울처럼 따라갈 것** (후속 통합이 쉬워짐)
