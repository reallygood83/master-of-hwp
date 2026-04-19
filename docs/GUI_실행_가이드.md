# GUI 실행 가이드

## 현재 GUI 성격
현재 GUI는 완성형 에디터가 아니라,
`master-of-hwp` MCP 코어를 로컬에서 직접 검증하기 위한 **로컬 웹 워크벤치**다.

## 실행
프로젝트 루트에서:

```bash
./scripts/run_gui.sh
```

기본 접속 주소:

```text
http://127.0.0.1:8876
```

## 환경변수
### 포트 변경
```bash
MASTER_OF_HWP_GUI_PORT=8899 ./scripts/run_gui.sh
```

### 로컬 파일 허용 범위
기본적으로 사용자 홈 디렉터리(`$HOME`)를 열 수 있다.
필요하면 범위를 좁힐 수 있다.

```bash
MASTER_OF_HWP_ALLOWED_WORKSPACE=/Users/moon/Documents ./scripts/run_gui.sh
```

## 현재 가능한 것
- 상태 확인
- 로컬 파일 브라우저로 HWP/HWPX/TXT/MD 탐색
- 문서 열기
- 텍스트 추출
- 구조 추출
- 문단 치환
- 문단 삽입
- 저장
- 저장본 검증

## 사용 흐름
1. 왼쪽 상단의 "로컬 문서 찾기"에서 폴더를 탐색한다.
2. HWP/HWPX 파일을 클릭하면 파일 경로가 자동으로 채워진다.
3. "문서 열기"를 눌러 세션을 만든다.
4. "텍스트 추출" 또는 "구조 추출"로 현재 문서 상태를 확인한다.
5. 문단 인덱스를 넣고 치환/삽입을 실행한다.
6. 저장 경로를 확인한 뒤 저장하고, 저장본 검증을 실행한다.

## 현재 한계
- GUI는 현재 MCP tool을 직접 호출하는 local web shell이다.
- 시각적 문서 렌더링 편집기까지는 아니다.
- 결과 창은 현재 JSON 중심이다.
- table creation roundtrip persistence는 아직 실패 상태다.
