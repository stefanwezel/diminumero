# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "sqlalchemy>=2",
#   "psycopg[binary]",
#   "matplotlib",
#   "rich",
#   "python-dotenv",
# ]
# ///
"""
Fetch poll responses from the diminumero database and render simple plots.

By default this script targets *production*: it loads `.env.prod` from the
repo root (gitignored) and reads `DATABASE_URL` from there. Pass `--db` to
override, or point it at the local dev SQLite explicitly.

Usage:
    uv run tools/analyze_poll.py                                  # prod (via .env.prod)
    uv run tools/analyze_poll.py --db sqlite:///instance/diminumero.db
    uv run tools/analyze_poll.py --db "postgresql+psycopg://user:pw@host/db" --out /tmp/poll
    DATABASE_URL=sqlite:///./data/diminumero.db uv run tools/analyze_poll.py

Outputs:
  - A terminal summary table (counts + percentages per question).
  - Bar-chart PNGs (one per question) into --out (default: ./poll_charts/).
  - A combined poll_summary.png with all three multiple-choice questions.
  - The list of free-form responses printed to the terminal.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from dotenv import dotenv_values
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from sqlalchemy import create_engine, text

console = Console()

LOCAL_SQLITE_URL = "sqlite:///instance/diminumero.db"
ENV_PROD_FILE = Path(__file__).resolve().parent.parent / ".env.prod"


def resolve_db_url() -> str:
    """Pick the DB URL with this precedence:

    1. `DATABASE_URL` already exported in the shell.
    2. `DATABASE_URL` from `.env.prod` next to the repo root (production default).
    3. Local dev SQLite — last resort, so contributors without prod access
       still get a working command.
    """
    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        return env_url
    if ENV_PROD_FILE.exists():
        prod_url = dotenv_values(ENV_PROD_FILE).get("DATABASE_URL")
        if prod_url:
            return prod_url
    return LOCAL_SQLITE_URL

# Display labels for each enum value — keeps charts readable without
# pulling translations.py into a CLI script.
LABELS = {
    "color_scheme_pref": {
        "dark": "Dark (new)",
        "light": "Light (classic)",
        "no_preference": "No preference",
    },
    "cards_aware": {
        "yes": "Yes",
        "no": "No",
    },
    "device": {
        "mobile": "Mobile",
        "desktop": "Desktop",
    },
}

QUESTION_TITLES = {
    "color_scheme_pref": "Prefer the new dark color scheme?",
    "cards_aware": "Aware of the index-cards feature?",
    "device": "Mobile or desktop?",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument(
        "--db",
        default=None,
        help=(
            "SQLAlchemy DB URL. Defaults to $DATABASE_URL, then "
            f"DATABASE_URL in {ENV_PROD_FILE.name}, then {LOCAL_SQLITE_URL}."
        ),
    )
    parser.add_argument(
        "--out",
        default="poll_charts",
        help="Output directory for PNG charts (default: ./poll_charts)",
    )
    return parser.parse_args()


def fetch_responses(db_url: str) -> list[dict]:
    engine = create_engine(db_url)
    sql = text(
        "SELECT id, user_sub, color_scheme_pref, cards_aware, device, "
        "freeform, created_at FROM poll_responses ORDER BY created_at"
    )
    with engine.connect() as conn:
        rows = conn.execute(sql).mappings().all()
    return [dict(r) for r in rows]


def percent(n: int, total: int) -> float:
    return (n / total * 100) if total else 0.0


def print_summary(rows: list[dict]) -> None:
    total = len(rows)
    logged_in = sum(1 for r in rows if r["user_sub"])
    first = rows[0]["created_at"] if rows else None
    last = rows[-1]["created_at"] if rows else None

    header = (
        f"Total responses: [bold]{total}[/bold]    "
        f"Logged-in: [bold]{logged_in}[/bold]    "
        f"Anonymous: [bold]{total - logged_in}[/bold]\n"
        f"First: {first}    Last: {last}"
    )
    console.print(Panel(header, title="[bold]Poll responses[/bold]", border_style="blue"))

    for field in ("color_scheme_pref", "cards_aware", "device"):
        counts = Counter(r[field] for r in rows)
        table = Table(
            title=QUESTION_TITLES[field], box=box.SIMPLE, padding=(0, 2)
        )
        table.add_column("Option", style="cyan")
        table.add_column("Count", justify="right")
        table.add_column("Share", justify="right", style="dim")
        for key, label in LABELS[field].items():
            n = counts.get(key, 0)
            table.add_row(label, str(n), f"{percent(n, total):.1f}%")
        console.print(table)

    freeform = [r["freeform"] for r in rows if r["freeform"]]
    if freeform:
        ff_table = Table(
            title=f"Free-form responses ({len(freeform)})",
            box=box.SIMPLE_HEAVY,
            show_lines=True,
        )
        ff_table.add_column("#", style="dim", justify="right")
        ff_table.add_column("Response")
        for i, txt in enumerate(freeform, 1):
            ff_table.add_row(str(i), txt)
        console.print(ff_table)
    else:
        console.print("[dim]No free-form responses yet.[/dim]")


def render_charts(rows: list[dict], out_dir: Path) -> None:
    # Heavy import — only when we actually plot.
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir.mkdir(parents=True, exist_ok=True)
    total = len(rows)

    fields = ("color_scheme_pref", "cards_aware", "device")

    # Individual per-question PNGs
    for field in fields:
        counts = Counter(r[field] for r in rows)
        labels = list(LABELS[field].values())
        values = [counts.get(k, 0) for k in LABELS[field].keys()]

        fig, ax = plt.subplots(figsize=(6, 4))
        bars = ax.bar(labels, values, color="#724E91")
        ax.set_title(QUESTION_TITLES[field])
        ax.set_ylabel("Responses")
        ax.set_ylim(0, max(values + [1]) * 1.18)
        for bar, v in zip(bars, values):
            pct = percent(v, total)
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height(),
                f"{v}\n({pct:.0f}%)",
                ha="center",
                va="bottom",
                fontsize=9,
            )
        fig.tight_layout()
        path = out_dir / f"{field}.png"
        fig.savefig(path, dpi=120)
        plt.close(fig)
        console.print(f"  wrote [green]{path}[/green]")

    # Combined summary figure (3 panels side by side)
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    for ax, field in zip(axes, fields):
        counts = Counter(r[field] for r in rows)
        labels = list(LABELS[field].values())
        values = [counts.get(k, 0) for k in LABELS[field].keys()]
        ax.bar(labels, values, color="#724E91")
        ax.set_title(QUESTION_TITLES[field], fontsize=10)
        ax.set_ylim(0, max(values + [1]) * 1.18)
        ax.tick_params(axis="x", labelsize=8)
        for i, v in enumerate(values):
            pct = percent(v, total)
            ax.text(
                i, v, f"{v}\n({pct:.0f}%)", ha="center", va="bottom", fontsize=8
            )
    fig.suptitle(
        f"diminumero poll — {total} responses "
        f"(generated {datetime.now():%Y-%m-%d %H:%M})",
        fontsize=11,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    summary_path = out_dir / "poll_summary.png"
    fig.savefig(summary_path, dpi=120)
    plt.close(fig)
    console.print(f"  wrote [green]{summary_path}[/green]")


def _redact(url: str) -> str:
    """Strip the password from a DB URL for safe display."""
    import re

    return re.sub(r"(://[^:/@]+:)[^@]+(@)", r"\1***\2", url)


def main() -> None:
    args = parse_args()
    db_url = args.db or resolve_db_url()
    console.print(f"[dim]Using DB: {_redact(db_url)}[/dim]")
    try:
        rows = fetch_responses(db_url)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Failed to query {_redact(db_url)}: {exc}[/red]")
        sys.exit(1)

    if not rows:
        console.print("[yellow]No poll responses found yet.[/yellow]")
        return

    print_summary(rows)
    console.print()
    render_charts(rows, Path(args.out))


if __name__ == "__main__":
    main()
