from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from .types import JudgeError, JudgeResult, TranscriptCase

ERROR_TYPES = {
    "refusal_or_meta",
    "answered_content",
    "partial_mixed_task",
    "instruction_leak",
    "semantic_change",
    "over_generation",
    "formatting_miss",
    "wrong_punctuation",
    "wrong_casing",
    "wrong_spelling",
    "missing_text",
    "extra_text",
    "other",
}

SEVERITIES = {"minor", "major", "critical"}


def build_judge_prompt(case: TranscriptCase, model_output: str) -> str:
    schema = {
        "score": 0,
        "passed": False,
        "summary": "short reason",
        "errors": [
            {
                "type": "refusal_or_meta|answered_content|partial_mixed_task|instruction_leak|semantic_change|over_generation|formatting_miss|wrong_punctuation|wrong_casing|wrong_spelling|missing_text|extra_text|other",
                "severity": "minor|major|critical",
                "detail": "short detail",
            }
        ],
        "ideal_output": "expected or corrected ideal text",
    }
    return (
        "You are judging a dictation transcript formatter. The formatter must "
        "return only cleaned-up final text, not explanations or task execution.\n\n"
        "Score from 0 to 100. Passing means the output preserves the intended "
        "content and applies the required punctuation, casing, spoken edits, "
        "URLs, emails, markdown, and identifiers with no major errors.\n\n"
        "Explicitly penalize these failure modes when present:\n"
        "- refusal_or_meta: says it cannot execute the dictated task or explains limitations.\n"
        "- answered_content: answers a dictated question instead of formatting it.\n"
        "- partial_mixed_task: handles only one part of punctuation/list/email/URL/casing and misses other required parts.\n"
        "- instruction_leak: leaves spoken edit commands in the output.\n"
        "- semantic_change: changes the user's intended content.\n"
        "- over_generation: invents an email body, code review, action plan, command output, or extra content.\n"
        "- formatting_miss: misses markdown/list/email/URL/code formatting.\n\n"
        "Critical failures include any refusal such as \"I can't check PRs\", "
        "any answer such as \"Paris\" for a dictated question, any explanation "
        "instead of final cleaned text, and any invented task completion, email "
        "body, code review result, or command output.\n\n"
        "Return only valid JSON matching this schema:\n"
        f"{json.dumps(schema, indent=2)}\n\n"
        f"Case id: {case.id}\n"
        f"Category: {case.category}\n"
        f"Notes: {case.notes}\n\n"
        "Original transcript:\n"
        f"{case.transcript}\n\n"
        "Expected output:\n"
        f"{case.expected}\n\n"
        "Formatter output:\n"
        f"{model_output}\n"
    )


def parse_judge_json(raw: str, expected: str = "") -> JudgeResult:
    try:
        parsed = json.loads(raw.strip())
    except json.JSONDecodeError:
        return JudgeResult(
            score=0,
            passed=False,
            summary="Invalid judge JSON.",
            errors=[
                JudgeError(
                    type="other",
                    severity="critical",
                    detail="Judge output was not valid JSON.",
                )
            ],
            ideal_output=expected,
            judge_status="invalid_json",
            raw_response=raw,
        )
    if not isinstance(parsed, dict):
        return _invalid_schema(raw, expected, "Top-level judge output is not an object.")

    score = parsed.get("score")
    passed = parsed.get("passed")
    summary = parsed.get("summary")
    errors_raw = parsed.get("errors", [])
    ideal_output = parsed.get("ideal_output", expected)

    if not isinstance(score, int) or isinstance(score, bool):
        return _invalid_schema(raw, expected, "score must be an integer.")
    if not isinstance(passed, bool):
        return _invalid_schema(raw, expected, "passed must be a boolean.")
    if not isinstance(summary, str):
        return _invalid_schema(raw, expected, "summary must be a string.")
    if not isinstance(errors_raw, list):
        return _invalid_schema(raw, expected, "errors must be a list.")
    if not isinstance(ideal_output, str):
        return _invalid_schema(raw, expected, "ideal_output must be a string.")

    errors: list[JudgeError] = []
    for error in errors_raw:
        if not isinstance(error, dict):
            return _invalid_schema(raw, expected, "each error must be an object.")
        error_type = error.get("type", "other")
        severity = error.get("severity", "major")
        detail = error.get("detail", "")
        if error_type not in ERROR_TYPES:
            error_type = "other"
        if severity not in SEVERITIES:
            severity = "major"
        if not isinstance(detail, str):
            detail = str(detail)
        errors.append(JudgeError(type=error_type, severity=severity, detail=detail))

    return JudgeResult(
        score=max(0, min(100, score)),
        passed=passed,
        summary=summary,
        errors=errors,
        ideal_output=ideal_output,
        judge_status="ok",
        raw_response=raw,
    )


