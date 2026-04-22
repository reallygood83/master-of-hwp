"""LLM provider protocols and optional Anthropic / OpenAI / CLI implementations."""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    """Minimal provider interface used by the AI edit loop."""

    def complete(self, system: str, user: str, *, max_tokens: int = 1024) -> str:
        """Return raw text completion."""

    def complete_json(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
        *,
        max_tokens: int = 1024,
    ) -> dict[str, Any]:
        """Return structured JSON completion matching schema."""


class AnthropicProvider:
    """Anthropic Claude provider loaded lazily from the optional `ai` extra."""

    def __init__(self, model: str = "claude-opus-4-7", api_key: str | None = None) -> None:
        self.model = model
        resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        try:
            import anthropic  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "Install master-of-hwp with the 'ai' extra to use AnthropicProvider."
            ) from exc
        self._client = anthropic.Anthropic(api_key=resolved_key)

    def complete(self, system: str, user: str, *, max_tokens: int = 1024) -> str:
        """Return raw text completion."""
        message = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        parts = [
            str(getattr(block, "text", ""))
            for block in getattr(message, "content", [])
            if getattr(block, "type", "") == "text"
        ]
        return "\n".join(part for part in parts if part).strip()

    def complete_json(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
        *,
        max_tokens: int = 1024,
    ) -> dict[str, Any]:
        """Return structured JSON completion matching schema."""
        del schema
        text = self.complete(
            system,
            f"{user}\n\nReturn only a JSON object. No markdown.",
            max_tokens=max_tokens,
        )
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Anthropic response was not JSON: {text[:200]}") from exc
        if not isinstance(payload, dict):
            raise ValueError("Anthropic response JSON was not an object.")
        return payload


class OpenAIProvider:
    """OpenAI provider loaded lazily from the optional `ai` extra.

    Suitable for the Codex CLI crowd (users who prefer OpenAI models).
    Uses the `openai` SDK and defaults to GPT-4o.
    """

    def __init__(self, model: str = "gpt-4o", api_key: str | None = None) -> None:
        self.model = model
        resolved_key = api_key or os.environ.get("OPENAI_API_KEY")
        try:
            from openai import OpenAI  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "Install master-of-hwp with the 'ai' extra + openai to use OpenAIProvider."
            ) from exc
        self._client = OpenAI(api_key=resolved_key)

    def complete(self, system: str, user: str, *, max_tokens: int = 1024) -> str:
        """Return raw text completion."""
        response = self._client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        content = response.choices[0].message.content or ""
        return str(content).strip()

    def complete_json(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
        *,
        max_tokens: int = 1024,
    ) -> dict[str, Any]:
        """Return structured JSON completion matching schema."""
        del schema
        response = self._client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"{user}\n\nReturn only a JSON object."},
            ],
        )
        text = response.choices[0].message.content or "{}"
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"OpenAI response was not JSON: {text[:200]}") from exc
        if not isinstance(payload, dict):
            raise ValueError("OpenAI response JSON was not an object.")
        return payload


