# RHWP 저장 실연동 가이드

## 현재 상태
읽기와 구조 추출은 실제 bridge 기반으로 동작한다.
저장도 현재 두 가지 방식으로 동작한다.

## 1. blank-document text export
- 세션의 최종 텍스트를 새 blank document에 삽입
- `exportHwp()` / `exportHwpx()`로 저장
- 텍스트 내용 저장은 가능하지만 원본 구조를 보존하지 않음

## 2. roundtrip operation replay
- 기존 원본 `.hwp/.hwpx`를 다시 로드
- 기록된 문단 치환/삽입 연산을 재적용
- `exportHwp()` / `exportHwpx()`로 저장

이 방식은 blank export보다 더 많은 원본 구조를 유지할 수 있다.

## 확인된 한계
현재 bridge에서 아래는 아직 지속적으로 저장되지 않는다.

- `createTable()`는 live document에서는 성공처럼 보이지만,
  export 후 다시 로드하면 테이블이 남아있지 않다.
- 따라서 **table creation roundtrip persistence는 아직 미지원**으로 본다.

## 현재 의미
즉 지금은 아래처럼 이해하면 된다.

- ✅ 유효한 `.hwp` / `.hwpx` 생성
- ✅ 수정 텍스트 저장
- ✅ 문단 치환/삽입에 대한 부분 구조 보존형 roundtrip save
- ✅ 실제 HWP/HWPX에서 table metadata 추출
- ❌ table creation roundtrip persistence
- ❌ 완전한 서식/표/개체 보존형 편집 저장

## 다음 목표
- table creation persistence가 왜 export 시 소실되는지 rhwp/@rhwp/core 레벨에서 원인 파악
- 표/서식/개체 편집 연산 replay 확대
- CLI 에이전트 실제 연결 검증
