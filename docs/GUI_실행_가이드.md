# GUI 실행 가이드

## 현재 GUI 성격
현재 GUI는 완성형 에디터가 아니라,
`master-of-hwp` MCP 코어를 로컬에서 직접 검증하기 위한 **얇은 로컬 웹 쉘**이다.

## 실행
프로젝트 루트에서:

```bash
./scripts/run_gui.sh
```

기본 접속 주소:

```text
http://127.0.0.1:8876
```

## 환경변수로 포트 변경
```bash
MASTER_OF_HWP_GUI_PORT=8899 ./scripts/run_gui.sh
```

## 현재 가능한 것
- 상태 확인
- 문서 열기
- 텍스트 추출
- 구조 추출
- 문단 치환
- 문단 삽입
- 저장
- 저장본 검증

## 현재 한계
- GUI는 현재 MCP tool을 직접 호출하는 local web shell이다.
- 시각적 문서 렌더링 편집기까지는 아니다.
- table creation roundtrip persistence는 아직 실패 상태다.
