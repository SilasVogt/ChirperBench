from __future__ import annotations

import subprocess
import time

from .types import ProcessResult


def parse_ollama_list(stdout: str) -> list[str]:
    models: list[str] = []
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split()
        if not parts:
            continue
        if parts[0].upper() == "NAME":
            continue
        models.append(parts[0])
    return models


def list_installed_models(timeout: int = 30) -> list[str]:
    proc = subprocess.run(
        ["ollama", "list"],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "ollama list failed")
    return parse_ollama_list(proc.stdout)


def run_model(model: str, prompt: str, timeout: int) -> ProcessResult:
    command = ["ollama", "run", "--nowordwrap", "--hidethinking", "--keepalive", "0", model]
    start = time.monotonic()
    try:
        proc = subprocess.run(
            command,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        elapsed = time.monotonic() - start
        return ProcessResult(
            stdout=proc.stdout,
            stderr=proc.stderr,
            returncode=proc.returncode,
            elapsed_seconds=elapsed,
            timed_out=False,
            command=command,
        )
    except subprocess.TimeoutExpired as exc:
        elapsed = time.monotonic() - start
        stdout = _to_text(exc.stdout)
        stderr = _to_text(exc.stderr)
        return ProcessResult(
            stdout=stdout,
            stderr=stderr,
            returncode=None,
            elapsed_seconds=elapsed,
            timed_out=True,
            command=command,
        )
    except FileNotFoundError as exc:
        elapsed = time.monotonic() - start
        return ProcessResult(
            stdout="",
            stderr=str(exc),
            returncode=127,
            elapsed_seconds=elapsed,
            timed_out=False,
            command=command,
        )


def stop_model(model: str, timeout: int = 30) -> ProcessResult:
    command = ["ollama", "stop", model]
    start = time.monotonic()
    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return ProcessResult(
            stdout=proc.stdout,
            stderr=proc.stderr,
            returncode=proc.returncode,
            elapsed_seconds=time.monotonic() - start,
            command=command,
        )
    except subprocess.TimeoutExpired as exc:
        return ProcessResult(
            stdout=_to_text(exc.stdout),
            stderr=_to_text(exc.stderr),
            returncode=None,
            elapsed_seconds=time.monotonic() - start,
            timed_out=True,
            command=command,
        )
    except FileNotFoundError as exc:
        return ProcessResult(
            stdout="",
            stderr=str(exc),
            returncode=127,
            elapsed_seconds=time.monotonic() - start,
            command=command,
        )


def _to_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value

