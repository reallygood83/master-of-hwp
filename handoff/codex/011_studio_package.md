---
id: 011
from: claude
to: codex
status: pending
created: 2026-04-21
priority: high
size: large
---

# master-of-hwp-studio 패키지 (일반 사용자용 원클릭 Studio)

## 배경

v0.1.0 PyPI 배포 후 사용자 지적: **"많은 사람들은 rhwp 에디터와 Claude Code 연결시켰던 GUI 프로그램을 사용하고 싶어 할 거야. 이것 빠진 거야?"**

정답: 레포에 `mcp-server/` + `gui/` 가 있지만 PyPI 패키지로 안 나옴.
일반 사용자 (선생님/공무원) 입장에서는:
- **개발자용 Core API** = 지금의 `master-of-hwp`
- **일반인용 원클릭 Studio** = 지금 없음 ← 이번 작업

## 목적

```bash
pip install master-of-hwp-studio
mohwp studio
```

→ 자동으로:
1. 로컬 MCP 서버 기동 (포트 8000)
2. rhwp 에디터 서빙 (포트 7700)
3. 브라우저로 `http://127.0.0.1:8000` 열기
4. Claude Desktop MCP 설정 스니펫을 터미널에 출력 (copy-paste 가이드)

## In-Scope (6개 제출물)

### 1. 새 Python 패키지 레이아웃

`mcp-server/` 를 정식 배포 가능한 구조로 재편:

```
master_of_hwp_studio/          # 신규 패키지 (snake_case)
  __init__.py
  __main__.py                  # python -m master_of_hwp_studio
  cli.py                       # mohwp 커맨드 진입점
  mcp/                         # 기존 mcp-server 내용 이동
    __init__.py
    server.py                  # FastMCP 서버
    gui_server.py
    gui_ai.py
    adapters/
    orchestration/
    schemas/
    tools/
  web/                         # 기존 gui/ 내용 이동
    index.html
    app.css
    app.js
  resources/
    claude_desktop_mcp.json   # Claude Desktop 설정 템플릿
```

**중요:** 기존 `mcp-server/` 와 `gui/` 는 **이동 대신 symlink 또는 그대로 두고 패키지에서 참조**해도 OK. 하지만 배포 가능성 고려해서 `master_of_hwp_studio/` 로 정식 이동 권장.

### 2. `mcp-server/pyproject.toml` → 루트에 새 `studio/pyproject.toml` (별도 패키지)

```toml
[project]
name = "master-of-hwp-studio"
version = "0.1.0"
description = "One-click HWP editing Studio for non-developers — MCP server + web GUI bundled"
readme = "studio/README.md"
requires-python = ">=3.11"
license = { text = "MIT" }

dependencies = [
    "master-of-hwp>=0.1.0",    # Core API 의존
    "fastmcp>=3.2.0",
    "uvicorn[standard]>=0.30.0",  # GUI 서버
    "click>=8.1.0",            # CLI
]

[project.scripts]
mohwp = "master_of_hwp_studio.cli:main"

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "httpx>=0.27",            # MCP 테스트
]
```

**위치 결정:** `studio/` 폴더 (루트에 신규). 기존 `master_of_hwp/` 와 자매 패키지로.

### 3. CLI — `master_of_hwp_studio/cli.py`

```python
import click

@click.group()
def main():
    """master-of-hwp-studio — AI-powered HWP editing."""


@main.command()
@click.option("--port", default=8000)
@click.option("--editor-port", default=7700)
@click.option("--open-browser/--no-open-browser", default=True)
def studio(port: int, editor_port: int, open_browser: bool):
    """Start MCP server + web GUI, optionally open browser."""
    # 1. Launch MCP server in background thread
    # 2. Launch GUI web server on port
    # 3. Launch rhwp editor static server on editor-port (if bundled)
    # 4. Print Claude Desktop MCP config snippet
    # 5. webbrowser.open(f"http://127.0.0.1:{port}")


@main.command()
def mcp_config():
    """Print Claude Desktop MCP config snippet for copy-paste."""
    # Print JSON snippet to add to ~/Library/Application Support/Claude/claude_desktop_config.json
    ...
```

### 4. MCP 서버 도구 재정리 — `master_of_hwp_studio/mcp/server.py`

기존 `mcp-server/server.py` 를 새 Core API (`master-of-hwp>=0.1.0`) 위에서 재구성:

```python
from fastmcp import FastMCP
from master_of_hwp import HwpDocument

mcp = FastMCP("master-of-hwp-studio")


@mcp.tool()
def open_document(path: str) -> dict:
    """Open a HWP/HWPX file and return its summary."""
    return HwpDocument.open(path).summary()


@mcp.tool()
def find_paragraphs(path: str, query: str, regex: bool = False) -> list[dict]:
    """Find paragraphs matching query in a document."""
    doc = HwpDocument.open(path)
    return [
        {"section": s, "paragraph": p, "text": t}
        for s, p, t in doc.find_paragraphs(query, regex=regex)
    ]


@mcp.tool()
def replace_paragraph(
    path: str, section_index: int, paragraph_index: int, new_text: str, output_path: str
) -> dict:
    """Replace one paragraph and save to output_path."""
    doc = HwpDocument.open(path)
    edited = doc.replace_paragraph(section_index, paragraph_index, new_text)
    from pathlib import Path
    Path(output_path).write_bytes(edited.raw_bytes)
    return {"success": True, "output": output_path}


# More tools: summary, sections, paragraphs, tables, etc.
```

