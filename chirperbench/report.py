from __future__ import annotations

import json
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


def new_run_id(now: datetime | None = None) -> str:
    return (now or datetime.now()).strftime("%Y%m%d-%H%M%S")


def safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_")
    return cleaned or "item"


def relpath(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def rank_models(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        by_model[str(result.get("model", ""))].append(result)

    rows: list[dict[str, Any]] = []
    for model, model_results in by_model.items():
        count = len(model_results)
        scores = [_result_score(result) for result in model_results]
        pass_count = sum(1 for result in model_results if bool(result.get("passed")))
        latencies = [
            float(result.get("latency_seconds", 0.0) or 0.0)
            for result in model_results
        ]
        judge_error_count = sum(
            len((result.get("judge") or {}).get("errors") or [])
            for result in model_results
        )
        ollama_error_count = sum(
            1 for result in model_results if result.get("ollama_status") != "ok"
        )
        rows.append(
            {
                "model": model,
                "case_count": count,
                "average_score": round(sum(scores) / count, 2) if count else 0.0,
                "pass_count": pass_count,
                "pass_rate": round(pass_count / count, 4) if count else 0.0,
                "median_latency_seconds": round(statistics.median(latencies), 4)
                if latencies
                else 0.0,
                "error_count": judge_error_count + ollama_error_count,
                "ollama_error_count": ollama_error_count,
                "judge_error_count": judge_error_count,
            }
        )

    rows.sort(
        key=lambda row: (
            -float(row["average_score"]),
            -float(row["pass_rate"]),
            float(row["median_latency_seconds"]),
            int(row["error_count"]),
            str(row["model"]),
        )
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def refresh_summary(run_data: dict[str, Any]) -> dict[str, Any]:
    results = list(run_data.get("results") or [])
    cases = list(run_data.get("cases") or [])
    case_by_id = {case.get("id"): case for case in cases}
    models = list(run_data.get("models") or [])
    if not models:
        models = sorted({str(result.get("model", "")) for result in results if result.get("model")})

    leaderboard = rank_models(results)
    per_case = []
    matrix = []
    for case in cases:
        case_id = case.get("id")
        case_results = [result for result in results if result.get("case_id") == case_id]
        scores = [_result_score(result) for result in case_results]
        pass_count = sum(1 for result in case_results if bool(result.get("passed")))
        per_case.append(
            {
                "case_id": case_id,
                "category": case.get("category", ""),
                "model_count": len(case_results),
                "average_score": round(sum(scores) / len(scores), 2) if scores else 0.0,
                "pass_rate": round(pass_count / len(case_results), 4)
                if case_results
                else 0.0,
            }
        )
        cells = {}
        for model in models:
            result = next(
                (
                    item
                    for item in case_results
                    if item.get("model") == model and item.get("case_id") == case_id
                ),
                None,
            )
            cells[model] = {
                "score": _result_score(result) if result else None,
                "passed": bool(result.get("passed")) if result else False,
                "ollama_status": result.get("ollama_status") if result else "missing",
                "judge_status": result.get("judge_status") if result else "missing",
            }
        matrix.append(
            {
                "case_id": case_id,
                "category": case.get("category", ""),
                "cells": cells,
            }
        )

    error_counts: Counter[str] = Counter()
    severity_counts: Counter[str] = Counter()
    for result in results:
        judge = result.get("judge") or {}
        for error in judge.get("errors") or []:
            error_counts[str(error.get("type", "other"))] += 1
            severity_counts[str(error.get("severity", "major"))] += 1
        if result.get("ollama_status") != "ok":
            error_counts["ollama_run_failed"] += 1
            severity_counts["critical"] += 1

    run_data["summary"] = {
        "leaderboard": leaderboard,
        "models": leaderboard,
        "cases": per_case,
        "matrix": matrix,
        "error_counts": dict(sorted(error_counts.items())),
        "severity_counts": dict(sorted(severity_counts.items())),
        "result_count": len(results),
        "case_count": len(cases),
        "model_count": len(models),
    }
    return run_data["summary"]


def write_run_artifacts(run_dir: Path, run_data: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    refresh_summary(run_data)
    (run_dir / "run.json").write_text(
        json.dumps(run_data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (run_dir / "summary.md").write_text(render_summary_markdown(run_data), encoding="utf-8")


def load_run(path: Path) -> dict[str, Any]:
    run_data = json.loads(path.read_text(encoding="utf-8"))
    refresh_summary(run_data)
    return run_data


def render_summary_markdown(run_data: dict[str, Any]) -> str:
    refresh_summary(run_data)
    lines = [
        f"# ChirperBench Run {run_data.get('run_id', '')}",
        "",
        f"Created: {run_data.get('created_at', '')}",
        f"Judge enabled: {run_data.get('judge_enabled', False)}",
        f"Models: {', '.join(run_data.get('models') or [])}",
        f"Cases: {len(run_data.get('cases') or [])}",
        "",
        "## Leaderboard",
        "",
        "| Rank | Model | Average score | Pass rate | Median latency | Errors |",
        "| ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in run_data["summary"]["leaderboard"]:
        lines.append(
            "| {rank} | {model} | {average_score:.2f} | {pass_rate:.1%} | "
            "{median_latency_seconds:.3f}s | {error_count} |".format(**row)
        )
    lines.extend(["", "## Error Counts", ""])
    error_counts = run_data["summary"].get("error_counts") or {}
    if error_counts:
        for error_type, count in error_counts.items():
            lines.append(f"- `{error_type}`: {count}")
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def _result_score(result: dict[str, Any] | None) -> int:
    if not result:
        return 0
    score = result.get("score")
    if isinstance(score, int) and not isinstance(score, bool):
        return max(0, min(100, score))
    judge = result.get("judge") or {}
    score = judge.get("score")
    if isinstance(score, int) and not isinstance(score, bool):
        return max(0, min(100, score))
    return 0

