# Architecture

## Principles

1. **의존성은 아래로만** — Layer N은 Layer <N만 호출
2. **불변성 우선** — 편집은 새 객체를 반환, 원본 불변
3. **모든 쓰기는 검증 통과 후에만** — 저장 전 round-trip 검증 의무
4. **AI는 플러그인** — Core는 AI 없이도 동작

## Layers

### Layer 1: Core API (`master_of_hwp/`)

사용자가 직접 사용하는 파이썬 API. 모든 상위 레이어는 이것을 통해 HWP를 다룬다.

```
master_of_hwp/
├── core/              # 도메인 모델
│   ├── document.py       # HwpDocument
│   ├── section.py        # Section
│   ├── paragraph.py      # Paragraph
│   └── table.py          # Table, Cell
├── operations/        # 편집 연산 (순수 함수, 불변)
│   ├── text.py           # replace/insert/delete text
│   ├── structure.py      # 단락/표 조작
│   └── registry.py       # 연산 등록/탐색
├── ai/                # 에이전트 레이어 (Layer 4 진입점)
│   ├── intent.py         # 자연어 → EditIntent
│   ├── planner.py        # EditIntent → 원자 연산 시퀀스
│   └── providers.py      # LLM provider protocol
├── fidelity/          # 왕복 재현율 보증
│   ├── roundtrip.py      # measure_roundtrip()
│   └── diff.py           # 구조적 diff
└── adapters/          # 외부 엔진 바인딩
    ├── rhwp_bridge.py    # Rust/WASM 엔진 브리지
    └── mcp_adapter.py    # MCP 서버가 Core를 소비
```

### Layer 2: Editor (`vendor/rhwp-main/rhwp-studio/`)
- 현재: WASM 기반 React 에디터
- 상태: **Feature Freeze** (v0.2까지 버그 수정만)
- v0.3부터 Core API를 소비하는 얇은 프론트엔드로 재작성 예정

### Layer 3: Recipes
- 도메인별 템플릿/에이전트
- 예: `recipes/teacher/parent_letter.py`, `recipes/officer/official_memo.py`
- 각 Recipe는 Layer 1 API만 사용

### Layer 4: Agentic Capabilities
- `ai/`에 구현되는 고차 기능
- 현재 스코프: intent parser → planner → executor → verifier
- 외부 AI는 `providers.py`의 Protocol을 구현해 주입

## Data Flow

```
[사용자 자연어 요청]
         │
         ▼
   ai.intent.parse_edit_intent()
         │
         ▼
   ai.planner.plan_operations()  ──►  [EditPlan: 원자 연산 리스트]
         │
         ▼
   operations.execute()            ──►  HwpDocument (new)
         │
         ▼
   fidelity.verify()               ──►  [pass/fail]
         │
         ├── pass: doc.save()
         └── fail: rollback + 사용자 알림
```

## Versioning Contract

| 버전 대역 | 의미 | 호환성 |
|---|---|---|
| v0.0.x | 실험적, API 파괴 허용 | 없음 |
| v0.x.y (x≥1) | 공개 프리뷰 | 마이너 단위로 파괴 가능 |
| v1.0.0 | **계약 시작** | SemVer 엄격 준수 |
| v1.x.y | 안정 | 추가만 허용, 제거 시 deprecation |

## MCP 서버와의 관계

현재 `mcp-server/`는 자체 로직을 가진 실행 유닛이지만, 향후:

```
mcp-server/  ──► master_of_hwp.adapters.mcp_adapter ──► master_of_hwp.core
            (얇은 래퍼)
```

MCP 서버는 Core API의 소비자 중 하나가 된다.

## 테스트 전략

- **Unit**: `tests/unit/` — 각 모듈 고립 테스트
- **Fidelity**: `tests/fidelity/` — 왕복 재현율 벤치마크 (`samples/` 소비)
- **Property**: `tests/property/` — Hypothesis 기반 불변식 검증
- **Integration**: `tests/integration/` — Core + Adapter + MCP 전체 흐름

목표 커버리지: **80%+**. fidelity는 별도 스코어카드 관리.
