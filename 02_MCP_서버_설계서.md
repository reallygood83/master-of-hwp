# master-of-hwp MCP 서버 설계서

- 작성일: 2026-04-19
- 프로젝트: master-of-hwp
- 문서 목적: rhwp 기반 HWP/HWPX 처리 기능을 AI 에이전트가 안전하고 일관되게 호출할 수 있도록, MCP 서버의 구조와 도구 명세를 정의한다.

---

## 1. 문서 개요

이 설계서는 master-of-hwp의 핵심 연결부인 **MCP 서버**를 정의한다.

이 서버의 역할은 단순하다.

- AI는 자연어를 이해한다.
- rhwp는 HWP 문서를 읽고 수정한다.
- MCP 서버는 둘 사이를 이어준다.

즉,

> **AI가 HWP 문서를 다루기 위해 호출하는 공식 인터페이스가 MCP 서버다.**

이 문서에서는 아래를 정리한다.

1. MCP 서버의 목적과 범위
2. 전체 아키텍처
3. Tool 설계 원칙
4. 1차 구현 Tool 목록
5. 각 Tool의 입력/출력 명세
6. 에러 처리 방식
7. 보안 및 개인정보 처리 원칙
8. 공무원/교사 특화 시나리오 연결 방식
9. 구현 단계와 남은 쟁점

---

## 2. 설계 목표

이번 MCP 서버 설계의 목표는 다음과 같다.

### 목표 1. AI가 HWP 문서를 읽을 수 있게 한다
- 문서 전체 텍스트 추출
- 문단/섹션/표 구조 추출
- 문서 기반 질의응답 준비

### 목표 2. AI가 HWP 문서를 제한적으로 수정할 수 있게 한다
- 특정 위치 텍스트 치환
- 문단 삽입
- 새 파일 저장

### 목표 3. AI가 표 같은 구조를 생성할 수 있게 한다
- 정형 표 생성
- 셀 데이터 채우기
- 일정표/비교표/기록표 형태 대응

### 목표 4. 초기에는 안전성과 예측 가능성을 우선한다
- 자유도가 높은 범용 수정보다,
  **성공률 높은 구조화된 도구 호출**을 먼저 제공한다.

---

## 3. 설계 범위

## 3.1 1차 범위 (이번 설계의 직접 대상)
- HWP/HWPX 파일 열기
- 텍스트 추출
- 문서 구조 추출
- 특정 위치 텍스트 수정
- 문단 삽입
- 간단한 표 생성
- 다른 이름으로 저장

## 3.2 2차 범위 (후속 확장)
- 선택 영역 기반 재작성
- 표 스타일링
- 템플릿 기반 새 문서 생성
- 문서 비교
- 섹션 단위 복제/이동
- 웹 UI 연동

## 3.3 현재 범위에서 제외
- 고급 그래프/차트 직접 생성
- 도형/개체 복잡 제어
- 모든 서식 완전 보존
- 협업 승인 워크플로우
- 사용자 계정/기관 관리

---

## 4. 전체 아키텍처

```text
[사용자]
   ↓ 자연어 요청
[Claude Code CLI / Codex CLI]
   ↓ MCP Tool 호출
[master-of-hwp MCP Server]
   ↓ 내부 Adapter 호출
[rhwp Wrapper Layer]
   ↓ 문서 처리
[HWP/HWPX 파일]
```

---

## 5. 구성 요소 설명

## 5.1 AI 클라이언트 계층
대상:
- Claude Code CLI
- Codex CLI

역할:
- 사용자의 자연어를 해석
- 어떤 Tool을 어떤 순서로 호출할지 결정
- Tool 결과를 다시 사용자 친화적인 응답으로 정리

이 계층은 “생각”을 담당하고,
MCP 서버는 “실행”을 담당한다.

## 5.2 MCP 서버 계층
역할:
- AI가 호출할 Tool 제공
- 입력 검증
- 문서 위치 계산
- rhwp 래퍼 호출
- 결과 JSON 응답 반환

이 계층은 **AI 친화적 API 표면**을 제공해야 한다.

