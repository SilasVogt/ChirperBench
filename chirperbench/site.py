from __future__ import annotations

import json
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any

from .judge_codex import ERROR_TYPES
from .prompt import CANONICAL_PROMPT_TEMPLATE
from .report import load_run, refresh_summary


def generate_site(runs_dir: str | Path, site_dir: str | Path) -> Path:
    runs_path = Path(runs_dir)
    site_path = Path(site_dir)
    data_path = site_path / "data"
    site_path.mkdir(parents=True, exist_ok=True)
    data_path.mkdir(parents=True, exist_ok=True)

    runs = _discover_runs(runs_path)
    payload = {
        "runs": [],
        "data": {},
        "error_types": sorted(ERROR_TYPES),
        "prompt_template": CANONICAL_PROMPT_TEMPLATE,
    }
    latest_run_id = ""
    for run_file in runs:
        run_data = load_run(run_file)
        run_id = str(run_data.get("run_id") or run_file.parent.name)
        run_data["run_id"] = run_id
        refresh_summary(run_data)
        public_run_data = make_public_run_data(run_data)
        payload["runs"].append(
            {
                "id": run_id,
                "created_at": public_run_data.get("created_at", ""),
                "result_count": len(public_run_data.get("results") or []),
            }
        )
        payload["data"][run_id] = public_run_data
        target = data_path / f"{run_id}.json"
        target.write_text(json.dumps(public_run_data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        summary_target = data_path / f"{run_id}-summary.json"
        summary_target.write_text(
            json.dumps(make_public_summary_data(public_run_data), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        latest_run_id = run_id

    if latest_run_id:
        shutil.copyfile(data_path / f"{latest_run_id}.json", data_path / "latest-run.json")
        shutil.copyfile(data_path / f"{latest_run_id}-summary.json", data_path / "latest-summary.json")
    else:
        (data_path / "latest-run.json").write_text("{}\n", encoding="utf-8")
        (data_path / "latest-summary.json").write_text("{}\n", encoding="utf-8")

    index_html = _render_index(payload)
    index_path = site_path / "index.html"
    index_path.write_text(index_html, encoding="utf-8")
    return index_path


def _discover_runs(runs_path: Path) -> list[Path]:
    if (runs_path / "run.json").exists():
        return [runs_path / "run.json"]
    if not runs_path.exists():
        return []
    return sorted(path / "run.json" for path in runs_path.iterdir() if (path / "run.json").exists())


def make_public_run_data(run_data: dict[str, Any]) -> dict[str, Any]:
    public = {
        "run_id": run_data.get("run_id", ""),
        "created_at": run_data.get("created_at", ""),
        "models": list(run_data.get("models") or []),
        "cases": deepcopy(run_data.get("cases") or []),
        "judge_enabled": run_data.get("judge_enabled", False),
        "judge_model": run_data.get("judge_model"),
        "judge_reasoning_effort": run_data.get("judge_reasoning_effort"),
        "judge_tier": run_data.get("judge_tier"),
        "options": deepcopy(run_data.get("options") or {}),
        "telemetry": deepcopy(run_data.get("telemetry") or {}),
        "summary": deepcopy(run_data.get("summary") or {}),
        "results": [],
    }
    for result in run_data.get("results") or []:
        judge = result.get("judge") or {}
        public["results"].append(
            {
                "model": result.get("model", ""),
                "case_id": result.get("case_id", ""),
                "category": result.get("category", ""),
                "output": result.get("output", ""),
                "score": result.get("score", 0),
                "passed": result.get("passed", False),
                "latency_seconds": result.get("latency_seconds", 0.0),
                "timed_out": result.get("timed_out", False),
                "ollama_status": result.get("ollama_status", ""),
                "judge_status": result.get("judge_status", ""),
                "telemetry": _public_telemetry(result.get("telemetry") or {}),
                "judge": _public_judge(judge) if judge else None,
            }
        )
    return public


def make_public_summary_data(run_data: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": run_data.get("run_id", ""),
        "created_at": run_data.get("created_at", ""),
        "judge_enabled": run_data.get("judge_enabled", False),
        "judge_model": run_data.get("judge_model"),
        "judge_reasoning_effort": run_data.get("judge_reasoning_effort"),
        "judge_tier": run_data.get("judge_tier"),
        "model_count": len(run_data.get("models") or []),
        "case_count": len(run_data.get("cases") or []),
        "result_count": len(run_data.get("results") or []),
        "telemetry": deepcopy(run_data.get("telemetry") or {}),
        "summary": deepcopy(run_data.get("summary") or {}),
    }


def _public_judge(judge: dict[str, Any]) -> dict[str, Any]:
    return {
        "score": judge.get("score", 0),
        "passed": judge.get("passed", False),
        "summary": judge.get("summary", ""),
        "errors": deepcopy(judge.get("errors") or []),
        "ideal_output": judge.get("ideal_output", ""),
        "judge_status": judge.get("judge_status", ""),
        "returncode": judge.get("returncode"),
        "elapsed_seconds": judge.get("elapsed_seconds", 0.0),
    }


def _public_telemetry(telemetry: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": telemetry.get("status", ""),
        "provider": telemetry.get("provider", ""),
        "reason": telemetry.get("reason", ""),
        "sample_count": telemetry.get("sample_count", 0),
        "elapsed_seconds": telemetry.get("elapsed_seconds", 0.0),
        "metrics": deepcopy(telemetry.get("metrics") or {}),
        "device": deepcopy(telemetry.get("device") or {}),
    }


def _render_index(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True).replace("</", "<\\/")
    return INDEX_TEMPLATE.replace("__RUN_DATA__", encoded)


INDEX_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ChirperBench Scores</title>
  <style>
    :root {
      color-scheme: light;
      --paper: #f7f7f2;
      --ink: #181713;
      --muted: #6d6a61;
      --line: #d8d4c8;
      --panel: #ffffff;
      --green: #147a5c;
      --red: #b43d2f;
      --gold: #d7a529;
      --cyan: #1b7f95;
      --lavender: #7962a8;
      --shadow: 0 18px 45px rgba(20, 18, 13, 0.09);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background:
        linear-gradient(90deg, rgba(24,23,19,0.035) 1px, transparent 1px) 0 0 / 32px 32px,
        linear-gradient(0deg, rgba(24,23,19,0.03) 1px, transparent 1px) 0 0 / 32px 32px,
        var(--paper);
      color: var(--ink);
      font-family: ui-serif, Georgia, Cambria, "Times New Roman", serif;
    }
    button, input, select {
      font: inherit;
    }
    .shell {
      width: min(1480px, calc(100vw - 28px));
      margin: 0 auto;
      padding: 28px 0 44px;
    }
    header {
      display: grid;
      grid-template-columns: 1.2fr auto;
      gap: 18px;
      align-items: end;
      border-bottom: 2px solid var(--ink);
      padding-bottom: 18px;
      margin-bottom: 22px;
    }
    h1, h2 {
      margin: 0;
      letter-spacing: 0;
    }
    h1 {
      font-size: clamp(2.1rem, 4vw, 4.8rem);
      line-height: 0.92;
      max-width: 900px;
    }
    h2 {
      font-size: 1.16rem;
      text-transform: uppercase;
      margin-bottom: 12px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    }
    .controls {
      display: flex;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;
      justify-content: flex-end;
    }
    .top-nav {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 16px;
    }
    .nav-button {
      border: 1px solid var(--ink);
      background: var(--panel);
      color: var(--ink);
      min-height: 36px;
      padding: 7px 10px;
      cursor: pointer;
      box-shadow: 3px 3px 0 rgba(24, 23, 19, 0.12);
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.82rem;
    }
    .nav-button.active {
      background: var(--ink);
      color: #fff;
    }
    select, .download, .filter-chip {
      border: 1px solid var(--ink);
      background: var(--panel);
      color: var(--ink);
      min-height: 38px;
      padding: 8px 10px;
      box-shadow: 4px 4px 0 rgba(24, 23, 19, 0.12);
    }
    .download {
      text-decoration: none;
      display: inline-flex;
      align-items: center;
    }
    .stats {
      display: grid;
      grid-template-columns: repeat(5, minmax(140px, 1fr));
      gap: 12px;
      margin-bottom: 22px;
    }
    .stat {
      background: var(--ink);
      color: #fff;
      padding: 15px 16px;
      min-height: 92px;
      box-shadow: var(--shadow);
    }
    .stat:nth-child(2) { background: var(--green); }
    .stat:nth-child(3) { background: var(--cyan); }
    .stat:nth-child(4) { background: var(--gold); color: var(--ink); }
    .stat:nth-child(5) { background: var(--lavender); }
    .stat .label {
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.74rem;
      text-transform: uppercase;
      opacity: 0.78;
    }
    .stat .value {
      font-size: clamp(1.15rem, 1.8vw, 2rem);
      line-height: 1;
      margin-top: 9px;
      font-weight: 700;
      overflow-wrap: anywhere;
    }
    .stat .detail {
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.78rem;
      margin-top: 8px;
      opacity: 0.82;
    }
    .grid {
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      gap: 20px;
    }
    .view[hidden] {
      display: none;
    }
    section {
      min-width: 0;
    }
    .about-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }
    .about-panel,
    .test-browser {
      border: 2px solid var(--ink);
      background: var(--panel);
      box-shadow: var(--shadow);
      padding: 15px;
      min-width: 0;
    }
    .about-panel.wide {
      grid-column: 1 / -1;
    }
    .about-panel h3,
    .test-card h3 {
      margin: 0 0 10px;
      font-size: 1.2rem;
      line-height: 1.1;
    }
    .about-panel p,
    .about-panel li {
      line-height: 1.42;
      margin: 0 0 9px;
    }
    .about-panel ul {
      margin: 0;
      padding-left: 20px;
    }
    .prompt-box {
      border: 1px solid var(--line);
      background: #fffdf7;
      padding: 12px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.84rem;
    }
    .test-top {
      display: grid;
      grid-template-columns: minmax(220px, 1fr) auto;
      gap: 12px;
      align-items: start;
      margin-bottom: 12px;
    }
    .pager {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      justify-content: flex-end;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.82rem;
    }
    .test-card {
      display: grid;
      gap: 12px;
    }
    .test-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.78rem;
    }
    .test-meta span {
      border: 1px solid var(--line);
      background: #fffdf7;
      padding: 5px 7px;
    }
    .viz-wrap {
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      gap: 12px;
      border: 2px solid var(--ink);
      background: var(--panel);
      box-shadow: var(--shadow);
      padding: 13px;
    }
    .plot-head {
      display: flex;
      gap: 10px;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.86rem;
    }
    .plot-card {
      min-height: 380px;
      border: 1px solid var(--line);
      background:
        linear-gradient(90deg, rgba(24,23,19,0.045) 1px, transparent 1px) 0 0 / 48px 48px,
        linear-gradient(0deg, rgba(24,23,19,0.045) 1px, transparent 1px) 0 0 / 48px 48px,
        #fffdf7;
      overflow: hidden;
    }
    .scatter {
      display: block;
      width: 100%;
      height: auto;
      min-height: 360px;
    }
    .axis,
    .gridline {
      stroke: var(--ink);
      stroke-width: 1;
      vector-effect: non-scaling-stroke;
    }
    .gridline {
      opacity: 0.16;
    }
    .point {
      cursor: pointer;
      stroke: var(--ink);
      stroke-width: 1.5;
      vector-effect: non-scaling-stroke;
      transition: r 120ms ease, opacity 120ms ease;
    }
    .point:hover {
      r: 8;
      opacity: 0.85;
    }
    .axis-label,
    .point-label {
      fill: var(--ink);
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
    }
    .point-label {
      font-weight: 700;
    }
    .metric-note {
      color: var(--muted);
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.82rem;
    }
    .compare-wrap {
      border: 2px solid var(--ink);
      background: var(--panel);
      box-shadow: var(--shadow);
      padding: 13px;
      display: grid;
      gap: 12px;
    }
    .compare-controls {
      display: grid;
      grid-template-columns: minmax(220px, 1fr) auto;
      gap: 12px;
      align-items: start;
    }
    .compare-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      justify-content: flex-end;
    }
    .small-button {
      border: 1px solid var(--ink);
      background: #fff;
      color: var(--ink);
      min-height: 34px;
      padding: 7px 10px;
      cursor: pointer;
      box-shadow: 3px 3px 0 rgba(24, 23, 19, 0.12);
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.82rem;
    }
    .model-picker {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .model-chip {
      border: 1px solid var(--line);
      background: #fffdf7;
      display: inline-flex;
      align-items: center;
      gap: 7px;
      padding: 7px 9px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.78rem;
      cursor: pointer;
      flex-wrap: wrap;
    }
    .model-chip.pick-score { background: #edf8f1; border-color: var(--green); }
    .model-chip.pick-fastest { background: #eaf7fa; border-color: var(--cyan); }
    .model-chip.pick-balanced { background: #fff5d3; border-color: var(--gold); }
    .model-chip.special-favorite { box-shadow: inset 0 -4px 0 rgba(121, 98, 168, 0.45); }
    .model-chip.special-funny { box-shadow: inset 0 -4px 0 rgba(180, 61, 47, 0.45); }
    .model-chip input {
      accent-color: var(--green);
    }
    .chip-text {
      font-weight: 700;
    }
    .compare-badges {
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
      margin-top: 6px;
    }
    .model-badge.badge-score { color: var(--green); background: #edf8f1; }
    .model-badge.badge-fastest { color: var(--cyan); background: #eaf7fa; }
    .model-badge.badge-balanced { color: #8a6500; background: #fff5d3; }
    .model-badge.badge-favorite { color: var(--lavender); background: #f0ecfb; }
    .model-badge.badge-funny { color: var(--red); background: #fbe9e6; }
    .compare-reference {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }
    .compare-strip {
      display: grid;
      grid-auto-flow: column;
      grid-auto-columns: minmax(320px, 1fr);
      gap: 12px;
      overflow-x: auto;
      padding-bottom: 4px;
    }
    .compare-card {
      border: 1px solid var(--ink);
      background: #fff;
      min-width: 0;
      display: grid;
      grid-template-rows: auto auto minmax(160px, 1fr) auto;
    }
    .compare-card.pick-score { border-color: var(--green); }
    .compare-card.pick-fastest { border-color: var(--cyan); }
    .compare-card.pick-balanced { border-color: var(--gold); }
    .compare-card.special-favorite { outline: 3px solid rgba(121, 98, 168, 0.35); outline-offset: -5px; }
    .compare-card.special-funny { outline: 3px dashed rgba(180, 61, 47, 0.45); outline-offset: -5px; }
    .compare-card header {
      display: block;
      border: 0;
      border-bottom: 1px solid var(--line);
      margin: 0;
      padding: 10px 11px;
      background: var(--ink);
      color: #fff;
    }
    .compare-card.pick-score header { background: var(--green); }
    .compare-card.pick-fastest header { background: var(--cyan); }
    .compare-card.pick-balanced header { background: var(--gold); color: var(--ink); }
    .compare-card header strong {
      display: block;
      line-height: 1.15;
    }
    .compare-meta {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 1px;
      background: var(--line);
      border-bottom: 1px solid var(--line);
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.77rem;
    }
    .compare-meta span {
      background: #fffdf7;
      padding: 7px 9px;
      min-width: 0;
      overflow-wrap: anywhere;
    }
    .compare-output,
    .compare-summary {
      padding: 11px;
      min-width: 0;
    }
    .compare-output {
      border-bottom: 1px solid var(--line);
    }
    .compare-summary {
      color: var(--muted);
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.78rem;
      background: #fbfaf5;
    }
    .chart-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }
    .chart-panel {
      border: 2px solid var(--ink);
      background: var(--panel);
      box-shadow: var(--shadow);
      padding: 13px;
      min-width: 0;
    }
    .chart-panel.wide {
      grid-column: 1 / -1;
    }
    .chart-title {
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.86rem;
      text-transform: uppercase;
      margin-bottom: 10px;
    }
    .bar-row {
      display: grid;
      grid-template-columns: minmax(150px, 0.8fr) minmax(160px, 2fr) auto;
      gap: 10px;
      align-items: center;
      margin: 8px 0;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.8rem;
    }
    .stacked-track,
    .issue-track {
      height: 16px;
      border: 1px solid var(--ink);
      background: #ece9df;
      display: flex;
      overflow: hidden;
    }
    .stack-pass {
      background: var(--green);
    }
    .stack-fail {
      background: var(--red);
    }
    .issue-fill {
      background: var(--red);
      height: 100%;
    }
    .chart-legend {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      color: var(--muted);
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.78rem;
      margin-top: 9px;
    }
    .legend-swatch {
      display: inline-block;
      width: 11px;
      height: 11px;
      border: 1px solid var(--ink);
      margin-right: 5px;
      vertical-align: -1px;
    }
    .severity-grid {
      display: grid;
      grid-template-columns: minmax(160px, 1.2fr) repeat(3, minmax(90px, 1fr));
      border: 1px solid var(--ink);
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.8rem;
      overflow-x: auto;
    }
    .severity-grid > div {
      border-right: 1px solid var(--line);
      border-bottom: 1px solid var(--line);
      padding: 8px;
      min-width: 0;
      overflow-wrap: anywhere;
    }
    .severity-grid .head {
      background: var(--ink);
      color: #fff;
      font-weight: 700;
    }
    .severity-cell {
      color: var(--ink);
      font-weight: 700;
    }
    .severity-minor { background: #eef7f2; }
    .severity-major { background: #fff1c2; }
    .severity-critical { background: #f7d7d3; }
    .table-wrap {
      overflow: auto;
      border: 2px solid var(--ink);
      background: var(--panel);
      box-shadow: var(--shadow);
    }
    table {
      width: 100%;
      border-collapse: collapse;
      min-width: 720px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.89rem;
    }
    th, td {
      border-bottom: 1px solid var(--line);
      padding: 10px 11px;
      vertical-align: top;
      text-align: left;
    }
    th {
      position: sticky;
      top: 0;
      background: var(--ink);
      color: #fff;
      z-index: 1;
      white-space: nowrap;
      cursor: pointer;
    }
    tbody tr:hover td {
      background: #fff7d8;
    }
    tr.pick-score td {
      background: #edf8f1;
    }
    tr.pick-fastest td {
      background: #eaf7fa;
    }
    tr.pick-balanced td {
      background: #fff5d3;
    }
    .model-badge {
      display: inline-block;
      margin: 3px 4px 0 0;
      padding: 2px 5px;
      border: 1px solid currentColor;
      color: var(--muted);
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.68rem;
      white-space: nowrap;
    }
    .sort-hint,
    .table-note {
      color: var(--muted);
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.82rem;
      margin: -4px 0 10px;
    }
    .num { text-align: right; }
    .model-name {
      font-weight: 800;
      font-family: ui-serif, Georgia, Cambria, "Times New Roman", serif;
      font-size: 1rem;
    }
    .bar {
      display: grid;
      grid-template-columns: 88px minmax(110px, 1fr);
      align-items: center;
      gap: 10px;
      min-width: 190px;
    }
    .track {
      height: 12px;
      border: 1px solid var(--ink);
      background: #ece9df;
      overflow: hidden;
    }
    .fill {
      height: 100%;
      background: var(--green);
    }
    .fill.pass { background: var(--cyan); }
    .fill.latency { background: var(--gold); }
    .fill.bad { background: var(--red); }
    .matrix-cell {
      min-width: 86px;
      font-weight: 800;
    }
    #matrixTable {
      --matrix-case-width: 330px;
      --matrix-category-width: 210px;
    }
    #matrixTable th,
    #matrixTable td {
      box-sizing: border-box;
    }
    #matrixTable th:nth-child(1),
    #matrixTable td:nth-child(1) {
      position: sticky;
      left: 0;
      width: var(--matrix-case-width);
      min-width: var(--matrix-case-width);
      max-width: var(--matrix-case-width);
      background: var(--panel);
      z-index: 2;
    }
    #matrixTable th:nth-child(2),
    #matrixTable td:nth-child(2) {
      position: sticky;
      left: var(--matrix-case-width);
      width: var(--matrix-category-width);
      min-width: var(--matrix-category-width);
      max-width: var(--matrix-category-width);
      background: var(--panel);
      box-shadow: 10px 0 16px rgba(24, 23, 19, 0.13);
      z-index: 2;
    }
    #matrixTable th:nth-child(1),
    #matrixTable th:nth-child(2) {
      background: var(--ink);
      z-index: 4;
    }
    #matrixTable tbody tr:hover td:nth-child(1),
    #matrixTable tbody tr:hover td:nth-child(2) {
      background: #fff7d8;
    }
    .pass { color: var(--green); }
    .fail { color: var(--red); }
    .muted { color: var(--muted); }
    .filters {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin: 0 0 12px;
    }
    .filter-chip {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      cursor: pointer;
      min-height: 34px;
      box-shadow: none;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.78rem;
    }
    .filter-chip input {
      accent-color: var(--red);
    }
    .toggle {
      border: 1px solid var(--ink);
      background: #fff;
      min-width: 30px;
      height: 30px;
      cursor: pointer;
      box-shadow: 3px 3px 0 rgba(24, 23, 19, 0.12);
    }
    .detail-row td {
      background: #fbfaf5;
      border-bottom: 2px solid var(--ink);
    }
    .detail-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    }
    .detail-block {
      border: 1px solid var(--line);
      background: #fff;
      padding: 11px;
      min-width: 0;
    }
    .detail-block b {
      display: block;
      margin-bottom: 8px;
      color: var(--muted);
      text-transform: uppercase;
      font-size: 0.76rem;
    }
    pre {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      line-height: 1.35;
    }
    .error-pill {
      display: inline-block;
      padding: 3px 6px;
      border: 1px solid currentColor;
      margin: 0 4px 4px 0;
      color: var(--red);
      background: #fff;
      white-space: nowrap;
    }
    .empty {
      border: 2px dashed var(--line);
      padding: 28px;
      background: rgba(255,255,255,0.65);
      color: var(--muted);
    }
    @media (max-width: 860px) {
      .shell { width: min(100vw - 18px, 1480px); padding-top: 16px; }
      header { grid-template-columns: 1fr; align-items: start; }
      .controls { justify-content: flex-start; }
      .stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .about-grid,
      .test-top { grid-template-columns: 1fr; }
      .detail-grid { grid-template-columns: 1fr; }
      .compare-controls,
      .compare-reference { grid-template-columns: 1fr; }
      .chart-grid { grid-template-columns: 1fr; }
      .bar-row { grid-template-columns: 1fr; }
      .pager { justify-content: flex-start; }
      .compare-actions { justify-content: flex-start; }
      h1 { font-size: 2.35rem; }
    }
    @media (max-width: 520px) {
      .stats { grid-template-columns: 1fr; }
      select, .download { width: 100%; justify-content: center; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <header>
      <div>
        <h1>ChirperBench Scores</h1>
        <nav class="top-nav" aria-label="Site sections">
          <button class="nav-button active" type="button" data-view="scores">Scores</button>
          <button class="nav-button" type="button" data-view="about">About ChirperBench</button>
          <button class="nav-button" type="button" data-view="tests">View Tests</button>
        </nav>
      </div>
      <div class="controls">
        <select id="runSelect" aria-label="Run"></select>
        <a class="download" id="downloadRun" href="data/latest-run.json" target="_blank" rel="noopener">run.json</a>
        <a class="download" id="downloadSummary" href="data/latest-summary.json" target="_blank" rel="noopener">summary.json</a>
      </div>
    </header>

    <div class="view" id="scoresView">
      <div class="stats" id="stats"></div>

      <div class="grid">
        <section>
          <h2>Overall Leaderboard</h2>
          <p class="sort-hint">Click any column header to sort. Highlighted rows mark highest score, lowest latency, and best score per second.</p>
          <div class="table-wrap"><table id="leaderboardTable"></table></div>
        </section>

        <section>
          <h2>Model Metrics</h2>
          <p class="table-note">Judge issues are model-output mistakes found by the judge. One result can have multiple issues; run failures are shown separately as statuses.</p>
          <div class="table-wrap"><table id="modelTable"></table></div>
        </section>

        <section>
          <h2>Telemetry Graphs</h2>
          <div class="viz-wrap">
            <div class="plot-head">
              <label for="metricSelect">Score vs</label>
              <select id="metricSelect" aria-label="Telemetry metric"></select>
            </div>
            <div class="plot-card" id="scatterPlot"></div>
            <div class="metric-note" id="telemetryNote"></div>
          </div>
        </section>

        <section>
          <h2>Outcome Graphs</h2>
          <div class="chart-grid">
            <div class="chart-panel">
              <div class="chart-title">Pass / Fail by Transcript Category</div>
              <div id="categoryOutcomeChart"></div>
            </div>
            <div class="chart-panel">
              <div class="chart-title">Judge Issues by Type</div>
              <div id="issueTypeChart"></div>
            </div>
            <div class="chart-panel wide">
              <div class="chart-title">Issue Type by Severity</div>
              <div id="issueSeverityChart"></div>
            </div>
          </div>
        </section>

        <section>
          <h2>Case Matrix</h2>
          <div class="table-wrap"><table id="matrixTable"></table></div>
        </section>

        <section>
          <h2>Compare Outputs</h2>
          <div class="compare-wrap">
            <div class="compare-controls">
              <select id="compareCaseSelect" aria-label="Transcript to compare"></select>
              <div class="compare-actions">
                <button class="small-button" id="compareTop" type="button">Top 6</button>
                <button class="small-button" id="compareAll" type="button">All</button>
                <button class="small-button" id="compareClear" type="button">Clear</button>
              </div>
            </div>
            <div class="model-picker" id="compareModels"></div>
            <div class="compare-reference" id="compareReference"></div>
            <div class="compare-strip" id="compareGrid"></div>
          </div>
        </section>

        <section>
          <h2>Detailed Results</h2>
          <div class="filters" id="filters"></div>
          <div class="table-wrap"><table id="detailTable"></table></div>
        </section>
      </div>
    </div>

    <div class="view" id="aboutView" hidden>
      <section>
        <h2>About ChirperBench</h2>
        <div class="about-grid">
          <article class="about-panel">
            <h3>What This Measures</h3>
            <p>ChirperBench checks whether local Ollama models can clean up dictated transcripts without treating the dictated words as instructions to execute.</p>
            <p>The suite stresses command-like text, dictated questions, email requests, markdown, URLs, code identifiers, spelling corrections, mixed formatting, and cases where no change is needed.</p>
          </article>
          <article class="about-panel">
            <h3>How A Run Works</h3>
            <ul>
              <li>Each installed Ollama model is run sequentially against every transcript case.</li>
              <li>The model receives the same formatter prompt and only the raw transcript.</li>
              <li>Outputs, runtime, statuses, and optional AMD sysfs GPU telemetry are saved in machine-readable run data.</li>
              <li>When judging is enabled, Codex CLI uses gpt-5.5 with high reasoning to score the output against the expected result.</li>
            </ul>
          </article>
          <article class="about-panel">
            <h3>Scoring</h3>
            <p>Scores run from 0 to 100. Passing means the judge accepted the cleaned transcript as meeting the case target.</p>
            <p>Judge issues are model-output mistakes, not necessarily process crashes. One result can have several judge issues, such as answering a dictated question, refusing a command-like transcript, leaking spoken edits, or inventing extra text.</p>
          </article>
          <article class="about-panel">
            <h3>Run Context</h3>
            <div id="aboutRunFacts"></div>
          </article>
          <article class="about-panel wide">
            <h3>Formatter Prompt</h3>
            <pre class="prompt-box" id="promptTemplate"></pre>
          </article>
        </div>
      </section>
    </div>

    <div class="view" id="testsView" hidden>
      <section>
        <h2>View Tests</h2>
        <div class="test-browser">
          <div class="test-top">
            <select id="testSelect" aria-label="Test case"></select>
            <div class="pager">
              <button class="small-button" id="testPrev" type="button">Previous</button>
              <span id="testPage"></span>
              <button class="small-button" id="testNext" type="button">Next</button>
            </div>
          </div>
          <article class="test-card" id="testCard"></article>
        </div>
      </section>
    </div>
  </div>

  <script type="application/json" id="run-data">__RUN_DATA__</script>
  <script>
    const embedded = JSON.parse(document.getElementById("run-data").textContent);
    const runSelect = document.getElementById("runSelect");
    const filters = document.getElementById("filters");
    const metricSelect = document.getElementById("metricSelect");
    const compareCaseSelect = document.getElementById("compareCaseSelect");
    const compareModels = document.getElementById("compareModels");
    const testSelect = document.getElementById("testSelect");
    const views = {
      scores: document.getElementById("scoresView"),
      about: document.getElementById("aboutView"),
      tests: document.getElementById("testsView")
    };
    const selectedErrors = new Set();
    const selectedCompareModels = new Set();
    let currentRunId = embedded.runs.length ? embedded.runs[embedded.runs.length - 1].id : "";
    let testCaseIndex = 0;
    const sortStates = {
      leaderboard: { key: "rank", dir: "asc" },
      model: { key: "average_score", dir: "desc" },
      matrix: { key: "case", dir: "asc" },
      detail: { key: "model", dir: "asc" }
    };
    let scatterMetricKey = "median_latency_seconds";
    let compareCaseId = "";
    const scatterMetrics = [
      { key: "median_latency_seconds", label: "median latency", unit: "s" },
      { key: "median_power_w_avg", label: "average power", unit: "W" },
      { key: "peak_power_w", label: "peak power", unit: "W" },
      { key: "median_vram_mb_peak", label: "peak VRAM", unit: "MB" },
      { key: "median_gpu_busy_percent_avg", label: "average GPU busy", unit: "%" },
      { key: "error_count", label: "judge issue count", unit: "" }
    ];
    const specialCompareModels = {
      "granite4.1:8b": { label: "Silas' favorite", className: "special-favorite", badgeClass: "badge-favorite" },
      "lfm2.5-thinking:1.2b": { label: "extremely funny", className: "special-funny", badgeClass: "badge-funny" }
    };

    function esc(value) {
      return String(value ?? "").replace(/[&<>"']/g, char => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        "\"": "&quot;",
        "'": "&#39;"
      }[char]));
    }

    function pct(value) {
      return `${Math.round(Number(value || 0) * 100)}%`;
    }

    function number(value, digits = 2) {
      const num = Number(value || 0);
      return num.toFixed(digits);
    }

    function metricText(value, unit = "", digits = 1) {
      if (typeof value !== "number" || Number.isNaN(value)) return "NA";
      return `${value.toFixed(digits)}${unit}`;
    }

    function scorePerSecond(row) {
      const latency = Math.max(Number(row?.median_latency_seconds || 0), 0.001);
      return Number(row?.average_score || 0) / latency;
    }

    function resultErrors(result) {
      const judge = result.judge || {};
      return Array.isArray(judge.errors) ? judge.errors : [];
    }

    function resultHasSelectedError(result) {
      if (!selectedErrors.size) return true;
      return resultErrors(result).some(error => selectedErrors.has(error.type));
    }

    function bar(label, value, max, cls = "") {
      const safeMax = Math.max(Number(max || 0), 1);
      const width = Math.max(0, Math.min(100, Number(value || 0) / safeMax * 100));
      return `<div class="bar"><span>${esc(label)}</span><div class="track"><div class="fill ${cls}" style="width:${width}%"></div></div></div>`;
    }

    function currentRun() {
      return embedded.data[currentRunId] || null;
    }

    function viewFromHash() {
      const key = window.location.hash.replace(/^#/, "");
      return Object.prototype.hasOwnProperty.call(views, key) ? key : "scores";
    }

    function setupViewNavigation() {
      document.querySelectorAll(".nav-button[data-view]").forEach(button => {
        button.addEventListener("click", () => {
          showView(button.dataset.view || "scores", true);
        });
      });
      window.addEventListener("hashchange", () => showView(viewFromHash(), false));
      window.addEventListener("popstate", () => showView(viewFromHash(), false));
      showView(viewFromHash(), false);
    }

    function showView(view, updateHash) {
      const next = Object.prototype.hasOwnProperty.call(views, view) ? view : "scores";
      Object.entries(views).forEach(([key, element]) => {
        element.hidden = key !== next;
      });
      document.querySelectorAll(".nav-button[data-view]").forEach(button => {
        button.classList.toggle("active", button.dataset.view === next);
      });
      if (updateHash) {
        const nextUrl = next === "scores"
          ? `${window.location.pathname}${window.location.search}`
          : `#${next}`;
        window.history.pushState(null, "", nextUrl);
      }
    }

    function setupRunSelect() {
      runSelect.innerHTML = embedded.runs.map(run => {
        const label = `${run.id} (${run.result_count} results)`;
        return `<option value="${esc(run.id)}">${esc(label)}</option>`;
      }).join("");
      runSelect.value = currentRunId;
      runSelect.addEventListener("change", () => {
        currentRunId = runSelect.value;
        render();
      });
    }

    function setupCompareButtons() {
      document.getElementById("compareTop").addEventListener("click", () => {
        const run = currentRun();
        selectedCompareModels.clear();
        for (const model of topModels(run, 6)) selectedCompareModels.add(model);
        renderCompare(run);
      });
      document.getElementById("compareAll").addEventListener("click", () => {
        const run = currentRun();
        selectedCompareModels.clear();
        for (const model of run?.models || []) selectedCompareModels.add(model);
        renderCompare(run);
      });
      document.getElementById("compareClear").addEventListener("click", () => {
        selectedCompareModels.clear();
        renderCompare(currentRun());
      });
    }

    function setupTestBrowser() {
      testSelect.addEventListener("change", event => {
        testCaseIndex = Number(event.target.value || 0);
        renderTests(currentRun());
      });
      document.getElementById("testPrev").addEventListener("click", () => {
        testCaseIndex = Math.max(0, testCaseIndex - 1);
        renderTests(currentRun());
      });
      document.getElementById("testNext").addEventListener("click", () => {
        const count = (currentRun()?.cases || []).length;
        testCaseIndex = Math.min(Math.max(0, count - 1), testCaseIndex + 1);
        renderTests(currentRun());
      });
    }

    function setupFilters() {
      const preferred = [
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
        "other"
      ];
      filters.innerHTML = preferred.map(type => `
        <label class="filter-chip">
          <input type="checkbox" value="${esc(type)}">
          ${esc(type)}
        </label>
      `).join("");
      filters.querySelectorAll("input").forEach(input => {
        input.addEventListener("change", event => {
          const type = event.target.value;
          if (event.target.checked) selectedErrors.add(type);
          else selectedErrors.delete(type);
          renderDetails(currentRun());
        });
      });
    }

    function setupMetricSelect() {
      metricSelect.innerHTML = scatterMetrics.map(metric => `
        <option value="${esc(metric.key)}">${esc(metric.label)}</option>
      `).join("");
      metricSelect.value = scatterMetricKey;
      metricSelect.addEventListener("change", () => {
        scatterMetricKey = metricSelect.value;
        renderTelemetry(currentRun());
      });
    }

    function renderStats(run) {
      const summary = run.summary || {};
      const picks = modelPicks(run);
      document.getElementById("stats").innerHTML = [
        ["run", run.run_id || "", `${summary.result_count || 0} results`],
        ["highest score", picks.score?.model || "none", picks.score ? `${number(picks.score.average_score, 2)} avg score` : ""],
        ["lowest latency", picks.fastest?.model || "none", picks.fastest ? `${number(picks.fastest.median_latency_seconds, 3)}s median` : ""],
        ["best score/sec", picks.balanced?.model || "none", picks.balanced ? `${number(scorePerSecond(picks.balanced), 2)} pts/s` : ""],
        ["models", summary.model_count || 0, `${summary.case_count || 0} transcripts`]
      ].map(([label, value, detail]) => `
        <div class="stat"><div class="label">${esc(label)}</div><div class="value">${esc(value)}</div><div class="detail">${esc(detail)}</div></div>
      `).join("");
    }

    function renderAbout(run) {
      document.getElementById("promptTemplate").textContent = embedded.prompt_template || "";
      if (!run) {
        document.getElementById("aboutRunFacts").innerHTML = `<div class="empty">No run data found.</div>`;
        return;
      }
      const summary = run.summary || {};
      const telemetry = summary.telemetry || {};
      const facts = [
        ["run", run.run_id || "unknown"],
        ["models", summary.model_count || 0],
        ["transcripts", summary.case_count || 0],
        ["results", summary.result_count || 0],
        ["judge", run.judge_enabled ? `${run.judge_model || "unknown"} / ${run.judge_reasoning_effort || "default"}` : "disabled"],
        ["judge tier", run.judge_tier || "standard"],
        ["telemetry", telemetry.available ? (telemetry.providers || []).join(", ") || "available" : "none"],
        ["samples", telemetry.sample_count || 0]
      ];
      document.getElementById("aboutRunFacts").innerHTML = `
        <div class="test-meta">
          ${facts.map(([label, value]) => `<span><b>${esc(label)}</b>: ${esc(value)}</span>`).join("")}
        </div>
      `;
    }

    function renderTests(run) {
      const cases = run?.cases || [];
      if (!cases.length) {
        testSelect.innerHTML = "";
        document.getElementById("testPage").textContent = "0 / 0";
        document.getElementById("testCard").innerHTML = `<div class="empty">No test cases found.</div>`;
        document.getElementById("testPrev").disabled = true;
        document.getElementById("testNext").disabled = true;
        return;
      }
      testCaseIndex = Math.max(0, Math.min(testCaseIndex, cases.length - 1));
      testSelect.innerHTML = cases.map((item, index) => `
        <option value="${index}">${index + 1}. ${esc(item.id)} · ${esc(item.category || "")}</option>
      `).join("");
      testSelect.value = String(testCaseIndex);
      document.getElementById("testPage").textContent = `${testCaseIndex + 1} / ${cases.length}`;
      document.getElementById("testPrev").disabled = testCaseIndex === 0;
      document.getElementById("testNext").disabled = testCaseIndex === cases.length - 1;
      const item = cases[testCaseIndex];
      document.getElementById("testCard").innerHTML = `
        <div>
          <h3>${esc(item.id)}</h3>
          <div class="test-meta">
            <span>${esc(item.category || "uncategorized")}</span>
            <span>case ${testCaseIndex + 1} of ${cases.length}</span>
          </div>
        </div>
        <div class="detail-grid">
          <div class="detail-block"><b>Raw Transcript</b><pre>${esc(item.transcript || "")}</pre></div>
          <div class="detail-block"><b>Expected Output</b><pre>${esc(item.expected || "")}</pre></div>
        </div>
        ${item.notes ? `<div class="detail-block"><b>Notes</b><pre>${esc(item.notes)}</pre></div>` : ""}
      `;
    }

    function table(id, headers, rows, onSort = null) {
      const head = `<thead><tr>${headers.map(h => `<th data-key="${esc(h.key)}">${esc(h.label)}</th>`).join("")}</tr></thead>`;
      const body = `<tbody>${rows.join("")}</tbody>`;
      const el = document.getElementById(id);
      el.innerHTML = head + body;
      if (onSort) {
        el.querySelectorAll("th[data-key]").forEach(th => {
          th.addEventListener("click", () => {
            onSort(th.dataset.key);
          });
        });
      }
    }

    function toggleSort(state, key) {
      state.dir = state.key === key && state.dir === "asc" ? "desc" : "asc";
      state.key = key;
    }

    function sortedRows(rows, state, valueFn) {
      const dir = state.dir === "asc" ? 1 : -1;
      return rows.slice().sort((a, b) => {
        const av = valueFn(a, state.key);
        const bv = valueFn(b, state.key);
        if (typeof av === "number" && typeof bv === "number") {
          return (av - bv) * dir;
        }
        return String(av ?? "").localeCompare(String(bv ?? "")) * dir;
      });
    }

    function modelSortValue(row, key) {
      if (key === "model") return row.model || "";
      if (key === "score_per_second") return scorePerSecond(row);
      const value = row[key];
      return typeof value === "number" && Number.isFinite(value) ? value : 0;
    }

    function modelPicks(run) {
      const rows = run?.summary?.leaderboard || [];
      return {
        score: maxBy(rows, row => Number(row.average_score || 0)),
        fastest: minBy(rows, row => Number(row.median_latency_seconds || Infinity)),
        balanced: maxBy(rows, scorePerSecond)
      };
    }

    function maxBy(rows, fn) {
      return rows.reduce((best, row) => !best || fn(row) > fn(best) ? row : best, null);
    }

    function minBy(rows, fn) {
      return rows.reduce((best, row) => !best || fn(row) < fn(best) ? row : best, null);
    }

    function pickClasses(row, picks) {
      return [
        picks.score?.model === row.model ? "pick-score" : "",
        picks.fastest?.model === row.model ? "pick-fastest" : "",
        picks.balanced?.model === row.model ? "pick-balanced" : ""
      ].filter(Boolean).join(" ");
    }

    function pickBadges(row, picks) {
      const badges = badgeSpans(modelBadgeItems(row.model, picks));
      return badges ? `<div>${badges}</div>` : "";
    }

    function modelToneClasses(model, picks) {
      const special = specialCompareModels[model];
      return [
        pickClasses({ model }, picks),
        special ? special.className : ""
      ].filter(Boolean).join(" ");
    }

    function modelBadgeItems(model, picks) {
      const badges = [];
      if (picks.score?.model === model) badges.push({ label: "highest score", className: "badge-score" });
      if (picks.fastest?.model === model) badges.push({ label: "lowest latency", className: "badge-fastest" });
      if (picks.balanced?.model === model) badges.push({ label: "best score/s", className: "badge-balanced" });
      const special = specialCompareModels[model];
      if (special) badges.push({ label: special.label, className: special.badgeClass });
      return badges;
    }

    function badgeSpans(items) {
      return items.map(item => `<span class="model-badge ${esc(item.className)}">${esc(item.label)}</span>`).join("");
    }

    function compareBadges(model, picks) {
      const badges = badgeSpans(modelBadgeItems(model, picks));
      return badges ? `<div class="compare-badges">${badges}</div>` : "";
    }

    function renderLeaderboard(run) {
      const picks = modelPicks(run);
      const rows = sortedRows(run.summary?.leaderboard || [], sortStates.leaderboard, modelSortValue).map(row => `
        <tr class="${pickClasses(row, picks)}">
          <td class="num">${row.rank}</td>
          <td class="model-name">${esc(row.model)}${pickBadges(row, picks)}</td>
          <td>${bar(number(row.average_score, 2), row.average_score, 100, row.average_score < 70 ? "bad" : "")}</td>
          <td>${bar(pct(row.pass_rate), row.pass_rate, 1, "pass")}</td>
          <td>${number(row.median_latency_seconds, 3)}s</td>
          <td class="num">${number(scorePerSecond(row), 2)}</td>
          <td class="num">${metricText(row.median_power_w_avg, "W", 2)}</td>
          <td class="num">${metricText(row.median_vram_mb_peak, "MB", 1)}</td>
          <td class="num">${row.error_count}</td>
        </tr>
      `);
      table("leaderboardTable", [
        { key: "rank", label: "Rank" },
        { key: "model", label: "Model" },
        { key: "average_score", label: "Score" },
        { key: "pass_rate", label: "Pass Rate" },
        { key: "median_latency_seconds", label: "Median Latency" },
        { key: "score_per_second", label: "Score/Sec" },
        { key: "median_power_w_avg", label: "Avg Power" },
        { key: "median_vram_mb_peak", label: "Peak VRAM" },
        { key: "error_count", label: "Judge Issues" }
      ], rows, key => {
        toggleSort(sortStates.leaderboard, key);
        renderLeaderboard(currentRun());
      });
    }

    function renderModelTable(run) {
      const picks = modelPicks(run);
      const models = sortedRows(run.summary?.models || [], sortStates.model, modelSortValue);
      const maxLatency = Math.max(1, ...models.map(row => Number(row.median_latency_seconds || 0)));
      const rows = models.map(row => `
        <tr class="${pickClasses(row, picks)}">
          <td class="model-name">${esc(row.model)}${pickBadges(row, picks)}</td>
          <td>${bar(number(row.average_score, 2), row.average_score, 100, row.average_score < 70 ? "bad" : "")}</td>
          <td>${bar(pct(row.pass_rate), row.pass_rate, 1, "pass")}</td>
          <td>${bar(`${number(row.median_latency_seconds, 3)}s`, row.median_latency_seconds, maxLatency, "latency")}</td>
          <td class="num">${number(scorePerSecond(row), 2)}</td>
          <td class="num">${metricText(row.median_power_w_avg, "W", 2)}</td>
          <td class="num">${metricText(row.median_vram_mb_peak, "MB", 1)}</td>
          <td class="num">${metricText(row.median_gpu_busy_percent_avg, "%", 1)}</td>
          <td class="num">${row.error_count}</td>
        </tr>
      `);
      table("modelTable", [
        { key: "model", label: "Model" },
        { key: "average_score", label: "Score" },
        { key: "pass_rate", label: "Pass Rate" },
        { key: "median_latency_seconds", label: "Latency" },
        { key: "score_per_second", label: "Score/Sec" },
        { key: "median_power_w_avg", label: "Avg Power" },
        { key: "median_vram_mb_peak", label: "Peak VRAM" },
        { key: "median_gpu_busy_percent_avg", label: "GPU Busy" },
        { key: "error_count", label: "Judge Issues" }
      ], rows, key => {
        toggleSort(sortStates.model, key);
        renderModelTable(currentRun());
      });
    }

    function renderTelemetry(run) {
      const metric = scatterMetrics.find(item => item.key === scatterMetricKey) || scatterMetrics[0];
      const rows = (run.summary?.models || [])
        .map(row => ({
          model: row.model,
          score: Number(row.average_score || 0),
          passRate: Number(row.pass_rate || 0),
          value: modelMetric(row, metric.key),
          errors: Number(row.error_count || 0)
        }))
        .filter(row => typeof row.value === "number" && Number.isFinite(row.value));
      if (!rows.length) {
        document.getElementById("scatterPlot").innerHTML = `<div class="empty">No values for ${esc(metric.label)} in this run.</div>`;
        document.getElementById("telemetryNote").textContent = `Telemetry samples: ${run.summary?.telemetry?.sample_count || 0}`;
        return;
      }

      const width = 880;
      const height = 380;
      const margin = { left: 76, right: 28, top: 24, bottom: 58 };
      const xValues = rows.map(row => row.value);
      let xMin = Math.min(...xValues);
      let xMax = Math.max(...xValues);
      if (xMin === xMax) {
        xMin -= 1;
        xMax += 1;
      }
      const xPad = (xMax - xMin) * 0.08;
      xMin -= xPad;
      xMax += xPad;
      const plotW = width - margin.left - margin.right;
      const plotH = height - margin.top - margin.bottom;
      const x = value => margin.left + ((value - xMin) / (xMax - xMin)) * plotW;
      const y = value => margin.top + (1 - Math.max(0, Math.min(100, value)) / 100) * plotH;
      const ticks = [0, 25, 50, 75, 100];
      const xTicks = Array.from({ length: 5 }, (_, index) => xMin + ((xMax - xMin) * index) / 4);
      const points = rows.map(row => {
        const color = row.passRate >= 0.8 ? "var(--green)" : row.passRate >= 0.5 ? "var(--gold)" : "var(--red)";
        const label = `${row.model}: score ${number(row.score, 2)}, ${metric.label} ${formatMetric(row.value, metric)}`;
        return `
          <g>
            <circle class="point" cx="${x(row.value).toFixed(1)}" cy="${y(row.score).toFixed(1)}" r="6" fill="${color}">
              <title>${esc(label)}</title>
            </circle>
            <text class="point-label" x="${(x(row.value) + 9).toFixed(1)}" y="${(y(row.score) - 8).toFixed(1)}">${esc(row.model)}</text>
          </g>
        `;
      }).join("");

      document.getElementById("scatterPlot").innerHTML = `
        <svg class="scatter" viewBox="0 0 ${width} ${height}" role="img" aria-label="Score vs ${esc(metric.label)}">
          ${ticks.map(tick => `
            <line class="gridline" x1="${margin.left}" x2="${width - margin.right}" y1="${y(tick)}" y2="${y(tick)}"></line>
            <text class="axis-label" x="${margin.left - 12}" y="${y(tick) + 4}" text-anchor="end">${tick}</text>
          `).join("")}
          ${xTicks.map(tick => `
            <line class="gridline" x1="${x(tick)}" x2="${x(tick)}" y1="${margin.top}" y2="${height - margin.bottom}"></line>
            <text class="axis-label" x="${x(tick)}" y="${height - margin.bottom + 24}" text-anchor="middle">${esc(formatMetric(tick, metric))}</text>
          `).join("")}
          <line class="axis" x1="${margin.left}" x2="${margin.left}" y1="${margin.top}" y2="${height - margin.bottom}"></line>
          <line class="axis" x1="${margin.left}" x2="${width - margin.right}" y1="${height - margin.bottom}" y2="${height - margin.bottom}"></line>
          <text class="axis-label" x="${margin.left}" y="15">score</text>
          <text class="axis-label" x="${width - margin.right}" y="${height - 14}" text-anchor="end">${esc(metric.label)}</text>
          ${points}
        </svg>
      `;
      document.getElementById("telemetryNote").textContent =
        `Telemetry samples: ${run.summary?.telemetry?.sample_count || 0}; provider: ${(run.summary?.telemetry?.providers || []).join(", ") || "none"}`;
    }

    function renderOutcomeGraphs(run) {
      renderCategoryOutcomeChart(run);
      renderIssueTypeChart(run);
      renderIssueSeverityChart(run);
    }

    function renderCategoryOutcomeChart(run) {
      const groups = new Map();
      for (const result of run.results || []) {
        const key = result.category || "uncategorized";
        if (!groups.has(key)) groups.set(key, { category: key, pass: 0, fail: 0 });
        const group = groups.get(key);
        if (result.passed) group.pass += 1;
        else group.fail += 1;
      }
      const rows = Array.from(groups.values()).sort((a, b) => (b.pass + b.fail) - (a.pass + a.fail) || a.category.localeCompare(b.category));
      if (!rows.length) {
        document.getElementById("categoryOutcomeChart").innerHTML = `<div class="empty">No result data.</div>`;
        return;
      }
      document.getElementById("categoryOutcomeChart").innerHTML = rows.map(row => {
        const total = row.pass + row.fail;
        const passWidth = total ? row.pass / total * 100 : 0;
        const failWidth = 100 - passWidth;
        return `
          <div class="bar-row">
            <span>${esc(row.category)}</span>
            <div class="stacked-track" title="${row.pass} passed, ${row.fail} failed">
              <div class="stack-pass" style="width:${passWidth}%"></div>
              <div class="stack-fail" style="width:${failWidth}%"></div>
            </div>
            <span>${row.pass}/${total} pass</span>
          </div>
        `;
      }).join("") + `
        <div class="chart-legend">
          <span><span class="legend-swatch" style="background: var(--green)"></span>passed</span>
          <span><span class="legend-swatch" style="background: var(--red)"></span>failed</span>
        </div>
      `;
    }

    function renderIssueTypeChart(run) {
      const counts = issueCounts(run);
      const rows = Object.entries(counts).sort((a, b) => b[1] - a[1]);
      if (!rows.length) {
        document.getElementById("issueTypeChart").innerHTML = `<div class="empty">No judge issues recorded.</div>`;
        return;
      }
      const max = Math.max(...rows.map(([, count]) => count), 1);
      document.getElementById("issueTypeChart").innerHTML = rows.map(([type, count]) => `
        <div class="bar-row">
          <span>${esc(type)}</span>
          <div class="issue-track" title="${count} judge issues">
            <div class="issue-fill" style="width:${Math.max(2, count / max * 100)}%"></div>
          </div>
          <span>${count}</span>
        </div>
      `).join("");
    }

    function renderIssueSeverityChart(run) {
      const counts = issueSeverityCounts(run);
      const types = Object.keys(counts).sort((a, b) => totalSeverity(counts[b]) - totalSeverity(counts[a]) || a.localeCompare(b));
      if (!types.length) {
        document.getElementById("issueSeverityChart").innerHTML = `<div class="empty">No judge issues recorded.</div>`;
        return;
      }
      const max = Math.max(...types.flatMap(type => ["minor", "major", "critical"].map(severity => counts[type][severity] || 0)), 1);
      document.getElementById("issueSeverityChart").innerHTML = `
        <div class="severity-grid">
          <div class="head">Issue Type</div>
          <div class="head">Minor</div>
          <div class="head">Major</div>
          <div class="head">Critical</div>
          ${types.map(type => `
            <div>${esc(type)}</div>
            ${["minor", "major", "critical"].map(severity => {
              const count = counts[type][severity] || 0;
              const opacity = 0.18 + (count / max * 0.82);
              return `<div class="severity-cell severity-${severity}" style="opacity:${count ? opacity.toFixed(2) : 0.28}">${count}</div>`;
            }).join("")}
          `).join("")}
        </div>
      `;
    }

    function issueCounts(run) {
      const counts = {};
      for (const result of run.results || []) {
        for (const error of resultErrors(result)) {
          const type = error.type || "other";
          counts[type] = (counts[type] || 0) + 1;
        }
      }
      return counts;
    }

    function issueSeverityCounts(run) {
      const counts = {};
      for (const result of run.results || []) {
        for (const error of resultErrors(result)) {
          const type = error.type || "other";
          const severity = error.severity || "major";
          if (!counts[type]) counts[type] = { minor: 0, major: 0, critical: 0 };
          counts[type][severity] = (counts[type][severity] || 0) + 1;
        }
      }
      return counts;
    }

    function totalSeverity(row) {
      return (row.minor || 0) + (row.major || 0) + (row.critical || 0);
    }

    function modelMetric(row, key) {
      const value = row[key];
      if (typeof value === "number" && Number.isFinite(value)) return value;
      return null;
    }

    function formatMetric(value, metric) {
      const digits = metric.key === "median_latency_seconds" || metric.key.includes("power") ? 2 : 1;
      if (metric.unit === "") return number(value, 0);
      return `${Number(value).toFixed(digits)}${metric.unit}`;
    }

    function renderMatrix(run) {
      const models = run.models || [];
      const matrixRows = sortedRows(run.summary?.matrix || [], sortStates.matrix, matrixSortValue);
      const rows = matrixRows.map(row => {
        const cells = models.map(model => {
          const cell = row.cells?.[model] || {};
          const score = cell.score == null ? "NA" : cell.score;
          const cls = cell.passed ? "pass" : "fail";
          return `<td class="matrix-cell ${cls}">${esc(score)}</td>`;
        }).join("");
        return `<tr><td>${esc(row.case_id)}</td><td>${esc(row.category)}</td>${cells}</tr>`;
      });
      table("matrixTable", [
        { key: "case", label: "Case" },
        { key: "category", label: "Category" },
        ...models.map(model => ({ key: model, label: model }))
      ], rows, key => {
        toggleSort(sortStates.matrix, key);
        renderMatrix(currentRun());
      });
    }

    function matrixSortValue(row, key) {
      if (key === "case") return String(row.case_id || "");
      if (key === "category") return String(row.category || "");
      const score = row.cells?.[key]?.score;
      return typeof score === "number" && Number.isFinite(score) ? score : -1;
    }

    function renderCompare(run) {
      const cases = run.cases || [];
      if (!cases.length) {
        document.getElementById("compareReference").innerHTML = "";
        document.getElementById("compareGrid").innerHTML = `<div class="empty">No cases in this run.</div>`;
        return;
      }
      if (!cases.some(item => item.id === compareCaseId)) {
        compareCaseId = cases.find(item => item.id === "onboarding_mixed_format")?.id || cases[0].id;
      }
      const availableModels = new Set(run.models || []);
      for (const model of Array.from(selectedCompareModels)) {
        if (!availableModels.has(model)) selectedCompareModels.delete(model);
      }
      if (!selectedCompareModels.size) {
        for (const model of topModels(run, 6)) selectedCompareModels.add(model);
      }
      compareCaseSelect.innerHTML = cases.map(item => `
        <option value="${esc(item.id)}">${esc(item.id)} · ${esc(item.category || "")}</option>
      `).join("");
      compareCaseSelect.value = compareCaseId;
      compareCaseSelect.onchange = event => {
        compareCaseId = event.target.value;
        renderCompare(currentRun());
      };

      const models = run.models || [];
      const picks = modelPicks(run);
      compareModels.innerHTML = models.map(model => `
        <label class="model-chip ${modelToneClasses(model, picks)}">
          <input type="checkbox" value="${esc(model)}" ${selectedCompareModels.has(model) ? "checked" : ""}>
          <span class="chip-text">${esc(model)}</span>
          ${compareBadges(model, picks)}
        </label>
      `).join("");
      compareModels.querySelectorAll("input").forEach(input => {
        input.addEventListener("change", event => {
          const model = event.target.value;
          if (event.target.checked) selectedCompareModels.add(model);
          else selectedCompareModels.delete(model);
          renderCompareCards(run);
        });
      });

      const caseInfo = cases.find(item => item.id === compareCaseId) || cases[0];
      document.getElementById("compareReference").innerHTML = `
        <div class="detail-block"><b>Raw Transcript</b><pre>${esc(caseInfo.transcript || "")}</pre></div>
        <div class="detail-block"><b>Expected Output</b><pre>${esc(caseInfo.expected || "")}</pre></div>
      `;
      renderCompareCards(run);
    }

    function renderCompareCards(run) {
      const picks = modelPicks(run);
      const results = (run.results || [])
        .filter(result => result.case_id === compareCaseId && selectedCompareModels.has(result.model))
        .sort((a, b) => (run.models || []).indexOf(a.model) - (run.models || []).indexOf(b.model));
      if (!results.length) {
        document.getElementById("compareGrid").innerHTML = `<div class="empty">Select one or more models to compare.</div>`;
        return;
      }
      document.getElementById("compareGrid").innerHTML = results.map(result => {
        const metrics = result.telemetry?.metrics || {};
        const errors = resultErrors(result);
        const summary = result.judge?.summary || result.stderr || "";
        return `
          <article class="compare-card ${modelToneClasses(result.model, picks)}">
            <header>
              <strong>${esc(result.model)}</strong>
              <span>${esc(result.case_id)}</span>
              ${compareBadges(result.model, picks)}
            </header>
            <div class="compare-meta">
              <span>score ${esc(result.score ?? 0)}</span>
              <span class="${result.passed ? "pass" : "fail"}">${result.passed ? "passed" : "failed"}</span>
              <span>${number(result.latency_seconds, 3)}s</span>
              <span>${esc(result.judge_status || "no judge")}</span>
              <span>${metricText(metricValue(metrics, "power_w_avg"), "W", 2)}</span>
              <span>${metricText(metricValue(metrics, "vram_mb_peak"), "MB", 1)}</span>
            </div>
            <div class="compare-output"><pre>${esc(result.output || "")}</pre></div>
            <div class="compare-summary">
              <pre>${esc(summaryText(summary, errors))}</pre>
            </div>
          </article>
        `;
      }).join("");
    }

    function topModels(run, count) {
      return (run?.summary?.leaderboard || [])
        .slice(0, count)
        .map(row => row.model)
        .filter(Boolean);
    }

    function metricValue(metrics, key) {
      const value = metrics?.[key];
      return typeof value === "number" && Number.isFinite(value) ? value : null;
    }

    function summaryText(summary, errors) {
      const lines = [];
      if (summary) lines.push(summary);
      if (errors.length) {
        lines.push("");
        for (const error of errors) {
          lines.push(`${error.type || "other"} (${error.severity || "major"}): ${error.detail || ""}`);
        }
      }
      return lines.join("\n") || "No judge summary.";
    }

    function renderDetails(run) {
      const caseMap = Object.fromEntries((run.cases || []).map(item => [item.id, item]));
      let results = sortedRows(
        (run.results || []).filter(resultHasSelectedError),
        sortStates.detail,
        detailSortValue
      );
      const rows = [];
      results.forEach((result, index) => {
        const caseInfo = caseMap[result.case_id] || {};
        const errors = resultErrors(result);
        const errorHtml = errors.length
          ? errors.map(error => `<span class="error-pill">${esc(error.type)}</span>`).join("")
          : `<span class="muted">none</span>`;
        const detailId = `detail-${index}`;
        rows.push(`
          <tr>
            <td><button class="toggle" data-detail="${detailId}" aria-expanded="false">+</button></td>
            <td class="model-name">${esc(result.model)}</td>
            <td>${esc(result.case_id)}</td>
            <td>${esc(caseInfo.category || result.category || "")}</td>
            <td class="${result.passed ? "pass" : "fail"}">${esc(result.score ?? 0)}</td>
            <td>${esc(result.ollama_status || "")}</td>
            <td>${esc(result.judge_status || "")}</td>
            <td>${number(result.latency_seconds, 3)}s</td>
            <td class="num">${metricText(resultMetric(result, "power_w_avg"), "W", 2)}</td>
            <td class="num">${metricText(resultMetric(result, "vram_mb_peak"), "MB", 1)}</td>
            <td class="num">${metricText(resultMetric(result, "gpu_busy_percent_avg"), "%", 1)}</td>
            <td>${errorHtml}</td>
          </tr>
          <tr id="${detailId}" class="detail-row" hidden>
            <td colspan="12">
              <div class="detail-grid">
                <div class="detail-block"><b>Raw Transcript</b><pre>${esc(caseInfo.transcript || "")}</pre></div>
                <div class="detail-block"><b>Expected Output</b><pre>${esc(caseInfo.expected || "")}</pre></div>
                <div class="detail-block"><b>Model Output</b><pre>${esc(result.output || "")}</pre></div>
                <div class="detail-block"><b>Judge Summary</b><pre>${esc(result.judge?.summary || result.stderr || "")}</pre></div>
                <div class="detail-block"><b>Telemetry</b><pre>${esc(telemetryText(result))}</pre></div>
              </div>
            </td>
          </tr>
        `);
      });
      table("detailTable", [
        { key: "open", label: "" },
        { key: "model", label: "Model" },
        { key: "case", label: "Case" },
        { key: "category", label: "Category" },
        { key: "score", label: "Score" },
        { key: "ollama", label: "Ollama" },
        { key: "judge", label: "Judge" },
        { key: "latency", label: "Latency" },
        { key: "power", label: "Avg Power" },
        { key: "vram", label: "Peak VRAM" },
        { key: "gpu", label: "GPU Busy" },
        { key: "errors", label: "Judge Issues" }
      ], rows, key => {
        toggleSort(sortStates.detail, key);
        renderDetails(currentRun());
      });
      document.querySelectorAll(".toggle").forEach(button => {
        button.addEventListener("click", () => {
          const row = document.getElementById(button.dataset.detail);
          const open = row.hasAttribute("hidden");
          row.toggleAttribute("hidden", !open);
          button.textContent = open ? "-" : "+";
          button.setAttribute("aria-expanded", String(open));
        });
      });
    }

    function detailSortValue(result, key) {
      if (key === "score") return Number(result.score || 0);
      if (key === "latency") return Number(result.latency_seconds || 0);
      if (key === "power") return Number(resultMetric(result, "power_w_avg") || 0);
      if (key === "vram") return Number(resultMetric(result, "vram_mb_peak") || 0);
      if (key === "gpu") return Number(resultMetric(result, "gpu_busy_percent_avg") || 0);
      if (key === "case") return String(result.case_id || "");
      if (key === "category") return String(result.category || "");
      if (key === "ollama") return String(result.ollama_status || "");
      if (key === "judge") return String(result.judge_status || "");
      if (key === "errors") return resultErrors(result).length;
      return String(result.model || "");
    }

    function resultMetric(result, key) {
      const value = result.telemetry?.metrics?.[key];
      return typeof value === "number" && Number.isFinite(value) ? value : null;
    }

    function telemetryText(result) {
      const telemetry = result.telemetry || {};
      const metrics = telemetry.metrics || {};
      const lines = [
        `status: ${telemetry.status || "missing"}`,
        `provider: ${telemetry.provider || "none"}`,
        `samples: ${telemetry.sample_count || 0}`
      ];
      if (metrics.power_w_avg != null) lines.push(`average power: ${metricText(metrics.power_w_avg, "W", 2)}`);
      if (metrics.power_w_peak != null) lines.push(`peak power: ${metricText(metrics.power_w_peak, "W", 2)}`);
      if (metrics.vram_mb_peak != null) lines.push(`peak VRAM: ${metricText(metrics.vram_mb_peak, "MB", 1)}`);
      if (metrics.vram_total_mb != null) lines.push(`VRAM total: ${metricText(metrics.vram_total_mb, "MB", 1)}`);
      if (metrics.gpu_busy_percent_avg != null) lines.push(`average GPU busy: ${metricText(metrics.gpu_busy_percent_avg, "%", 1)}`);
      if (telemetry.reason) lines.push(`reason: ${telemetry.reason}`);
      return lines.join("\n");
    }

    function setupDownloads(run) {
      const runId = run?.run_id || "";
      const runLink = document.getElementById("downloadRun");
      runLink.href = runId ? `data/${encodeURIComponent(runId)}.json` : "data/latest-run.json";
      const summary = document.getElementById("downloadSummary");
      summary.href = runId ? `data/${encodeURIComponent(runId)}-summary.json` : "data/latest-summary.json";
    }

    function render() {
      const run = currentRun();
      if (!run) {
        document.getElementById("stats").innerHTML = "";
        renderAbout(null);
        renderTests(null);
        return;
      }
      setupDownloads(run);
      renderAbout(run);
      renderStats(run);
      renderLeaderboard(run);
      renderModelTable(run);
      renderTelemetry(run);
      renderOutcomeGraphs(run);
      renderMatrix(run);
      renderCompare(run);
      renderTests(run);
      renderDetails(run);
    }

    setupViewNavigation();
    setupRunSelect();
    setupFilters();
    setupMetricSelect();
    setupCompareButtons();
    setupTestBrowser();
    render();
  </script>
</body>
</html>
"""
