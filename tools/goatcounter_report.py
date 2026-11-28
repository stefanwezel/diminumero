# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "python-dotenv",
# ]
# ///
"""Break down how diminumero is used, from its GoatCounter data.

GoatCounter's dashboard lists raw paths. This groups them into the site's own
sections (number drills, reference pages, Learn pages, verbs, cards, friend
challenges) and by the language being learned. From the hit-level CSV export
it also follows each visit from where it landed to where it left: entry pages,
the number-drill funnel, common journeys, what people do after landing.

Setup: in GoatCounter, open your name in the top menu → API, create a key that
may read statistics and export, and add it to .env (gitignored):

    GOATCOUNTER_API_KEY=...

Usage:
    uv run tools/goatcounter_report.py                  # last 90 days
    uv run tools/goatcounter_report.py --days 0         # everything exported
    uv run tools/goatcounter_report.py --offline        # re-render the cached export
    uv run tools/goatcounter_report.py --source api     # aggregate API only, no sessions
    uv run tools/goatcounter_report.py --tz Europe/Berlin --open

Output: build/goatcounter/report.html (charts and tables), plus the key
findings in the terminal. The raw export is cached in
build/goatcounter/<site>/hits.csv (gitignored, like all of build/) and grown
incrementally from the last exported hit. GoatCounter allows one export an
hour, so a re-run within the hour re-renders the cached data.

If the export can't be made (the key lacks the permission, or the site doesn't
keep individual pageviews), the report falls back to the aggregate stats API:
the same breakdown by section, language, referrer and device, without the
session-based parts.

What GoatCounter can't see: visitors whose ad blocker drops count.js, and
anything inside a page after it loaded (Listening rounds swap questions in
without a page load). `flask quiz-stats` counts number drills server-side and
is the authority on how many were actually answered.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import html
import importlib.util
import io
import json
import math
import os
import re
import statistics
import sys
import time
import webbrowser
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import dotenv_values

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SITE = (
    "stefanwezel"  # templates/base.html counts to stefanwezel.goatcounter.com
)
DEFAULT_OUT = REPO_ROOT / "build" / "goatcounter"
EXPORT_COOLDOWN = timedelta(hours=1)  # GoatCounter: one export an hour
EXPORT_TIMEOUT_S = 600
API_MIN_INTERVAL_S = 0.26  # GoatCounter allows 4 requests a second
API_DAYS_WHEN_ALL = 730  # --days 0 in API mode: the API needs a start date

# The CSV export's columns this script reads (format version 2).
EXPORT_VERSION = "2"
REQUIRED_COLUMNS = (
    "Path",
    "Event",
    "Browser",
    "System",
    "Session",
    "Bot",
    "Referrer",
    "Referrer scheme",
    "Screen size",
    "Location",
    "FirstVisit",
    "Date",
)


# ---------------------------------------------------------------------------
# The site's map: which path is which part of diminumero
# ---------------------------------------------------------------------------

# key -> (label, group). Groups are what the per-language table splits by.
SECTIONS: dict[str, tuple[str, str]] = {
    "landing": ("Landing page", "Browse"),
    "menu": ("Language menu", "Browse"),
    "numbers_setup": ("Number drill setup", "Number drills"),
    "number_drill": ("Number drill", "Number drills"),
    "listening_setup": ("Listening setup", "Number drills"),
    "listening_drill": ("Listening drill", "Number drills"),
    "drill_results": ("Drill results", "Number drills"),
    "reference": ("Number list (1-100 / 1-1000)", "Read"),
    "learn_numbers": ("Learn: numbers", "Read"),
    "cheat_sheet": ("Verb cheat sheet", "Read"),
    "learn_verbs": ("Learn: verbs", "Read"),
    "worksheet": ("Printable worksheet", "Read"),
    "verbs": ("Verb list", "Verbs"),
    "verb_drill": ("Verb drill", "Verbs"),
    "verb_results": ("Verb drill results", "Verbs"),
    "cards": ("Index cards", "Cards"),
    "card_drill": ("Index-card practice", "Cards"),
    "challenge": ("Friend challenge", "Challenge"),
    "info": ("About & legal", "Other"),
    "other": ("Unrecognised path", "Other"),
}
DRILL_SECTIONS = {"number_drill", "listening_drill", "verb_drill", "card_drill"}
NUMBER_DRILL_SECTIONS = {"number_drill", "listening_drill"}
NUMBER_PRACTICE_SECTIONS = {"numbers_setup", "listening_setup"} | NUMBER_DRILL_SECTIONS
FINISHED_SECTIONS = {"drill_results", "verb_results"}
READ_SECTIONS = {k for k, (_, g) in SECTIONS.items() if g == "Read"}

# Sub-paths under /<lang_code>/ (see "URL Route Structure" in CLAUDE.md).
LANG_SUBPAGES: dict[str, tuple[str, str | None]] = {
    "": ("menu", None),
    "numbers": ("numbers_setup", None),
    "conjugation-cheat-sheet": ("cheat_sheet", None),
    "quiz/easy": ("number_drill", "Easy"),
    "quiz/advanced": ("number_drill", "Advanced"),
    "quiz/hardcore": ("number_drill", "Hardcore"),
    "listening": ("listening_setup", None),
    "listen": ("listening_drill", "Listening"),
    "results": ("drill_results", None),
    "learn": ("learn_numbers", None),
    "learn/conjugations": ("learn_verbs", None),
    "worksheet": ("worksheet", None),
    "conjugate": ("verbs", None),
    "conjugate/practice": ("verb_drill", None),
    "conjugate/practice/results": ("verb_results", None),
}
REFERENCE_RE = re.compile(r"numbers/\d+-\d+")
DRILL_MODES = ("Easy", "Advanced", "Hardcore", "Listening")


def load_language_names() -> dict[str, str]:
    """code -> English name, read from languages/config.py without importing the app.

    Loading the file on its own skips languages/__init__.py, which pulls in the
    number decks. A failure only costs the names: paths then match any
    two-letter prefix.
    """
    path = REPO_ROOT / "languages" / "config.py"
    try:
        spec = importlib.util.spec_from_file_location("_diminumero_langs", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return {
            code: info.get("name", code)
            for code, info in module.AVAILABLE_LANGUAGES.items()
        }
    except Exception as exc:  # noqa: BLE001 — names are a nicety
        print(f"note: couldn't read language names ({exc})", file=sys.stderr)
        return {}


@dataclass(frozen=True)
class Page:
    section: str
    lang: str | None = None  # the language being learned
    mode: str | None = None  # number-drill mode
    hl: str | None = None  # the ?hl= UI-language version


def classify(path: str, languages: dict[str, str]) -> Page:
    """Which part of the site a counted path is.

    count.js reports the canonical URL, which keeps only `?hl=`, so a shared
    preset link counts as its config screen (/es/numbers) and every friend
    challenge page as the fixed /challenge/link.
    """
    raw, _, query = path.partition("?")
    hl = (parse_qs(query).get("hl") or [None])[0]
    parts = [p for p in raw.split("/") if p]
    if not parts:
        return Page("landing", hl=hl)
    head, rest = parts[0], "/".join(parts[1:])
    if head == "challenge":
        return Page("challenge", hl=hl)
    if head == "cards":
        practice = bool(parts[1:]) and parts[1] == "practice"
        return Page("card_drill" if practice else "cards", hl=hl)
    if head in ("privacy", "about", "imprint"):
        return Page("info", hl=hl)
    is_lang = head in languages if languages else bool(re.fullmatch(r"[a-z]{2}", head))
    if is_lang:
        if rest in LANG_SUBPAGES:
            section, mode = LANG_SUBPAGES[rest]
            return Page(section, head, mode, hl)
        if REFERENCE_RE.fullmatch(rest):
            return Page("reference", head, hl=hl)
        return Page("other", head, hl=hl)
    return Page("other", hl=hl)


def section_label(key: str) -> str:
    return SECTIONS[key][0]


# ---------------------------------------------------------------------------
# Referrers, devices, countries
# ---------------------------------------------------------------------------

DIRECT = "Direct / no referrer"
# Order matters: AI assistants and classrooms live on google./microsoft.
# hosts that the search rule would otherwise claim.
REFERRER_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("This site", re.compile(r"diminumero|^localhost$|^127\.0\.0\.1$")),
    # Coming back from logging in (Auth0, and the identity providers behind it)
    # lands on /callback: a round trip, not someone arriving from Google.
    (
        "Back from sign-in",
        re.compile(
            r"\.auth0\.com$|^accounts\.google\.[a-z.]+$|^appleid\.apple\.com$|"
            r"^login\.(live|microsoftonline)\.com$"
        ),
    ),
    (
        "AI assistants",
        re.compile(
            r"(^|\.)(chatgpt\.com|openai\.com|perplexity\.ai|claude\.ai|"
            r"gemini\.google\.com|bard\.google\.com|copilot\.microsoft\.com|"
            r"you\.com|phind\.com|deepseek\.com|chat\.mistral\.ai|grok\.com|meta\.ai)$"
        ),
    ),
    (
        "Classrooms & schools",
        re.compile(
            r"(^|\.)(classroom\.google\.com|teams\.microsoft\.com|teams\.live\.com|"
            r"instructure\.com|schoology\.com|padlet\.com|blackboard\.com|"
            r"itslearning\.com)$|moodle|\.edu$|\.edu\.[a-z]+$|\.ac\.[a-z]+$|\.sch\.uk$"
        ),
    ),
    (
        "Email",
        re.compile(
            r"(^|\.)mail\.|webmail|^com\.google\.android\.gm$|"
            r"outlook\.(live|office|office365)\.com$"
        ),
    ),
    (
        "Search engines",
        re.compile(
            r"(^|\.)(google|bing|duckduckgo|yahoo|yandex|ecosia|baidu|qwant|"
            r"startpage|naver|seznam|kagi|mojeek|sogou|aol|daum|ask)(\.[a-z]{2,3})+$|"
            r"(^|\.)search\.brave\.com$|googlequicksearchbox"
        ),
    ),
    (
        "Social & forums",
        re.compile(
            r"(^|\.)(reddit\.com|redd\.it|facebook\.com|fb\.com|instagram\.com|"
            r"t\.co|twitter\.com|x\.com|linkedin\.com|lnkd\.in|youtube\.com|"
            r"youtu\.be|tiktok\.com|threads\.net|discord\.com|discord\.gg|t\.me|"
            r"telegram\.org|whatsapp\.com|news\.ycombinator\.com|bsky\.app|"
            r"quora\.com|vk\.com|pinterest(\.[a-z]{2,3})+|mastodon(\.[a-z]+)+|"
            r"lemmy(\.[a-z]+)+|zalo\.me|line\.me|kakaotalk\.com|wechat\.com)$|"
            # Android apps report their package name.
            r"^(com\.reddit\.frontpage|com\.facebook\.(katana|orca|lite)|"
            r"com\.instagram\.android|com\.twitter\.android|com\.whatsapp|"
            r"org\.telegram\.messenger|com\.discord|com\.linkedin\.android|"
            r"com\.zing\.zalo|jp\.naver\.line\.android|com\.kakao\.talk)$"
        ),
    ),
]
# Referrer groups that are a trip out and back rather than a way in.
ROUND_TRIPS = {"This site", "Back from sign-in"}
# GoatCounter replaces some referrers with a generated name ("Email", "Google").
NAMED_REFERRERS = {
    "Search engines": {
        "google",
        "bing",
        "duckduckgo",
        "yahoo",
        "yandex",
        "ecosia",
        "baidu",
        "qwant",
        "startpage",
        "brave",
        "kagi",
    },
    "Email": {"email", "gmail", "outlook", "thunderbird", "yahoo mail"},
    "Social & forums": {
        "reddit",
        "facebook",
        "twitter",
        "x",
        "linkedin",
        "hacker news",
        "instagram",
        "youtube",
        "mastodon",
        "telegram",
        "whatsapp",
        "discord",
        "bluesky",
        "tiktok",
        "zalo",
        "line",
        "kakaotalk",
    },
    "AI assistants": {"chatgpt", "perplexity", "claude", "gemini", "copilot"},
}


def referrer_host(ref: str) -> str:
    parsed = urlparse(ref if "://" in ref else f"//{ref}")
    host = (parsed.hostname or ref).lower()
    return host.removeprefix("www.")


def referrer_source(ref: str, scheme: str) -> tuple[str, str]:
    """(group, label) for a hit's referrer and GoatCounter's referrer scheme."""
    ref = (ref or "").strip()
    if not ref:
        return DIRECT, "(none)"
    host = referrer_host(ref)
    for group, rule in REFERRER_RULES:
        if rule.search(host):
            return group, host
    if "." not in host:
        for group, names in NAMED_REFERRERS.items():
            if host in names:
                return group, ref
    if scheme == "c":
        return "Campaigns", ref
    if scheme == "g":
        return "Email" if "mail" in host else "Other websites", ref
    if scheme == "o":
        return "Apps & other", ref
    return "Other websites", host


MOBILE_SYSTEMS = ("android", "ios", "ipados")

# The aggregate API names a screen-size group only by its id; these are the
# labels GoatCounter's dashboard gives them.
SIZE_GROUPS = {
    "phone": "Phones",
    "largephone": "Large phones, small tablets",
    "tablet": "Tablets and small laptops",
    "desktop": "Computer monitors",
    "desktophd": "Monitors larger than HD",
    "unknown": "Unknown",
}


def device_class(size: str, system: str) -> str:
    """Phone / Tablet / Desktop from count.js's "width,height,scale" and the OS.

    The shorter screen side, so a phone held sideways is still a phone. A
    desktop OS is a desktop whatever its size (iPadOS Safari reports macOS, so
    iPads mostly land here).
    """
    try:
        w, h = (float(v) for v in size.split(",")[:2])
    except ValueError:
        w = h = 0.0
    short = min(w, h)
    mobile_os = system.lower().startswith(MOBILE_SYSTEMS)
    if short <= 0:
        return "Mobile (size unknown)" if mobile_os else "Unknown"
    if mobile_os or not system:
        return "Phone" if short < 600 else "Tablet"
    return "Desktop / laptop"


def without_version(name: str) -> str:
    """ "Chrome 131" -> "Chrome", "Windows 10" -> "Windows", "iOS 17.1" -> "iOS"."""
    return re.sub(r"\s+[\d.]+$", "", name.strip()) or "Unknown"


COUNTRY_NAMES = {
    "US": "United States",
    "GB": "United Kingdom",
    "DE": "Germany",
    "AT": "Austria",
    "CH": "Switzerland",
    "FR": "France",
    "ES": "Spain",
    "IT": "Italy",
    "NL": "Netherlands",
    "BE": "Belgium",
    "PT": "Portugal",
    "IE": "Ireland",
    "DK": "Denmark",
    "SE": "Sweden",
    "NO": "Norway",
    "FI": "Finland",
    "PL": "Poland",
    "CZ": "Czechia",
    "UA": "Ukraine",
    "TR": "Turkey",
    "RU": "Russia",
    "CA": "Canada",
    "MX": "Mexico",
    "BR": "Brazil",
    "AR": "Argentina",
    "CO": "Colombia",
    "CL": "Chile",
    "PE": "Peru",
    "IN": "India",
    "NP": "Nepal",
    "CN": "China",
    "JP": "Japan",
    "KR": "South Korea",
    "TW": "Taiwan",
    "HK": "Hong Kong",
    "SG": "Singapore",
    "AU": "Australia",
    "NZ": "New Zealand",
    "PH": "Philippines",
    "ID": "Indonesia",
    "VN": "Vietnam",
    "TH": "Thailand",
    "MY": "Malaysia",
    "PK": "Pakistan",
    "BD": "Bangladesh",
    "EG": "Egypt",
    "SA": "Saudi Arabia",
    "AE": "United Arab Emirates",
    "MA": "Morocco",
    "NG": "Nigeria",
    "ZA": "South Africa",
    "KE": "Kenya",
    "IL": "Israel",
    "GR": "Greece",
    "RO": "Romania",
    "HU": "Hungary",
}


def country_label(location: str) -> str:
    code = location.split("-")[0].strip().upper()
    if not code:
        return "Unknown"
    return COUNTRY_NAMES.get(code, code)


# ---------------------------------------------------------------------------
# GoatCounter API
# ---------------------------------------------------------------------------


class ApiError(Exception):
    def __init__(
        self, status: int | None, message: str, retry_after: float | None = None
    ):
        super().__init__(message)
        self.status = status
        # Seconds until a rate limit resets, when GoatCounter said so.
        self.retry_after = retry_after


def _error_text(payload: bytes) -> str:
    try:
        body = json.loads(payload)
    except ValueError:
        return payload.decode("utf-8", "replace").strip()[:300] or "(empty response)"
    if isinstance(body, dict):
        if body.get("error"):
            return str(body["error"])
        if body.get("errors"):
            return json.dumps(body["errors"])
    return str(body)[:300]


def _wait_in_text(text: str) -> float | None:
    """Seconds from a Go duration in an error ("try again in 59m20.15s")."""
    match = re.search(r"\bin (\d[\d.hms]*)", text)
    if not match:
        return None
    parts = re.findall(r"(\d+(?:\.\d+)?)([hms])", match.group(1))
    return sum(float(n) * {"h": 3600, "m": 60, "s": 1}[u] for n, u in parts) or None


class GoatCounter:
    def __init__(self, base_url: str, key: str):
        self.base_url = base_url.rstrip("/")
        self.key = key
        self._last_call = 0.0

    def call(
        self, method: str, path: str, *, params=None, body=None
    ) -> tuple[int, bytes]:
        url = self.base_url + path
        if params:
            url += "?" + urlencode(params, doseq=True)
        data = None if body is None else json.dumps(body).encode()
        headers = {
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "User-Agent": "goatcounter-report-script",
        }
        for attempt in range(6):
            wait = API_MIN_INTERVAL_S - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()
            request = Request(url, data=data, method=method, headers=headers)
            try:
                with urlopen(request, timeout=120) as response:
                    return response.status, response.read()
            except HTTPError as exc:
                payload = exc.read()
                reset = exc.headers.get("X-Rate-Limit-Reset", "")
                retry_in = float(reset) if reset.replace(".", "", 1).isdigit() else 1.0
                # A short reset is the per-second limit; a long one is the
                # hourly export limit, which isn't worth sleeping through.
                if exc.code == 429 and attempt < 5 and retry_in <= 10:
                    time.sleep(max(retry_in, 0.5))
                    continue
                text = _error_text(payload)
                raise ApiError(
                    exc.code,
                    text,
                    (retry_in if reset else _wait_in_text(text))
                    if exc.code == 429
                    else None,
                ) from None
            except URLError as exc:
                raise ApiError(
                    None, f"couldn't reach {self.base_url}: {exc.reason}"
                ) from None
        raise ApiError(429, "rate limited")

    def json(self, method: str, path: str, **kwargs) -> tuple[int, dict]:
        status, payload = self.call(method, path, **kwargs)
        try:
            return status, json.loads(payload or b"{}")
        except ValueError:
            raise ApiError(status, f"{path} didn't return JSON") from None


# ---------------------------------------------------------------------------
# The CSV export, cached and grown incrementally
# ---------------------------------------------------------------------------


@dataclass
class ExportCache:
    directory: Path

    @property
    def csv_path(self) -> Path:
        return self.directory / "hits.csv"

    @property
    def state_path(self) -> Path:
        return self.directory / "state.json"

    def state(self) -> dict:
        try:
            return json.loads(self.state_path.read_text())
        except (OSError, ValueError):
            return {}

    def save_state(self, state: dict) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2) + "\n")
        os.replace(tmp, self.state_path)

    def has_data(self) -> bool:
        return self.csv_path.exists() and self.csv_path.stat().st_size > 0

    def append(self, export_text: str) -> int:
        """Add an export's rows to the cache; returns the number of rows added."""
        new_rows = list(csv.reader(io.StringIO(export_text)))
        new_rows = [r for r in new_rows if r]
        if not new_rows:
            return 0
        header, rows = new_rows[0], new_rows[1:]
        existing = ""
        if self.has_data():
            existing = self.csv_path.read_text(encoding="utf-8")
            old_header = next(csv.reader(io.StringIO(existing)), None)
            if old_header and old_header != header:
                raise SystemExit(
                    f"The export's columns changed ({old_header[:3]}… → {header[:3]}…). "
                    f"Move {self.csv_path} aside and run again to start a fresh cache."
                )
        out = io.StringIO()
        writer = csv.writer(out, lineterminator="\n")
        if not existing:
            writer.writerow(header)
        writer.writerows(rows)
        self.directory.mkdir(parents=True, exist_ok=True)
        tmp = self.csv_path.with_suffix(".tmp")
        tmp.write_text(existing + out.getvalue(), encoding="utf-8")
        os.replace(tmp, self.csv_path)
        return len(rows)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def sync_export(gc: GoatCounter, cache: ExportCache, log) -> str | None:
    """Fetch the hits GoatCounter has recorded since the last export.

    Returns why there is nothing to use (the hourly limit, or an empty
    export), as a sentence for the report's notes.
    """
    state = cache.state()
    # Every POST counts against GoatCounter's hourly limit, a failed one too,
    # and asking again while blocked seems to restart the hour. So no request
    # goes out until the later of an hour after the last attempt and whatever
    # reset GoatCounter last gave.
    allowed_at = None
    if state.get("last_export_at"):
        allowed_at = datetime.fromisoformat(state["last_export_at"]) + EXPORT_COOLDOWN
    if state.get("export_blocked_until"):
        blocked = datetime.fromisoformat(state["export_blocked_until"])
        allowed_at = max(allowed_at, blocked) if allowed_at else blocked
    if allowed_at and _utcnow() < allowed_at:
        minutes = int((allowed_at - _utcnow()).total_seconds() // 60) + 1
        wait = (
            f"GoatCounter allows one export an hour "
            f"(next in ~{minutes} min, at {allowed_at.astimezone():%H:%M})"
        )
        if cache.has_data():
            log(f"Using the cached export: {wait}.")
        return f"No CSV export yet: {wait}"

    # GoatCounter added a JSON export in 2026; the CSV one now has to be asked
    # for by name.
    body = {"format": "csv"}
    if state.get("last_hit_id"):
        body["start_from_hit_id"] = int(state["last_hit_id"])
    log(
        "Starting a GoatCounter export"
        + (
            f" from hit #{body['start_from_hit_id']:,}…"
            if "start_from_hit_id" in body
            else " of all hits…"
        )
    )
    state["last_export_at"] = _utcnow().isoformat()
    state.pop("export_blocked_until", None)
    cache.save_state(state)
    try:
        _, export = gc.json("POST", "/export", body=body)
    except ApiError as exc:
        if exc.status == 429 and exc.retry_after:
            until = _utcnow() + timedelta(seconds=exc.retry_after)
            state["export_blocked_until"] = until.isoformat()
            cache.save_state(state)
        raise
    export_id = export.get("id")
    if export_id is None:
        raise ApiError(None, f"the export response had no id: {export}")

    deadline = time.monotonic() + EXPORT_TIMEOUT_S
    while not export.get("finished_at"):
        if export.get("error"):
            break
        if time.monotonic() > deadline:
            raise ApiError(
                None, f"export {export_id} didn't finish in {EXPORT_TIMEOUT_S}s"
            )
        time.sleep(2)
        _, export = gc.json("GET", f"/export/{export_id}")
    if export.get("error"):
        raise ApiError(None, f"export failed: {export['error']}")

    added = 0
    if int(export.get("num_rows") or 0) > 0:
        for _ in range(30):
            status, payload = gc.call("GET", f"/export/{export_id}/download")
            if status != 202:
                break
            time.sleep(2)
        else:
            raise ApiError(202, f"export {export_id} never became downloadable")
        if payload[:2] == b"\x1f\x8b":
            payload = gzip.decompress(payload)
        added = cache.append(payload.decode("utf-8-sig"))
    last_hit = int(export.get("last_hit_id") or 0)
    if last_hit > int(state.get("last_hit_id") or 0):
        state["last_hit_id"] = last_hit
    state["synced_at"] = _utcnow().isoformat()
    cache.save_state(state)
    log(f"Export {export_id}: {added:,} new hits.")
    if not cache.has_data():
        # The export reads GoatCounter's stored pageviews, which it keeps only
        # with this setting on (off by default); the totals don't need them.
        return (
            "GoatCounter's export is empty: the site isn't storing individual "
            "pageviews. Turn on Settings → Data collection → Individual "
            "pageviews; exports include pageviews from then on"
        )
    return None


# ---------------------------------------------------------------------------
# Hits and sessions
# ---------------------------------------------------------------------------


@dataclass
class Hit:
    path: str
    page: Page
    when: datetime  # in the report's time zone
    session: str
    referrer: str
    ref_scheme: str
    browser: str
    system: str
    size: str
    location: str


def _truthy(value: str) -> bool:
    return value.strip().lower() in ("true", "t", "1", "yes")


def _parse_when(value: str) -> datetime:
    when = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def read_hits(path: Path, languages: dict[str, str], tz) -> tuple[list[Hit], Counter]:
    """Every pageview in the cached export, plus a count of what was skipped."""
    skipped: Counter[str] = Counter()
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        if not header:
            return [], skipped
        version = re.match(r"\d*", header[0]).group()
        drop_first = False
        if header[0].isdigit():  # "2,Path,…" rather than "2Path,…"
            header, drop_first = header[1:], True
        else:
            header = [header[0][len(version) :], *header[1:]]
        if version != EXPORT_VERSION:
            raise SystemExit(
                f"{path} is export format {version or '?'}; this script reads "
                f"version {EXPORT_VERSION}. Move it aside to start a fresh cache."
            )
        missing = [c for c in REQUIRED_COLUMNS if c not in header]
        if missing:
            raise SystemExit(f"{path} lacks the columns {missing}; header is {header}")
        col = {name: header.index(name) for name in REQUIRED_COLUMNS}

        hits = []
        for row in reader:
            if not row:
                continue
            if drop_first:
                row = row[1:]
            if len(row) < len(header):
                skipped["malformed rows"] += 1
                continue
            if row[col["Bot"]].strip() not in ("", "0"):
                skipped["bots"] += 1
                continue
            if _truthy(row[col["Event"]]):
                skipped["events"] += 1
                continue
            try:
                when = _parse_when(row[col["Date"]]).astimezone(tz)
            except ValueError:
                skipped["malformed rows"] += 1
                continue
            path_value = row[col["Path"]] or "/"
            hits.append(
                Hit(
                    path=path_value,
                    page=classify(path_value, languages),
                    when=when,
                    session=row[col["Session"]].strip(),
                    referrer=row[col["Referrer"]],
                    ref_scheme=row[col["Referrer scheme"]].strip(),
                    browser=row[col["Browser"]],
                    system=row[col["System"]],
                    size=row[col["Screen size"]],
                    location=row[col["Location"]],
                )
            )
    hits.sort(key=lambda h: h.when)
    return hits, skipped


@dataclass
class Session:
    id: str
    hits: list[Hit]

    @property
    def entry(self) -> Hit:
        return self.hits[0]

    @property
    def sections(self) -> set[str]:
        return {h.page.section for h in self.hits}

    @property
    def languages(self) -> set[str]:
        return {h.page.lang for h in self.hits if h.page.lang}

    def steps(self) -> list[str]:
        """Sections in visiting order, repeats in a row collapsed."""
        out: list[str] = []
        for hit in self.hits:
            if not out or out[-1] != hit.page.section:
                out.append(hit.page.section)
        return out


def build_sessions(hits: list[Hit]) -> list[Session]:
    grouped: dict[str, list[Hit]] = defaultdict(list)
    for i, hit in enumerate(hits):
        # A hit without a session ID can't be joined to anything: its own visit.
        grouped[hit.session or f"_nosession_{i}"].append(hit)
    sessions = [
        Session(sid, sorted(hs, key=lambda h: h.when)) for sid, hs in grouped.items()
    ]
    sessions.sort(key=lambda s: s.entry.when)
    return sessions


# ---------------------------------------------------------------------------
# The dataset both sources reduce to
# ---------------------------------------------------------------------------


@dataclass
class Dataset:
    source: str  # "export" | "api"
    unit: str  # what the counts count: "sessions" | "visits"
    start: date
    end: date
    tz_name: str
    daily: list[tuple[date, int, int | None]]  # day, sessions/visits, pageviews
    views: Counter  # path -> unique visits (GoatCounter's own count)
    pageviews: Counter | None  # path -> raw page loads (export only)
    referrers: Counter  # (group, label) -> sessions/visits
    browsers: Counter
    systems: Counter
    countries: Counter
    devices: Counter
    sessions: list[Session] | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        if self.sessions is not None:
            return len(self.sessions)
        return sum(v for _, v, _ in self.daily)


def dataset_from_hits(hits, skipped, start, end, tz_name, notes) -> Dataset:
    hits = [h for h in hits if start <= h.when.date() <= end]
    sessions = build_sessions(hits)
    if hits:
        start = max(start, hits[0].when.date())
        end = min(end, hits[-1].when.date())

    per_day_sessions = Counter(s.entry.when.date() for s in sessions)
    per_day_views = Counter(h.when.date() for h in hits)
    days = [start + timedelta(n) for n in range((end - start).days + 1)] if hits else []
    daily = [(d, per_day_sessions[d], per_day_views[d]) for d in days]

    views: Counter[str] = Counter()
    for s in sessions:
        for path in {h.path for h in s.hits}:
            views[path] += 1
    pageviews = Counter(h.path for h in hits)

    referrers: Counter = Counter()
    browsers: Counter = Counter()
    systems: Counter = Counter()
    countries: Counter = Counter()
    devices: Counter = Counter()
    for s in sessions:
        e = s.entry
        referrers[referrer_source(e.referrer, e.ref_scheme)] += 1
        browsers[without_version(e.browser)] += 1
        systems[without_version(e.system)] += 1
        countries[country_label(e.location)] += 1
        devices[device_class(e.size, e.system)] += 1

    no_session = sum(1 for s in sessions if s.id.startswith("_nosession_"))
    if sessions and no_session / len(sessions) > 0.2:
        notes.append(
            f"{no_session:,} hits carry no session ID (GoatCounter's session "
            "tracking may be off), so each counts as its own visit and journeys "
            "are shorter than they really are."
        )
    if skipped:
        notes.append(
            "Left out: "
            + ", ".join(f"{n:,} {what}" for what, n in skipped.items())
            + "."
        )
    return Dataset(
        source="export",
        unit="sessions",
        start=start,
        end=end,
        tz_name=tz_name,
        daily=daily,
        views=views,
        pageviews=pageviews,
        referrers=referrers,
        browsers=browsers,
        systems=systems,
        countries=countries,
        devices=devices,
        sessions=sessions,
        notes=notes,
    )


def _api_window(start: date, end: date) -> dict:
    # GoatCounter wants hour-rounded RFC 3339 times; end is exclusive.
    return {
        "start": f"{start.isoformat()}T00:00:00Z",
        "end": f"{(end + timedelta(1)).isoformat()}T00:00:00Z",
    }


def _api_stat_page(gc: GoatCounter, page: str, window: dict) -> list[dict]:
    out, offset = [], 0
    while True:
        _, body = gc.json(
            "GET", f"/stats/{page}", params={**window, "limit": 100, "offset": offset}
        )
        batch = body.get("stats") or []
        out.extend(batch)
        if not body.get("more") or not batch:
            return out
        offset += len(batch)


def dataset_from_api(
    gc, start, end, tz_name, notes, log, *, trim_leading=False
) -> Dataset:
    window = _api_window(start, end)
    log("Reading aggregate stats from the GoatCounter API…")
    _, total = gc.json("GET", "/stats/total", params=window)
    daily = []
    for stat in total.get("stats") or []:
        try:
            daily.append(
                (
                    date.fromisoformat(stat["day"][:10]),
                    int(stat.get("daily") or 0),
                    None,
                )
            )
        except (KeyError, ValueError):
            continue
    daily.sort()

    views: Counter[str] = Counter()
    seen: list[int] = []
    while True:
        params = {**window, "limit": 100}
        if seen:
            params["exclude_paths"] = seen
        _, body = gc.json("GET", "/stats/hits", params=params)
        fresh = [h for h in body.get("hits") or [] if h.get("path_id") not in seen]
        for hit in fresh:
            seen.append(hit.get("path_id"))
            if not hit.get("event"):
                views[hit.get("path") or "/"] += int(hit.get("count") or 0)
        if not body.get("more") or not fresh:
            break

    def counter(page: str, label=lambda s: s.get("name") or "Unknown") -> Counter:
        # Summed, not assigned: two rows can share a label (both unnamed).
        out: Counter[str] = Counter()
        for s in _api_stat_page(gc, page, window):
            out[label(s)] += int(s.get("count") or 0)
        return +out

    # Only referred visits: GoatCounter counts every page a visitor opens and
    # only the first carries a referrer, so "no referrer" here would lump
    # direct arrivals in with every click inside the site.
    referrers: Counter = Counter()
    for stat in _api_stat_page(gc, "toprefs", window):
        name = (stat.get("name") or "").strip()
        if name and name.lower() not in ("(no data)", "(unknown)"):
            source = referrer_source(name, stat.get("ref_scheme") or "")
            referrers[source] += int(stat.get("count") or 0)

    notes.append(
        "From GoatCounter's aggregate API: counts are visits (GoatCounter's "
        "visitor count), and the session-based parts (entry pages, funnel, "
        "journeys) need the CSV export."
    )
    if trim_leading:
        # "Everything" asks for a fixed span back; start where the data does,
        # or the per-day average counts days before the site existed.
        while daily and not daily[0][1]:
            daily.pop(0)
        if daily:
            start = daily[0][0]
    return Dataset(
        source="api",
        unit="visits",
        start=start,
        end=end,
        tz_name=tz_name,
        daily=daily,
        views=views,
        pageviews=None,
        referrers=referrers,
        browsers=counter("browsers"),
        systems=counter("systems"),
        countries=counter("locations"),
        devices=counter(
            "sizes",
            lambda s: SIZE_GROUPS.get(s.get("id") or "", s.get("name") or "Unknown"),
        ),
        sessions=None,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Breakdowns
# ---------------------------------------------------------------------------


def share(part: int, whole: int) -> float:
    return part / whole if whole else 0.0


def pct(value: float) -> str:
    if value == 0:
        return "0%"
    if value < 0.01:
        return "<1%"
    return f"{value:.0%}" if value >= 0.1 else f"{value:.1%}"


def per_section(ds: Dataset) -> Counter:
    """Export: sessions that touched each section. API: visits per section."""
    if ds.sessions is not None:
        return Counter(sec for s in ds.sessions for sec in s.sections)
    out: Counter[str] = Counter()
    for path, n in ds.views.items():
        out[classify(path, LANGUAGES).section] += n
    return out


def referrer_groups(ds: Dataset) -> Counter:
    out: Counter[str] = Counter()
    for (group, _), n in ds.referrers.items():
        out[group] += n
    return out


@dataclass
class LanguageRow:
    code: str
    total: int
    read: int
    drilled: int
    finished: int
    verbs: int


def per_language(ds: Dataset) -> list[LanguageRow]:
    rows: dict[str, LanguageRow] = {}

    def row(code):
        return rows.setdefault(code, LanguageRow(code, 0, 0, 0, 0, 0))

    if ds.sessions is not None:
        for s in ds.sessions:
            for code in s.languages:
                secs = {h.page.section for h in s.hits if h.page.lang == code}
                r = row(code)
                r.total += 1
                r.read += bool(secs & READ_SECTIONS)
                r.drilled += bool(secs & NUMBER_PRACTICE_SECTIONS)
                r.finished += "drill_results" in secs
                r.verbs += bool(
                    secs
                    & {
                        "verbs",
                        "verb_drill",
                        "verb_results",
                        "learn_verbs",
                        "cheat_sheet",
                    }
                )
    else:
        for path, n in ds.views.items():
            page = classify(path, LANGUAGES)
            if not page.lang:
                continue
            r = row(page.lang)
            r.total += n
            r.read += n if page.section in READ_SECTIONS else 0
            r.drilled += n if page.section in NUMBER_PRACTICE_SECTIONS else 0
            r.finished += n if page.section == "drill_results" else 0
            r.verbs += (
                n
                if page.section
                in {"verbs", "verb_drill", "verb_results", "learn_verbs", "cheat_sheet"}
                else 0
            )
    return sorted(rows.values(), key=lambda r: -r.total)


def per_mode(ds: Dataset) -> Counter:
    out: Counter[str] = Counter()
    if ds.sessions is not None:
        for s in ds.sessions:
            for mode in {h.page.mode for h in s.hits if h.page.mode}:
                out[mode] += 1
    else:
        for path, n in ds.views.items():
            mode = classify(path, LANGUAGES).mode
            if mode:
                out[mode] += n
    return out


# UI languages that aren't also taught on the site, so LANGUAGES lacks them.
UI_LANGUAGE_NAMES = {"ar": "Arabic", "uk": "Ukrainian"}


def per_hl(ds: Dataset) -> Counter:
    out: Counter[str] = Counter()
    for path, n in ds.views.items():
        hl = classify(path, LANGUAGES).hl
        if hl:
            name = UI_LANGUAGE_NAMES.get(hl) or LANGUAGES.get(hl) or hl
            out[f"{name} ({hl})"] += n
    return out


def funnel(sessions: list[Session]) -> list[tuple[str, int]]:
    stages = [
        ("All sessions", lambda s: True),
        ("Viewed any language's pages", lambda s: bool(s.languages)),
        (
            "Opened number practice",
            lambda s: bool(s.sections & NUMBER_PRACTICE_SECTIONS),
        ),
        (
            "Reached a drill question page",
            lambda s: bool(s.sections & NUMBER_DRILL_SECTIONS),
        ),
        ("Finished a drill (results page)", lambda s: "drill_results" in s.sections),
    ]
    return [(label, sum(1 for s in sessions if test(s))) for label, test in stages]


def depth_buckets(sessions: list[Session]) -> list[tuple[str, int]]:
    bands = [
        ("1 page", 1, 1),
        ("2", 2, 2),
        ("3", 3, 3),
        ("4-5", 4, 5),
        ("6-10", 6, 10),
        ("11-20", 11, 20),
        ("21+", 21, 10**9),
    ]
    counts = Counter()
    for s in sessions:
        n = len(s.hits)
        for label, lo, hi in bands:
            if lo <= n <= hi:
                counts[label] += 1
                break
    return [(label, counts[label]) for label, _, _ in bands]


def journeys(sessions: list[Session], limit=15, max_steps=5) -> list[tuple[str, int]]:
    counts: Counter[str] = Counter()
    for s in sessions:
        steps = [section_label(k) for k in s.steps()]
        text = " → ".join(steps[:max_steps]) + (
            " → …" if len(steps) > max_steps else ""
        )
        counts[text] += 1
    return counts.most_common(limit)


def next_steps(
    sessions: list[Session], entries=6, per_entry=6
) -> list[tuple[str, int, list[tuple[str, int]]]]:
    by_entry: dict[str, Counter] = defaultdict(Counter)
    for s in sessions:
        steps = s.steps()
        by_entry[steps[0]][
            section_label(steps[1]) if len(steps) > 1 else "Left the site"
        ] += 1
    ranked = sorted(by_entry.items(), key=lambda kv: -sum(kv[1].values()))[:entries]
    return [
        (section_label(k), sum(c.values()), c.most_common(per_entry)) for k, c in ranked
    ]


def heat(sessions: list[Session]) -> list[list[int]]:
    grid = [[0] * 24 for _ in range(7)]
    for s in sessions:
        grid[s.entry.when.weekday()][s.entry.when.hour] += 1
    return grid


def findings(ds: Dataset) -> list[str]:
    """The headline facts, as plain sentences (terminal and report)."""
    out = []
    total = ds.total
    if not total:
        return ["No pageviews in this window."]
    days = max((ds.end - ds.start).days + 1, 1)
    u = ds.unit
    if ds.sessions is not None:
        pv = sum(ds.pageviews.values())
        out.append(
            f"{total:,} {u} and {pv:,} pageviews from {ds.start:%d %b %Y} to "
            f"{ds.end:%d %b %Y}, about {total / days:,.1f} {u} a day."
        )
    else:
        out.append(
            f"{total:,} {u} from {ds.start:%d %b %Y} to {ds.end:%d %b %Y}, "
            f"about {total / days:,.1f} a day."
        )

    # Coming back from a login or another page here is no way of finding
    # the site; the chart shows them, the headline is about sources.
    groups = Counter(
        {g: n for g, n in referrer_groups(ds).items() if g not in ROUND_TRIPS}
    )
    ref_total = sum(groups.values())
    top = [
        f"{g if g[:2].isupper() else g.lower()} {pct(share(n, ref_total))}"
        for g, n in groups.most_common(3)
    ]
    who = u if ds.sessions is not None else "referred visits"
    out.append(f"Where {who} come from: " + ", ".join(top) + ".")

    if ds.sessions is not None:
        s = ds.sessions
        entries = Counter(x.entry.page.section for x in s)
        out.append(
            "Where they land: "
            + ", ".join(
                f"{section_label(k)} {pct(share(n, total))}"
                for k, n in entries.most_common(3)
            )
            + "."
        )
        one_page = sum(1 for x in s if len(x.hits) == 1)
        med = statistics.median(len(x.hits) for x in s)
        out.append(
            f"{pct(share(one_page, total))} of sessions view one page and leave; "
            f"the median session loads {med:g} page{'' if med == 1 else 's'}."
        )
        drilled = sum(1 for x in s if x.sections & DRILL_SECTIONS)
        finished = sum(1 for x in s if x.sections & FINISHED_SECTIONS)
        read_only = sum(
            1
            for x in s
            if x.sections & READ_SECTIONS and not x.sections & DRILL_SECTIONS
        )
        out.append(
            f"{pct(share(drilled, total))} of sessions reach a drill (numbers, listening, "
            f"verbs or cards) and {pct(share(finished, total))} finish one; "
            f"{pct(share(read_only, total))} read a Learn or reference page without drilling."
        )

    langs = per_language(ds)
    if langs:
        out.append(
            "Most visited languages: "
            + ", ".join(
                f"{LANGUAGES.get(r.code, r.code)} {pct(share(r.total, total))}"
                for r in langs[:4]
            )
            + "."
        )
    modes = per_mode(ds)
    if modes:
        out.append(
            "Drill modes used: "
            + ", ".join(
                f"{m} {n:,}" for m, n in sorted(modes.items(), key=lambda kv: -kv[1])
            )
            + f" {u}."
        )

    sections = per_section(ds)
    extras = [
        (label, sections.get(key, 0))
        for key, label in (
            ("challenge", "friend challenges"),
            ("worksheet", "worksheets"),
            ("cards", "index cards"),
            ("verbs", "the verb list"),
        )
    ]
    out.append(
        "Smaller features: "
        + ", ".join(f"{label} {pct(share(n, total))}" for label, n in extras)
        + f" of {u}."
    )

    if ds.sessions is not None:
        phones = ds.devices.get("Phone", 0)
        out.append(f"{pct(share(phones, total))} of sessions are on a phone.")
    return out


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

esc = html.escape


def bar_list(
    rows: list[tuple[str, int]],
    total: int | None,
    unit: str,
    *,
    limit: int = 12,
    sort: bool = True,
    value_text=None,
    tip=None,
    reserve: str = "6.5rem",
) -> str:
    """Ranked horizontal bars, value at each bar's tip; a long tail folds into Other."""
    rows = [(label, n) for label, n in rows]
    if sort:
        rows.sort(key=lambda r: -r[1])
    if len(rows) > limit:
        rest = rows[limit - 1 :]
        rows = rows[: limit - 1] + [
            (f"All others ({len(rest)})", sum(n for _, n in rest))
        ]
    if not rows:
        return '<p class="empty">No data in this window.</p>'
    top = max(n for _, n in rows) or 1
    out = [f'<div class="bars" style="--reserve:{reserve}">']
    for i, (label, n) in enumerate(rows):
        frac = n / top
        text = (
            value_text(i, label, n)
            if value_text
            else (f"{n:,}" + (f" · {pct(share(n, total))}" if total else ""))
        )
        tip_value = (
            tip(i, label, n)
            if tip
            else f"{n:,} {unit}" + (f" ({pct(share(n, total))})" if total else "")
        )
        out.append(
            f'<div class="bar-row" tabindex="0" data-tip-value="{esc(tip_value)}" '
            f'data-tip-label="{esc(label)}"><span class="bar-label">{esc(label)}</span>'
            f'<span class="bar-track"><span class="bar{" zero" if n == 0 else ""}" '
            f'style="--f:{frac:.4f}"></span><span class="bar-value">{esc(text)}</span>'
            f"</span></div>"
        )
    out.append("</div>")
    return "".join(out)


def table(headers: list[str], rows: list[list], numeric: set[int] = frozenset()) -> str:
    head = "".join(
        f"<th{' class=num' if i in numeric else ''}>{esc(h)}</th>"
        for i, h in enumerate(headers)
    )
    body = []
    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            if isinstance(cell, Markup):
                content = str(cell)
            elif isinstance(cell, int):
                content = f"{cell:,}"
            else:
                content = esc(str(cell))
            cells.append(f"<td{' class=num' if i in numeric else ''}>{content}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return (
        f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead>'
        f"<tbody>{''.join(body)}</tbody></table></div>"
    )


class Markup(str):
    """Already-escaped HTML for a table cell."""


def meter(value: int, top: int, text: str) -> Markup:
    frac = value / top if top else 0
    return Markup(
        f'<span class="meter-cell"><span class="meter"><span style="--f:{frac:.4f}">'
        f"</span></span><span>{esc(text)}</span></span>"
    )


def card(
    title: str, body: str, *, sub: str = "", table_html: str = "", wide=False
) -> str:
    details = (
        f'<details class="table-view"><summary>Show as table</summary>{table_html}</details>'
        if table_html
        else ""
    )
    return (
        f'<section class="card{" wide" if wide else ""}"><h3>{esc(title)}</h3>'
        + (f'<p class="sub">{esc(sub)}</p>' if sub else "")
        + body
        + details
        + "</section>"
    )


def kpi_row(tiles: list[tuple[str, str, str]]) -> str:
    return (
        '<div class="kpis">'
        + "".join(
            f'<div class="kpi"><div class="kpi-label">{esc(label)}</div>'
            f'<div class="kpi-value">{esc(value)}</div>'
            + (f'<div class="kpi-note">{esc(note)}</div>' if note else "")
            + "</div>"
            for label, value, note in tiles
        )
        + "</div>"
    )


def timeseries(ds: Dataset) -> str:
    data = [
        {"d": d.isoformat(), "v": v, **({"p": p} if p is not None else {})}
        for d, v, p in ds.daily
    ]
    blob = json.dumps(data).replace("</", "<\\/")
    rows = [
        [d.strftime("%a %d %b %Y"), v] + ([p] if p is not None else [])
        for d, v, p in ds.daily
    ]
    headers = ["Day", ds.unit.capitalize()] + (
        ["Pageviews"] if ds.pageviews is not None else []
    )
    body = (
        f'<script type="application/json" id="daily-data">{blob}</script>'
        f'<div class="ts" data-src="daily-data" data-unit="{esc(ds.unit)}" '
        f'role="img" aria-label="{esc(ds.unit.capitalize())} per day"></div>'
    )
    return card(
        f"{ds.unit.capitalize()} per day",
        body,
        sub=f"Days in {ds.tz_name}."
        + (" Pageviews in the tooltip." if ds.pageviews is not None else ""),
        table_html=table(headers, rows, {1, 2}),
        wide=True,
    )


def heatmap(grid: list[list[int]], tz_name: str) -> str:
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    top = max(max(r) for r in grid) or 1
    cells = ["<span></span>"] + [
        f'<span class="heat-hour">{h:02d}</span>' if h % 3 == 0 else "<span></span>"
        for h in range(24)
    ]
    for d, row in enumerate(grid):
        cells.append(f'<span class="heat-day">{days[d]}</span>')
        for h, n in enumerate(row):
            step = math.ceil(5 * n / top) if n else 0
            cells.append(
                f'<span class="cell s{step}" data-tip-value="{n:,} sessions" '
                f'data-tip-label="{days[d]} {h:02d}:00–{h:02d}:59"></span>'
            )
    legend = (
        '<div class="heat-legend"><span>fewer</span>'
        + "".join(f'<span class="cell s{i}"></span>' for i in range(1, 6))
        + "<span>more</span></div>"
    )
    rows = [[days[d]] + row + [sum(row)] for d, row in enumerate(grid)]
    rows.append(
        ["All"]
        + [sum(grid[d][h] for d in range(7)) for h in range(24)]
        + [sum(map(sum, grid))]
    )
    tbl = table(
        ["Day"] + [f"{h:02d}" for h in range(24)] + ["Total"], rows, set(range(1, 26))
    )
    return card(
        "When sessions start",
        f'<div class="heat">{"".join(cells)}</div>{legend}',
        sub=f"Weekday × hour, {tz_name}. Visitors are worldwide, so this is "
        "the site's clock, not theirs.",
        table_html=tbl,
        wide=True,
    )


def render_report(ds: Dataset, generated: datetime) -> str:
    u, total = ds.unit, ds.total
    lines = findings(ds)
    parts: list[str] = []

    # KPI row
    if ds.sessions is not None:
        s = ds.sessions
        tiles = [
            ("Sessions", f"{total:,}", f"{ds.start:%d %b} – {ds.end:%d %b %Y}"),
            ("Pageviews", f"{sum(ds.pageviews.values()):,}", "every page load"),
            (
                "One-page sessions",
                pct(share(sum(1 for x in s if len(x.hits) == 1), total)),
                "landed and left",
            ),
            (
                "Reached a drill",
                pct(share(sum(1 for x in s if x.sections & DRILL_SECTIONS), total)),
                "numbers, listening, verbs, cards",
            ),
            (
                "Finished a drill",
                pct(share(sum(1 for x in s if x.sections & FINISHED_SECTIONS), total)),
                "reached a results page",
            ),
        ]
    else:
        langs = per_language(ds)
        tiles = [
            ("Visits", f"{total:,}", f"{ds.start:%d %b} – {ds.end:%d %b %Y}"),
            (
                "Visits a day",
                f"{total / max((ds.end - ds.start).days + 1, 1):,.1f}",
                "",
            ),
            ("Pages with visits", f"{len(ds.views):,}", "distinct paths"),
            (
                "Top language",
                LANGUAGES.get(langs[0].code, langs[0].code) if langs else "–",
                "",
            ),
        ]
    parts.append(kpi_row(tiles))
    parts.append(
        '<section class="card wide findings"><h3>Key findings</h3><ul>'
        + "".join(f"<li>{esc(line)}</li>" for line in lines)
        + "</ul></section>"
    )

    # Over time
    parts.append('<h2>Over time</h2><div class="grid">')
    parts.append(timeseries(ds))
    if ds.sessions is not None:
        parts.append(heatmap(heat(ds.sessions), ds.tz_name))
    parts.append("</div>")

    # Acquisition
    groups = referrer_groups(ds)
    ref_total = sum(groups.values())
    parts.append('<h2>How people arrive</h2><div class="grid">')
    if ds.sessions is not None:
        parts.append(
            card(
                "Where sessions come from",
                bar_list(list(groups.items()), ref_total, u),
                sub="The referrer of each session's first page.",
            )
        )
    else:
        parts.append(
            card(
                "Where referred visits come from",
                bar_list(list(groups.items()), ref_total, u),
                sub="Visits that carried a referrer. Direct arrivals can't be told "
                "apart from clicks within the site here; the CSV export can.",
            )
        )
    top_refs = [
        (label, g, n) for (g, label), n in ds.referrers.most_common() if g != DIRECT
    ][:30]
    parts.append(
        card(
            "Top referrers",
            table(
                ["Referrer", "Kind", u.capitalize()],
                [
                    [label, Markup(f'<span class="nowrap">{esc(g)}</span>'), n]
                    for label, g, n in top_refs
                ],
                {2},
            )
            if top_refs
            else '<p class="empty">No referrers in this window.</p>',
        )
    )
    if ds.sessions is not None:
        entries = Counter(x.entry.page.section for x in ds.sessions)
        parts.append(
            card(
                "Where sessions land",
                bar_list([(section_label(k), n) for k, n in entries.items()], total, u),
                sub="The first page of each session.",
            )
        )
        entry_paths = Counter(x.entry.path for x in ds.sessions).most_common(15)
        parts.append(
            card(
                "Top landing pages",
                table(
                    ["Path", "Section", "Sessions"],
                    [
                        [p, section_label(classify(p, LANGUAGES).section), n]
                        for p, n in entry_paths
                    ],
                    {2},
                ),
            )
        )
    parts.append("</div>")

    # What they do
    sections = per_section(ds)
    parts.append('<h2>What people do</h2><div class="grid">')
    parts.append(
        card(
            "Sections used",
            bar_list(
                [(section_label(k), n) for k, n in sections.items()], total, u, limit=20
            ),
            sub=(
                "Share of sessions that opened each part of the site at least once; "
                "a session can count in several."
            )
            if ds.sessions is not None
            else "Visits per part of the site.",
        )
    )
    if ds.sessions is not None:
        stages = funnel(ds.sessions)

        def funnel_text(i, label, n):
            prev = stages[i - 1][1] if i else n
            return f"{n:,} · {pct(share(n, total))}" + (
                f" · {pct(share(n, prev))} of previous" if i else ""
            )

        parts.append(
            card(
                "Number-drill funnel",
                bar_list(
                    stages,
                    total,
                    u,
                    sort=False,
                    value_text=funnel_text,
                    tip=lambda i, label, n: funnel_text(i, label, n),
                    reserve="13rem",
                ),
                sub="Sessions that got at least this far. A drill's results "
                "page appears after its tenth question.",
            )
        )
        parts.append(
            card(
                "Pages per session",
                bar_list(depth_buckets(ds.sessions), total, u, sort=False),
                sub="Page loads per session. Every answered drill question "
                "reloads the page, so drilling sessions sit on the right.",
            )
        )
    modes = per_mode(ds)
    parts.append(
        card(
            "Drill modes",
            bar_list([(m, modes.get(m, 0)) for m in DRILL_MODES], None, u, sort=False),
            sub=f"{u.capitalize()} that reached a number-drill page in each mode.",
        )
    )
    parts.append("</div>")

    # Journeys
    if ds.sessions is not None:
        parts.append('<h2>Journeys</h2><div class="grid">')
        top_j = journeys(ds.sessions)
        jmax = max((n for _, n in top_j), default=1)
        parts.append(
            card(
                "Most common journeys",
                table(
                    ["Journey (sections in order)", "Sessions"],
                    [
                        [j, meter(n, jmax, f"{n:,} · {pct(share(n, total))}")]
                        for j, n in top_j
                    ],
                    {1},
                ),
                sub="Each session's sections in the order visited, repeats collapsed, "
                "first five steps.",
                wide=True,
            )
        )
        for entry, n_entry, nexts in next_steps(ds.sessions):
            parts.append(
                card(
                    f"After landing on {entry}",
                    bar_list(nexts, n_entry, u, sort=False),
                    sub=f"{n_entry:,} sessions. Their next section.",
                )
            )
        parts.append("</div>")

    # Languages
    langs = per_language(ds)
    parts.append('<h2>Languages</h2><div class="grid">')
    if langs:
        top_l = langs[0].total
        what = "sessions that" if ds.sessions is not None else "visits that"
        headers = [
            "Language",
            u.capitalize(),
            "Read / learn",
            "Number practice",
            "Finished drill",
            "Verbs",
        ]
        rows = [
            [
                LANGUAGES.get(r.code, r.code),
                meter(r.total, top_l, f"{r.total:,}"),
                pct(share(r.read, r.total)),
                pct(share(r.drilled, r.total)),
                pct(share(r.finished, r.total)),
                pct(share(r.verbs, r.total)),
            ]
            for r in langs
        ]
        parts.append(
            card(
                "By language being learned",
                table(headers, rows, {1, 2, 3, 4, 5}),
                sub=f"Columns are the share of that language's {what} "
                + (
                    "touched Learn/reference pages, number practice, a results page, "
                    "verb pages (a session can count in several)."
                    if ds.sessions is not None
                    else "went to each kind of page."
                ),
                wide=True,
            )
        )
    hl = per_hl(ds)
    parts.append(
        card(
            "Translated page versions (?hl=)",
            bar_list(list(hl.items()), sum(ds.views.values()), "visits"),
            sub="Visits to a ?hl= version of a page, by UI language: "
            "a sign the hreflang pages are found. English pages have no ?hl=.",
        )
    )
    parts.append("</div>")

    # Audience
    parts.append('<h2>Devices and places</h2><div class="grid">')
    dev_total = sum(ds.devices.values())
    parts.append(
        card(
            "Devices",
            bar_list(list(ds.devices.items()), dev_total, u),
            sub="From screen size and OS."
            if ds.sessions is not None
            else "GoatCounter's screen-size groups.",
        )
    )
    parts.append(
        card(
            "Browsers",
            bar_list(list(ds.browsers.items()), sum(ds.browsers.values()), u, limit=8),
        )
    )
    parts.append(
        card(
            "Operating systems",
            bar_list(list(ds.systems.items()), sum(ds.systems.values()), u, limit=8),
        )
    )
    parts.append(
        card(
            "Countries",
            bar_list(
                list(ds.countries.items()), sum(ds.countries.values()), u, limit=15
            ),
        )
    )
    parts.append("</div>")

    # Raw paths
    top_paths = ds.views.most_common(60)
    headers = ["Path", "Section", "Visits"] + (
        ["Pageviews"] if ds.pageviews is not None else []
    )
    rows = [
        [p, section_label(classify(p, LANGUAGES).section), n]
        + ([ds.pageviews[p]] if ds.pageviews is not None else [])
        for p, n in top_paths
    ]
    parts.append('<h2>All pages</h2><div class="grid">')
    parts.append(
        card(
            f"Top {len(top_paths)} paths",
            table(headers, rows, {2, 3}),
            sub="Visits = sessions that loaded the page (what GoatCounter's "
            "dashboard counts); pageviews = every load."
            if ds.sessions is not None
            else "Visits per path, as GoatCounter's dashboard counts them.",
            wide=True,
        )
    )
    parts.append("</div>")

    notes = ds.notes + [
        "GoatCounter doesn't see visitors whose ad blocker drops count.js, or "
        "anything after a page loaded (Listening rounds swap questions in "
        "place). `flask quiz-stats` counts number drills on the server.",
        "count.js reports each page's canonical URL, so a shared preset link "
        "counts as its setup screen and every friend-challenge page as "
        "/challenge/link.",
    ]
    if ds.sessions is not None:
        notes.append(
            "A session is GoatCounter's session ID: one browser over a "
            "few hours. A person who comes back the next day is a new session."
        )
    source = (
        "GoatCounter CSV export (hit level)"
        if ds.source == "export"
        else "GoatCounter stats API (aggregates)"
    )
    foot = (
        "<footer><h3>How to read this</h3><ul>"
        + "".join(f"<li>{esc(n)}</li>" for n in notes)
        + f"</ul><p>Source: {esc(source)}. Generated {generated:%d %b %Y %H:%M} UTC by "
        "tools/goatcounter_report.py.</p></footer>"
    )

    return (
        TEMPLATE.replace("{{BODY}}", "".join(parts))
        .replace("{{FOOT}}", foot)
        .replace("{{RANGE}}", esc(f"{ds.start:%d %b %Y} – {ds.end:%d %b %Y}"))
    )


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>diminumero usage</title>
<style>
:root {
  color-scheme: light;
  --page: #f9f9f7; --surface: #fcfcfb; --ink: #0b0b0b; --ink-2: #52514e; --muted: #898781;
  --grid: #e1e0d9; --axis: #c3c2b7; --border: rgba(11,11,11,0.10); --hover: rgba(11,11,11,0.04);
  --series-1: #2a78d6;
  --s0: #f0efec; --s1: #cde2fb; --s2: #86b6ef; --s3: #3987e5; --s4: #1c5cab; --s5: #0d366b;
  --shadow: 0 4px 16px rgba(11,11,11,0.10);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --page: #0d0d0d; --surface: #1a1a19; --ink: #f0efec; --ink-2: #c3c2b7; --muted: #898781;
    --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,0.10); --hover: rgba(255,255,255,0.05);
    --series-1: #3987e5;
    --s0: #2c2c2a; --s1: #104281; --s2: #1c5cab; --s3: #2a78d6; --s4: #5598e7; --s5: #9ec5f4;
    --shadow: 0 4px 16px rgba(0,0,0,0.5);
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --page: #0d0d0d; --surface: #1a1a19; --ink: #f0efec; --ink-2: #c3c2b7; --muted: #898781;
  --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,0.10); --hover: rgba(255,255,255,0.05);
  --series-1: #3987e5;
  --s0: #2c2c2a; --s1: #104281; --s2: #1c5cab; --s3: #2a78d6; --s4: #5598e7; --s5: #9ec5f4;
  --shadow: 0 4px 16px rgba(0,0,0,0.5);
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--page); color: var(--ink);
  font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 1120px; margin: 0 auto; padding: 32px 16px 64px; }
