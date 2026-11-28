"""Counting the number drills people actually answer and finish.

The site's two other traffic numbers disagree by an order of magnitude, each
for a structural reason: GoatCounter runs in the browser, so ad blockers hide
some visitors from it, and the proxy's request count includes every crawler,
scanner and static file. This counts what neither can see. A drill is recorded
only once a question in it has been *answered*, which is a form POST no crawler
sends. That includes crawlers following a shared drill link: those links start
a drill on a plain GET, which is why "started" can't mean "opened". The drill
is stamped finished when its last answer is in.

Nothing identifies the person. A row is a language, a mode, where the drill
was started from and two timestamps, under a random per-drill token.

Recording is best effort: a database error is logged and swallowed, because a
broken counter must never break the drill it is counting.
"""

import secrets
from collections import Counter
from datetime import datetime, time, timedelta, timezone

import click
from flask import current_app
from flask.cli import with_appcontext
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from models import QuizRun, db

SOURCE_FORM = "form"
SOURCE_LINK = "link"
# A friend challenge. Short because the column is String(8).
SOURCE_CHALLENGE = "chal"

# Internal mode names that aren't what the site calls them.
MODE_LABELS = {"audio": "listening"}
# Stored source values that aren't what the report should call them.
SOURCE_LABELS = {SOURCE_CHALLENGE: "challenge"}


def new_run_token() -> str:
    return secrets.token_hex(16)


def record_started(token, lang, mode, number_system, source):
    """Record a drill on its first answered question. Idempotent per token."""
    if not (token and lang and mode):
        return
    try:
        db.session.add(
            QuizRun(
                token=token,
                lang=lang,
                mode=mode,
                number_system=number_system,
                source=source,
            )
        )
        db.session.commit()
    except IntegrityError:
        # Already counted: the same first answer arrived twice (a double
        # click sends both before either response updates the cookie).
        db.session.rollback()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.warning("Could not record a started quiz", exc_info=True)


def record_finished(token):
    """Stamp a drill finished. Only the first call per drill changes anything."""
    if not token:
        return
    try:
        db.session.execute(
            update(QuizRun)
            .where(QuizRun.token == token, QuizRun.finished_at.is_(None))
            .values(finished_at=datetime.now(timezone.utc))
        )
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.warning("Could not record a finished quiz", exc_info=True)


def language_label(lang, number_system):
    """`es`, or `cy (traditional)` for a language with numeral systems."""
    if number_system and number_system != "default":
        return f"{lang} ({number_system})"
    return lang


def summarize(days):
    """Started/finished counts for the last `days` UTC days, today included.

    A drill is attributed to the day it was started, so a drill finished just
    after midnight still counts as finished on the day before.
    """
    today = datetime.now(timezone.utc).date()
    first_day = today - timedelta(days=days - 1)
    rows = db.session.execute(
        select(
            QuizRun.lang,
            QuizRun.mode,
            QuizRun.number_system,
            QuizRun.source,
            QuizRun.started_at,
            QuizRun.finished_at,
        ).where(QuizRun.started_at >= datetime.combine(first_day, time.min))
    ).all()

    def tally(key):
        started, finished = Counter(), Counter()
        for row in rows:
            started[key(row)] += 1
            if row.finished_at is not None:
                finished[key(row)] += 1
        return started, finished

    def ranked(key):
        started, finished = tally(key)
        return [(k, started[k], finished[k]) for k, _ in started.most_common()]

    started, finished = tally(lambda row: row.started_at.date())
    return {
        "first_day": first_day,
        "last_day": today,
        "by_day": [
            (day, started[day], finished[day])
            for day in (first_day + timedelta(days=i) for i in range(days))
        ],
        "by_language": ranked(lambda row: language_label(row.lang, row.number_system)),
        "by_mode": ranked(lambda row: MODE_LABELS.get(row.mode, row.mode)),
        "by_source": ranked(lambda row: SOURCE_LABELS.get(row.source, row.source)),
        "total": (len(rows), sum(1 for row in rows if row.finished_at is not None)),
    }


def _table(heading, rows):
    width = max([len(heading)] + [len(str(label)) for label, _, _ in rows])
    lines = [f"{heading:<{width}}  started  finished"]
    lines += [f"{str(label):<{width}}  {s:>7}  {f:>8}" for label, s, f in rows]
    return lines


@click.command("quiz-stats")
@click.option(
    "--days",
    default=30,
    show_default=True,
    type=click.IntRange(1, 3660),
    help="How many UTC days to report, today included.",
)
@with_appcontext
def quiz_stats_command(days):
    """Count the number drills people answered and finished."""
    stats = summarize(days)
    started, finished = stats["total"]
    rate = f" ({finished / started:.0%} finished)" if started else ""
    lines = [
        f"Number drills answered, {stats['first_day']} to {stats['last_day']} (UTC)",
        "A drill counts once a question in it is answered.",
        "",
        *_table("day", stats["by_day"]),
        f"total: {started} started, {finished} finished{rate}",
    ]
    for heading, key in (
        ("language", "by_language"),
        ("mode", "by_mode"),
        ("started from", "by_source"),
    ):
        if stats[key]:
            lines += ["", *_table(heading, stats[key])]
    click.echo("\n".join(lines))
