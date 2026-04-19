# CLI MCP 연동 가이드

이 문서는 `master-of-hwp` MCP 서버를 Claude Code CLI, Codex CLI, OpenCode CLI에 연결하는 방법을 정리한다.

## 전제
- 프로젝트 경로: `/Users/moon/Desktop/master-of-hwp`
- MCP 서버 실행 파일: `/Users/moon/Desktop/master-of-hwp/scripts/run_mcp_server.sh`
- 현재 서버는 stdio 기반으로 실행된다.
- 런처는 `mcp-server/.venv/bin/python`이 있으면 그 인터프리터를 우선 사용한다.

---

## 1. Claude Code CLI

### 프로젝트 스코프 등록
```bash
claude mcp add --transport stdio --scope project master-of-hwp -- /Users/moon/Desktop/master-of-hwp/scripts/run_mcp_server.sh
```

### 확인
```bash
claude mcp list
claude mcp get master-of-hwp
```

### 대안: `.mcp.json`
프로젝트 루트에 아래와 같은 파일을 둘 수 있다.

```json
{
  "mcpServers": {
    "master-of-hwp": {
      "command": "/Users/moon/Desktop/master-of-hwp/scripts/run_mcp_server.sh",
      "args": [],
      "env": {}
    }
  }
}
```

### 로컬 승인 설정 예시
`.claude/settings.local.json`

```json
{
  "enableAllProjectMcpServers": true,
  "enabledMcpjsonServers": ["master-of-hwp"]
}
```

---

## 2. Codex CLI

### 설정 파일
`~/.codex/config.toml`

```toml
[mcp_servers.master_of_hwp]
command = "/Users/moon/Desktop/master-of-hwp/scripts/run_mcp_server.sh"
args = []
enabled = true
startup_timeout_sec = 30
tool_timeout_sec = 60
```

### 확인
```bash
codex mcp list
codex mcp get master_of_hwp
```

### 참고
Codex는 stdio MCP에서 startup timeout 이슈가 보고된 적이 있으므로,
초기에는 `startup_timeout_sec = 30` 이상을 권장한다.

---

## 3. OpenCode CLI

### 설정 파일
`~/.config/opencode/opencode.json`

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "master-of-hwp": {
      "type": "local",
      "command": ["/Users/moon/Desktop/master-of-hwp/scripts/run_mcp_server.sh"],
      "enabled": true,
      "environment": {}
    }
  }
}
```

### 확인
```bash
opencode mcp list
opencode mcp debug master-of-hwp
```

---

## 4. 현재 의미
현재 `master-of-hwp`는 아래 기능을 MCP tool로 제공한다.

- `rhwp_integration_status`
- `rhwp_save_status`
- `open_document`
- `extract_document_text`
- `extract_document_structure`
- `replace_paragraph_text`
- `insert_paragraph_after`
- `save_as`
- `validate_document`

즉 지금 바로 CLI 에이전트에 붙여서,
문서를 열고, 읽고, 구조를 보고, 텍스트 기반 편집 세션을 돌릴 수 있다.

---

## 5. 현재 한계
- HWP/HWPX 읽기와 구조 추출은 실제 bridge로 연동됨
- HWP/HWPX 저장도 실제로 동작하지만, 현재는 **텍스트 기반 저장** 또는 **문단 편집 roundtrip replay** 수준이다.
- 원본의 표/개체/서식/레이아웃을 완전 보존하는 저장은 아직 미구현이다.
- table creation roundtrip persistence는 아직 실패 상태다.

---

## 6. 추천 순서
1. Claude Code CLI에 먼저 등록
2. `rhwp_integration_status` 호출
3. `.hwp` / `.hwpx` 샘플로 `extract_document_text` 테스트
4. `open_document` → `replace_paragraph_text` → `save_as` 흐름 검증
5. 이후 Codex/OpenCode에 같은 서버 연결