## 5.3 rhwp Wrapper 계층
역할:
- rhwp CLI 또는 라이브러리 호출 추상화
- 파일 열기/저장/구조 읽기/수정 수행
- 내부 에러를 MCP 응답용 에러로 변환

직접 rhwp를 MCP tool에 바로 노출하기보다,
중간 래퍼 계층을 두는 것이 좋다.

이유:
- 내부 구현 교체가 쉬움
- 에러 처리 표준화 가능
- 테스트가 쉬움
- 추후 SaaS 전환 시 재사용 가능

---

## 6. 구현 언어 선택

## 6.1 1차 추천
**Python + FastMCP**

이유:
- 프로토타입 속도가 빠름
- subprocess/파일 처리 래핑이 편함
- Tool 정의가 직관적임
- PoC 단계에 적합함

## 6.2 2차 대안
**TypeScript + MCP SDK**

이유:
- 향후 웹 확장과 연결성이 좋음
- rhwp-studio와의 통합 맥락이 자연스러움

## 6.3 현재 판단
- **PoC는 Python으로 시작**
- **제품 확장 시 TypeScript 재검토**

---

## 7. 설계 원칙

### 원칙 1. Tool은 작고 명확해야 한다
Tool 하나가 너무 많은 일을 하면 AI가 실수하기 쉽다.

예:
- 좋은 예: `extract_document_text`, `create_table`
- 나쁜 예: `do_anything_on_document`

### 원칙 2. 위치 지정은 일관되어야 한다
문서 수정 Tool은 항상 같은 방식으로 위치를 지정해야 한다.

예:
- 문단 인덱스 기반
- 섹션 ID 기반
- 표 ID 기반

### 원칙 3. 모든 수정은 저장 전 검증 가능해야 한다
가능하면 아래 흐름이 좋다.

1. 구조 읽기
2. 수정 요청
3. 결과 저장
4. 저장 파일 검증

### 원칙 4. 원본 파일을 함부로 덮어쓰지 않는다
초기 단계에서는 반드시 **save_as 중심**으로 간다.

### 원칙 5. 에러는 AI가 해석하기 쉬워야 한다
단순한 stack trace보다,
“무슨 문제가 발생했고 다음에 무엇을 시도해야 하는지”가 보여야 한다.

---

## 8. 데이터 모델 초안

## 8.1 DocumentHandle
문서 세션 또는 문서 식별용 객체

```json
{
  "document_id": "doc_001",
  "path": "/path/to/file.hwp",
  "format": "hwp",
  "readonly": false
}
```

## 8.2 ParagraphRef
문단 참조 구조

```json
{
  "paragraph_index": 12,
  "section_index": 2
}
```

## 8.3 TableRef
표 참조 구조

```json
{
  "table_id": "table_002",
  "section_index": 1,
  "table_index": 0
}
```

## 8.4 ToolResult 기본 구조

```json
{
  "ok": true,
  "message": "text extracted successfully",
  "data": {}
}
```

실패 시:

```json
{
  "ok": false,
  "error_code": "INVALID_POSITION",
  "message": "paragraph_index 999 is out of range",
  "suggestion": "call extract_document_structure first"
}
```

---

## 9. 1차 Tool 목록

1차 구현에서는 아래 Tool을 우선 제공한다.

1. `open_document`
2. `extract_document_text`
3. `extract_document_structure`
4. `replace_paragraph_text`
5. `insert_paragraph_after`
6. `create_table`
7. `fill_table_cells`
8. `save_as`
9. `validate_document`

---

## 10. Tool 상세 명세

## 10.1 `open_document`

### 목적
문서 파일을 열고 이후 Tool 호출에 필요한 문서 식별 정보를 반환한다.

### 입력
```json
{
  "path": "/absolute/path/to/file.hwp",
  "readonly": true
}
```

### 출력
```json
{
  "ok": true,
  "message": "document opened",
  "data": {
    "document_id": "doc_001",
    "path": "/absolute/path/to/file.hwp",
    "format": "hwp",
    "readonly": true
  }
}
```

### 검증 규칙
- path는 절대경로여야 함
- 파일 존재 여부 확인
- 확장자 또는 실제 포맷 확인
- readonly가 true면 수정 Tool 차단

---

## 10.2 `extract_document_text`

