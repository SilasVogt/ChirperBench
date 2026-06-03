from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TranscriptCase:
    id: str
    category: str
    transcript: str
    expected: str
    notes: str

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "category": self.category,
            "transcript": self.transcript,
            "expected": self.expected,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class JudgeError:
    type: str
    severity: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {
            "type": self.type,
            "severity": self.severity,
            "detail": self.detail,
        }


@dataclass
class JudgeResult:
    score: int
    passed: bool
    summary: str
    errors: list[JudgeError] = field(default_factory=list)
    ideal_output: str = ""
    judge_status: str = "ok"
    raw_response: str = ""
    stdout: str = ""
    stderr: str = ""
    returncode: int | None = None
    elapsed_seconds: float = 0.0
    prompt_path: str = ""
    output_path: str = ""
    command: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "passed": self.passed,
            "summary": self.summary,
            "errors": [error.to_dict() for error in self.errors],
            "ideal_output": self.ideal_output,
            "judge_status": self.judge_status,
            "raw_response": self.raw_response,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "returncode": self.returncode,
            "elapsed_seconds": self.elapsed_seconds,
            "prompt_path": self.prompt_path,
            "output_path": self.output_path,
            "command": self.command,
        }


@dataclass
class ProcessResult:
    stdout: str
    stderr: str
    returncode: int | None
    elapsed_seconds: float
    timed_out: bool = False
    command: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out

    @property
    def status(self) -> str:
        if self.timed_out:
            return "timeout"
        if self.returncode == 0:
            return "ok"
        return "failed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "stdout": self.stdout,
            "stderr": self.stderr,
            "returncode": self.returncode,
            "elapsed_seconds": self.elapsed_seconds,
            "timed_out": self.timed_out,
            "status": self.status,
            "command": self.command,
        }