### 5. GUI 통합 — `master_of_hwp_studio/web/` 에 이식 + `importlib.resources` 로 서빙

CLI 의 `studio` 명령은 `importlib.resources.files("master_of_hwp_studio.web")` 로 정적 파일 서빙.

```python
from importlib import resources
from http.server import HTTPServer, SimpleHTTPRequestHandler

web_root = resources.files("master_of_hwp_studio.web")
# Serve web_root on specified port
```

기존 `gui/` 의 HTML/CSS/JS 를 **그대로** `master_of_hwp_studio/web/` 에 복사.

### 6. 최소 테스트 — `studio/tests/`

- `test_cli_help()`: `mohwp --help` 가 동작
- `test_mcp_tools_import()`: MCP 도구들 import 가능
- `test_mcp_open_document_tool()`: `open_document` tool 이 실 샘플 읽고 summary 반환
- `test_web_assets_bundled()`: `importlib.resources` 로 `index.html` 읽힘

## Out-of-Scope

- rhwp 에디터 바이너리 번들링 (WASM 은 용량 큼; Studio 실행 시 `npm install -g @rhwp/core` 같은 별도 설치 안내)
  - 대안: rhwp 설치 안 돼 있으면 "에디터 없이 텍스트 뷰 모드" 로 폴백
- Windows/macOS 인스톨러 (`.app`, `.exe`)
- 다국어 UI (v0.2.x 에서 추가)
- 사용자 프로필 / 계정 시스템
- 파일 공유 / 클라우드 연동

## 인수 기준

- [ ] `studio/` 폴더 + `master_of_hwp_studio/` 패키지 생성
- [ ] `studio/pyproject.toml` 로 `python -m build` 가 wheel 생성
- [ ] `pip install ./studio` 로 설치 후 `mohwp studio` 실행 → 브라우저 자동 열림
- [ ] MCP 서버가 Claude Desktop 에서 인식 (수동 config 후)
- [ ] 최소 4개 테스트 통과
- [ ] 기존 `master-of-hwp` (Core) 게이트는 영향 없음

## 구현 힌트

### Claude Desktop MCP config 출력

```python
def print_mcp_config():
    import json
    config_path = "~/Library/Application Support/Claude/claude_desktop_config.json"
    snippet = {
        "mcpServers": {
            "master-of-hwp": {
                "command": "mohwp",
                "args": ["mcp-serve"],
            }
        }
    }
    print(f"# Add to {config_path}:")
    print(json.dumps(snippet, indent=2, ensure_ascii=False))
```

### MCP 서버 stdio 모드

Claude Desktop 은 stdio 로 MCP 서버와 통신. FastMCP 는 기본 stdio 지원.

```python
# mohwp mcp-serve 서브커맨드
@main.command("mcp-serve")
def mcp_serve():
    from master_of_hwp_studio.mcp.server import mcp
    mcp.run()  # stdio
```

### 포트 충돌 감지

```python
import socket
def find_free_port(preferred: int) -> int:
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]
```

## 완료 후 할 일

1. `git mv handoff/codex/011_*.md handoff/codex/done/`
2. `handoff/review/011_review_studio_package.md` — 6개 제출물 상태 + `python -m build` 결과
3. 커밋: `feat(studio): master-of-hwp-studio package — one-click MCP + GUI (spike #011)`
4. 트레일러 필수 + `git push origin main`
5. **PyPI 업로드 + v0.1 태깅은 절대 하지 말 것** — 사용자 수동

## 스타일

- Studio 패키지는 Core 패키지 (master-of-hwp) 를 **의존성으로만** 사용
- Studio 코드에서 HWP 파싱을 다시 하지 말 것 (Core API 재사용)
- CLI 는 `click` 기반, 서브커맨드 구조
- 모든 공개 심볼 타입 힌트 + docstring
- `mypy strict` 준수

## 중요: 부분 진행 OK

큰 스파이크. 다음 순서로 우선 구현:

1. **필수** (이 없으면 PyPI 배포 불가):
   - `master_of_hwp_studio/` 패키지 + `studio/pyproject.toml`
   - `mohwp studio` CLI 명령 (최소 버전)
   - MCP 서버 기동
2. **중요** (일반 사용자 체감):
   - 브라우저 자동 열기
   - Claude Desktop config 스니펫 출력
3. **있으면 좋음** (다음 버전):
   - 포트 충돌 감지
   - rhwp 에디터 fallback 모드

2단계까지만 landing 해도 합격. 1단계만 되면 차단 사유를 리뷰에 명시.
