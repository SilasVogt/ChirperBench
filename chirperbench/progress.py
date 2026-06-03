from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProgressEstimate:
    completed: int
    total: int
    percent: float
    elapsed_seconds: float
    average_seconds: float | None
    eta_seconds: float | None
    last_seconds: float | None = None


def estimate_progress(
    *,
    completed: int,
    total: int,
    elapsed_seconds: float,
    last_seconds: float | None = None,
) -> ProgressEstimate:
    safe_total = max(0, total)
    safe_completed = min(max(0, completed), safe_total) if safe_total else max(0, completed)
    percent = (safe_completed / safe_total * 100) if safe_total else 0.0
    average = elapsed_seconds / safe_completed if safe_completed else None
    remaining = max(0, safe_total - safe_completed)
    eta = average * remaining if average is not None else None
    return ProgressEstimate(
        completed=safe_completed,
        total=safe_total,
        percent=percent,
        elapsed_seconds=max(0.0, elapsed_seconds),
        average_seconds=average,
        eta_seconds=eta,
        last_seconds=last_seconds,
    )


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "pending"
    whole_seconds = max(0, int(round(seconds)))
    hours, remainder = divmod(whole_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def format_progress(
    *,
    completed: int,
    total: int,
    elapsed_seconds: float,
    last_seconds: float | None = None,
) -> str:
    estimate = estimate_progress(
        completed=completed,
        total=total,
        elapsed_seconds=elapsed_seconds,
        last_seconds=last_seconds,
    )
    parts = [
        f"{estimate.completed}/{estimate.total}",
        f"{estimate.percent:.1f}%",
        f"elapsed {format_duration(estimate.elapsed_seconds)}",
        f"avg {format_duration(estimate.average_seconds)}/result",
        f"eta {format_duration(estimate.eta_seconds)}",
    ]
    if estimate.last_seconds is not None:
        parts.append(f"last {format_duration(estimate.last_seconds)}")
    return " | ".join(parts)

