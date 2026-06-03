from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .judge_codex import ERROR_TYPES
from .report import load_run, refresh_summary


def generate_site(runs_dir: str | Path, site_dir: str | Path) -> Path:
    runs_path = Path(runs_dir)
    site_path = Path(site_dir)
    data_path = site_path / "data"
    site_path.mkdir(parents=True, exist_ok=True)
    data_path.mkdir(parents=True, exist_ok=True)

    runs = _discover_runs(runs_path)
    payload = {"runs": [], "data": {}, "error_types": sorted(ERROR_TYPES)}
    latest_run_id = ""
    for run_file in runs:
        run_data = load_run(run_file)
        run_id = str(run_data.get("run_id") or run_file.parent.name)
        run_data["run_id"] = run_id
        refresh_summary(run_data)
        payload["runs"].append(
            {
                "id": run_id,
                "created_at": run_data.get("created_at", ""),
                "result_count": len(run_data.get("results") or []),
            }
        )
        payload["data"][run_id] = run_data
        target = data_path / f"{run_id}.json"
        target.write_text(json.dumps(run_data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        latest_run_id = run_id

    if latest_run_id:
        shutil.copyfile(data_path / f"{latest_run_id}.json", data_path / "latest-run.json")
    else:
        (data_path / "latest-run.json").write_text("{}\n", encoding="utf-8")

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
    .stat:nth-child(4) { background: var(--lavender); }
    .stat:nth-child(5) { background: var(--red); }
    .stat .label {
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.74rem;
      text-transform: uppercase;
      opacity: 0.78;
    }
    .stat .value {
      font-size: 2rem;
      line-height: 1;
      margin-top: 9px;
      font-weight: 700;
    }
    .grid {
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      gap: 20px;
    }
    section {
      min-width: 0;
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
      .detail-grid { grid-template-columns: 1fr; }
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
      </div>
      <div class="controls">
        <select id="runSelect" aria-label="Run"></select>
        <a class="download" id="downloadRun" href="data/latest-run.json" download>run.json</a>
        <a class="download" id="downloadSummary" href="#" download>summary.md</a>
      </div>
    </header>

    <div class="stats" id="stats"></div>

    <div class="grid">
      <section>
        <h2>Overall Leaderboard</h2>
        <div class="table-wrap"><table id="leaderboardTable"></table></div>
      </section>

      <section>
        <h2>Model Metrics</h2>
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
        <h2>Case Matrix</h2>
        <div class="table-wrap"><table id="matrixTable"></table></div>
      </section>

      <section>
        <h2>Detailed Results</h2>
        <div class="filters" id="filters"></div>
        <div class="table-wrap"><table id="detailTable"></table></div>
      </section>
    </div>
  </div>

  <script type="application/json" id="run-data">__RUN_DATA__</script>
  <script>
    const embedded = JSON.parse(document.getElementById("run-data").textContent);
    const runSelect = document.getElementById("runSelect");
    const filters = document.getElementById("filters");
    const metricSelect = document.getElementById("metricSelect");
    const selectedErrors = new Set();
    let currentRunId = embedded.runs.length ? embedded.runs[embedded.runs.length - 1].id : "";
    let sortState = { key: "model", dir: "asc" };
    let scatterMetricKey = "median_latency_seconds";
    const scatterMetrics = [
      { key: "median_latency_seconds", label: "median latency", unit: "s" },
      { key: "median_power_w_avg", label: "average power", unit: "W" },
      { key: "peak_power_w", label: "peak power", unit: "W" },
      { key: "median_vram_mb_peak", label: "peak VRAM", unit: "MB" },
      { key: "median_gpu_busy_percent_avg", label: "average GPU busy", unit: "%" },
      { key: "error_count", label: "error count", unit: "" }
    ];

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
      const top = (summary.leaderboard || [])[0] || {};
      const errorTotal = Object.values(summary.error_counts || {}).reduce((sum, value) => sum + Number(value || 0), 0);
      document.getElementById("stats").innerHTML = [
        ["run", run.run_id || ""],
        ["top model", top.model || "none"],
        ["results", summary.result_count || 0],
        ["telemetry", summary.telemetry?.sample_count || 0],
        ["errors", errorTotal]
      ].map(([label, value]) => `
        <div class="stat"><div class="label">${esc(label)}</div><div class="value">${esc(value)}</div></div>
      `).join("");
    }

    function table(id, headers, rows) {
      const head = `<thead><tr>${headers.map(h => `<th data-key="${esc(h.key)}">${esc(h.label)}</th>`).join("")}</tr></thead>`;
      const body = `<tbody>${rows.join("")}</tbody>`;
      const el = document.getElementById(id);
      el.innerHTML = head + body;
      el.querySelectorAll("th[data-key]").forEach(th => {
        th.addEventListener("click", () => {
          const key = th.dataset.key;
          sortState = {
            key,
            dir: sortState.key === key && sortState.dir === "asc" ? "desc" : "asc"
          };
          renderDetails(currentRun());
        });
      });
    }

    function renderLeaderboard(run) {
      const rows = (run.summary?.leaderboard || []).map(row => `
        <tr>
          <td class="num">${row.rank}</td>
          <td class="model-name">${esc(row.model)}</td>
          <td>${bar(number(row.average_score, 2), row.average_score, 100, row.average_score < 70 ? "bad" : "")}</td>
          <td>${bar(pct(row.pass_rate), row.pass_rate, 1, "pass")}</td>
          <td>${number(row.median_latency_seconds, 3)}s</td>
          <td class="num">${row.error_count}</td>
        </tr>
      `);
      table("leaderboardTable", [
        { key: "rank", label: "Rank" },
        { key: "model", label: "Model" },
        { key: "score", label: "Score" },
        { key: "pass", label: "Pass Rate" },
        { key: "latency", label: "Median Latency" },
        { key: "errors", label: "Errors" }
      ], rows);
    }

    function renderModelTable(run) {
      const models = run.summary?.models || [];
      const maxLatency = Math.max(1, ...models.map(row => Number(row.median_latency_seconds || 0)));
      const rows = models.map(row => `
        <tr>
          <td class="model-name">${esc(row.model)}</td>
          <td>${bar(number(row.average_score, 2), row.average_score, 100, row.average_score < 70 ? "bad" : "")}</td>
          <td>${bar(pct(row.pass_rate), row.pass_rate, 1, "pass")}</td>
          <td>${bar(`${number(row.median_latency_seconds, 3)}s`, row.median_latency_seconds, maxLatency, "latency")}</td>
          <td class="num">${metricText(row.median_power_w_avg, "W", 2)}</td>
          <td class="num">${metricText(row.median_vram_mb_peak, "MB", 1)}</td>
          <td class="num">${metricText(row.median_gpu_busy_percent_avg, "%", 1)}</td>
          <td class="num">${row.case_count}</td>
          <td class="num">${row.error_count}</td>
        </tr>
      `);
      table("modelTable", [
        { key: "model", label: "Model" },
        { key: "score", label: "Score" },
        { key: "pass", label: "Pass Rate" },
        { key: "latency", label: "Latency" },
        { key: "power", label: "Avg Power" },
        { key: "vram", label: "Peak VRAM" },
        { key: "gpu", label: "GPU Busy" },
        { key: "cases", label: "Cases" },
        { key: "errors", label: "Errors" }
      ], rows);
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
      const rows = (run.summary?.matrix || []).map(row => {
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
      ], rows);
    }

    function renderDetails(run) {
      const caseMap = Object.fromEntries((run.cases || []).map(item => [item.id, item]));
      let results = (run.results || []).filter(resultHasSelectedError);
      results = results.slice().sort((a, b) => {
        const dir = sortState.dir === "asc" ? 1 : -1;
        const av = detailSortValue(a, sortState.key);
        const bv = detailSortValue(b, sortState.key);
        if (av < bv) return -1 * dir;
        if (av > bv) return 1 * dir;
        return 0;
      });
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
        { key: "errors", label: "Errors" }
      ], rows);
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
      const md = renderSummaryMarkdown(run);
      const blob = new Blob([md], { type: "text/markdown" });
      summary.href = URL.createObjectURL(blob);
      summary.download = runId ? `${runId}-summary.md` : "summary.md";
    }

    function renderSummaryMarkdown(run) {
      if (!run) return "";
      const lines = [`# ChirperBench Run ${run.run_id || ""}`, "", "## Leaderboard", ""];
      for (const row of run.summary?.leaderboard || []) {
        lines.push(`${row.rank}. ${row.model}: ${number(row.average_score, 2)} (${pct(row.pass_rate)})`);
      }
      lines.push("");
      return lines.join("\n");
    }

    function render() {
      const run = currentRun();
      if (!run) {
        document.querySelector(".grid").innerHTML = `<div class="empty">No run data found.</div>`;
        document.getElementById("stats").innerHTML = "";
        return;
      }
      setupDownloads(run);
      renderStats(run);
      renderLeaderboard(run);
      renderModelTable(run);
      renderTelemetry(run);
      renderMatrix(run);
      renderDetails(run);
    }

    setupRunSelect();
    setupFilters();
    setupMetricSelect();
    render();
  </script>
</body>
</html>
"""