header h1 { font-size: 26px; margin: 0 0 4px; font-weight: 650; }
header p { margin: 0 0 24px; color: var(--ink-2); }
h2 { font-size: 18px; font-weight: 650; margin: 36px 0 12px; }
h3 { font-size: 15px; font-weight: 600; margin: 0 0 4px; }
.sub { margin: 0 0 14px; color: var(--ink-2); font-size: 13px; }
.grid { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(min(100%, 420px), 1fr)); }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
  padding: 16px 18px; min-width: 0; }
.card.wide { grid-column: 1 / -1; }
.findings { margin-top: 16px; }
.findings ul { margin: 8px 0 0; padding-left: 20px; }
.findings li { margin: 4px 0; }
.kpis { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(min(100%, 170px), 1fr)); }
.kpi { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 14px 16px; }
.kpi-label { font-size: 13px; color: var(--ink-2); }
.kpi-value { font-size: 28px; font-weight: 600; line-height: 1.2; margin-top: 2px; }
.kpi-note { font-size: 12px; color: var(--muted); }
.bars { display: grid; gap: 4px; }
.bar-row { display: grid; grid-template-columns: minmax(6rem, 40%) minmax(0, 1fr); align-items: center;
  gap: 12px; padding: 3px 6px; margin: 0 -6px; border-radius: 6px; }
