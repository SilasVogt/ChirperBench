from __future__ import annotations

import argparse
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .cases import filter_cases
from .judge_codex import run_judge
from .ollama import list_installed_models, run_model, stop_model
from .prompt import render_prompt
from .progress import format_duration, format_progress
from .report import new_run_id, relpath, safe_filename, write_run_artifacts
from .site import generate_site
from .telemetry import TelemetryRecorder, build_telemetry_reader


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return run_command(args)
    if args.command == "site":
        return site_command(args)
    parser.print_help()
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="chirperbench")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run Ollama models through ChirperBench.")
    run_parser.add_argument("--models", nargs="+", help="Model names. Defaults to all installed Ollama models.")
    run_parser.add_argument("--case", action="append", dest="cases", help="Case id to run. May be repeated.")
    run_parser.add_argument("--output-dir", default="./runs", help="Directory that receives timestamped run folders.")
    run_parser.add_argument("--site-dir", default="./site", help="Directory for generated static site.")
    run_parser.add_argument("--timeout", type=int, default=180, help="Timeout in seconds for each Ollama run.")
    run_parser.add_argument("--judge-timeout", type=int, default=300, help="Timeout in seconds for each Codex judge run.")
    run_parser.add_argument("--no-judge", action="store_true", help="Skip Codex judging.")
    run_parser.add_argument("--judge-tier", choices=["standard", "priority"], default="standard")
    run_parser.add_argument("--keep-loaded", action="store_true", help="Do not run ollama stop after each result.")
    run_parser.add_argument("--no-site", action="store_true", help="Do not refresh the static site after the run.")
    run_parser.add_argument(
        "--telemetry",
        choices=["auto", "off", "amd-sysfs"],
        default="auto",
        help="Capture local GPU telemetry when supported. Default: auto.",
    )
    run_parser.add_argument(
        "--telemetry-interval",
        type=float,
        default=0.5,
        help="Seconds between telemetry samples. Default: 0.5.",
    )
    run_parser.add_argument(
        "--progress-interval",
        type=float,
        default=30.0,
        help="Seconds between long-stage progress heartbeats. Use 0 to disable. Default: 30.",
    )

    site_parser = subparsers.add_parser("site", help="Generate the static score site from saved runs.")
    site_parser.add_argument("--runs-dir", default="./runs")
    site_parser.add_argument("--site-dir", default="./site")
    return parser