### 목적
문서 전체 텍스트를 AI 분석용으로 추출한다.

### 입력
```json
{
  "document_id": "doc_001",
  "include_tables": true,
  "max_chars": 50000
}
```

### 출력
```json
{
  "ok": true,
  "message": "text extracted",
  "data": {
    "text": "문서 전체 내용...",
    "char_count": 12432,
    "paragraph_count": 85,
    "truncated": false
  }
}
```

### 주의사항
- 너무 긴 문서는 truncate 여부 표시
- 표 텍스트 포함 여부 명확히 표시
- 후속 RAG용으로 paragraph_count 제공

---

## 10.3 `extract_document_structure`

### 목적
문서 수정과 정밀 질의응답을 위해 구조 정보를 추출한다.

### 입력
```json
{
  "document_id": "doc_001",
  "include_paragraphs": true,
  "include_tables": true,
  "include_headings": true
}
```

### 출력 예시
```json
{
  "ok": true,
  "message": "structure extracted",
  "data": {
    "sections": [
      {
        "section_index": 0,
        "title": "1. 사업 개요"
      }
    ],
    "paragraphs": [
      {
        "paragraph_index": 0,
        "section_index": 0,
        "text_preview": "본 사업은..."
      }
    ],
    "tables": [
      {
        "table_id": "table_001",
        "section_index": 0,
        "rows": 4,
        "cols": 3
      }
    ]
  }
}
```

### 설계 포인트
- 수정 Tool은 이 구조 결과를 기준으로 동작함
- AI가 위치를 추정하지 않도록 유도해야 함

---

## 10.4 `replace_paragraph_text`

### 목적
특정 문단의 내용을 통째로 교체한다.

### 입력
```json
{
  "document_id": "doc_001",
  "paragraph_index": 12,
  "new_text": "수정된 문단 내용입니다.",
  "preserve_style": true
}
```

### 출력
```json
{
  "ok": true,
  "message": "paragraph replaced",
  "data": {
    "paragraph_index": 12,
    "old_length": 83,
    "new_length": 42
  }
}
```

### 검증 규칙
- paragraph_index 범위 확인
- readonly 문서 차단
- 빈 문자열 허용 여부 별도 정책 필요

### 비고
초기에는 “문단 단위 치환”만 지원하고,
문장 일부 정밀 편집은 2차로 미룬다.

---

## 10.5 `insert_paragraph_after`

### 목적
특정 문단 뒤에 새 문단을 삽입한다.

### 입력
```json
{
  "document_id": "doc_001",
  "after_paragraph_index": 12,
  "text": "추가할 문단입니다.",
  "style_mode": "inherit"
}
```

### 출력
```json
{
  "ok": true,
  "message": "paragraph inserted",
  "data": {
    "inserted_after": 12,
    "new_paragraph_index": 13
  }
}
```

### style_mode 후보
- `inherit`: 앞 문단 스타일 상속
- `plain`: 기본 스타일

---

## 10.6 `create_table`

### 목적
자연어 요청에서 파생된 표 구조를 문서에 삽입한다.

### 입력
```json
{
  "document_id": "doc_001",
  "after_paragraph_index": 20,
  "rows": 4,
  "cols": 3,
  "header": true,
  "title": "예산 비교표"
}
```

### 출력
```json
{
  "ok": true,
  "message": "table created",
  "data": {
    "table_id": "table_003",
    "rows": 4,
    "cols": 3,
    "inserted_after": 20
  }
}
```

### 설계 포인트
- 1차에서는 기본 표만 생성
- 복잡한 병합 셀은 후속 범위

---

## 10.7 `fill_table_cells`

### 목적
생성된 표 또는 기존 표의 셀에 데이터를 채운다.

### 입력
```json
{
  "document_id": "doc_001",
  "table_id": "table_003",
  "cells": [
    { "row": 0, "col": 0, "text": "항목" },
    { "row": 0, "col": 1, "text": "예산" },
    { "row": 1, "col": 0, "text": "홍보" },
    { "row": 1, "col": 1, "text": "1000000" }
  ]
}
```