.bar-row:hover, .bar-row:focus-visible { background: var(--hover); outline: none; }
.bar-row:focus-visible { box-shadow: 0 0 0 2px var(--series-1); }
.bar-label { font-size: 13px; overflow-wrap: anywhere; }
.bar-track { display: flex; align-items: center; gap: 8px; min-width: 0; }
.bar { flex: none; height: 14px; width: calc((100% - var(--reserve, 6.5rem)) * var(--f)); min-width: 2px;
  background: var(--series-1); border-radius: 0 4px 4px 0; }
.bar.zero { min-width: 0; width: 0; }
.bar-row:hover .bar, .bar-row:focus-visible .bar { filter: brightness(1.12); }
.bar-value { font-size: 12.5px; color: var(--ink-2); font-variant-numeric: tabular-nums; white-space: nowrap; }
.empty { color: var(--muted); font-size: 13px; margin: 0; }
.table-wrap { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: 13px; }
th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--grid); vertical-align: top; }
th { color: var(--ink-2); font-weight: 600; white-space: nowrap; }
td { overflow-wrap: anywhere; }
.nowrap { white-space: nowrap; }
.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.meter-cell { display: inline-flex; flex-wrap: wrap; align-items: center; gap: 4px 8px;
  justify-content: flex-end; width: 100%; }
