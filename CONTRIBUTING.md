# Contributing to master-of-hwp

기여해주셔서 감사합니다. 이 프로젝트는 **솔로 오픈소스**로 운영되며, **안정성과 품질을 속도보다 우선**합니다.

## 철학 (꼭 읽어주세요)

- **Platform-first**: 템플릿/앱이 아니라 HWP 편집 인프라입니다.
- **v0.x는 실험적**: API가 예고 없이 바뀝니다. v1.0 전까지 호환성 보장 없음.
- **Round-trip fidelity는 계약**: 모든 저장 경로는 구조 훼손 없음을 증명해야 합니다.
- **기능보다 테스트**: 새 기능 PR은 테스트 없이는 병합되지 않습니다.

자세한 비전은 [docs/ROADMAP.md](docs/ROADMAP.md), 구조는 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## 개발 환경

```bash
# Python 패키지
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 테스트
pytest                    # 전체
pytest -m unit            # 단위 테스트만
pytest -m fidelity        # 왕복 재현율 벤치마크
pytest --cov=master_of_hwp

# 린트/포맷
ruff check .
black --check .
```

## PR 체크리스트

- [ ] 관련 이슈 번호 언급
- [ ] 테스트 추가 (커버리지 유지 또는 상승)
- [ ] `ruff check` + `black --check` 통과
- [ ] 공개 API 변경 시 `docs/ROADMAP.md` 업데이트
- [ ] 커밋 메시지는 `<type>: <description>` 형식 (feat/fix/refactor/docs/test/chore)

## 기여 범위별 가이드

### 🟢 환영: 손쉬운 첫 기여

- 테스트 추가 (샘플 HWP 파일별 fidelity 케이스)
- 문서 오탈자 / 예제 보강
- 타입 힌트 보강
- Recipe 추가 (`recipes/` 디렉토리, Phase 3 공개 예정)

### 🟡 논의 필요: 이슈 먼저

- 새 Core API 추가
- 에이전트 레이어 변경
- 새 외부 의존성 도입

### 🔴 현재 받지 않음

- 에디터(`vendor/rhwp-main/rhwp-studio/`) 새 기능 — **Feature Freeze** 중
- 플러그인 시스템, 마이크로서비스화
- 다국어 UI (Korean-first 유지)

## 버그 리포트

재현 가능한 최소 예제를 포함해주세요. `.github/ISSUE_TEMPLATE/bug.md` 템플릿 사용.

## 커뮤니케이션

- Issues: 버그 / 기능 제안
- Discussions: 아키텍처 토론 / 질문
- PR: 실제 변경

## 행동 강령

상호 존중. 기술적 비판은 환영, 인신공격은 차단.