### 출력
```json
{
  "ok": true,
  "message": "table updated",
  "data": {
    "table_id": "table_003",
    "updated_cells": 4
  }
}
```

---

## 10.8 `save_as`

### 목적
수정된 문서를 새 파일로 저장한다.

### 입력
```json
{
  "document_id": "doc_001",
  "output_path": "/absolute/path/to/output.hwp"
}
```

### 출력
```json
{
  "ok": true,
  "message": "document saved",
  "data": {
    "output_path": "/absolute/path/to/output.hwp"
  }
}
```

### 설계 포인트
- 초기에는 원본 덮어쓰기 금지 권장
- 출력 경로 유효성 검사 필수

---

## 10.9 `validate_document`

### 목적
저장된 문서가 최소한 구조적으로 유효한지 확인한다.

### 입력
```json
{
  "path": "/absolute/path/to/output.hwp"
}
```

### 출력
```json
{
  "ok": true,
  "message": "document validated",
  "data": {
    "readable": true,
    "text_extractable": true,
    "warnings": []
  }
}
```

### 필요 이유
AI가 수정한 뒤 “저장은 되었지만 실제로 열 수 없는 파일”이 되는 상황을 막아야 한다.

---

## 11. Tool 호출 권장 흐름

### 11.1 문서 기반 Q&A
1. `open_document`
2. `extract_document_text`
3. 필요 시 `extract_document_structure`
4. AI 응답 생성

### 11.2 문단 수정
1. `open_document`
2. `extract_document_structure`
3. `replace_paragraph_text`
4. `save_as`
5. `validate_document`

### 11.3 표 생성
1. `open_document`
2. `extract_document_structure`
3. `create_table`
4. `fill_table_cells`
5. `save_as`
6. `validate_document`

---

## 12. 에러 처리 정책

## 12.1 에러 코드 초안
- `FILE_NOT_FOUND`
- `UNSUPPORTED_FORMAT`
- `READONLY_DOCUMENT`
- `INVALID_DOCUMENT_ID`
- `INVALID_POSITION`
- `TABLE_NOT_FOUND`
- `VALIDATION_FAILED`
- `RHWP_EXECUTION_FAILED`
- `INTERNAL_ERROR`

## 12.2 에러 응답 형식

```json
{
  "ok": false,
  "error_code": "INVALID_POSITION",
  "message": "after_paragraph_index 999 is out of range",
  "suggestion": "call extract_document_structure first to get valid indexes"
}
```

## 12.3 에러 처리 원칙
- 메시지는 짧고 명확해야 함
- suggestion 필드를 최대한 제공
- 내부 stack trace는 기본 응답에 노출하지 않음
- 디버그 모드에서만 상세 로그 허용

---

## 13. 보안 및 개인정보 처리 원칙

공무원/교사 문서는 민감한 내용을 다룰 수 있다.
MCP 서버는 초기부터 보안 관점을 가져야 한다.

### 원칙
- 기본은 **로컬 파일 처리**
- 원문 저장 로그 최소화
- 테스트 샘플은 비식별 문서 사용
- 외부 API 전송이 필요한 경우 명시적 고지
- 경로 접근 범위를 제한

### 체크 항목
- [ ] 허용된 디렉터리 외 접근 차단
- [ ] 파일 경로 검증
- [ ] 로그에 문서 원문 전체 남기지 않기
- [ ] 학생 정보/민원 정보 포함 문서 사용 금지 정책 수립

---

## 14. 공무원 특화 사용 시나리오와 Tool 연결

### 시나리오 A. 보고서 요약
- 사용 Tool:
  - `open_document`
  - `extract_document_text`

### 시나리오 B. 공문 문체로 재작성
- 사용 Tool:
  - `open_document`
  - `extract_document_structure`
  - `replace_paragraph_text`
  - `save_as`

### 시나리오 C. 회의자료 표 생성
- 사용 Tool:
  - `open_document`
  - `create_table`
  - `fill_table_cells`
  - `save_as`

핵심은 공무원 업무에서 자주 반복되는
**요약 / 정리 / 표 작성 / 문체 전환**을 빠르게 처리하는 것이다.

---

## 15. 교사 특화 사용 시나리오와 Tool 연결

