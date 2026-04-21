---
id: 010
from: claude
to: codex
status: done
created: 2026-04-21
priority: high
size: large
blocked_by: 009
---

# 자연어 편집 자동 루프 (v0.3 핵심)

## 배경

v0.1.0 PyPI 배포 완료. v0.2 = HWPX/HWP 쓰기 확장. v0.3 = **AI 편집 루프**.

사용자는 "자연어 편집 자동 루프"를 HWPX 표 셀 편집과 함께 우선순위로 명시.
#009 (HWPX 셀 편집) 가 먼저 landing 되면 이 스파이크가 그 위에 올라간다.

**사전 조건:** #009가 승인 + 통합되어 있을 것.

## 목적

```python
doc = HwpDocument.open("가정통신문.hwpx")
edited = doc.ai_edit("첫 번째 문단의 '급식비'를 '수업료'로 바꿔줘")
# → Claude API 호출 → 의도 파싱 → 위치 결정 → 편집 → fidelity 검증 → 롤백 or commit
```

Phase 2 AI 스켈레톤 (`master_of_hwp/ai/`) 을 실제 동작 루프로 채운다.
LLM은 Claude 를 기본, provider 추상화로 교체 가능.

## In-Scope (5개 제출물)

### 1. LLM provider 추상화 — `master_of_hwp/ai/providers.py` (신규)

```python
from typing import Protocol

class LLMProvider(Protocol):
    def complete(self, system: str, user: str, *, max_tokens: int = 1024) -> str:
        """Return raw text completion."""

    def complete_json(
        self, system: str, user: str, schema: dict, *, max_tokens: int = 1024
    ) -> dict:
        """Return structured JSON completion matching schema."""


class AnthropicProvider:
    def __init__(self, model: str = "claude-opus-4-7", api_key: str | None = None):
        ...

    def complete(self, system, user, *, max_tokens=1024) -> str: ...
    def complete_json(self, system, user, schema, *, max_tokens=1024) -> dict: ...
```

- `anthropic` 패키지를 **optional** 의존성으로 (`pyproject.toml` 의 `[project.optional-dependencies]` 에 `ai = ["anthropic>=0.40.0"]` 추가)
- import 를 지연 (`AnthropicProvider.__init__` 내부에서 import) — 설치 안 해도 패키지 import 가능
- API key는 환경변수 `ANTHROPIC_API_KEY` 기본 사용

### 2. 의도 파싱 업그레이드 — `master_of_hwp/ai/intent.py` 확장

기존 `parse_edit_intent` 는 rule-based stub. LLM 백엔드 추가:

```python
def parse_intent_llm(request: str, doc: HwpDocument, provider: LLMProvider) -> EditIntent:
    """LLM-backed intent parser.

    Uses provider.complete_json with a JSON schema that matches EditIntent.
    Falls back to parse_edit_intent (rule-based) if LLM returns unparseable.
    """
```

**LLM prompt 설계:** JSON 모드로 `{action, target_description, parameters, confidence}` 반환.
`action` 은 `EditAction` enum 값 중 하나.

### 3. 위치 결정 — `master_of_hwp/ai/locator.py` 구현

기존 `locate_targets` 는 `NotImplementedError`. 실 구현:

```python
def locate_targets(
    intent: EditIntent, doc: HwpDocument, provider: LLMProvider | None = None
) -> list[ParagraphLocator]:
    """Resolve intent to concrete document coordinates.

    Algorithm:
        1. find_paragraphs 로 substring candidates 수집
        2. 0개면 빈 리스트 반환
        3. 1개면 바로 confidence=1.0 반환
        4. 여러 개 + provider 있으면 LLM 재랭킹
        5. provider 없으면 첫 후보 confidence=0.5 반환
    """
```

### 4. 통합 `HwpDocument.ai_edit()` — `master_of_hwp/core/document.py`

```python
def ai_edit(
    self,
    natural_language_request: str,
    *,
    provider: "LLMProvider | None" = None,
    dry_run: bool = False,
    confidence_threshold: float = 0.5,
) -> "AIEditResult":
    """Execute a natural-language edit request.

    Pipeline: intent → locate → operation → apply → verify → (rollback on fail).

    Args:
        natural_language_request: Korean or English instruction.
        provider: LLM provider. If None, uses rule-based intent + first-match locator.
        dry_run: If True, plan but don't apply; result.new_doc == self.
        confidence_threshold: Minimum combined confidence; below this
            ai_edit refuses to apply (returns AIEditResult with status=refused).

    Returns:
        AIEditResult dataclass with:
            - status: "applied" | "refused" | "failed"
            - intent: EditIntent
            - locator: ParagraphLocator | None
            - new_doc: HwpDocument (== self if not applied)
            - fidelity_report: FidelityReport | None
            - message: str (human-readable explanation)
    """
```

