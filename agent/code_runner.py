"""
CodeRunner — Python REPL, Bash shell, and file utilities for the agent.

Two operating modes
-------------------
sandbox=True  (Podman)
    A container is started with <cwd>/sandbox_workspace bind-mounted as
    /workspace. All code execution happens inside the container. No security
    review is required — the sandbox is the boundary.

    File operations (read_file, write_file, patch_file) are executed inside
    the container via exec_run rather than by the host Python process. This
    means the container's own filesystem namespace handles all path resolution
    and symlink following — a symlink inside /workspace that points outside it
    only reaches the container image, never the host. There is no TOCTOU
    window because the host process never opens any file at all.

sandbox=False  (local)
    Both Python and bash are stateless — each call is an independent
    subprocess invocation with no shared state between calls. Before every
    execution the UTILITY_MODEL reviews the snippet for risks and the user
    must give explicit consent (unless the review rates it "low" risk and
    CODE_SECURITY_AUTORUN_LOW is True).

    File operations execute directly on the host filesystem.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from openai import OpenAI

from .config import (
    UTILITY_MODEL,
    SANDBOX_ENABLED,
    SANDBOX_IMAGE,
    SANDBOX_WORKDIR_NAME,
    CODE_SECURITY_REVIEW,
    CODE_SECURITY_AUTORUN_LOW,
)
from .tools import Tools

try:
    import podman as _podman_mod
except ImportError:
    _podman_mod = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------

MAX_OUTPUT_LEN: int = 8_000   # characters; longer output is trimmed from middle
SHELL_TIMEOUT: float = 30.0   # seconds per bash command
PYTHON_TIMEOUT: float = 30.0  # seconds per Python snippet


# ---------------------------------------------------------------------------
# CodeRunner
# ---------------------------------------------------------------------------

class CodeRunner:
    """Unified execution environment and file utility suite for the agent."""

    def __init__(
        self,
        client: OpenAI,
        sandbox: bool = SANDBOX_ENABLED,
        image: str = SANDBOX_IMAGE,
    ) -> None:
        self._client  = client
        self._sandbox = sandbox
        self._image   = image
        self._workdir = Path.cwd() / SANDBOX_WORKDIR_NAME
        self._workdir.mkdir(parents=True, exist_ok=True)

        self._container: object = None  # podman container handle

        if sandbox:
            self._start_container()

    # ------------------------------------------------------------------
    # Sandbox lifecycle
    # ------------------------------------------------------------------

    def _start_container(self) -> None:
        if _podman_mod is None:
            print(
                "[CodeRunner] podman-py not installed — falling back to local mode. "
                "Install the sandbox extra: pip install 'agent[sandbox]'"
            )
            self._sandbox = False
            return

        try:
            pc = _podman_mod.PodmanClient()
            self._container = pc.containers.run(
                self._image,
                command=["sleep", "infinity"],
                detach=True,
                remove=True,
                mounts=[
                    {
                        "type": "bind",
                        "source": str(self._workdir),
                        "target": "/workspace",
                        "read_only": False,
                    }
                ],
                working_dir="/workspace",
                # Run as the host user so bind-mount file ownership matches.
                # userns_mode="keep-id" is a rootless-Podman feature that maps
                # the host UID to the same UID inside the container — so files
                # created in /workspace are owned by the calling user on both
                # sides of the bind mount.
                userns_mode="keep-id",
                # Point HOME at the agent user's home dir so pip.conf / .npmrc
                # are found even when the effective UID != 1000.
                environment={"HOME": "/home/agent"},
            )
            print(
                f"[CodeRunner] Sandbox started  image={self._image}  "
                f"workdir={self._workdir}"
            )
        except Exception as exc:
            print(f"[CodeRunner] Podman failed ({exc}) — falling back to local mode.")
            self._sandbox = False
            self._container = None

    def _exec_in_container(self, cmd: list[str]) -> str:
        if self._container is None:
            return "[Error] No sandbox container is running."
        try:
            result = self._container.exec_run(  # type: ignore[union-attr]
                cmd=cmd, workdir="/workspace"
            )
            (retcode, output) = result
            output = output.decode("utf-8", errors="replace") if isinstance(output, bytes) else str(output)
            if retcode != 0:
                output += f"\n[Command exited with code {retcode}]"
            return output
        except Exception as exc:
            return f"[Container exec error] {exc}"

    def cleanup(self) -> None:
        """Stop the sandbox container if one is running."""
        if self._container is not None:
            try:
                self._container.stop()  # type: ignore[union-attr]
                print("[CodeRunner] Sandbox container stopped.")
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Security review (local mode only)
    # ------------------------------------------------------------------

    def _security_review(self, snippet: str, language: str) -> bool:
        """Ask UTILITY_MODEL to assess risk then get explicit user consent.

        Returns True if execution should proceed, False if the user declines.
        Skipped entirely in sandbox mode or when CODE_SECURITY_REVIEW is False.
        """
        if self._sandbox or not CODE_SECURITY_REVIEW:
            return True

        prompt = (
            f"You are a security advisor. An AI agent wants to execute the following "
            f"{language} code on the user's computer.\n\n"
            f"```{language}\n{snippet}\n```\n\n"
            "Respond ONLY with valid JSON — no other text:\n"
            '{"risk": "low|medium|high", "concerns": "brief note or none", '
            '"safe_to_run": true|false}\n\n'
            "Risk levels:\n"
            "  low    — read-only, arithmetic, string ops, clearly benign\n"
            "  medium — file writes, network calls, subprocess spawning, system info\n"
            "  high   — destructive fs ops, credential access, data exfiltration, "
            "privilege escalation"
        )
        try:
            resp = self._client.chat.completions.create(
                model=UTILITY_MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            review: dict = json.loads(resp.choices[0].message.content or "{}")
        except Exception as exc:
            review = {"risk": "unknown", "concerns": str(exc), "safe_to_run": False}

        risk     = str(review.get("risk", "unknown")).lower()
        concerns = str(review.get("concerns", "")).strip()
        safe     = bool(review.get("safe_to_run", False))

        if risk == "low" and safe and CODE_SECURITY_AUTORUN_LOW:
            return True

        print(f"\n[Security Review] Risk: {risk.upper()}")
        if concerns and concerns.lower() not in ("none", ""):
            print(f"[Security Review] {concerns}")
        try:
            answer = input("[Security Review] Execute this code? (yes/no): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False
        return answer in ("yes", "y")

    # ------------------------------------------------------------------
    # Python execution
    # ------------------------------------------------------------------

    def run_python(self, snippet: str) -> str:
        if not self._security_review(snippet, "python"):
            return "[Execution cancelled by user.]"
        if self._sandbox:
            raw = self._exec_in_container(["python3", "-c", snippet])
        else:
            try:
                result = subprocess.run(
                    ["python3", "-c", snippet],
                    capture_output=True,
                    text=True,
                    timeout=PYTHON_TIMEOUT,
                )
                raw = (result.stdout + result.stderr).strip()
                if result.returncode != 0 and not raw:
                    raw = f"[Exited with code {result.returncode}]"
            except subprocess.TimeoutExpired:
                return f"[TIMEOUT after {PYTHON_TIMEOUT}s — process was killed.]"
        return _cap(raw)

    def restart_python(self) -> str:  # kept for tool compatibility
        return (
            "The Python executor is stateless — each run_python call is an independent "
            "subprocess, so there is no persistent session to reset."
        )

    # ------------------------------------------------------------------
    # Shell execution
    # ------------------------------------------------------------------

    def run_shell(self, command: str) -> str:
        if not self._security_review(command, "bash"):
            return "[Execution cancelled by user.]"
        if self._sandbox:
            raw = self._exec_in_container(["bash", "-c", command])
        else:
            try:
                result = subprocess.run(
                    ["bash", "-c", command],
                    capture_output=True,
                    text=True,
                    timeout=SHELL_TIMEOUT,
                )
                raw = (result.stdout + result.stderr).strip()
                if result.returncode != 0:
                    raw += f"\n[Exited with code {result.returncode}]"
            except subprocess.TimeoutExpired:
                return f"[TIMEOUT after {SHELL_TIMEOUT}s — process was killed.]"
        return _cap(raw)

    def restart_shell(self) -> str:  # kept for tool compatibility
        return (
            "The shell executor is stateless — each run_shell call is an independent "
            "bash -c invocation, so there is no persistent session to reset."
        )

    # ------------------------------------------------------------------
    # Path resolution
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def _container_path(self, path: str) -> str:
        """Return the absolute path as seen from inside the container.

        Relative paths are anchored to /workspace. Absolute paths are used
        as-is — the container filesystem namespace provides isolation, so an
        absolute path like /etc refers only to the container's /etc, not the
        host's. No host-side path validation is needed because the host Python
        process never opens the file.
        """
        p = Path(path)
        if p.is_absolute():
            return str(p)
        return str(Path("/workspace") / p)

    def _local_path(self, path: str) -> Path:
        """Normalise a path for local (non-sandbox) mode."""
        p = Path(path)
        return p if p.is_absolute() else Path.cwd() / p

    # ------------------------------------------------------------------
    # File utilities
    # ------------------------------------------------------------------

    def read_file(
        self,
        path: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
    ) -> str:
        try:
            if self._sandbox:
                # Execute entirely inside the container — no host I/O,
                # no TOCTOU window, no symlink surface on the host side.
                cp = self._container_path(path)
                if start_line is None and end_line is None:
                    raw = self._exec_in_container(["cat", cp])
                else:
                    s = (start_line - 1) if start_line else 0
                    e = repr(end_line) if end_line is not None else "None"
                    script = (
                        f"t=open({repr(cp)},encoding='utf-8',errors='replace').read();"
                        f"lines=t.splitlines(keepends=True);"
                        f"print(''.join(lines[{s}:{e}]),end='')"
                    )
                    raw = self._exec_in_container(["python3", "-c", script])
                return _cap(raw)
            # Local mode — direct host I/O
            target = self._local_path(path)
            text = target.read_text(encoding="utf-8", errors="replace")
            if start_line is not None or end_line is not None:
                lines = text.splitlines(keepends=True)
                s = (start_line - 1) if start_line else 0
                e = end_line if end_line else len(lines)
                text = "".join(lines[s:e])
            return _cap(text)
        except Exception as exc:
            return f"[read_file error] {exc}"

    def write_file(self, path: str, content: str) -> str:
        try:
            if self._sandbox:
                # Ship content into the container as base64 to avoid any shell
                # quoting issues with arbitrary text.
                cp = self._container_path(path)
                b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
                script = (
                    f"import base64,pathlib;"
                    f"p=pathlib.Path({repr(cp)});"
                    f"p.parent.mkdir(parents=True,exist_ok=True);"
                    f"p.write_bytes(base64.b64decode({repr(b64)}))"
                )
                raw = self._exec_in_container(["python3", "-c", script])
                if raw.strip():
                    return f"[write_file error] {raw.strip()}"
                return f"Written {len(content):,} characters to '{cp}'."
            # Local mode — atomic write via temp file
            target = self._local_path(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=target.parent)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(content)
                os.replace(tmp, target)
            except Exception:
                os.unlink(tmp)
                raise
            return f"Written {len(content):,} characters to '{target}'."
        except Exception as exc:
            return f"[write_file error] {exc}"

    def patch_file(self, path: str, diff: str) -> str:
        """Apply a unified diff to a file using the patch(1) utility.

        The diff is applied with ``patch --no-backup-if-mismatch -F3``:
        - ``--no-backup-if-mismatch`` keeps the working tree clean.
        - ``-F3`` allows up to 3 lines of fuzz so minor context shifts
          (from previous edits) don't cause needless failures.
        """
        try:
            if self._sandbox:
                # Ship the diff into the container as base64, write it to a
                # temp file there, then invoke patch(1) against the target.
                # The host never opens either file.
                cp = self._container_path(path)
                diff_b64 = base64.b64encode(diff.encode("utf-8")).decode("ascii")
                script = (
                    "import base64,os,subprocess,sys,tempfile;"
                    f"d=base64.b64decode({repr(diff_b64)});"
                    "fd,tmp=tempfile.mkstemp(suffix='.patch');"
                    "os.write(fd,d);os.close(fd);"
                    "r=subprocess.run("
                    f"    ['patch','--no-backup-if-mismatch','-F3','-i',tmp,{repr(cp)}],"
                    "    capture_output=True,text=True);"
                    "os.unlink(tmp);"
                    "out=(r.stdout+r.stderr).strip();"
                    "print(out) if out else None;"
                    "sys.exit(r.returncode)"
                )
                raw = self._exec_in_container(["python3", "-c", script])
                stripped = raw.strip()
                if stripped:
                    return stripped
                return f"Patched '{cp}' successfully."
            # Local mode — write diff to a host temp file and run patch(1).
            target = self._local_path(path)
            fd, tmp = tempfile.mkstemp(suffix=".patch")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(diff)
                result = subprocess.run(
                    ["patch", "--no-backup-if-mismatch", "-F3", "-i", tmp, str(target)],
                    capture_output=True,
                    text=True,
                )
                out = (result.stdout + result.stderr).strip()
                if result.returncode != 0:
                    return f"[patch_file error] patch(1) failed:\n{out}"
                return out or f"Patched '{target}' successfully."
            finally:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
        except Exception as exc:
            return f"[patch_file error] {exc}"

    # ------------------------------------------------------------------
    # Tool registration
    # ------------------------------------------------------------------

    def register_tools(self, tools: Tools) -> None:
        _sandbox_note = (
            " Executes inside a Podman sandbox container; the workspace "
            "directory is bind-mounted so files written there are visible on the host."
            if self._sandbox else
            " Executes on the host. The UTILITY_MODEL reviews the code for risks "
            "and the user must confirm before execution proceeds."
        )

        tools.add_tool(
            {
                "name": "run_python",
                "description": (
                    "Execute a Python code snippet in a stateless subprocess and return "
                    "all stdout and stderr. Each call is an independent `python3 -c` "
                    "invocation — no variables, imports, or definitions persist between "
                    "calls. Ideal for data processing, calculations, file parsing, or "
                    "any computation. If a task needs multiple steps, either write them "
                    "all in one snippet or use write_file + run_shell to run a script."
                    + _sandbox_note
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": (
                                "Valid Python source code to execute. Multi-line code is "
                                "fully supported. Use print() to produce visible output — "
                                "bare expression values are NOT automatically displayed. "
                                "Each call starts with a clean interpreter state."
                            ),
                        }
                    },
                    "required": ["code"],
                },
            },
            lambda p: self.run_python(p["code"]),
        )

        tools.add_tool(
            {
                "name": "run_shell",
                "description": (
                    "Execute a bash command or pipeline in a stateless shell invocation "
                    "and return combined stdout and stderr. Each call is an independent "
                    "`bash -c` process — no state (environment variables, working "
                    "directory, or functions) persists between calls. When directory "
                    "context matters, chain the cd and the command: "
                    "'cd /path/to/dir && git log --oneline -10'. Use this for filesystem "
                    "operations, running programs, package installation, git, build "
                    "tools, and anything more naturally expressed as a shell command "
                    "than Python."
                    + _sandbox_note
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": (
                                "A bash command, pipeline, or multi-line script. "
                                "Examples: 'ls -la', 'cd /repo && git log --oneline -10', "
                                "'pip install requests', 'find . -name \"*.py\" | wc -l'. "
                                "Avoid commands requiring interactive TTY input — they will "
                                "block until the timeout is reached. Each call starts in "
                                "the process working directory; use cd && … to change dirs."
                            ),
                        }
                    },
                    "required": ["command"],
                },
            },
            lambda p: self.run_shell(p["command"]),
        )

        tools.add_tool(
            {
                "name": "read_file",
                "description": (
                    "Read the text contents of a file and return them as a string. "
                    "Optionally restrict to a line range to avoid loading large files "
                    "entirely — lines are 1-indexed and both ends are inclusive. "
                    "Use this to inspect source code, configuration files, logs, "
                    "or any text-based file on the filesystem."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Absolute or relative path to the file.",
                        },
                        "start_line": {
                            "type": "integer",
                            "description": "First line to read (1-based, inclusive). Omit to start from line 1.",
                        },
                        "end_line": {
                            "type": "integer",
                            "description": "Last line to read (1-based, inclusive). Omit to read to end of file.",
                        },
                    },
                    "required": ["path"],
                },
            },
            lambda p: self.read_file(p["path"], p.get("start_line"), p.get("end_line")),
        )

        tools.add_tool(
            {
                "name": "write_file",
                "description": (
                    "Write content to a file, creating it (and any missing parent "
                    "directories) if it does not exist, or overwriting it completely "
                    "if it does. The write is atomic — the old file is never partially "
                    "overwritten. Use this to create new scripts, config files, or save "
                    "generated text. For targeted edits to existing files, prefer "
                    "patch_file to avoid accidentally discarding unchanged content."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Absolute or relative path to write to.",
                        },
                        "content": {
                            "type": "string",
                            "description": "Complete text content to write. Replaces any existing content.",
                        },
                    },
                    "required": ["path", "content"],
                },
            },
            lambda p: self.write_file(p["path"], p["content"]),
        )

        tools.add_tool(
            {
                "name": "patch_file",
                "description": (
                    "Apply a unified diff to a file using the patch(1) utility. "
                    "Preferred over write_file for editing existing files — patch "
                    "is line-number anchored, tolerates minor context shifts (e.g. "
                    "after previous edits moved lines), and makes the change intent "
                    "explicit. Supply the diff in standard unified format as produced "
                    "by `diff -u original modified`. The `--- / +++` header lines are "
                    "optional; a bare hunk starting with `@@ ... @@` is accepted. "
                    "Multiple hunks in one diff are supported."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the file to patch.",
                        },
                        "diff": {
                            "type": "string",
                            "description": (
                                "Unified diff to apply. Example:\n"
                                "@@ -10,6 +10,7 @@\n"
                                " def foo():\n"
                                "-    return 1\n"
                                "+    # updated\n"
                                "+    return 2\n"
                                " \n"
                                "Include 3 or more lines of unchanged context around "
                                "each change so patch can locate the hunk precisely."
                            ),
                        },
                    },
                    "required": ["path", "diff"],
                },
            },
            lambda p: self.patch_file(p["path"], p["diff"]),
        )



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cap(text: str) -> str:
    """Trim output that would flood the context window, preserving head and tail."""
    if len(text) <= MAX_OUTPUT_LEN:
        return text
    half = MAX_OUTPUT_LEN // 2
    trimmed = len(text) - MAX_OUTPUT_LEN
    return (
        text[:half]
        + f"\n\n[... {trimmed:,} characters trimmed from middle ...]\n\n"
        + text[-half:]
    )
        
    