### 시나리오 A. 가정통신문 초안 보정
- 사용 Tool:
  - `open_document`
  - `extract_document_structure`
  - `replace_paragraph_text`
  - `save_as`

### 시나리오 B. 수업안 구조 정리
- 사용 Tool:
  - `open_document`
  - `extract_document_structure`
  - `insert_paragraph_after`
  - `replace_paragraph_text`

### 시나리오 C. 학생 상담 기록표 생성
- 사용 Tool:
  - `open_document`
  - `create_table`
  - `fill_table_cells`
  - `save_as`

핵심은 교사 업무에서 자주 나오는
**안내문 / 수업안 / 상담기록 / 학급 운영 문서**를 빠르게 만드는 것이다.

---

## 16. 구현 단계 제안

## Phase 1. 최소 읽기/저장 PoC
- `open_document`
- `extract_document_text`
- `save_as`
- `validate_document`

목표:
- 읽기와 저장 루프부터 안정화

## Phase 2. 구조 추출/문단 수정
- `extract_document_structure`
- `replace_paragraph_text`
- `insert_paragraph_after`

목표:
- 문서 수정의 기본 루프 완성

## Phase 3. 표 생성
- `create_table`
- `fill_table_cells`

목표:
- 공무원/교사 실사용 가치가 높은 표 생성 구현

## Phase 4. CLI 통합 검증
- Claude Code CLI 연결
- Codex CLI 연결
- 실제 샘플 문서 테스트

## Phase 5. 역할 특화 데모
- 공무원용 데모 1개
- 교사용 데모 1개

---

## 17. 파일 구조 제안

```text
master-of-hwp/
├─ docs/
├─ samples/
│  ├─ public-official/
│  └─ teacher/
├─ outputs/
├─ notes/
├─ mcp-server/
│  ├─ server.py
│  ├─ tools/
│  ├─ adapters/
│  └─ schemas/
└─ experiments/
```

### mcp-server 내부 예시

```text
mcp-server/
├─ server.py
├─ config.py
├─ tools/
│  ├─ open_document.py
│  ├─ extract_document_text.py
│  ├─ extract_document_structure.py
│  ├─ replace_paragraph_text.py
│  ├─ insert_paragraph_after.py
│  ├─ create_table.py
│  ├─ fill_table_cells.py
│  ├─ save_as.py
│  └─ validate_document.py
├─ adapters/
│  └─ rhwp_adapter.py
└─ schemas/
   └─ common.py
```

---

## 18. 검증 우선순위

구현 순서는 아래가 가장 좋다.

1. **extract_document_text**
2. **extract_document_structure**
3. **replace_paragraph_text**
4. **save_as + validate_document**
5. **create_table**
6. **fill_table_cells**

이 순서가 좋은 이유:
- 읽기가 먼저 안정돼야 AI가 판단 가능
- 구조가 있어야 수정 가능
- 저장 검증이 있어야 수정이 안전함
- 표 생성은 그 다음에 붙여도 가치가 큼

---

## 19. 오픈 이슈

아직 구현 전에 확인이 필요한 쟁점들이다.

- [ ] rhwp가 문단 단위 위치 참조를 얼마나 안정적으로 제공하는가
- [ ] HWP와 HWPX 지원 차이가 있는가
- [ ] 표 생성 API가 어느 수준까지 되는가
- [ ] 스타일 보존이 어느 정도 가능한가
- [ ] 문서 저장 후 재검증 속도가 충분히 빠른가
- [ ] CLI 기반 사용성이 실제 업무 흐름에 맞는가

---

## 20. 최종 요약

이번 설계의 핵심은 복잡하지 않다.

- AI는 자연어를 이해한다.
- MCP 서버는 안전한 Tool을 제공한다.
- rhwp는 실제 문서를 읽고 수정한다.

그리고 1차 목표는 분명하다.

> **master-of-hwp MCP 서버는 “문서를 읽고, 구조를 파악하고, 문단을 수정하고, 표를 만들고, 새 파일로 저장하는 것”까지를 안정적으로 제공해야 한다.**

여기까지 되면,
공무원과 교사를 위한 실무형 HWP AI 도우미의 핵심 기반은 완성된다.
