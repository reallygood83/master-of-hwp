# RHWP 실연동 가이드

## 현재 상태
현재 `master-of-hwp`는 Claude Code 기반 MCP 에디터 코어는 구현되어 있지만,
실제 `.hwp` / `.hwpx` 추출은 아직 로컬 rhwp 명령에 연결되지 않았다.

## 준비 조건
아래 중 하나가 필요하다.

1. 로컬에서 직접 실행 가능한 `rhwp` 추출 명령
2. 또는 rhwp를 호출하는 별도 파이썬 래퍼 스크립트

## 필요한 환경변수
`RHWP_EXTRACT_COMMAND`

이 값은 반드시 아래 placeholder를 포함해야 한다.
- `{input}`
- `{include_tables}`

예시 형태:

```bash
export RHWP_EXTRACT_COMMAND='python3 /Users/moon/Desktop/master-of-hwp/scripts/rhwp_extract_template.py --input {input} --include-tables {include_tables}'
```

## 확인 방법
MCP에서 `rhwp_integration_status` tool을 호출하면 현재 상태를 확인할 수 있다.

확인 항목:
- 환경변수 설정 여부
- placeholder 포함 여부
- `rhwp` / `rhwp-studio` 실행 파일 존재 여부
- 현재 허용 workspace 경로

## 현재 권장 순서
1. 실제 rhwp 추출 명령 확보
2. `RHWP_EXTRACT_COMMAND` 설정
3. `.hwp` 샘플 파일로 `extract_document_text(path=...)` 테스트
4. 그 다음 `.hwp` 구조 추출과 저장 루트 구현