.meter { display: inline-block; width: clamp(48px, 10vw, 90px); height: 8px; border-radius: 4px; background: var(--grid); overflow: hidden; flex: none; }
.meter > span { display: block; height: 100%; width: calc(100% * var(--f)); background: var(--series-1); border-radius: 4px; }
details.table-view { margin-top: 12px; }
details.table-view summary { cursor: pointer; color: var(--ink-2); font-size: 13px; }
details.table-view[open] summary { margin-bottom: 8px; }
.ts { position: relative; height: 240px; }
.ts svg { display: block; width: 100%; height: 100%; overflow: visible; }
.ts text { fill: var(--muted); font-size: 11px; font-variant-numeric: tabular-nums; }
.ts .grid-line { stroke: var(--grid); stroke-width: 1; }
.ts .base { stroke: var(--axis); stroke-width: 1; }
.ts .line { fill: none; stroke: var(--series-1); stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
.ts .area { fill: var(--series-1); opacity: 0.10; }
.ts .cross { stroke: var(--axis); stroke-width: 1; }
.ts .dot { fill: var(--series-1); stroke: var(--surface); stroke-width: 2; }
.ts svg:focus-visible { outline: 2px solid var(--series-1); outline-offset: 4px; border-radius: 4px; }
.heat { display: grid; grid-template-columns: 2.6rem repeat(24, minmax(0, 1fr)); gap: 2px; align-items: center; }
.heat .cell { height: 20px; border-radius: 3px; }
.heat-hour, .heat-day { font-size: 11px; color: var(--muted); font-variant-numeric: tabular-nums; }
.heat-hour { align-self: end; }
.cell.s0 { background: var(--s0); } .cell.s1 { background: var(--s1); } .cell.s2 { background: var(--s2); }
.cell.s3 { background: var(--s3); } .cell.s4 { background: var(--s4); } .cell.s5 { background: var(--s5); }
.heat .cell:hover { outline: 2px solid var(--ink); outline-offset: -1px; }
.heat-legend { display: flex; align-items: center; gap: 3px; margin-top: 10px; font-size: 11px; color: var(--muted); }
.heat-legend .cell { width: 18px; height: 12px; border-radius: 2px; }
.heat-legend span:first-child { margin-right: 4px; } .heat-legend span:last-child { margin-left: 4px; }
.tooltip { position: fixed; z-index: 10; pointer-events: none; background: var(--surface); color: var(--ink);
  border: 1px solid var(--border); border-radius: 8px; box-shadow: var(--shadow); padding: 6px 10px;
  font-size: 12.5px; max-width: 280px; display: none; }
.tooltip strong { display: block; font-weight: 600; font-variant-numeric: tabular-nums; }
.tooltip span { color: var(--ink-2); }
footer { margin-top: 40px; color: var(--ink-2); font-size: 13px; }
footer ul { padding-left: 20px; }
@media (max-width: 560px) {
  .bar-row { grid-template-columns: minmax(0, 1fr); gap: 2px; }
  .kpi-value { font-size: 24px; }
  .heat .cell { height: 14px; }
  th, td { padding: 6px 4px; }
}
</style>
</head>
<body>
<main>
<header><h1>How diminumero is used</h1><p>{{RANGE}}</p></header>
{{BODY}}
{{FOOT}}
</main>
<script>
(function () {
  var tip = document.createElement('div');
  tip.className = 'tooltip';
  document.body.appendChild(tip);
  function setTip(value, label) {
    var strong = document.createElement('strong');
    strong.textContent = value;
    var span = document.createElement('span');
    span.textContent = label;
    tip.replaceChildren(strong, span);
    tip.style.display = 'block';
  }
  function place(x, y) {
    var r = tip.getBoundingClientRect();
    var left = Math.min(x + 14, window.innerWidth - r.width - 8);
    var top = y - r.height - 12;
    if (top < 8) top = y + 18;
    tip.style.left = Math.max(8, left) + 'px';
    tip.style.top = top + 'px';
  }
  function hide() { tip.style.display = 'none'; }

  document.addEventListener('pointermove', function (e) {
    var el = e.target.closest && e.target.closest('[data-tip-value]');
    if (!el) { if (!e.target.closest || !e.target.closest('.ts')) hide(); return; }
    setTip(el.dataset.tipValue, el.dataset.tipLabel || '');
    place(e.clientX, e.clientY);
  });
  document.addEventListener('focusin', function (e) {
    var el = e.target.closest && e.target.closest('[data-tip-value]');
    if (!el) return;
    setTip(el.dataset.tipValue, el.dataset.tipLabel || '');
    var r = el.getBoundingClientRect();
    place(r.left + r.width / 2, r.top);
  });
  document.addEventListener('focusout', hide);
  window.addEventListener('scroll', hide, { passive: true });

  var NS = 'http://www.w3.org/2000/svg';
  function el(name, attrs, parent) {
    var node = document.createElementNS(NS, name);
    for (var k in attrs) node.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(node);
    return node;
  }
  function niceStep(max) {
    var raw = max / 4, mag = Math.pow(10, Math.floor(Math.log10(raw || 1)));
    var steps = [1, 2, 2.5, 5, 10];
    for (var i = 0; i < steps.length; i++) if (steps[i] * mag >= raw) return Math.max(steps[i] * mag, 1);
    return 10 * mag;
  }
  var fmt = new Intl.NumberFormat('en');
  var dayFmt = new Intl.DateTimeFormat('en', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
  var tickFmt = new Intl.DateTimeFormat('en', { day: 'numeric', month: 'short', timeZone: 'UTC' });

  document.querySelectorAll('.ts').forEach(function (host) {
    var data = JSON.parse(document.getElementById(host.dataset.src).textContent);
    var unit = host.dataset.unit;
    if (!data.length) { host.textContent = 'No data in this window.'; return; }
    var current = data.length - 1;
    function render() {
      var W = host.clientWidth, H = host.clientHeight, m = { l: 44, r: 12, t: 10, b: 26 };
      var max = Math.max.apply(null, data.map(function (d) { return d.v; }).concat([1]));
      var step = niceStep(max), top = Math.ceil(max / step) * step;
      var n = data.length, pw = W - m.l - m.r, ph = H - m.t - m.b;
      function x(i) { return m.l + (n === 1 ? pw / 2 : i * pw / (n - 1)); }
      function y(v) { return m.t + ph - v / top * ph; }
      host.replaceChildren();
      var svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, tabindex: '0',
        'aria-label': unit + ' per day; use the arrow keys to read days' }, host);
      for (var t = 0; t <= top + 1e-9; t += step) {
        el('line', { x1: m.l, x2: W - m.r, y1: y(t), y2: y(t), 'class': t === 0 ? 'base' : 'grid-line' }, svg);
        var lbl = el('text', { x: m.l - 8, y: y(t) + 4, 'text-anchor': 'end' }, svg);
        lbl.textContent = t >= 10000 ? fmt.format(t / 1000) + 'K' : fmt.format(t);
      }
      var every = Math.max(1, Math.ceil(n / Math.max(2, Math.floor(pw / 80))));
      for (var i = 0; i < n; i += every) {
        var tx = el('text', { x: x(i), y: H - 6, 'text-anchor': i === 0 ? 'start' : 'middle' }, svg);
        tx.textContent = tickFmt.format(new Date(data[i].d + 'T00:00:00Z'));
      }
      var line = data.map(function (d, i) { return (i ? 'L' : 'M') + x(i).toFixed(1) + ' ' + y(d.v).toFixed(1); }).join(' ');
      el('path', { d: line + ' L' + x(n - 1).toFixed(1) + ' ' + y(0) + ' L' + x(0).toFixed(1) + ' ' + y(0) + ' Z', 'class': 'area' }, svg);
      el('path', { d: line, 'class': 'line' }, svg);
      var cross = el('line', { y1: m.t, y2: m.t + ph, 'class': 'cross', visibility: 'hidden' }, svg);
      var dot = el('circle', { r: 4, 'class': 'dot', visibility: 'hidden' }, svg);
      function show(i, cx, cy) {
        current = i;
        var d = data[i];
        cross.setAttribute('x1', x(i)); cross.setAttribute('x2', x(i));
        dot.setAttribute('cx', x(i)); dot.setAttribute('cy', y(d.v));
        cross.setAttribute('visibility', 'visible'); dot.setAttribute('visibility', 'visible');
        var label = dayFmt.format(new Date(d.d + 'T00:00:00Z'));
        if (d.p !== undefined) label += ' · ' + fmt.format(d.p) + ' pageviews';
        setTip(fmt.format(d.v) + ' ' + unit, label);
        var r = svg.getBoundingClientRect();
        place(cx !== undefined ? cx : r.left + x(i), cy !== undefined ? cy : r.top + y(d.v));
      }
      function clear() { cross.setAttribute('visibility', 'hidden'); dot.setAttribute('visibility', 'hidden'); hide(); }
      svg.addEventListener('pointermove', function (e) {
        var r = svg.getBoundingClientRect();
        var i = Math.round((e.clientX - r.left - m.l) / (pw || 1) * (n - 1));
        show(Math.max(0, Math.min(n - 1, i)), e.clientX, e.clientY);
      });
      svg.addEventListener('pointerleave', clear);
      svg.addEventListener('blur', clear);
      svg.addEventListener('focus', function () { show(current); });
      svg.addEventListener('keydown', function (e) {
        if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
          e.preventDefault();
          show(Math.max(0, Math.min(n - 1, current + (e.key === 'ArrowLeft' ? -1 : 1))));
        }
      });
    }
    render();
    var width = host.clientWidth;
    new ResizeObserver(function () {
      if (host.clientWidth !== width) { width = host.clientWidth; render(); }
    }).observe(host);
  });
})();
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