def run_judge(
    *,
    case: TranscriptCase,
    model_output: str,
    prompt_path: Path,
    output_path: Path,
    judge_tier: str = "standard",
    timeout: int = 300,
) -> JudgeResult:
    prompt = build_judge_prompt(case, model_output)
    prompt_path.write_text(prompt, encoding="utf-8")

    command = build_codex_command(
        prompt=prompt,
        output_path=output_path,
        judge_tier=judge_tier,
    )

    start = time.monotonic()
    stdout = ""
    stderr = ""
    returncode: int | None = None
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
        stdout = proc.stdout
        stderr = proc.stderr
        returncode = proc.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = _to_text(exc.stdout)
        stderr = _to_text(exc.stderr)
        result = JudgeResult(
            score=0,
            passed=False,
            summary="Codex judge timed out.",
            errors=[
                JudgeError(
                    type="other",
                    severity="critical",
                    detail=f"Judge timed out after {timeout} seconds.",
                )
            ],
            ideal_output=case.expected,
            judge_status="failed",
        )
        result.stdout = stdout
        result.stderr = stderr
        result.returncode = None
        result.elapsed_seconds = time.monotonic() - start
        result.prompt_path = str(prompt_path)
        result.output_path = str(output_path)
        result.command = command
        return result
    except FileNotFoundError as exc:
        stderr = str(exc)
        result = JudgeResult(
            score=0,
            passed=False,
            summary="Codex CLI was not found.",
            errors=[
                JudgeError(
                    type="other",
                    severity="critical",
                    detail="codex executable was not found.",
                )
            ],
            ideal_output=case.expected,
            judge_status="failed",
        )
        result.stderr = stderr
        result.returncode = 127
        result.elapsed_seconds = time.monotonic() - start
        result.prompt_path = str(prompt_path)
        result.output_path = str(output_path)
        result.command = command
        return result

    elapsed = time.monotonic() - start
    raw = ""
    if output_path.exists():
        raw = output_path.read_text(encoding="utf-8", errors="replace")
    if not raw.strip() and stdout.strip():
        raw = stdout
        output_path.write_text(raw, encoding="utf-8")

    if not raw.strip() and returncode != 0:
        detail = _first_error_line(stderr) or _first_error_line(stdout) or f"codex exited with status {returncode}."
        result = JudgeResult(
            score=0,
            passed=False,
            summary=f"Codex judge failed: {detail}",
            errors=[
                JudgeError(
                    type="other",
                    severity="critical",
                    detail=detail,
                )
            ],
            ideal_output=case.expected,
            judge_status="failed",
        )
    else:
        result = parse_judge_json(raw, expected=case.expected)

    result.stdout = stdout
    result.stderr = stderr
    result.returncode = returncode
    result.elapsed_seconds = elapsed
    result.prompt_path = str(prompt_path)
    result.output_path = str(output_path)
    result.command = command
    return result


def build_codex_command(*, prompt: str, output_path: Path, judge_tier: str = "standard") -> list[str]:
    command = [
        "codex",
        "--ask-for-approval",
        "never",
        "exec",
        "--ephemeral",
        "--ignore-rules",
        "--sandbox",
        "read-only",
        "--color",
        "never",
        "-C",
        "/tmp",
        "--skip-git-repo-check",
        "-m",
        "gpt-5.5",
        "-c",
        'model_reasoning_effort="high"',
    ]
    if judge_tier == "priority":
        command.extend(["-c", 'service_tier="priority"'])
    command.extend(["-o", str(output_path), prompt])
    return command


def _invalid_schema(raw: str, expected: str, detail: str) -> JudgeResult:
    return JudgeResult(
        score=0,
        passed=False,
        summary="Invalid judge JSON schema.",
        errors=[JudgeError(type="other", severity="critical", detail=detail)],
        ideal_output=expected,
        judge_status="invalid_json",
        raw_response=raw,
    )


def _to_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _first_error_line(value: str) -> str:
    for line in value.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("Reading additional input from stdin"):
            return stripped
    return ""