- 기본 provider 없음 (offline/rule-based mode 가능)
- dry_run=True 는 UI 프리뷰용

### 5. 테스트 — `tests/integration/test_ai_edit.py`

**중요: LLM 호출 테스트는 network/API key 가 없으면 skip.**

- `test_ai_edit_rule_based_dry_run`: provider 없이 dry_run → refused 상태 + intent 확인
- `test_ai_edit_rule_based_applies_if_unique_match`: find_paragraphs 가 정확히 1개면 rule-based 도 적용
- `test_ai_edit_confidence_threshold_refusal`: threshold 0.9 로 설정 시 rule-based 는 거의 refused
- `test_ai_edit_with_llm_integration` (skip if no `ANTHROPIC_API_KEY`):
  실제 Claude API 호출, "첫 문단을 X로 바꿔줘" 성공 시나리오
- `test_ai_edit_rejects_unknown_intent`: "날씨 어때?" → refused + status="refused"

## Out-of-Scope

- 표 셀 편집 자연어 경로 (HwpDocument.ai_edit 에서 replace 만 처리; 표 셀 edit 은 v0.3.x)
- 삽입/삭제 자연어 경로 (write ops 가 아직 없어서)
- 멀티턴 대화 / 이전 컨텍스트 유지
- 이미지/수식 이해
- OpenAI 등 다른 provider 실구현 (Protocol 만 정의, 실 구현은 contribution 받기)

## 인수 기준

- [ ] `ai/providers.py`, 업그레이드된 `ai/intent.py`, 실 구현 `ai/locator.py`
- [ ] `HwpDocument.ai_edit()` + `AIEditResult` dataclass
- [ ] 5+ 통합 테스트 (3개는 API key 없어도 통과해야 함)
- [ ] `pyproject.toml` 에 `ai` optional deps 추가
- [ ] 전 품질 게이트 통과 (현재 88+ → 93+ passed with skips)
- [ ] mypy strict 통과

## 구현 힌트

### JSON Schema for intent parsing

```python
INTENT_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["replace_text", "insert_paragraph", "delete_range",
                     "update_table_cell", "unknown"],
        },
        "target_description": {"type": "string"},
        "parameters": {
            "type": "object",
            "properties": {
                "find": {"type": "string"},
                "replace_with": {"type": "string"},
            },
        },
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    },
    "required": ["action", "target_description", "confidence"],
}
```

### Anthropic SDK JSON mode (pseudocode)

```python
import anthropic
client = anthropic.Anthropic(api_key=api_key)
message = client.messages.create(
    model=model,
    max_tokens=max_tokens,
    system=system,
    messages=[{"role": "user", "content": user}],
    # Note: proper JSON schema mode = tool use with forced tool call
)
```

### Fidelity 검증 통합

ai_edit 내부에서:
```python
from master_of_hwp.fidelity.harness import verify_replace_roundtrip
# replace_paragraph 직전에 snapshot, 후에 verify_replace_roundtrip
# structural_equal == False 면 rollback
```

## 완료 후 할 일

1. `git mv handoff/codex/010_*.md handoff/codex/done/`
2. `handoff/review/010_review_ai_edit_loop.md` 생성
3. 커밋: `feat(ai): natural-language edit loop with Claude provider (spike #010)`
4. 트레일러 필수: Confidence / Scope-risk / Reversibility / Directive / Tested / Not-tested
5. `git push origin main`

## 스타일

- LLM 호출은 **함수 내부에서** lazy import (`import anthropic` inside method)
- API key 없이 import / test discovery / rule-based path 는 모두 동작해야 함
- 공개 심볼 타입 힌트 + docstring 100%
- 에러 메시지는 사용자(선생님)에게 읽히는 한국어/영어 섞여도 OK

## 중요: 부분 진행 정책

이 스파이크는 큼. 모두 끝내지 못해도 OK:

- provider + intent LLM 업그레이드 + locator 실구현 ✅, ai_edit 부분 ⚠️, test 3개 → 합격
- 단, LLM 없이 동작하는 rule-based path 는 **반드시** landing 되어야 함 (API key 없는 사용자도 써야 함)
- 커밋 트레일러 `Not-tested:` 에 꼼꼼히 기록