class _CLIProviderBase:
    """Shared machinery for shell-invoked LLM CLIs.

    Rationale: many users already pay for Claude Code CLI (`claude`) or
    OpenAI's Codex CLI (`codex`) via subscription and would rather not
    configure an API key. These providers shell out to the CLI binary
    so calls go through the user's existing subscription.
    """

    executable: str = ""
    display_name: str = ""

    def __init__(self, executable: str | None = None, timeout: float = 120.0) -> None:
        resolved = executable or self.executable
        self._use_wsl = False
        self._wsl_target = ""
        discovered = shutil.which(resolved) if resolved else None
        if not discovered and sys.platform == "win32":
            # Windows fallback: try `wsl <cli>`. Useful when the user installed
            # Claude Code / Codex CLI inside WSL (npm) for subscription use.
            wsl_path = shutil.which("wsl") or shutil.which("wsl.exe")
            if wsl_path and _wsl_has_command(wsl_path, resolved):
                self._executable_path = wsl_path
                self._use_wsl = True
                self._wsl_target = resolved
                self._timeout = timeout
                return
        if not discovered:
            raise RuntimeError(f"{self.display_name} CLI ({resolved!r}) not found on PATH.")
        self._executable_path = discovered
        self._timeout = timeout

    def _run(self, args: list[str], *, stdin: str | None = None) -> str:
        # Windows: .cmd/.bat scripts require shell=True to execute via subprocess.
        # WSL fallback: prepend `wsl -e <target>` so args are passed to the
        # CLI installed inside the Linux subsystem.
        use_shell = False
        if self._use_wsl:
            cmd: list[str] | str = [self._executable_path, "-e", self._wsl_target, *args]
        else:
            cmd = [self._executable_path, *args]
        if sys.platform == "win32" and not self._use_wsl:
            ext = Path(self._executable_path).suffix.lower()
            if ext in {".cmd", ".bat"}:
                use_shell = True
                import shlex

                cmd = shlex.join([self._executable_path, *args])
        try:
            result = subprocess.run(  # noqa: S603 — executable resolved via shutil.which
                cmd,
                input=stdin,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                check=False,
                shell=use_shell,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"{self.display_name} CLI timed out after {self._timeout}s") from exc
        if result.returncode != 0:
            stderr_tail = result.stderr.strip().splitlines()[-5:]
            raise RuntimeError(
                f"{self.display_name} CLI exited {result.returncode}: " + " | ".join(stderr_tail)
            )
        return result.stdout.strip()

    def _wsl_translate_path(self, path: str) -> str:
        """When bridging through WSL, convert `C:\\x` → `/mnt/c/x` so the CLI
        inside Linux can open the file. Pass-through when not in WSL mode.
        """
        if not self._use_wsl:
            return path
        import re

        match = re.match(r"^([A-Za-z]):[\\/](.*)$", path)
        if match:
            drive = match.group(1).lower()
            rest = match.group(2).replace("\\", "/")
            return f"/mnt/{drive}/{rest}"
        return path

    def complete_json(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
        *,
        max_tokens: int = 1024,
    ) -> dict[str, Any]:
        """Return structured JSON completion by asking the CLI for JSON."""
        del schema
        text = self.complete(  # type: ignore[attr-defined]
            system,
            f"{user}\n\nReturn ONLY a JSON object. No markdown, no prose.",
            max_tokens=max_tokens,
        )
        try:
            payload = json.loads(_extract_json_block(text))
        except (ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"{self.display_name} response was not JSON: {text[:200]}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"{self.display_name} response JSON was not an object.")
        return payload


class ClaudeCodeCLIProvider(_CLIProviderBase):
    """Invoke the `claude` CLI in print mode (no API key needed)."""

    executable = "claude"
    display_name = "Claude Code"

    def complete(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 1024,
        attachments: list[str] | None = None,
    ) -> str:
        del max_tokens  # Claude CLI governs its own token budget.
        # Claude Code CLI can read files when referenced with @path syntax.
        # In WSL-bridge mode, translate Windows paths to /mnt/<drive>/... form.
        attach_paths = [self._wsl_translate_path(p) for p in (attachments or [])]
        attach_block = ""
        if attach_paths:
            refs = "\n".join(f"- @{p}" for p in attach_paths)
            attach_block = f"\n\n참고 첨부 파일 (내용을 읽어서 활용):\n{refs}"
        prompt = f"{system}\n\n{user}{attach_block}" if system else f"{user}{attach_block}"
        return self._run(["-p", prompt])


class CodexCLIProvider(_CLIProviderBase):
    """Invoke the `codex` CLI in exec mode (no API key needed)."""

    executable = "codex"
    display_name = "Codex"

    _IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}

    def complete(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 1024,
        attachments: list[str] | None = None,
    ) -> str:
        del max_tokens
        # Split attachments: images → `-i`, others → path reference in prompt.
        # Translate Windows paths when bridging through WSL.
        image_paths: list[str] = []
        file_refs: list[str] = []
        for path_str in attachments or []:
            translated = self._wsl_translate_path(path_str)
            p = Path(path_str)
            if p.suffix.lower() in self._IMAGE_SUFFIXES:
                image_paths.append(translated)
            else:
                file_refs.append(translated)
        attach_block = ""
        if file_refs:
            listed = "\n".join(f"- {p}" for p in file_refs)
            attach_block = f"\n\n참고 첨부 파일 (내용을 읽어서 활용):\n{listed}"
        prompt = f"{system}\n\n{user}{attach_block}" if system else f"{user}{attach_block}"

        with tempfile.NamedTemporaryFile(
            mode="r", suffix=".txt", delete=False, encoding="utf-8"
        ) as handle:
            output_path = Path(handle.name)
        try:
            args = ["exec", "--skip-git-repo-check"]
            for img in image_paths:
                args.extend(["-i", img])
            args.extend(["--output-last-message", str(output_path), prompt])
            self._run(args)
            return output_path.read_text(encoding="utf-8").strip()
        finally:
            with contextlib.suppress(OSError):
                output_path.unlink(missing_ok=True)


def _extract_json_block(text: str) -> str:
    """Return the first {...} block from a string, else the text itself."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return text
    return text[start : end + 1]


def _wsl_has_command(wsl_path: str, target: str) -> bool:
    """Check whether `target` is available as a command inside the default
    WSL distribution. Used on Windows to bridge Claude/Codex CLI installed
    inside WSL.
    """
    if not target:
        return False
    try:
        result = subprocess.run(  # noqa: S603
            [wsl_path, "-e", "which", target],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and bool(result.stdout.strip())