LANGUAGES: dict[str, str] = {}


def resolve_key() -> str | None:
    if os.environ.get("GOATCOUNTER_API_KEY"):
        return os.environ["GOATCOUNTER_API_KEY"]
    for name in (".env", ".env.prod"):
        value = dotenv_values(REPO_ROOT / name).get("GOATCOUNTER_API_KEY")
        if value:
            return value
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--site",
        default=os.environ.get("GOATCOUNTER_SITE", DEFAULT_SITE),
        help=f"GoatCounter site code (default {DEFAULT_SITE})",
    )
    parser.add_argument(
        "--api-url",
        help="API base URL, for a self-hosted GoatCounter "
        "(default https://<site>.goatcounter.com/api/v0)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="window in days, 0 = everything (default 90)",
    )
    parser.add_argument(
        "--source",
        choices=("auto", "export", "api"),
        default="auto",
        help="auto (default): the CSV export, else the aggregate API",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="don't call GoatCounter; use the cached export",
    )
    parser.add_argument(
        "--tz", default="UTC", help="time zone for days and hours (default UTC)"
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"output directory (default {DEFAULT_OUT.relative_to(REPO_ROOT)})",
    )
    parser.add_argument(
        "--open", action="store_true", help="open the report in a browser"
    )
    args = parser.parse_args(argv)

    global LANGUAGES
    LANGUAGES = load_language_names()
    try:
        tz = ZoneInfo(args.tz)
    except (ZoneInfoNotFoundError, ValueError):
        parser.error(f"unknown time zone {args.tz!r}")

    def log(message: str) -> None:
        print(message, file=sys.stderr)

    today = datetime.now(tz).date()
    end = today
    start = date(2000, 1, 1) if args.days <= 0 else today - timedelta(args.days - 1)
    cache = ExportCache(args.out / args.site)
    notes: list[str] = []

    key = None if args.offline else resolve_key()
    if not args.offline and not key:
        if cache.has_data() and args.source != "api":
            log("No GOATCOUNTER_API_KEY set: re-rendering the cached export.")
        else:
            parser.exit(
                2,
                "Set GOATCOUNTER_API_KEY (in .env or the environment). Create one in "
                f"GoatCounter: your name in the top menu → API, at "
                f"https://{args.site}.goatcounter.com.\n",
            )
    gc = (
        GoatCounter(args.api_url or f"https://{args.site}.goatcounter.com/api/v0", key)
        if key
        else None
    )

    ds: Dataset | None = None
    if args.source in ("auto", "export"):
        if gc:
            try:
                reason = sync_export(gc, cache, log)
                if reason and not cache.has_data():
                    if args.source == "export":
                        parser.exit(1, f"{reason}.\n")
                    log(f"{reason}. Using the aggregate API meanwhile.")
                    notes.append(f"{reason}.")
            except ApiError as exc:
                if exc.status == 401:
                    parser.exit(2, f"GoatCounter rejected the API key (401): {exc}\n")
                hint = (
                    " The key may lack the export permission."
                    if exc.status == 403
                    else ""
                )
                if cache.has_data():
                    log(
                        f"Couldn't refresh the export ({exc}).{hint} Using the cached copy."
                    )
                    synced = cache.state().get("synced_at", "?")[:16].replace("T", " ")
                    notes.append(
                        f"The export couldn't be refreshed ({exc}); this is the "
                        f"cached copy from {synced} UTC."
                    )
                elif args.source == "export":
                    parser.exit(1, f"Export failed: {exc}.{hint}\n")
                else:
                    log(
                        f"Export failed ({exc}).{hint} Falling back to the aggregate API."
                    )
                    notes.append(f"The CSV export failed ({exc}).{hint}")
        if cache.has_data():
            hits, skipped = read_hits(cache.csv_path, LANGUAGES, tz)
            if args.days <= 0 and hits:
                start = hits[0].when.date()
            ds = dataset_from_hits(hits, skipped, start, end, args.tz, notes)
        elif args.offline:
            parser.exit(
                1,
                f"No cached export in {cache.directory}; run without --offline first.\n",
            )

    if ds is None:
        if not gc:
            parser.exit(1, "No cached export and no API key.\n")
        if args.days <= 0:
            start = today - timedelta(API_DAYS_WHEN_ALL - 1)
        try:
            ds = dataset_from_api(
                gc, start, end, args.tz, notes, log, trim_leading=args.days <= 0
            )
        except ApiError as exc:
            parser.exit(1, f"GoatCounter API error ({exc.status}): {exc}\n")

    args.out.mkdir(parents=True, exist_ok=True)
    report = args.out / "report.html"
    report.write_text(render_report(ds, _utcnow()), encoding="utf-8")

    print()
    for line in findings(ds):
        print(f"  • {line}")
    for note in ds.notes:
        print(f"  ({note})")
    print(f"\nReport: {report}")
    if args.open:
        webbrowser.open(report.resolve().as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