def run_command(args: argparse.Namespace) -> int:
    try:
        cases = filter_cases(args.cases)
    except KeyError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    models = _model_args(args.models)
    if not models:
        try:
            models = list_installed_models()
        except Exception as exc:
            print(f"Unable to list Ollama models: {exc}", file=sys.stderr)
            return 2
    if not models:
        print("No models selected.", file=sys.stderr)
        return 2
    if not cases:
        print("No cases selected.", file=sys.stderr)
        return 2

    output_root = Path(args.output_dir)
    run_id = new_run_id()
    run_dir = output_root / run_id
    prompts_dir = run_dir / "prompts"
    outputs_dir = run_dir / "outputs"
    judge_prompts_dir = run_dir / "judge-prompts"
    judge_dir = run_dir / "judge"
    for directory in (prompts_dir, outputs_dir, judge_prompts_dir, judge_dir):
        directory.mkdir(parents=True, exist_ok=True)
    telemetry_reader = build_telemetry_reader(args.telemetry)

    run_data: dict[str, Any] = {
        "run_id": run_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "models": models,
        "cases": [case.to_dict() for case in cases],
        "judge_enabled": not args.no_judge,
        "judge_model": None if args.no_judge else "gpt-5.5",
        "judge_reasoning_effort": None if args.no_judge else "high",
        "judge_tier": args.judge_tier,
        "options": {
            "timeout": args.timeout,
            "judge_timeout": args.judge_timeout,
            "keep_loaded": args.keep_loaded,
            "output_dir": str(output_root),
            "site_dir": str(args.site_dir),
            "telemetry": args.telemetry,
            "telemetry_interval": args.telemetry_interval,
            "progress_interval": args.progress_interval,
        },
        "telemetry": {
            "mode": args.telemetry,
            "interval_seconds": args.telemetry_interval,
            "provider": telemetry_reader.provider,
            "status": telemetry_reader.status,
            "reason": telemetry_reader.reason,
            "device": telemetry_reader.describe(),
        },
        "results": [],
    }
    write_run_artifacts(run_dir, run_data)

    total = len(models) * len(cases)
    completed = 0
    run_started_at = time.monotonic()
    print(f"Run {run_id}: {len(models)} model(s) x {len(cases)} case(s) = {total} result(s)", flush=True)
    print(f"Artifacts: {run_dir / 'run.json'}", flush=True)
    print(f"Judge: {_judge_description(args)}", flush=True)
    print(f"Telemetry: {_telemetry_description(telemetry_reader.describe())}", flush=True)
    print(f"Progress: {format_progress(completed=0, total=total, elapsed_seconds=0)}", flush=True)
    for model in models:
        for case in cases:
            result_index = completed + 1
            result_started_at = time.monotonic()
            print("", flush=True)
            print(
                f"[{result_index}/{total} {result_index / total * 100:.1f}%] {model} / {case.id}",
                flush=True,
            )
            print(
                "  progress: "
                + format_progress(
                    completed=completed,
                    total=total,
                    elapsed_seconds=time.monotonic() - run_started_at,
                ),
                flush=True,
            )
            prompt = render_prompt(case.transcript)
            base_name = f"{safe_filename(model)}__{case.id}"
            prompt_path = prompts_dir / f"{base_name}.txt"
            output_path = outputs_dir / f"{base_name}.txt"
            prompt_path.write_text(prompt, encoding="utf-8")

            print(f"  stage: ollama run (timeout {format_duration(args.timeout)})", flush=True)
            telemetry = TelemetryRecorder(telemetry_reader, interval_seconds=args.telemetry_interval)
            telemetry.start()
            with _stage_heartbeat(
                stage="ollama run",
                progress_interval=args.progress_interval,
                run_started_at=run_started_at,
                stage_started_at=time.monotonic(),
                completed=completed,
                total=total,
            ):
                process = run_model(model, prompt, timeout=args.timeout)
            telemetry_result = telemetry.stop()
            output_path.write_text(process.stdout, encoding="utf-8")
            print(
                "  stage done: ollama "
                f"{process.status} in {format_duration(process.elapsed_seconds)}; "
                f"output {len(process.stdout)} chars; "
                f"telemetry {telemetry_result.get('sample_count', 0)} samples",
                flush=True,
            )
            stop_result = None
            if not args.keep_loaded:
                print("  stage: ollama stop", flush=True)
                with _stage_heartbeat(
                    stage="ollama stop",
                    progress_interval=args.progress_interval,
                    run_started_at=run_started_at,
                    stage_started_at=time.monotonic(),
                    completed=completed,
                    total=total,
                ):
                    stop_result = stop_model(model)
                print(
                    f"  stage done: stop {stop_result.status} in "
                    f"{format_duration(stop_result.elapsed_seconds)}",
                    flush=True,
                )

            result_record = {
                "model": model,
                "case_id": case.id,
                "category": case.category,
                "prompt_path": relpath(prompt_path, run_dir),
                "output_path": relpath(output_path, run_dir),
                "output": process.stdout,
                "stderr": process.stderr,
                "returncode": process.returncode,
                "latency_seconds": round(process.elapsed_seconds, 4),
                "timed_out": process.timed_out,
                "ollama_status": process.status,
                "ollama_command": process.command,
                "stop": stop_result.to_dict() if stop_result else None,
                "telemetry": telemetry_result,
                "judge_status": "skipped" if args.no_judge else "not_run",
                "judge": None,
                "score": 0,
                "passed": False,
            }

            if process.ok and not args.no_judge:
                print(f"  stage: judging with gpt-5.5 (timeout {format_duration(args.judge_timeout)})", flush=True)
                judge_prompt_path = judge_prompts_dir / f"{base_name}.txt"
                judge_output_path = judge_dir / f"{base_name}.json"
                with _stage_heartbeat(
                    stage="judging",
                    progress_interval=args.progress_interval,
                    run_started_at=run_started_at,
                    stage_started_at=time.monotonic(),
                    completed=completed,
                    total=total,
                ):
                    judge_result = run_judge(
                        case=case,
                        model_output=process.stdout,
                        prompt_path=judge_prompt_path,
                        output_path=judge_output_path,
                        judge_tier=args.judge_tier,
                        timeout=args.judge_timeout,
                    )
                judge_dict = judge_result.to_dict()
                judge_dict["prompt_path"] = relpath(judge_prompt_path, run_dir)
                judge_dict["output_path"] = relpath(judge_output_path, run_dir)
                result_record["judge"] = judge_dict
                result_record["judge_status"] = judge_result.judge_status
                result_record["score"] = judge_result.score
                result_record["passed"] = judge_result.passed
                print(
                    "  stage done: judge "
                    f"{judge_result.judge_status} in {format_duration(judge_result.elapsed_seconds)}; "
                    f"score {judge_result.score}; passed {judge_result.passed}",
                    flush=True,
                )
            elif args.no_judge:
                print("  stage: judge skipped (--no-judge)", flush=True)
            elif not process.ok:
                print("  stage: judge skipped (ollama run failed)", flush=True)

            run_data["results"].append(result_record)
            print("  stage: writing artifacts", flush=True)
            write_run_artifacts(run_dir, run_data)
            result_elapsed = time.monotonic() - result_started_at
            completed += 1
            print(
                "  done: "
                f"score {result_record['score']}; passed {result_record['passed']}; "
                + format_progress(
                    completed=completed,
                    total=total,
                    elapsed_seconds=time.monotonic() - run_started_at,
                    last_seconds=result_elapsed,
                ),
                flush=True,
            )

    benchmark_elapsed = time.monotonic() - run_started_at
    print(
        f"\nBenchmark finished: {completed}/{total} result(s) in {format_duration(benchmark_elapsed)}",
        flush=True,
    )
    if not args.no_site:
        site_started_at = time.monotonic()
        print("Refreshing static site...", flush=True)
        index_path = generate_site(output_root, args.site_dir)
        print(
            f"Site: {index_path} ({format_duration(time.monotonic() - site_started_at)})",
            flush=True,
        )
    print(f"Run: {run_dir / 'run.json'}", flush=True)
    return 0


