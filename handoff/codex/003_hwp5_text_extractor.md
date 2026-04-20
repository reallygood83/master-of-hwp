---
id: 003
from: claude
to: codex
status: pending
created: 2026-04-21
priority: high
---

# HWP 5.0 섹션 텍스트 추출 스파이크

## 배경 / 진행 상태

- 스파이크 #001 (HWP 5.0 섹션 카운트) — ✅ 완료
- 스파이크 #002 (HWPX 섹션 카운트) — ✅ 완료
- 통합 #003 (`HwpDocument.sections_count`) — ✅ Claude 완료 (commit `fcf76a6`)

이제 "몇 섹션인지"는 알 수 있다. 다음 단계는 **"각 섹션 안에 무엇이 쓰여 있는지"** 를 읽는 것.

## 목적

HWP 5.0 `BodyText/SectionN` 스트림에서 **평문 텍스트만 추출**하는 최소 파서를 작성한다.
완벽한 문서 모델이 아니라, "텍스트에 접근 가능함"을 증명하는 **스파이크**다.

이 결과물은 향후 `HwpDocument.plain_text` 속성과 AI 계층의 "이 섹션 요약해줘" 계열 작업의 기초가 된다.

## In-Scope

1. `master_of_hwp/adapters/hwp5_reader.py` 에 함수 추가:
   ```python
   def extract_section_texts(raw_bytes: bytes) -> list[str]:
       """Return the plain text of each BodyText/Section stream, one string per section."""
   ```
2. HWP 5.0 섹션 스트림은 **zlib 압축된 레코드 시퀀스**임을 반영
3. 최소 구현: 레코드 순회하며 `PARA_TEXT` (tag_id 0x43) 레코드만 추출
4. 단위 테스트 추가 (`tests/unit/test_hwp5_reader.py`):
   - 유효하지 않은 바이트 → 기존 예외 재사용
   - 실 샘플 (`samples/public-official/re-mixed-0tr.hwp`) → `len(texts) == count_sections(bytes)` 이고, 모든 요소가 `str` 이며, 적어도 하나는 비어 있지 않음

## Out-of-Scope

- 서식(폰트/크기/컬러)
- 표/그림/각주 재구성
- HWPX 쪽 텍스트 추출 — 별도 스파이크 #004
- `HwpDocument.plain_text` 통합 — Claude 후속

## 인수 기준

- [ ] `extract_section_texts(raw_bytes)` 구현 완료
- [ ] 반환 길이가 `count_sections(raw_bytes)` 와 항상 일치
- [ ] 모든 공개 심볼에 타입 힌트 + docstring
- [ ] 기존 36개 테스트 + 새 테스트 전부 통과
- [ ] `ruff`, `black`, `mypy strict` 전부 통과

## 참고 자료

- HWP 5.0 스펙 (한글과컴퓨터 공개): Section stream = zlib deflate(raw) of records
- 레코드 포맷: `tag_id(10bit) | level(10bit) | size(12bit)` header (4 bytes, little-endian)
- `PARA_TEXT` (0x43) = UTF-16LE 인코딩 텍스트
- 참고 구현: `vendor/rhwp-main/` (Rust 파서)
- 외부 라이브러리 추가 금지 — zlib는 stdlib

## 구현 힌트 (참고용)

```python
import zlib
from io import BytesIO
import olefile

def _decompress_section(raw: bytes) -> bytes:
    # HWP 5.0 Section streams use raw DEFLATE (no zlib header)
    # Try with -15 window bits first
    try:
        return zlib.decompress(raw, wbits=-15)
    except zlib.error:
        return zlib.decompress(raw)  # fallback

def _iter_records(stream: bytes):
    i = 0
    while i + 4 <= len(stream):
        header = int.from_bytes(stream[i:i+4], "little")
        tag_id = header & 0x3FF
        level = (header >> 10) & 0x3FF
        size = (header >> 20) & 0xFFF
        i += 4
        if size == 0xFFF:  # extended size
            size = int.from_bytes(stream[i:i+4], "little")
            i += 4
        payload = stream[i:i+size]
        i += size
        yield tag_id, level, payload
```

## 완료 후 할 일

1. `git mv handoff/codex/003_*.md handoff/codex/done/`
2. 상태를 `done` 으로 변경
3. 커밋 트레일러 형식은 #002와 동일하게:
   `Confidence / Scope-risk / Reversibility / Directive / Tested / Not-tested`
4. `handoff/review/003_review_*.md` 생성

## 스타일 가이드

- `hwp5_reader.py`의 기존 스타일 그대로
- Private helper는 `_name` 접두사
- 예외는 기존 `Hwp5FormatError` 재사용 (새 예외 만들지 말 것 — 에러 도메인 단일화)
