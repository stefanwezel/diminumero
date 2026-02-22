# /// script
# requires-python = ">=3.12"
# dependencies = ["rich"]
# ///
"""
Analyse and visualise stress test result files produced by tools/stress_test.py.

Usage:
    uv run tools/analyze_results.py <file> [<file2> ...] [--html [PATH]]

Examples:
    uv run tools/analyze_results.py /home/stefan/Documents/stress_test_results/stress_test_*.json
    uv run tools/analyze_results.py result.json --html
    uv run tools/analyze_results.py result1.json result2.json --html /tmp/report.html
"""

import argparse
import json
import math
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

DEFAULT_RESULTS_DIR = Path("/home/stefan/Documents/stress_test_results")
console = Console()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyse stress test JSON results from tools/stress_test.py"
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="One or more stress test result JSON files",
    )
    parser.add_argument(
        "--html",
        nargs="?",
        const="__auto__",
        default=None,
        metavar="PATH",
        help="Write an HTML report (default path when flag given without value: results dir)",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_file(path: str) -> dict | None:
    p = Path(path)
    if not p.exists():
        console.print(f"[red]File not found: {path}[/red]")
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError as exc:
        console.print(f"[red]Failed to parse {path}: {exc}[/red]")
        return None


# ---------------------------------------------------------------------------
# Statistics helpers
# ---------------------------------------------------------------------------


def percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    idx = (p / 100) * (len(sorted_values) - 1)
    lo = int(idx)
    hi = lo + 1
    if hi >= len(sorted_values):
        return sorted_values[-1]
    frac = idx - lo
    return sorted_values[lo] + frac * (sorted_values[hi] - sorted_values[lo])


def compute_derived(data: dict) -> dict:
    """Compute any stats not already in the JSON (e.g. from raw requests array)."""
    requests = data.get("requests", [])
    times = sorted(r["response_time_ms"] for r in requests)
    errors: dict[str, int] = defaultdict(int)
    for r in requests:
        if not r["success"] and r.get("error"):
            errors[r["error"]] += 1
    return {
        "sorted_times": times,
        "errors": dict(errors),
        "requests": requests,
    }


# ---------------------------------------------------------------------------
# ASCII bar chart helpers
# ---------------------------------------------------------------------------

BAR_CHAR = "█"
BAR_WIDTH = 30


def make_bar(fraction: float) -> str:
    filled = round(fraction * BAR_WIDTH)
    return BAR_CHAR * filled


def ascii_histogram(
    values: list[float],
    bins: int = 20,
    title: str = "Response Time Distribution",
) -> None:
    if not values:
        return
    lo, hi = min(values), max(values)
    if lo == hi:
        hi = lo + 1
    width = (hi - lo) / bins
    counts = [0] * bins
    for v in values:
        idx = min(int((v - lo) / width), bins - 1)
        counts[idx] += 1
    total = len(values)
    max_count = max(counts) or 1

    table = Table(
        title=title,
        box=box.SIMPLE,
        show_header=False,
        padding=(0, 1),
    )
    table.add_column("Range", style="cyan", no_wrap=True, min_width=18)
    table.add_column("Bar", no_wrap=True, min_width=BAR_WIDTH + 5)
    table.add_column("Pct", style="dim", justify="right")

    for i in range(bins):
        bin_lo = lo + i * width
        bin_hi = bin_lo + width
        count = counts[i]
        pct = count / total * 100
        bar = make_bar(count / max_count)
        table.add_row(
            f"{bin_lo:6.0f}–{bin_hi:.0f} ms",
            f"[green]{bar}[/green]",
            f"{pct:.1f}%",
        )

    console.print(table)


def rps_timeline(requests: list[dict], title: str = "Requests per Second") -> None:
    if not requests:
        return
    buckets: dict[int, int] = defaultdict(int)
    for r in requests:
        buckets[int(r["timestamp"])] += 1
    if not buckets:
        return

    min_t = min(buckets)
    max_t = max(buckets)
    counts = [buckets.get(t, 0) for t in range(min_t, max_t + 1)]
    max_count = max(counts) or 1

    table = Table(
        title=title,
        box=box.SIMPLE,
        show_header=False,
        padding=(0, 1),
    )
    table.add_column("Second", style="cyan", no_wrap=True, min_width=8)
    table.add_column("Bar", no_wrap=True, min_width=BAR_WIDTH + 5)
    table.add_column("RPS", style="dim", justify="right")

    for i, count in enumerate(counts):
        bar = make_bar(count / max_count)
        table.add_row(
            f"+{i:3d}s",
            f"[blue]{bar}[/blue]",
            str(count),
        )

    console.print(table)


# ---------------------------------------------------------------------------
# Terminal report for a single file
# ---------------------------------------------------------------------------


def print_report(data: dict, filename: str) -> None:
    derived = compute_derived(data)
    cfg = data.get("config", {})
    s = data.get("summary", {})
    by_ep = data.get("by_endpoint", {})
    requests = derived["requests"]
    times = derived["sorted_times"]

    # 1. Config panel
    cfg_lines = "\n".join(
        [
            f"  URL:       {cfg.get('url', '—')}",
            f"  Users:     {cfg.get('users', '—')}",
            f"  Duration:  {cfg.get('duration', '—')}s",
            f"  Mode:      {cfg.get('mode', '—')}",
            f"  Language:  {cfg.get('language', '—')}",
        ]
    )
    console.print(
        Panel(cfg_lines, title=f"[bold]{filename}[/bold]", border_style="blue")
    )

    # 2. Summary table
    summary_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    summary_table.add_column("Metric", style="bold cyan")
    summary_table.add_column("Value", justify="right")

    total = s.get("total_requests", 0)
    successful = s.get("successful_requests", 0)
    failed = s.get("failed_requests", 0)
    error_rate = s.get("error_rate_percent", 0.0)
    rps = s.get("requests_per_second", 0.0)
    avg_ms = s.get("avg_response_time_ms", 0.0)
    p50 = s.get("median_response_time_ms", 0.0)
    p95 = s.get("p95_response_time_ms", 0.0)
    p99 = s.get("p99_response_time_ms", 0.0)
    quizzes = s.get("total_quizzes_completed", 0)

    error_style = "red" if error_rate > 0 else "green"

    summary_table.add_row("Total requests", str(total))
    summary_table.add_row("Successful", f"[green]{successful}[/green]")
    summary_table.add_row("Failed", f"[{error_style}]{failed}[/{error_style}]")
    summary_table.add_row(
        "Error rate", f"[{error_style}]{error_rate:.2f}%[/{error_style}]"
    )
    summary_table.add_row("Requests/sec", f"{rps:.2f}")
    summary_table.add_row("Avg ms", f"{avg_ms:.1f}")
    summary_table.add_row("p50 ms", f"{p50:.1f}")
    summary_table.add_row("p95 ms", f"{p95:.1f}")
    summary_table.add_row("p99 ms", f"{p99:.1f}")
    summary_table.add_row("Quizzes completed", str(quizzes))

    console.print(summary_table)

    # 3. By-endpoint table
    if by_ep:
        ep_table = Table(
            title="By Endpoint",
            box=box.SIMPLE_HEAVY,
            show_header=True,
        )
        ep_table.add_column("Endpoint", style="cyan")
        ep_table.add_column("Method", justify="center")
        ep_table.add_column("Count", justify="right")
        ep_table.add_column("Success%", justify="right")
        ep_table.add_column("Avg ms", justify="right")
        ep_table.add_column("p50 ms", justify="right")
        ep_table.add_column("p95 ms", justify="right")
        ep_table.add_column("p99 ms", justify="right")

        # collect method per endpoint from raw requests
        ep_methods: dict[str, set[str]] = defaultdict(set)
        for r in requests:
            ep_methods[r["endpoint"]].add(r["method"])

        sorted_eps = sorted(by_ep.items(), key=lambda x: x[1]["count"], reverse=True)
        for ep, stats in sorted_eps:
            count = stats["count"]
            success_count = stats["success_count"]
            success_pct = success_count / count * 100 if count else 0.0
            method = "/".join(sorted(ep_methods.get(ep, {"?"})))
            sty = "red" if success_pct < 100 else ""
            ep_table.add_row(
                ep,
                method,
                str(count),
                f"[{sty}]{success_pct:.1f}%[/{sty}]" if sty else f"{success_pct:.1f}%",
                f"{stats['avg_ms']:.1f}",
                f"{stats['p50_ms']:.1f}",
                f"{stats['p95_ms']:.1f}",
                f"{stats['p99_ms']:.1f}",
            )

        console.print(ep_table)

    # 4. Response time histogram
    ascii_histogram(times, bins=20, title="Response Time Distribution")

    # 5. RPS timeline
    rps_timeline(requests, title="Requests per Second (timeline)")

    # 6. Errors section
    errors = derived["errors"]
    if errors and failed > 0:
        err_table = Table(title="Errors", box=box.SIMPLE_HEAVY)
        err_table.add_column("Error", style="red")
        err_table.add_column("Count", justify="right")
        for msg, cnt in sorted(errors.items(), key=lambda x: x[1], reverse=True):
            err_table.add_row(msg, str(cnt))
        console.print(err_table)


# ---------------------------------------------------------------------------
# Multi-file comparison
# ---------------------------------------------------------------------------


def print_comparison(datasets: list[tuple[str, dict]]) -> None:
    table = Table(title="Comparison", box=box.SIMPLE_HEAVY)
    table.add_column("Metric", style="bold cyan")
    for fname, _ in datasets:
        table.add_column(fname, justify="right")

    metrics_keys = [
        ("RPS", "requests_per_second", ".1f"),
        ("p50 ms", "median_response_time_ms", ".1f"),
        ("p95 ms", "p95_response_time_ms", ".1f"),
        ("p99 ms", "p99_response_time_ms", ".1f"),
        ("Error %", "error_rate_percent", ".2f"),
        ("Quizzes", "total_quizzes_completed", "d"),
    ]

    for label, key, fmt in metrics_keys:
        row = [label]
        for _, data in datasets:
            val = data.get("summary", {}).get(key, 0)
            if fmt == "d":
                row.append(str(int(val)))
            else:
                row.append(format(val, fmt))
        table.add_row(*row)

    console.print(table)


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

CHART_JS_CDN = "https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"

COLORS = [
    "rgba(54, 162, 235, 0.8)",
    "rgba(255, 99, 132, 0.8)",
    "rgba(75, 192, 192, 0.8)",
    "rgba(255, 159, 64, 0.8)",
]
COLORS_BORDER = [
    "rgba(54, 162, 235, 1)",
    "rgba(255, 99, 132, 1)",
    "rgba(75, 192, 192, 1)",
    "rgba(255, 159, 64, 1)",
]


def _js_array(values: list) -> str:
    return json.dumps(values)


def build_html(datasets: list[tuple[str, dict]]) -> str:
    # Build per-second timeline data for each file
    timeline_datasets = []
    for idx, (fname, data) in enumerate(datasets):
        requests = data.get("requests", [])
        if not requests:
            continue
        buckets: dict[int, list[float]] = defaultdict(list)
        for r in requests:
            buckets[int(r["timestamp"])].append(r["response_time_ms"])
        min_t = min(buckets)
        max_t = max(buckets)
        labels = list(range(0, max_t - min_t + 1))
        avg_per_sec = [
            round(
                sum(buckets.get(min_t + i, [0]))
                / max(len(buckets.get(min_t + i, [0])), 1),
                1,
            )
            for i in labels
        ]
        timeline_datasets.append(
            {
                "label": fname,
                "data": avg_per_sec,
                "labels": [str(l) for l in labels],
                "color": COLORS[idx % len(COLORS)],
                "border": COLORS_BORDER[idx % len(COLORS_BORDER)],
            }
        )

    # Endpoint latency comparison
    all_endpoints: list[str] = []
    for _, data in datasets:
        for ep in data.get("by_endpoint", {}):
            if ep not in all_endpoints:
                all_endpoints.append(ep)

    endpoint_datasets_p50 = []
    endpoint_datasets_p95 = []
    endpoint_datasets_p99 = []
    for idx, (fname, data) in enumerate(datasets):
        by_ep = data.get("by_endpoint", {})
        p50s = [by_ep.get(ep, {}).get("p50_ms", 0) for ep in all_endpoints]
        p95s = [by_ep.get(ep, {}).get("p95_ms", 0) for ep in all_endpoints]
        p99s = [by_ep.get(ep, {}).get("p99_ms", 0) for ep in all_endpoints]
        endpoint_datasets_p50.append(
            {"label": f"{fname} p50", "data": p50s, "color": COLORS[idx % len(COLORS)]}
        )
        endpoint_datasets_p95.append(
            {
                "label": f"{fname} p95",
                "data": p95s,
                "color": COLORS[(idx + 1) % len(COLORS)],
            }
        )
        endpoint_datasets_p99.append(
            {
                "label": f"{fname} p99",
                "data": p99s,
                "color": COLORS[(idx + 2) % len(COLORS)],
            }
        )

    endpoint_chart_datasets = (
        endpoint_datasets_p50 + endpoint_datasets_p95 + endpoint_datasets_p99
    )

    # Success/failure doughnut
    doughnut_labels = []
    doughnut_data = []
    doughnut_colors = []
    for idx, (fname, data) in enumerate(datasets):
        s = data.get("summary", {})
        doughnut_labels += [f"{fname} OK", f"{fname} Fail"]
        doughnut_data += [s.get("successful_requests", 0), s.get("failed_requests", 0)]
        doughnut_colors += [COLORS[idx % len(COLORS)], "rgba(220, 38, 38, 0.8)"]

    # Build HTML
    summary_cards_html = ""
    for fname, data in datasets:
        s = data.get("summary", {})
        summary_cards_html += f"""
        <div class="card-group">
          <h3>{fname}</h3>
          <div class="cards">
            <div class="card"><div class="card-value">{s.get("requests_per_second", 0):.1f}</div><div class="card-label">RPS</div></div>
            <div class="card"><div class="card-value">{s.get("error_rate_percent", 0):.2f}%</div><div class="card-label">Error Rate</div></div>
            <div class="card"><div class="card-value">{s.get("p95_response_time_ms", 0):.1f} ms</div><div class="card-label">p95</div></div>
            <div class="card"><div class="card-value">{s.get("total_quizzes_completed", 0)}</div><div class="card-label">Quizzes</div></div>
          </div>
        </div>
        """

    # Endpoint detail tables
    ep_tables_html = ""
    for fname, data in datasets:
        by_ep = data.get("by_endpoint", {})
        if not by_ep:
            continue
        rows = ""
        for ep, stats in sorted(
            by_ep.items(), key=lambda x: x[1]["count"], reverse=True
        ):
            count = stats["count"]
            sc = stats["success_count"]
            pct = sc / count * 100 if count else 0.0
            rows += (
                f"<tr><td>{ep}</td><td>{count}</td>"
                f"<td>{pct:.1f}%</td>"
                f"<td>{stats['avg_ms']:.1f}</td>"
                f"<td>{stats['p50_ms']:.1f}</td>"
                f"<td>{stats['p95_ms']:.1f}</td>"
                f"<td>{stats['p99_ms']:.1f}</td></tr>"
            )
        ep_tables_html += f"""
        <h3>{fname} — Endpoint Detail</h3>
        <table>
          <thead><tr><th>Endpoint</th><th>Count</th><th>Success%</th>
          <th>Avg ms</th><th>p50 ms</th><th>p95 ms</th><th>p99 ms</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
        """

    # Build timeline chart JS
    all_timeline_labels: list[str] = []
    if timeline_datasets:
        max_len = max(len(d["labels"]) for d in timeline_datasets)
        all_timeline_labels = [str(i) for i in range(max_len)]

    timeline_js_datasets = []
    for td in timeline_datasets:
        # pad shorter series
        padded = td["data"] + [None] * (len(all_timeline_labels) - len(td["data"]))
        timeline_js_datasets.append(
            f'{{"label":{json.dumps(td["label"])},"data":{json.dumps(padded)},'
            f'"borderColor":{json.dumps(td["border"])},"backgroundColor":"transparent",'
            f'"tension":0.3,"fill":false,"spanGaps":true}}'
        )

    ep_js_datasets = []
    for ed in endpoint_chart_datasets:
        ep_js_datasets.append(
            f'{{"label":{json.dumps(ed["label"])},"data":{json.dumps(ed["data"])},'
            f'"backgroundColor":{json.dumps(ed["color"])}}}'
        )

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Stress Test Report — {timestamp}</title>
<script src="{CHART_JS_CDN}"></script>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; color: #222; }}
  h1 {{ color: #333; }}
  h2 {{ color: #555; margin-top: 2em; border-bottom: 2px solid #ddd; padding-bottom: 4px; }}
  h3 {{ color: #666; }}
  .card-group {{ margin-bottom: 1.5em; }}
  .cards {{ display: flex; gap: 16px; flex-wrap: wrap; }}
  .card {{ background: white; border-radius: 8px; padding: 16px 24px; box-shadow: 0 1px 4px rgba(0,0,0,0.1); min-width: 120px; text-align: center; }}
  .card-value {{ font-size: 2em; font-weight: bold; color: #2563eb; }}
  .card-label {{ color: #666; font-size: 0.85em; margin-top: 4px; }}
  .chart-container {{ background: white; border-radius: 8px; padding: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.1); margin-bottom: 1.5em; max-width: 900px; }}
  .chart-row {{ display: flex; gap: 20px; flex-wrap: wrap; }}
  .chart-row .chart-container {{ flex: 1; min-width: 400px; }}
  table {{ border-collapse: collapse; width: 100%; max-width: 900px; background: white; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.1); margin-bottom: 1.5em; }}
  th, td {{ padding: 10px 14px; text-align: left; border-bottom: 1px solid #eee; }}
  th {{ background: #f0f4ff; color: #333; font-weight: 600; }}
  tr:last-child td {{ border-bottom: none; }}
  footer {{ color: #999; font-size: 0.8em; margin-top: 3em; }}
</style>
</head>
<body>
<h1>Stress Test Report</h1>
<p style="color:#666">Generated: {timestamp}</p>

<h2>Summary</h2>
{summary_cards_html}

<h2>Response Time over Time</h2>
<div class="chart-container">
  <canvas id="timelineChart"></canvas>
</div>

<div class="chart-row">
  <div class="chart-container">
    <h3>Endpoint Latency (p50 / p95 / p99)</h3>
    <canvas id="endpointChart"></canvas>
  </div>
  <div class="chart-container">
    <h3>Success vs Failure</h3>
    <canvas id="doughnutChart"></canvas>
  </div>
</div>

<h2>Endpoint Detail</h2>
{ep_tables_html}

<footer>Generated by tools/analyze_results.py</footer>

<script>
new Chart(document.getElementById('timelineChart'), {{
  type: 'line',
  data: {{
    labels: {_js_array(all_timeline_labels)},
    datasets: [{",".join(timeline_js_datasets)}]
  }},
  options: {{
    responsive: true,
    plugins: {{ title: {{ display: true, text: 'Avg Response Time (ms) per Second' }} }},
    scales: {{ y: {{ title: {{ display: true, text: 'ms' }} }} }}
  }}
}});

new Chart(document.getElementById('endpointChart'), {{
  type: 'bar',
  data: {{
    labels: {_js_array(all_endpoints)},
    datasets: [{",".join(ep_js_datasets)}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ position: 'top' }} }},
    scales: {{ y: {{ title: {{ display: true, text: 'ms' }} }} }}
  }}
}});

new Chart(document.getElementById('doughnutChart'), {{
  type: 'doughnut',
  data: {{
    labels: {_js_array(doughnut_labels)},
    datasets: [{{
      data: {_js_array(doughnut_data)},
      backgroundColor: {_js_array(doughnut_colors)}
    }}]
  }},
  options: {{ responsive: true }}
}});
</script>
</body>
</html>
"""
    return html


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    args = parse_args()

    datasets: list[tuple[str, dict]] = []
    for path in args.files:
        data = load_file(path)
        if data is not None:
            datasets.append((Path(path).name, data))

    if not datasets:
        console.print("[red]No valid result files to analyse.[/red]")
        sys.exit(1)

    for fname, data in datasets:
        print_report(data, fname)

    if len(datasets) >= 2:
        print_comparison(datasets)

    if args.html is not None:
        if args.html == "__auto__":
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            html_path = DEFAULT_RESULTS_DIR / f"report_{timestamp}.html"
        else:
            html_path = Path(args.html)

        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_content = build_html(datasets)
        html_path.write_text(html_content, encoding="utf-8")
        console.print(f"\n[green]HTML report written to: {html_path}[/green]")


if __name__ == "__main__":
    main()