def site_command(args: argparse.Namespace) -> int:
    index_path = generate_site(args.runs_dir, args.site_dir)
    print(f"Site: {index_path}")
    return 0


def _model_args(values: list[str] | None) -> list[str]:
    if not values:
        return []
    models: list[str] = []
    for value in values:
        for item in value.split(","):
            model = item.strip()
            if model:
                models.append(model)
    return models


def _judge_description(args: argparse.Namespace) -> str:
    if args.no_judge:
        return "disabled"
    if args.judge_tier == "priority":
        return "gpt-5.5, high reasoning, priority tier"
    return "gpt-5.5, high reasoning"


def _telemetry_description(device: dict[str, Any]) -> str:
    provider = device.get("provider", "none")
    status = device.get("status", "unknown")
    if status == "disabled":
        return "disabled"
    if status != "ok":
        reason = device.get("reason") or "not available"
        return f"{provider} {status}: {reason}"
    parts = [f"{provider} ok"]
    if device.get("card"):
        parts.append(str(device["card"]))
    if device.get("driver"):
        parts.append(str(device["driver"]))
    if device.get("vram_total_mb"):
        parts.append(f"{device['vram_total_mb']} MB VRAM")
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} ({', '.join(parts[1:])})"


class _stage_heartbeat:
    def __init__(
        self,
        *,
        stage: str,
        progress_interval: float,
        run_started_at: float,
        stage_started_at: float,
        completed: int,
        total: int,
    ):
        self.stage = stage
        self.progress_interval = float(progress_interval)
        self.run_started_at = run_started_at
        self.stage_started_at = stage_started_at
        self.completed = completed
        self.total = total
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def __enter__(self) -> "_stage_heartbeat":
        if self.progress_interval > 0:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)

    def _run(self) -> None:
        while not self._stop.wait(self.progress_interval):
            stage_elapsed = time.monotonic() - self.stage_started_at
            run_elapsed = time.monotonic() - self.run_started_at
            print(
                f"  still running: {self.stage} for {format_duration(stage_elapsed)}; "
                + format_progress(
                    completed=self.completed,
                    total=self.total,
                    elapsed_seconds=run_elapsed,
                ),
                flush=True,
            )
