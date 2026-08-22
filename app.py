"""Flask application for diminumero."""

import json
from collections import deque
from datetime import datetime, timezone
from functools import wraps
from urllib.parse import quote_plus, urlencode

from flask import (
    Flask,
    Response,
    g,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
)
from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
from flask_migrate import Migrate
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix
import hashlib
import jinja2
import logging
import quiz_logic
import os
import random
import re
import secrets
import sys
import threading
import time
from pathlib import Path

from models import Card, ConjugationStat, DeckShare, PollResponse, VerbCard, db
from config import (
    QUESTIONS_PER_QUIZ,
    DEFAULT_UI_LANGUAGE,
    SITE_URL,
    SPEED_BONUS_TIME_EASY,
    SPEED_BONUS_TIME_ADVANCED,
    SPEED_BONUS_TIME_HARDCORE,
    SUPPORTED_UI_LANGUAGES,
    PARTIAL_UI_LANGUAGES,
    RTL_UI_LANGUAGES,
)
from languages import (
    AVAILABLE_LANGUAGES,
    get_default_number_system,
    get_feedback_expression,
    get_language_numbers,
    get_language_ui_description,
    get_language_ui_name,
    get_languages_with_audio_mode,
    get_languages_with_conjugation,
    get_languages_with_conjugation_materials,
    get_languages_with_learn_materials,
    get_number_system,
    get_number_systems,
    get_number_usage_weights,
    get_ready_number_systems,
    is_language_ready,
    resolve_number_system,
)
from languages.notes_loader import get_notes
from translations import TRANSLATIONS
from conjugation_config import (
    CONJ_QUESTIONS_DEFAULT,
    conj_hint_model_verbs,
    conj_optional_person_index,
    conj_persons,
    conj_tense_keys,
    conj_tenses,
    person_label,
    tense_hint,
    tense_label,
)
from languages.de import conjugations as de_conjugations
from languages.es import conjugations as es_conjugations
from languages.it import conjugations as it_conjugations

# Committed global verb pools, one per conjugation language. Every language
# with `has_conjugation: True` in languages/config.py must have an entry here.
CONJ_POOLS = {"es": es_conjugations, "it": it_conjugations, "de": de_conjugations}

# Fallback language for globally-rendered conjugation links (nav, home page)
# when the session's learn language has no conjugation section.
DEFAULT_CONJUGATION_LANG = "es"


def _conj_pool(lang_code: str):
    """The committed verb pool module for a conjugation language."""
    return CONJ_POOLS[lang_code]


def _current_conjugation_lang() -> str:
    """Conjugation language for globally-rendered links (nav, home page).

    Follows the session's learn language when that language has a conjugation
    section, so e.g. a German learner's nav points at /de/conjugate.
    """
    learn_lang = session.get("learn_language")
    if learn_lang in get_languages_with_conjugation():
        return learn_lang
    return DEFAULT_CONJUGATION_LANG


# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
# Trust X-Forwarded-Proto/Host from the reverse proxy (Coolify/Traefik) so
# url_for(..., _external=True) emits https URLs — required for the Auth0
# redirect_uri to match the allowed callback in production.
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY", "dev-secret-key-change-in-production"
)

# SQLite lives under Flask's instance folder (gitignored, mount as a Docker
# volume in prod). The DATABASE_URL env var lets prod swap to Postgres later.
os.makedirs(app.instance_path, exist_ok=True)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL",
    f"sqlite:///{os.path.join(app.instance_path, 'diminumero.db')}",
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
# pool_pre_ping issues a cheap SELECT 1 before handing out a pooled connection,
# so a dropped Postgres connection (host NAT/firewall idle timeout) is detected
# and replaced instead of raising on the next real query. pool_recycle forces
# connections younger than 280s, staying under typical 300s idle cutoffs.
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 280,
}
db.init_app(app)
migrate = Migrate(app, db)


# Send app.logger output to stdout so `docker logs` captures it. Without this,
# uncaught exceptions disappear and 500s are impossible to diagnose.
if not app.logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)


@app.errorhandler(Exception)
def handle_unhandled_exception(e):
    """Log every unhandled exception so 500s show up in container logs."""
    if isinstance(e, HTTPException):
        return e
    app.logger.exception("Unhandled exception on %s %s", request.method, request.path)
    return ("Internal Server Error", 500)


# Auth0 OIDC client (Authlib).
# AUTH0_DOMAIN, AUTH0_CLIENT_ID, AUTH0_CLIENT_SECRET must be set in the env;
# see .env.example. The /login, /callback, /logout, /cards routes depend on this.
oauth = OAuth(app)
_auth0_domain = os.environ.get("AUTH0_DOMAIN")
if _auth0_domain:
    oauth.register(
        name="auth0",
        client_id=os.environ.get("AUTH0_CLIENT_ID"),
        client_secret=os.environ.get("AUTH0_CLIENT_SECRET"),
        client_kwargs={"scope": "openid profile email"},
        server_metadata_url=(
            f"https://{_auth0_domain}/.well-known/openid-configuration"
        ),
    )


def login_required(view):
    """Redirect to /login when no Auth0 user is on the session."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


@app.before_request
def initialize_ui_language():
    """Set default UI language on first visit if not already in session."""
    if "language" not in session:
        session["language"] = DEFAULT_UI_LANGUAGE


@app.url_defaults
def add_static_cache_bust(endpoint, values):
    """Append ?v=<file-mtime> to every static URL so an edited asset is fetched
    immediately while the file itself can still be cached for a long time.

    Costs one extra `stat` per asset — negligible, and the same stat Flask's
    static handler does to serve the file anyway.
    """
    if endpoint != "static" or not values.get("filename"):
        return
    try:
        mtime = os.stat(os.path.join(app.static_folder, values["filename"])).st_mtime
    except OSError:
        return
    values["v"] = str(int(mtime))


@app.after_request
def set_cache_headers(response):
    """Set Cache-Control headers based on the route."""
    path = request.path
    if g.get("no_store"):
        # A quiz rendered from a shared preset link lives on an otherwise
        # cacheable URL (/<lang>/numbers) but carries a live question and a
        # Set-Cookie — never let a proxy hand it to the next student.
        response.headers["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, max-age=0"
        )
        return response
    if response.mimetype == "application/pdf":
        # A worksheet PDF is seed-addressed and deterministic, so this URL is
        # always this exact document — worth a CDN or browser holding on to.
        # Keyed off the mimetype, not the path, so an HTML fallback served
        # after a failed render is never marked immutable.
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response
    if path in ("/about", "/privacy", "/imprint", "/"):
        response.headers["Cache-Control"] = "public, max-age=3600"
    elif path in ("/sitemap.xml", "/robots.txt"):
        response.headers["Cache-Control"] = "public, max-age=86400"
    elif (
        "/quiz/" in path
        or "/results" in path
        or path.startswith("/api/")
        or path in ("/login", "/callback", "/logout")
        or path.startswith("/cards")
        or "/conjugate" in path
    ):
        response.headers["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, max-age=0"
        )
    elif path.startswith("/static/"):
        # Versioned (?v=<mtime>) static URLs are safe to cache long-term: the
        # URL changes whenever the file does, so an edit is fetched immediately.
        # Unversioned direct hits keep the short, revalidating cache.
        if request.args.get("v"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            response.headers["Cache-Control"] = "public, max-age=600"
    elif "/learn" in path:
        response.headers["Cache-Control"] = "public, max-age=3600"
    else:
        response.headers["Cache-Control"] = "public, max-age=600"
    return response


OG_LOCALE_MAP = {
    "en": "en_US",
    "de": "de_DE",
    "es": "es_ES",
    "it": "it_IT",
    "fr": "fr_FR",
    "pt": "pt_BR",
    "ar": "ar_SA",
    "uk": "uk_UA",
    "cy": "cy_GB",
}


@app.context_processor
def inject_seo_context():
    """Inject SEO-related variables into all templates."""
    ui_language = session.get("language", DEFAULT_UI_LANGUAGE)
    base = SITE_URL.rstrip("/")
    canonical_url = base + request.path

    # og:locale
    og_locale = OG_LOCALE_MAP.get(ui_language, "en_US")
    og_locale_alternates = [v for k, v in OG_LOCALE_MAP.items() if k != ui_language]

    # Breadcrumbs
    breadcrumbs = [{"name": "Home", "url": f"{base}/"}]
    path = request.path.strip("/")
    if path:
        parts = path.split("/")
        if parts[0] in AVAILABLE_LANGUAGES:
            lang_name = AVAILABLE_LANGUAGES[parts[0]].get("name", parts[0])
            breadcrumbs.append({"name": lang_name, "url": f"{base}/{parts[0]}"})
            if len(parts) >= 2:
                sub = "/".join(parts[1:])
                breadcrumbs.append(
                    {"name": sub.replace("/", " - ").title(), "url": f"{base}/{path}"}
                )
        elif parts[0] in ("about", "privacy", "imprint"):
            breadcrumbs.append({"name": parts[0].title(), "url": f"{base}/{parts[0]}"})

    return {
        "ui_language": ui_language,
        "ui_dir": "rtl" if ui_language in RTL_UI_LANGUAGES else "ltr",
        # A locale that is still being translated is served with English
        # fallbacks; the page says so instead of pretending to be finished.
        "ui_language_partial": ui_language in PARTIAL_UI_LANGUAGES,
        "site_url": SITE_URL,
        "canonical_url": canonical_url,
        "og_locale": og_locale,
        "og_locale_alternates": og_locale_alternates,
        "breadcrumbs": breadcrumbs,
        "user": session.get("user"),
        "conjugation_lang": _current_conjugation_lang(),
        # Inline banner for a shared preset link whose params were adjusted.
        "preset_notices": g.get("preset_notices") or [],
        # Any URL carrying quiz params is a duplicate of the clean route as
        # far as a crawler is concerned: canonical_url above already drops the
        # query string, and base.html adds noindex when this is set.
        "has_quiz_params": _has_preset_params(),
    }


def get_text(key, learn_language=None):
    """Get translated text for the current language.

    `learn_language` overrides the session's learn language for keys whose
    text names the practiced language (LANGUAGE_NAME_PLACEHOLDER) — used by
    pages with their own language in the URL, e.g. /<lang>/conjugate.
    """
    ui_language = session.get("language", DEFAULT_UI_LANGUAGE)
    if learn_language is None:
        learn_language = session.get("learn_language", "es")

    # Language name/description keys are resolved from languages/config.py
    if key.startswith("lang_") and key.endswith("_name"):
        lang_code = key[5:-5]
        return get_language_ui_name(lang_code, ui_language)
    if key.startswith("lang_") and key.endswith("_description"):
        lang_code = key[5:-12]
        return get_language_ui_description(lang_code, ui_language)

    lang_texts = TRANSLATIONS.get(ui_language, {})
    if key in lang_texts:
        text = lang_texts[key]
    else:
        # Fall back to English for keys not translated in this UI language
        # (e.g. newer features) rather than leaking the raw key to the page.
        text = TRANSLATIONS.get(DEFAULT_UI_LANGUAGE, {}).get(key, key)
    text = text.replace(
        "LANGUAGE_NAME_PLACEHOLDER",
        get_language_ui_name(learn_language, ui_language),
    )
    return text


def _conj_text(key: str, lang_code: str) -> str:
    """Translated text for a per-conjugation-language key.

    A few conjugation strings name the language being conjugated (page title,
    add-verb placeholder, "not in our … list" error); those exist as
    ``<key>_es`` / ``<key>_de`` variants and are looked up here.
    """
    return get_text(f"{key}_{lang_code}")


# ===== Numeral systems =====
# A language may have more than one way of saying its numbers — Welsh decimal
# vs traditional, and the same shape would fit Korean Sino vs native or
# Belgian French. The declaration lives in languages/config.py; everything
# here is about carrying one choice through a drill and never showing a
# control to the 14 languages that have nothing to choose between.


def _number_system_text_key(lang_code, system_key):
    """The i18n key suffix a system's UI strings live under.

    Defaults to the system key, so a language that doesn't care gets
    `number_system_name_<key>` for free. Welsh overrides it to name its systems
    in Welsh (Degol / Ugeiniol) without claiming the generic `decimal` key for
    every language that might declare one later.
    """
    system = get_number_system(lang_code, system_key) or {}
    return system.get("label_key", system_key)


def _number_system_label(lang_code, system_key):
    """Translated name of a numeral system ('Degol', 'Ugeiniol')."""
    key = f"number_system_name_{_number_system_text_key(lang_code, system_key)}"
    label = get_text(key, learn_language=lang_code)
    return system_key.capitalize() if label == key else label


def _number_system_desc(lang_code, system_key):
    """One-line 'what it's for' blurb, or '' when the system has none."""
    key = f"number_system_desc_{_number_system_text_key(lang_code, system_key)}"
    desc = get_text(key, learn_language=lang_code)
    return "" if desc == key else desc


def _session_number_system(lang_code, requested=None):
    """The numeral system in force, remembered for the rest of the session.

    Anything unusable — another language's system, a typo, a system whose deck
    is still incomplete — resolves back to the language's default instead of
    raising, the same way an unusable range in a shared link does.
    """
    if requested is None:
        requested = session.get("number_system")
    resolved = resolve_number_system(lang_code, requested)
    session["number_system"] = resolved
    return resolved


def _session_usage_weights(lang_code, system_key=None):
    """How often each number of the active deck is worth asking, or None.

    Declared by the deck itself (traditional Welsh is the only one so far), so
    every other language draws exactly as it did before.
    """
    if system_key is None:
        system_key = session.get("number_system")
    return get_number_usage_weights(
        lang_code, resolve_number_system(lang_code, system_key)
    )


def _system_has_audio(lang_code, system_key):
    """Whether the Listening quiz may use this system's deck."""
    system = get_number_system(lang_code, system_key) or {}
    return bool(system.get("has_audio", True))


def _audio_number_system(lang_code):
    """The system a Listening session runs on.

    Listening MP3s are per language, not per system, so a system that declares
    no audio (traditional Welsh) falls back to the default deck rather than
    handing the player numbers it cannot pronounce.
    """
    active = _session_number_system(lang_code)
    if _system_has_audio(lang_code, active):
        return active
    return get_default_number_system(lang_code)


def _number_system_context(lang_code, active=None):
    """What a template needs to talk about this language's numeral systems.

    None when the language has fewer than two declared systems — the control,
    the label and the notice are then structurally absent rather than rendered
    as a dead one-option widget.
    """
    systems = get_number_systems(lang_code)
    if len(systems) < 2:
        return None

    ready = {system["key"] for system in get_ready_number_systems(lang_code)}
    active_key = resolve_number_system(lang_code, active)

    options = [
        {
            "key": system["key"],
            "label": _number_system_label(lang_code, system["key"]),
            "desc": _number_system_desc(lang_code, system["key"]),
            "active": system["key"] == active_key,
        }
        for system in systems
        if system["key"] in ready
    ]

    active_label = _number_system_label(lang_code, active_key)
    notices = []
    if len(options) < 2:
        # Only one system is usable, so say which one this drill is — the whole
        # point of naming it is that a learner shouldn't have to guess.
        notices.append(
            get_text("number_system_only_note", learn_language=lang_code).format(
                active_label
            )
        )
        for system in systems:
            if system["key"] in ready:
                continue
            notices.append(
                get_text(
                    "number_system_unavailable_note", learn_language=lang_code
                ).format(_number_system_label(lang_code, system["key"]))
            )

    return {
        "active": active_key,
        "active_label": active_label,
        # What the active system is *for*, so a compact picker (the menu tile)
        # can explain the choice without repeating both blurbs.
        "active_desc": _number_system_desc(lang_code, active_key),
        "options": options,
        "has_choice": len(options) > 1,
        "notices": notices,
    }


def _number_system_range_notice(lang_code, system_key, numbers):
    """Notice for a system that covers less than the language's usual range.

    Two different shortfalls, and conflating them would overstate what the
    learner is getting: a system can stop early (traditional Welsh ends around
    100 where decimal runs to ten million), and it can also be *sparse* inside
    its range while speakers are still filling it in. A deck of 30 numbers
    described as "covers 1-100" would be a small lie.
    """
    if len(get_number_systems(lang_code)) < 2 or not numbers:
        return None
    default_numbers = get_language_numbers(lang_code)
    low, high = min(numbers), max(numbers)
    if high >= max(default_numbers):
        return None

    label = _number_system_label(lang_code, system_key)
    if len(numbers) < high - low + 1:
        return get_text("number_system_sparse_note", learn_language=lang_code).format(
            label, len(numbers), low, high
        )
    return get_text(
        "number_system_partial_range_note", learn_language=lang_code
    ).format(label, low, high)


def _other_system_answer(lang_code, number, exclude_system):
    """The same number's word in another of this language's systems.

    Used to tell a learner "that's the decimal form" instead of a bare wrong,
    which would be false — the answer is correct Welsh, just not the Welsh this
    drill asked for.
    """
    for system in get_number_systems(lang_code):
        if system["key"] == exclude_system:
            continue
        try:
            deck = get_language_numbers(lang_code, system["key"])
        except ValueError:
            continue
        word = deck.get(number)
        if word:
            yield system["key"], word


def _wrong_system_flash(lang_code, number, user_answer):
    """Flash text when the answer is right in the language's *other* system."""
    if not user_answer:
        return None
    active = session.get("number_system") or get_default_number_system(lang_code)
    for system_key, word in _other_system_answer(lang_code, number, active):
        if quiz_logic.check_answer_advanced(user_answer, word):
            return get_text(
                "number_system_wrong_system_flash", learn_language=lang_code
            ).format(
                _number_system_label(lang_code, system_key),
                _number_system_label(lang_code, active),
            )
    return None


# ===== Per-number notes =====


def _notes_for(lang_code, numbers, when):
    """Notes to render for one surface, in the current UI language.

    `when="prompt"` is the guarded case: while the answer is still hidden, only
    notes that declare they reveal nothing *and* have been reviewed come back.
    """
    return get_notes(
        lang_code,
        system=session.get("number_system"),
        numbers=numbers,
        when=when,
        ui_lang=session.get("language", DEFAULT_UI_LANGUAGE),
    )


@app.route("/")
def index():
    """Language selection landing page."""
    # Create translated copy of language metadata
    translated_languages = {}
    for lang_code, lang_info in AVAILABLE_LANGUAGES.items():
        translated_languages[lang_code] = {
            **lang_info,  # Copy all properties
            "name": get_text(f"lang_{lang_code}_name"),
            "description": get_text(f"lang_{lang_code}_description"),
        }

    return render_template(
        "language_selection.html",
        languages=translated_languages,
        conjugation_langs=get_languages_with_conjugation(),
        get_text=get_text,
    )


@app.route("/<lang_code>")
def mode_selection(lang_code):
    """Mode selection page for a specific learning language."""
    # Validate language code
    if not is_language_ready(lang_code):
        flash(get_text("flash_invalid_language"), "error")
        return redirect(url_for("index"))

    # Store learning language in session
    session["learn_language"] = lang_code

    # Load numbers for this language, in whichever numeral system is in force.
    # `?system=` switches it from the menu tile's own toggle — same param, same
    # forgiving resolution, as on the number-practice config screen below.
    number_system = _session_number_system(lang_code, request.args.get("system"))
    try:
        numbers = get_language_numbers(lang_code, number_system)
        total_numbers = len(numbers)
    except ValueError:
        flash(get_text("flash_language_load_error"), "error")
        return redirect(url_for("index"))

    has_learn_materials = lang_code in get_languages_with_learn_materials()
    has_audio_mode = lang_code in get_languages_with_audio_mode() and _system_has_audio(
        lang_code, number_system
    )
    has_conjugation = lang_code in get_languages_with_conjugation()
    has_conjugation_materials = lang_code in get_languages_with_conjugation_materials()

    return render_template(
        "index.html",
        total_numbers=total_numbers,
        questions_per_quiz=QUESTIONS_PER_QUIZ,
        lang_code=lang_code,
        get_text=get_text,
        has_learn_materials=has_learn_materials,
        has_audio_mode=has_audio_mode,
        has_conjugation=has_conjugation,
        has_conjugation_materials=has_conjugation_materials,
        magnitude_level=session.get("magnitude_level", 1),
        number_systems=_number_system_context(lang_code, number_system),
    )


# ===== Shareable drill presets =====
# A teacher pastes one URL into Moodle or Teams and a student lands straight in
# the configured drill, e.g. /es/numbers?range=1-100&mode=listening&magnitude=2
# The params fully determine the drill, so the link works from a cold browser
# with no session, no cookies and no account.

PRESET_PARAM_KEYS = ("mode", "range", "magnitude")

# Public mode names accepted in a link -> internal session mode. The listening
# drill is "audio" internally, but "listening" is what a teacher would write.
PRESET_MODE_ALIASES = {
    "easy": "easy",
    "advanced": "advanced",
    "hardcore": "hardcore",
    "listening": "audio",
    "listen": "audio",
    "audio": "audio",
}

PRESET_DEFAULT_MODE = "easy"

# Where listening degrades to when the language has no playable audio.
PRESET_NO_AUDIO_FALLBACK_MODE = "advanced"

# Fewest numbers a range may leave in the deck: easy mode draws its three
# distractors from the deck, and the no-repeat rule needs room to move.
MIN_PRESET_DECK = 4

# "1-100", tolerating the dashes a word processor produces.
_RANGE_RE = re.compile(r"^(\d+)\s*[-–—]\s*(\d+)$")


def _has_preset_params():
    """True when the URL carries at least one recognised preset param.

    Unknown params (utm_source and friends) must not start a drill.
    """
    return any(key in request.args for key in PRESET_PARAM_KEYS)


def _numbers_in_range(numbers, num_range):
    """The deck narrowed to an inclusive (low, high) range."""
    if not num_range:
        return numbers
    low, high = num_range
    return {num: word for num, word in numbers.items() if low <= num <= high}


def _parse_range(value, numbers):
    """Parse a "min-max" range against what the language actually has.

    Returns (range_or_None, notice_key_or_None). Decks are sparse above 1000,
    so a syntactically fine range can still leave too few numbers to build a
    quiz from — that falls back to the full deck just like garbage does.
    """
    if value is None:
        return None, None

    match = _RANGE_RE.match(value.strip())
    if not match:
        return None, "preset_notice_range"

    low, high = int(match.group(1)), int(match.group(2))
    if low > high:
        low, high = high, low

    if len(_numbers_in_range(numbers, (low, high))) < MIN_PRESET_DECK:
        return None, "preset_notice_range_empty"

    return (low, high), None


def _parse_magnitude(value):
    """Parse a magnitude dial value. Returns (level, notice_key_or_None)."""
    if value is None:
        return 1, None
    try:
        level = int(value)
    except (TypeError, ValueError):
        return 1, "preset_notice_magnitude"
    if level not in range(1, 6):
        return 1, "preset_notice_magnitude"
    return level, None


def _playable_audio_numbers(lang_code, numbers):
    """The subset of `numbers` we have a pre-generated MP3 for."""
    available = _available_audio_numbers(lang_code)
    return {num: word for num, word in numbers.items() if num in available}


def _parse_preset_system(lang_code):
    """Resolve `?system=` for a shared link. Returns (system, notice_key|None).

    A link asking for a system this language doesn't have (or whose deck is
    still incomplete) falls back to the default rather than 404-ing, so a
    pasted URL always lands the student in a working drill.
    """
    raw = (request.args.get("system") or "").strip().lower()
    resolved = resolve_number_system(lang_code, raw or None)
    if raw and raw != resolved:
        return resolved, "preset_notice_system"
    return resolved, None


def _parse_preset(lang_code, numbers):
    """Resolve the query params into a drill. Never raises.

    Returns (mode, magnitude_level, num_range, system, notices), where notices
    are already-translated strings for the inline banner.
    """
    notice_keys = []

    system, system_notice = _parse_preset_system(lang_code)
    if system_notice:
        notice_keys.append(system_notice)

    raw_mode = (request.args.get("mode") or "").strip().lower()
    mode = PRESET_MODE_ALIASES.get(raw_mode, PRESET_DEFAULT_MODE)
    if raw_mode and raw_mode not in PRESET_MODE_ALIASES:
        notice_keys.append("preset_notice_mode")

    num_range, range_notice = _parse_range(request.args.get("range"), numbers)
    if range_notice:
        notice_keys.append(range_notice)

    magnitude_level, magnitude_notice = _parse_magnitude(request.args.get("magnitude"))
    if magnitude_notice:
        notice_keys.append(magnitude_notice)

    # Listening needs the language flag, a system that has audio, and MP3s that
    # survive the range filter — otherwise the student gets a player with
    # nothing to play.
    if mode == "audio":
        ranged = _numbers_in_range(numbers, num_range)
        if (
            lang_code not in get_languages_with_audio_mode()
            or not _system_has_audio(lang_code, system)
            or not _playable_audio_numbers(lang_code, ranged)
        ):
            mode = PRESET_NO_AUDIO_FALLBACK_MODE
            notice_keys.append("preset_notice_no_audio")

    notices = [get_text(key, learn_language=lang_code) for key in notice_keys]
    return mode, magnitude_level, num_range, system, notices


def _seed_quiz_session(lang_code, mode, magnitude_level, num_range=None, system=None):
    """Start a fresh quiz session, keeping only the UI language and any login.

    Shared by the two form-post seeders and the preset link path. The numeral
    system survives the clear the same way the login does: it describes what
    the learner is practising, not where they are in a round.
    """
    ui_language = session.get("language", DEFAULT_UI_LANGUAGE)
    saved_user = session.get("user")
    saved_system = session.get("number_system")
    session.clear()
    session["language"] = ui_language
    if saved_user is not None:
        session["user"] = saved_user
    session["learn_language"] = lang_code
    session["number_system"] = resolve_number_system(
        lang_code, system if system is not None else saved_system
    )
    session["score"] = 0
    session["total_questions"] = 0
    session["asked_numbers"] = []
    session["mode"] = mode
    session["magnitude_level"] = magnitude_level
    if num_range:
        session["number_range"] = list(num_range)
    session["quiz_start_time"] = time.time()


def _session_numbers(lang_code):
    """The deck for the running quiz.

    The language's numbers in the session's numeral system, narrowed to the
    session's range when the quiz was started from a link that set one. Every
    question of the drill goes through here, so question 2 stays in the
    teacher's system and range just like question 1.
    """
    numbers = get_language_numbers(
        lang_code, resolve_number_system(lang_code, session.get("number_system"))
    )
    num_range = session.get("number_range")
    if not num_range or len(num_range) != 2:
        return numbers
    # Never hand back an empty deck: a stale range must not blank the quiz.
    return _numbers_in_range(numbers, (num_range[0], num_range[1])) or numbers


@app.route("/<lang_code>/numbers")
def number_modes(lang_code):
    """Number-practice page: pick a difficulty (easy/advanced/hardcore).

    Split out of the language menu so it has its own URL and browser Back
    returns to the language menu rather than the landing page.
    """
    if not is_language_ready(lang_code):
        flash(get_text("flash_invalid_language"), "error")
        return redirect(url_for("index"))

    session["learn_language"] = lang_code

    # `?system=` picks the numeral system without starting anything: it is
    # deliberately not a preset param, so this URL still renders the config
    # screen (and stays indexable) rather than dropping into a drill.
    number_system = _session_number_system(lang_code, request.args.get("system"))

    try:
        numbers = get_language_numbers(lang_code, number_system)
    except ValueError:
        flash(get_text("flash_language_load_error"), "error")
        return redirect(url_for("index"))

    # A shared preset link renders the drill itself instead of this page.
    if _has_preset_params():
        return _start_preset_drill(lang_code, numbers)

    has_learn_materials = lang_code in get_languages_with_learn_materials()

    range_notice = _number_system_range_notice(lang_code, number_system, numbers)

    return render_template(
        "numbers.html",
        lang_code=lang_code,
        get_text=get_text,
        has_learn_materials=has_learn_materials,
        has_audio_mode=lang_code in get_languages_with_audio_mode()
        and _system_has_audio(lang_code, number_system),
        deck_min=min(numbers),
        deck_max=max(numbers),
        magnitude_level=session.get("magnitude_level", 1),
        number_systems=_number_system_context(lang_code, number_system),
        number_system_range_notice=range_notice,
        # A deck that lives entirely under 100 weights every magnitude level
        # identically, so the dial would be a control that does nothing.
        show_magnitude=quiz_logic.spans_multiple_magnitudes(numbers),
    )


# ===== Printable worksheets =====
# A teacher configures a sheet at /<lang>/worksheet, prints it on paper and
# hands it out. Everything on the sheet is a pure function of the URL
# (language, range, count, direction, seed), so re-opening that URL next term
# reprints the identical sheet — answer key included. Every number word is
# read straight out of the language's verified NUMBERS deck; nothing here
# builds a number word from rules.

WORKSHEET_PARAM_KEYS = (
    "count",
    "direction",
    "format",
    "range",
    "min",
    "max",
    "seed",
)

# `?format=pdf` renders the sheet server-side; anything else is the HTML page.
WORKSHEET_FORMAT_PDF = "pdf"
WORKSHEET_FORMATS = ("html", WORKSHEET_FORMAT_PDF)

# URL value -> internal direction. The short aliases are for a hand-typed URL.
WORKSHEET_DIRECTIONS = {
    "digits_to_words": "digits_to_words",
    "words_to_digits": "words_to_digits",
    "to_words": "digits_to_words",
    "to_digits": "words_to_digits",
}
WORKSHEET_DEFAULT_DIRECTION = "digits_to_words"

WORKSHEET_COUNT_DEFAULT = 20
WORKSHEET_COUNT_MIN = 1
WORKSHEET_COUNT_MAX = 60

# Sheet IDs get read off a printout and retyped, so the alphabet leaves out
# the characters that look alike in print (0/o, 1/l).
WORKSHEET_SEED_ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"
WORKSHEET_SEED_LENGTH = 6

# What we accept back as a seed. Anything else is treated as no seed at all.
_WORKSHEET_SEED_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$")

# Answer lengths above these stop fitting in a column on a portrait page, so
# the sheet drops to fewer, wider columns.
WORKSHEET_TWO_COLUMN_MAX_CHARS = 28
WORKSHEET_KEY_THREE_COLUMN_MAX_CHARS = 18
WORKSHEET_KEY_TWO_COLUMN_MAX_CHARS = 40


def _text_for_language(lang_code):
    """``get_text`` bound to one learn language.

    Worksheet pages are anonymous and stateless — the language comes from the
    URL, not the session — so LANGUAGE_NAME_PLACEHOLDER has to be resolved
    against `lang_code` explicitly.
    """

    def text(key):
        return get_text(key, learn_language=lang_code)

    return text


def _worksheet_pdf_bytes(html):
    """Render a worksheet's HTML to PDF bytes. Raises if PDF support is broken.

    WeasyPrint is imported here rather than at module scope so a machine
    without its native libraries (pango/harfbuzz) still boots the whole app —
    only the PDF path fails, and the route degrades to the HTML sheet.

    The stylesheet is handed over from disk instead of being left as a <link>
    in the template: its URL is an app route, and letting the PDF renderer
    fetch it over HTTP would have a worker call back into itself.
    """
    from weasyprint import CSS, HTML

    stylesheet = os.path.join(app.static_folder, "css", "worksheet.css")
    # base_url is the static dir so any future relative asset resolves from
    # disk; url_fetcher is never asked for an http:// URL as things stand.
    return HTML(string=html, base_url=app.static_folder).write_pdf(
        stylesheets=[CSS(filename=stylesheet)]
    )


# ===== Worksheet PDF cache and render budget =====
# A rendered sheet is a pure function of (language, UI language, direction,
# count, range, seed) — the same property the byte-identical test pins — so it
# can be cached and served without going near WeasyPrint.
#
# This is not only a speed-up. One sheet costs roughly 0.8s (10 exercises) to
# 6.5s (the 60-exercise maximum) of CPU, dominated by the multi-column
# balancing in worksheet.css; prod runs three *sync* gunicorn workers, and the
# route is anonymous. Three concurrent renders and the site serves nothing else
# — not a quiz, not /login. The cache absorbs genuine repeat traffic (a teacher
# reloading, a portal re-downloading, the batch tool re-running) and the budget
# below bounds what a script asking for endless fresh seeds can take.
#
# The cache lives under instance/, which prod bind-mounts, so all three workers
# share one copy of it and it survives a restart.
WORKSHEET_PDF_CACHE_MAX_FILES = 2000
_WORKSHEET_PDF_BUDGET_WINDOW = 60.0

# A cache dir of None disables caching and a budget of 0 disables the limit.
# The tests want a real render every time, and for the batch tool spending the
# CPU is the entire point of running it.
app.config.setdefault(
    "WORKSHEET_PDF_CACHE_DIR", os.path.join(app.instance_path, "worksheet_pdf")
)
app.config.setdefault(
    "WORKSHEET_PDF_BUDGET", int(os.getenv("WORKSHEET_PDF_BUDGET", "10"))
)

_worksheet_pdf_renders = deque()
_worksheet_pdf_lock = threading.Lock()


def _worksheet_pdf_cache_key(lang_code, sheet):
    """Everything the rendered bytes depend on, hashed.

    The UI language belongs in the key: the sheet's chrome — the instructions,
    the Name/Class/Date labels — is rendered in it, so an English and a German
    request for the same sheet are different documents. So does the numeral
    system: the same numbers in traditional Welsh are entirely different words,
    and serving one from the other's cache entry would print the wrong sheet.
    """
    parts = (
        lang_code,
        sheet.get("system") or "",
        session.get("language", DEFAULT_UI_LANGUAGE),
        sheet["direction"],
        str(sheet["count"]),
        f"{sheet['range_low']}-{sheet['range_high']}",
        sheet["seed"],
    )
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _worksheet_pdf_cached(key):
    """The cached bytes for this sheet, or None when it isn't cached."""
    cache_dir = app.config["WORKSHEET_PDF_CACHE_DIR"]
    if not cache_dir:
        return None
    try:
        with open(os.path.join(cache_dir, f"{key}.pdf"), "rb") as handle:
            return handle.read()
    except OSError:
        return None


def _worksheet_pdf_store(key, pdf):
    """Cache a rendered sheet. Never raises — a full disk must not 500."""
    cache_dir = app.config["WORKSHEET_PDF_CACHE_DIR"]
    if not cache_dir:
        return
    try:
        os.makedirs(cache_dir, exist_ok=True)
        # Write somewhere unique and rename into place: with three workers on
        # one directory, a reader must never catch a half-written file.
        tmp = os.path.join(cache_dir, f".{key}.{os.getpid()}")
        with open(tmp, "wb") as handle:
            handle.write(pdf)
        os.replace(tmp, os.path.join(cache_dir, f"{key}.pdf"))
        _worksheet_pdf_trim(cache_dir)
    except OSError:
        app.logger.warning("Could not cache worksheet PDF", exc_info=True)


def _worksheet_pdf_trim(cache_dir):
    """Bound the cache, oldest out first."""
    entries = [e for e in os.scandir(cache_dir) if e.name.endswith(".pdf")]
    if len(entries) <= WORKSHEET_PDF_CACHE_MAX_FILES:
        return
    entries.sort(key=lambda entry: entry.stat().st_mtime)
    for entry in entries[: len(entries) - WORKSHEET_PDF_CACHE_MAX_FILES]:
        try:
            os.unlink(entry.path)
        except OSError:
            pass


def _worksheet_pdf_budget_ok():
    """Whether this worker may spend CPU on another render right now."""
    budget = app.config["WORKSHEET_PDF_BUDGET"]
    if not budget:
        return True
    now = time.monotonic()
    with _worksheet_pdf_lock:
        while (
            _worksheet_pdf_renders
            and now - _worksheet_pdf_renders[0] > _WORKSHEET_PDF_BUDGET_WINDOW
        ):
            _worksheet_pdf_renders.popleft()
        if len(_worksheet_pdf_renders) >= budget:
            return False
        _worksheet_pdf_renders.append(now)
        return True


def _worksheet_pdf_filename(lang_code, sheet):
    """A filename a teacher can tell apart in a downloads folder.

    Carries the direction as well as the range: a batch run drops both
    directions of the same range into one directory.
    """
    span = f"{sheet['range_low']}-{sheet['range_high']}"
    direction = sheet["direction"].replace("_", "-")
    return f"diminumero-{lang_code}-numbers-{span}-{direction}-{sheet['seed']}.pdf"


def _mint_worksheet_seed():
    """A fresh sheet ID."""
    return "".join(
        secrets.choice(WORKSHEET_SEED_ALPHABET) for _ in range(WORKSHEET_SEED_LENGTH)
    )


def _worksheet_rng(seed):
    """The random generator a sheet's seed fixes.

    Hashing the seed here, rather than handing the string to random.seed(),
    keeps the draw independent of how CPython happens to turn text into
    Mersenne Twister state — a sheet printed today must reprint identically
    after an interpreter upgrade.
    """
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def _worksheet_range_arg(numbers):
    """The requested range as a "min-max" string, from either spelling.

    The setup form submits two number inputs (min/max) so it needs no JS; a
    hand-written link more likely carries the same `range=1-100` the drill
    links use. A one-sided form entry is completed from the deck's bounds.
    """
    raw = request.args.get("range")
    if raw is not None and raw.strip():
        return raw
    low = (request.args.get("min") or "").strip()
    high = (request.args.get("max") or "").strip()
    if not low and not high:
        return None
    return f"{low or min(numbers)}-{high or max(numbers)}"


def _parse_worksheet_range(value, numbers):
    """Parse a "min-max" range against what the language actually has.

    Returns (range_or_None, notice_key_or_None). Decks are sparse above 1000,
    so a syntactically fine range can still contain no numbers at all — that
    falls back to the whole deck just like garbage does.
    """
    if value is None:
        return None, None

    match = _RANGE_RE.match(value.strip())
    if not match:
        return None, "worksheet_notice_range"

    low, high = int(match.group(1)), int(match.group(2))
    if low > high:
        low, high = high, low

    if not _numbers_in_range(numbers, (low, high)):
        return None, "worksheet_notice_range_empty"

    return (low, high), None


def _parse_worksheet_count(value):
    """Parse the exercise count. Returns (count, notice_key_or_None).

    A field the teacher left blank is not a mistake — it just means "default".
    """
    if value is None or not str(value).strip():
        return WORKSHEET_COUNT_DEFAULT, None
    try:
        count = int(value)
    except (TypeError, ValueError):
        return WORKSHEET_COUNT_DEFAULT, "worksheet_notice_count"
    if count < WORKSHEET_COUNT_MIN:
        return WORKSHEET_COUNT_MIN, "worksheet_notice_count"
    if count > WORKSHEET_COUNT_MAX:
        return WORKSHEET_COUNT_MAX, "worksheet_notice_count"
    return count, None


def _build_worksheet(numbers, seed):
    """Resolve the query params into a sheet. Never raises.

    The draw is a shuffle of the in-range numbers seeded from `seed` alone, so
    the same seed and range always produce the same sequence and the exercise
    count only decides how much of it gets printed.
    """
    notice_keys = []

    raw_direction = (request.args.get("direction") or "").strip().lower()
    direction = WORKSHEET_DIRECTIONS.get(raw_direction, WORKSHEET_DEFAULT_DIRECTION)
    if raw_direction and raw_direction not in WORKSHEET_DIRECTIONS:
        notice_keys.append("worksheet_notice_direction")

    raw_format = (request.args.get("format") or "").strip().lower()
    sheet_format = raw_format if raw_format in WORKSHEET_FORMATS else "html"
    if raw_format and raw_format not in WORKSHEET_FORMATS:
        notice_keys.append("worksheet_notice_format")

    num_range, range_notice = _parse_worksheet_range(
        _worksheet_range_arg(numbers), numbers
    )
    if range_notice:
        notice_keys.append(range_notice)

    count, count_notice = _parse_worksheet_count(request.args.get("count"))
    if count_notice:
        notice_keys.append(count_notice)

    pool = sorted(_numbers_in_range(numbers, num_range))
    if count > len(pool):
        count = len(pool)
        notice_keys.append("worksheet_notice_count_capped")

    rng = _worksheet_rng(seed)
    rng.shuffle(pool)

    # The words come from the deck, never from a rule.
    exercises = [
        {"index": index, "number": number, "word": numbers[number]}
        for index, number in enumerate(pool[:count], start=1)
    ]

    longest = max((len(item["word"]) for item in exercises), default=0)
    low, high = num_range if num_range else (min(numbers), max(numbers))

    return {
        "exercises": exercises,
        "direction": direction,
        "format": sheet_format,
        "count": count,
        "range": num_range,
        "range_low": low,
        "range_high": high,
        "seed": seed,
        "columns": 2 if longest <= WORKSHEET_TWO_COLUMN_MAX_CHARS else 1,
        "key_columns": (
            3
            if longest <= WORKSHEET_KEY_THREE_COLUMN_MAX_CHARS
            else 2
            if longest <= WORKSHEET_KEY_TWO_COLUMN_MAX_CHARS
            else 1
        ),
        "notice_keys": notice_keys,
    }


@app.route("/<lang_code>/worksheet")
def worksheet(lang_code):
    """Printable number worksheet: the setup form, or the sheet it describes.

    Anonymous GET, no login and no session state — a teacher must be able to
    open, print and re-open this from any browser. With no worksheet params
    this is the setup form; with params it is the sheet itself, rendered from
    a standalone print template (no nav, no ads, no cookie banner).
    """
    if not is_language_ready(lang_code):
        flash(get_text("flash_invalid_language"), "error")
        return redirect(url_for("index"))

    # Worksheets are anonymous and stateless, so the numeral system comes from
    # the URL rather than the session — a printed sheet has to be reproducible
    # from its link alone.
    system = resolve_number_system(lang_code, request.args.get("system"))
    system_arg = system if system != get_default_number_system(lang_code) else None

    try:
        numbers = get_language_numbers(lang_code, system)
    except ValueError:
        flash(get_text("flash_language_load_error"), "error")
        return redirect(url_for("index"))

    text = _text_for_language(lang_code)

    if not any(key in request.args for key in WORKSHEET_PARAM_KEYS):
        return render_template(
            "worksheet.html",
            lang_code=lang_code,
            get_text=text,
            deck_min=min(numbers),
            deck_max=max(numbers),
            total_numbers=len(numbers),
            count_default=WORKSHEET_COUNT_DEFAULT,
            count_min=WORKSHEET_COUNT_MIN,
            count_max=WORKSHEET_COUNT_MAX,
            default_direction=WORKSHEET_DEFAULT_DIRECTION,
            number_systems=_number_system_context(lang_code, system),
        )

    # A sheet with no seed can't be reprinted, so mint one and bounce to the
    # URL that can. Only the seed changes, so the teacher lands on the sheet
    # they asked for and the address bar now holds the reprintable link.
    seed = (request.args.get("seed") or "").strip()
    if not _WORKSHEET_SEED_RE.match(seed):
        carried = {
            key: value
            for key, value in request.args.items()
            if key in WORKSHEET_PARAM_KEYS and key != "seed"
        }
        return redirect(
            url_for(
                "worksheet",
                lang_code=lang_code,
                seed=_mint_worksheet_seed(),
                system=system_arg,
                **carried,
            )
        )

    sheet = _build_worksheet(numbers, seed)
    sheet["system"] = system
    notices = [text(key) for key in sheet["notice_keys"]]

    # The footer prints the canonical spelling of this sheet's URL, so a
    # printout is enough to get the sheet back even without the original link.
    # The PDF and the page share it: both are the same sheet.
    canonical_args = {
        "count": sheet["count"],
        "direction": sheet["direction"],
        "range": (
            f"{sheet['range'][0]}-{sheet['range'][1]}" if sheet["range"] else None
        ),
        # Carried so a reprint of a non-default system's sheet prints the same
        # words; omitted for the default system, which keeps every existing
        # worksheet URL byte-for-byte what it was.
        "system": system_arg,
        "seed": sheet["seed"],
    }
    sheet_path = url_for("worksheet", lang_code=lang_code, **canonical_args)
    sheet_url = SITE_URL.rstrip("/") + sheet_path

    # Notes ride along on the answer key, never on the exercise side: the key
    # is the page the teacher reads, and it already carries every answer.
    sheet_notes = get_notes(
        lang_code,
        system=system,
        numbers=[item["number"] for item in sheet["exercises"]],
        when="reference",
        ui_lang=session.get("language", DEFAULT_UI_LANGUAGE),
    )

    if sheet["format"] == WORKSHEET_FORMAT_PDF:
        cache_key = _worksheet_pdf_cache_key(lang_code, sheet)
        pdf = _worksheet_pdf_cached(cache_key)

        if pdf is None and not _worksheet_pdf_budget_ok():
            # This worker has rendered enough for one minute. A render holds a
            # sync worker for seconds, so past the budget the printable page —
            # which does the same job through the browser — is a far better
            # answer than queueing more CPU ahead of everyone else's request.
            notices = notices + [text("worksheet_notice_pdf_failed")]
        elif pdf is None:
            try:
                pdf = _worksheet_pdf_bytes(
                    render_template(
                        "worksheet_sheet.html",
                        lang_code=lang_code,
                        get_text=text,
                        sheet=sheet,
                        notices=[],
                        sheet_url=sheet_url,
                        notes=sheet_notes,
                        pdf_mode=True,
                    )
                )
            except Exception:
                # A missing native library or font must not take the feature
                # down: the printable page does the same job in the browser.
                app.logger.exception("Worksheet PDF rendering failed for %s", lang_code)
                notices = notices + [text("worksheet_notice_pdf_failed")]
            else:
                _worksheet_pdf_store(cache_key, pdf)

        if pdf is not None:
            return Response(
                pdf,
                mimetype="application/pdf",
                headers={
                    "Content-Disposition": (
                        "attachment; "
                        f'filename="{_worksheet_pdf_filename(lang_code, sheet)}"'
                    )
                },
            )

    return render_template(
        "worksheet_sheet.html",
        lang_code=lang_code,
        get_text=text,
        sheet=sheet,
        notices=notices,
        sheet_url=sheet_url,
        notes=sheet_notes,
        pdf_url=url_for(
            "worksheet", lang_code=lang_code, format="pdf", **canonical_args
        ),
    )


@app.route("/set_language/<lang>")
def set_language(lang):
    """Set the UI language preference (not learning language)."""
    if lang in SUPPORTED_UI_LANGUAGES:
        session["language"] = lang
    # Redirect back to the referring page or index
    return redirect(request.referrer or url_for("index"))


def _results_redirect(lang_code):
    """Redirect to results, marking session for splash overlays if earned."""
    quiz_start_time = session.get("quiz_start_time")
    elapsed = time.time() - quiz_start_time if quiz_start_time else None
    mode = session.get("mode", "easy")
    speed_limits = {
        "easy": SPEED_BONUS_TIME_EASY,
        "advanced": SPEED_BONUS_TIME_ADVANCED,
        "hardcore": SPEED_BONUS_TIME_HARDCORE,
        "audio": SPEED_BONUS_TIME_ADVANCED,
    }
    speed_limit = speed_limits.get(mode, SPEED_BONUS_TIME_EASY)

    score = session.get("score", 0)
    score_percentage = (
        (score / QUESTIONS_PER_QUIZ) * 100 if QUESTIONS_PER_QUIZ > 0 else 0
    )

    if score_percentage == 100:
        session["show_perfect_splash"] = True
    if elapsed is not None and elapsed < speed_limit and score_percentage > 80:
        session["show_speed_splash"] = True

    return redirect(url_for("results", lang_code=lang_code))


@app.route("/<lang_code>/start", methods=["POST"])
def start_quiz(lang_code):
    """Initialize a new quiz session."""
    # Validate language code
    if not is_language_ready(lang_code):
        flash(get_text("flash_invalid_language"), "error")
        return redirect(url_for("index"))

    # Get mode from form (default to easy if not specified)
    mode = request.form.get("mode", "easy")

    # Validate mode
    if mode not in ["easy", "advanced", "hardcore"]:
        flash(get_text("flash_invalid_mode"), "error")
        return redirect(url_for("mode_selection", lang_code=lang_code))

    # Read magnitude level from form, validate (int 1-5, default 1)
    magnitude_level, _ = _parse_magnitude(request.form.get("magnitude_level"))

    # The share-link builder on the config screen also feeds its range and
    # numeral system into these forms, so pressing Start gives the teacher the
    # same drill the link they just copied produces.
    system = resolve_number_system(
        lang_code, request.form.get("system") or session.get("number_system")
    )
    try:
        numbers = get_language_numbers(lang_code, system)
    except ValueError:
        flash(get_text("flash_language_load_error"), "error")
        return redirect(url_for("mode_selection", lang_code=lang_code))
    num_range, _ = _parse_range(request.form.get("range"), numbers)

    _seed_quiz_session(lang_code, mode, magnitude_level, num_range, system)

    # Redirect to appropriate quiz
    if mode == "easy":
        return redirect(url_for("quiz_easy", lang_code=lang_code))
    elif mode == "advanced":
        return redirect(url_for("quiz_advanced", lang_code=lang_code))
    elif mode == "hardcore":
        return redirect(url_for("quiz_hardcore", lang_code=lang_code))


@app.route("/<lang_code>/quiz/easy", methods=["GET", "POST"])
def quiz_easy(lang_code):
    """Easy mode quiz page - multiple choice with 4 options."""

    # Validate language and session
    if not is_language_ready(lang_code) or session.get("learn_language") != lang_code:
        return redirect(url_for("index"))

    # Ensure user is in easy mode
    if session.get("mode") != "easy":
        return redirect(url_for("mode_selection", lang_code=lang_code))

    # Load numbers for this language (narrowed to a shared link's range)
    try:
        numbers = _session_numbers(lang_code)
    except ValueError:
        flash(get_text("flash_language_load_error"), "error")
        return redirect(url_for("mode_selection", lang_code=lang_code))

    if request.method == "POST":
        # Process the submitted answer
        user_answer = request.form.get("answer")
        correct_answer = session.get("correct_answer")
        if user_answer and correct_answer:
            is_correct = quiz_logic.check_answer(user_answer, correct_answer)

            if is_correct:
                session["score"] = session.get("score", 0) + 1
                flash(
                    get_text("flash_correct").format(
                        get_feedback_expression(lang_code)
                    ),
                    "success",
                )
            else:
                flash(get_text("flash_incorrect").format(correct_answer), "error")

            session["total_questions"] = session.get("total_questions", 0) + 1

        # Clear current question so next GET generates a new one
        session.pop("current_number", None)
        session.pop("correct_answer", None)
        session.pop("current_options", None)  # Clear options too

        # Check if quiz is complete
        if session.get("total_questions", 0) >= QUESTIONS_PER_QUIZ:
            return _results_redirect(lang_code)

        # Continue to next question
        return redirect(url_for("quiz_easy", lang_code=lang_code))

    # GET request - display question
    # Check if quiz should end
    # End the quiz only once no question is still mounted. After a reveal the
    # current question stays in the session (with total already incremented) so
    # it must still render; the "next" POST is what clears it and ends the round.
    if (
        "current_number" not in session
        and session.get("total_questions", 0) >= QUESTIONS_PER_QUIZ
    ):
        return redirect(url_for("results", lang_code=lang_code))

    # Check if we already have a current question (page refresh)
    if (
        "current_number" in session
        and "correct_answer" in session
        and "current_options" in session
    ):
        number = session["current_number"]
        correct_answer = session["correct_answer"]
        options = session["current_options"]
    else:
        # Generate new question
        asked_numbers = session.get("asked_numbers", [])
        number, correct_answer = quiz_logic.get_random_question(
            numbers,
            asked_numbers,
            magnitude_level=session.get("magnitude_level", 1),
            usage_weights=_session_usage_weights(lang_code),
        )

        # Generate multiple choice options
        options = quiz_logic.generate_multiple_choice(numbers, number, correct_answer)

        # Store in session
        session["current_number"] = number
        session["correct_answer"] = correct_answer
        session["current_options"] = options

        # Update asked numbers
        if "asked_numbers" not in session:
            session["asked_numbers"] = []
        session["asked_numbers"].append(number)

    # Get current progress
    score = session.get("score", 0)
    total = session.get("total_questions", 0)

    return render_template(
        "quiz_easy.html",
        number=number,
        options=options,
        score=score,
        total=total,
        max_questions=QUESTIONS_PER_QUIZ,
        lang_code=lang_code,
        get_text=get_text,
        notes=_notes_for(lang_code, number, "prompt"),
    )


@app.route("/<lang_code>/quiz/advanced", methods=["GET", "POST"])
def quiz_advanced(lang_code):
    """Advanced mode quiz page - text input with live validation."""

    # Validate language and session
    if not is_language_ready(lang_code) or session.get("learn_language") != lang_code:
        return redirect(url_for("index"))

    # Ensure user is in advanced mode
    if session.get("mode") != "advanced":
        return redirect(url_for("mode_selection", lang_code=lang_code))

    # Load numbers for this language (narrowed to a shared link's range)
    try:
        numbers = _session_numbers(lang_code)
    except ValueError:
        flash(get_text("flash_language_load_error"), "error")
        return redirect(url_for("mode_selection", lang_code=lang_code))

    if request.method == "POST":
        # Two-step reveal: mark the question as revealed and re-render the same
        # question so the modal can show the answer. Counts as a wrong attempt.
        if "reveal" in request.form:
            session["total_questions"] = session.get("total_questions", 0) + 1
            session["current_revealed"] = True
            return redirect(url_for("quiz_advanced", lang_code=lang_code))

        # Advance from a revealed question. The wrong attempt was already
        # recorded; the user must retype the shown answer before advancing (the
        # client enforces this too, but never trust the client). A wrong or
        # empty answer keeps the question mounted and revealed.
        if "next" in request.form:
            user_answer = request.form.get("answer", "").strip()
            correct_answer = session.get("correct_answer")
            if not (
                user_answer
                and correct_answer
                and quiz_logic.check_answer_advanced(user_answer, correct_answer)
            ):
                return redirect(url_for("quiz_advanced", lang_code=lang_code))
            session["current_revealed"] = False
            session.pop("current_number", None)
            session.pop("correct_answer", None)
            if session.get("total_questions", 0) >= QUESTIONS_PER_QUIZ:
                return _results_redirect(lang_code)
            return redirect(url_for("quiz_advanced", lang_code=lang_code))

        # Process the submitted answer
        user_answer = request.form.get("answer", "").strip()
        correct_answer = session.get("correct_answer")

        if user_answer and correct_answer:
            # Use word-by-word validation for final check
            is_correct = quiz_logic.check_answer_advanced(user_answer, correct_answer)

            if is_correct:
                session["score"] = session.get("score", 0) + 1
                flash(
                    get_text("flash_correct").format(
                        get_feedback_expression(lang_code)
                    ),
                    "success",
                )
            else:
                flash(get_text("flash_incorrect").format(correct_answer), "error")
                # If the answer is this number's word in the language's *other*
                # numeral system it isn't wrong Welsh, it is the wrong system —
                # say which, rather than leaving a correct word marked simply
                # incorrect.
                nudge = _wrong_system_flash(
                    lang_code, session.get("current_number"), user_answer
                )
                if nudge:
                    flash(nudge, "info")

            session["total_questions"] = session.get("total_questions", 0) + 1

        # Clear current question so next GET generates a new one
        session.pop("current_number", None)
        session.pop("correct_answer", None)
        session["current_revealed"] = False

        # Check if quiz is complete
        if session.get("total_questions", 0) >= QUESTIONS_PER_QUIZ:
            return _results_redirect(lang_code)

        # Continue to next question
        return redirect(url_for("quiz_advanced", lang_code=lang_code))

    # GET request - display question
    # Check if quiz should end
    # End the quiz only once no question is still mounted. After a reveal the
    # current question stays in the session (with total already incremented) so
    # it must still render; the "next" POST is what clears it and ends the round.
    if (
        "current_number" not in session
        and session.get("total_questions", 0) >= QUESTIONS_PER_QUIZ
    ):
        return redirect(url_for("results", lang_code=lang_code))

    # Check if we already have a current question (page refresh)
    if "current_number" in session and "correct_answer" in session:
        number = session["current_number"]
        correct_answer = session["correct_answer"]
    else:
        # Generate new question
        asked_numbers = session.get("asked_numbers", [])
        number, correct_answer = quiz_logic.get_random_question(
            numbers,
            asked_numbers,
            magnitude_level=session.get("magnitude_level", 1),
            usage_weights=_session_usage_weights(lang_code),
        )

        # Store in session
        session["current_number"] = number
        session["correct_answer"] = correct_answer

        # Update asked numbers
        if "asked_numbers" not in session:
            session["asked_numbers"] = []
        session["asked_numbers"].append(number)

    # Get current progress
    score = session.get("score", 0)
    total = session.get("total_questions", 0)

    revealed = bool(session.get("current_revealed"))

    return render_template(
        "quiz_advanced.html",
        number=number,
        correct_answer=correct_answer,
        revealed=revealed,
        score=score,
        total=total,
        max_questions=QUESTIONS_PER_QUIZ,
        lang_code=lang_code,
        get_text=get_text,
        # Once the answer is on screen there is nothing left to give away, so
        # the reveal is where a note can finally say what it knows.
        notes=_notes_for(lang_code, number, "revealed" if revealed else "prompt"),
    )


@app.route("/api/validate", methods=["POST"])
def validate_answer():
    """API endpoint for live validation of user input."""
    user_input = request.json.get("input", "")
    correct_answer = session.get("correct_answer", "")
    lang_code = session.get("learn_language", "")

    if not correct_answer:
        return jsonify({"error": "No active question"}), 400

    if not lang_code:
        return jsonify({"error": "No active language"}), 400

    validation = quiz_logic.validate_partial_answer(
        user_input, correct_answer, lang_code
    )

    return jsonify(validation)


@app.route("/<lang_code>/quiz/hardcore", methods=["GET", "POST"])
def quiz_hardcore(lang_code):
    """Hardcore mode quiz page - text input without intermediate feedback."""

    # Validate language and session
    if not is_language_ready(lang_code) or session.get("learn_language") != lang_code:
        return redirect(url_for("index"))

    # Ensure user is in hardcore mode
    if session.get("mode") != "hardcore":
        return redirect(url_for("mode_selection", lang_code=lang_code))

    # Load numbers for this language (narrowed to a shared link's range)
    try:
        numbers = _session_numbers(lang_code)
    except ValueError:
        flash(get_text("flash_language_load_error"), "error")
        return redirect(url_for("mode_selection", lang_code=lang_code))

    if request.method == "POST":
        # Two-step reveal: mark the question as revealed and re-render the same
        # question so the modal can show the answer. Counts as a wrong attempt.
        if "reveal" in request.form:
            session["total_questions"] = session.get("total_questions", 0) + 1
            session["current_revealed"] = True
            return redirect(url_for("quiz_hardcore", lang_code=lang_code))

        # Advance from a revealed question. The wrong attempt was already
        # recorded; the user must retype the shown answer before advancing (the
        # client enforces this too, but never trust the client). A wrong or
        # empty answer keeps the question mounted and revealed.
        if "next" in request.form:
            user_answer = request.form.get("answer", "").strip()
            correct_answer = session.get("correct_answer")
            if not (
                user_answer
                and correct_answer
                and quiz_logic.check_answer_advanced(user_answer, correct_answer)
            ):
                return redirect(url_for("quiz_hardcore", lang_code=lang_code))
            session["current_revealed"] = False
            session.pop("current_number", None)
            session.pop("correct_answer", None)
            if session.get("total_questions", 0) >= QUESTIONS_PER_QUIZ:
                return _results_redirect(lang_code)
            return redirect(url_for("quiz_hardcore", lang_code=lang_code))

        # Process the submitted answer
        user_answer = request.form.get("answer", "").strip()
        correct_answer = session.get("correct_answer")

        if user_answer and correct_answer:
            # Use advanced validation for final check
            is_correct = quiz_logic.check_answer_advanced(user_answer, correct_answer)

            if is_correct:
                session["score"] = session.get("score", 0) + 1
                flash(
                    get_text("flash_correct").format(
                        get_feedback_expression(lang_code)
                    ),
                    "success",
                )
            else:
                flash(get_text("flash_incorrect").format(correct_answer), "error")
                nudge = _wrong_system_flash(
                    lang_code, session.get("current_number"), user_answer
                )
                if nudge:
                    flash(nudge, "info")

            session["total_questions"] = session.get("total_questions", 0) + 1

        # Clear current question so next GET generates a new one
        session.pop("current_number", None)
        session.pop("correct_answer", None)
        session["current_revealed"] = False

        # Check if quiz is complete
        if session.get("total_questions", 0) >= QUESTIONS_PER_QUIZ:
            return _results_redirect(lang_code)

        # Continue to next question
        return redirect(url_for("quiz_hardcore", lang_code=lang_code))

    # GET request - display question
    # Check if quiz should end
    # End the quiz only once no question is still mounted. After a reveal the
    # current question stays in the session (with total already incremented) so
    # it must still render; the "next" POST is what clears it and ends the round.
    if (
        "current_number" not in session
        and session.get("total_questions", 0) >= QUESTIONS_PER_QUIZ
    ):
        return redirect(url_for("results", lang_code=lang_code))

    # Check if we already have a current question (page refresh)
    if "current_number" in session and "correct_answer" in session:
        number = session["current_number"]
        correct_answer = session["correct_answer"]
    else:
        # Generate new question
        asked_numbers = session.get("asked_numbers", [])
        number, correct_answer = quiz_logic.get_random_question(
            numbers,
            asked_numbers,
            magnitude_level=session.get("magnitude_level", 1),
            usage_weights=_session_usage_weights(lang_code),
        )

        # Store in session
        session["current_number"] = number
        session["correct_answer"] = correct_answer

        # Update asked numbers
        if "asked_numbers" not in session:
            session["asked_numbers"] = []
        session["asked_numbers"].append(number)

    # Get current progress
    score = session.get("score", 0)
    total = session.get("total_questions", 0)

    revealed = bool(session.get("current_revealed"))

    return render_template(
        "quiz_hardcore.html",
        number=number,
        correct_answer=correct_answer,
        revealed=revealed,
        score=score,
        total=total,
        max_questions=QUESTIONS_PER_QUIZ,
        lang_code=lang_code,
        get_text=get_text,
        notes=_notes_for(lang_code, number, "revealed" if revealed else "prompt"),
    )


def _available_audio_numbers(lang_code):
    """Return the set of numbers (ints) we have a pre-generated MP3 for."""
    audio_dir = Path(app.static_folder) / "audio" / lang_code
    if not audio_dir.is_dir():
        return set()
    numbers = set()
    for path in audio_dir.glob("*.mp3"):
        try:
            numbers.add(int(path.stem))
        except ValueError:
            continue
    return numbers


@app.route("/<lang_code>/listen/start", methods=["POST"])
def listen_start(lang_code):
    """Initialize a new Listening session."""
    if (
        not is_language_ready(lang_code)
        or lang_code not in get_languages_with_audio_mode()
    ):
        flash(get_text("flash_invalid_language"), "error")
        return redirect(url_for("index"))

    magnitude_level, _ = _parse_magnitude(request.form.get("magnitude_level"))

    # Audio is per language, not per numeral system: a system without MP3s
    # (traditional Welsh) listens on the default deck instead.
    _seed_quiz_session(
        lang_code, "audio", magnitude_level, system=_audio_number_system(lang_code)
    )

    return redirect(url_for("listen_quiz", lang_code=lang_code))


@app.route("/<lang_code>/listen", methods=["GET", "POST"])
def listen_quiz(lang_code):
    """Listening quiz: play a number, user types the digits."""
    if (
        not is_language_ready(lang_code)
        or lang_code not in get_languages_with_audio_mode()
    ):
        return redirect(url_for("index"))

    if session.get("learn_language") != lang_code or session.get("mode") != "audio":
        return redirect(url_for("mode_selection", lang_code=lang_code))

    try:
        numbers = _session_numbers(lang_code)
    except ValueError:
        flash(get_text("flash_language_load_error"), "error")
        return redirect(url_for("mode_selection", lang_code=lang_code))

    playable_numbers = _playable_audio_numbers(lang_code, numbers)
    if not playable_numbers:
        flash(get_text("flash_audio_missing"), "error")
        return redirect(url_for("mode_selection", lang_code=lang_code))

    if request.method == "POST":
        if "reveal" in request.form:
            session["total_questions"] = session.get("total_questions", 0) + 1
            session["current_revealed"] = True
            return redirect(url_for("listen_quiz", lang_code=lang_code))

        if "next" in request.form:
            session["current_revealed"] = False
            session.pop("current_number", None)
            session.pop("correct_answer", None)
            if session.get("total_questions", 0) >= QUESTIONS_PER_QUIZ:
                return _results_redirect(lang_code)
            return redirect(url_for("listen_quiz", lang_code=lang_code))

        raw_answer = request.form.get("answer", "")
        digits = re.sub(r"\D", "", raw_answer)
        current_number = session.get("current_number")
        correct_word = session.get("correct_answer")

        if digits and current_number is not None:
            if int(digits) == current_number:
                session["score"] = session.get("score", 0) + 1
                flash(
                    get_text("flash_correct").format(
                        get_feedback_expression(lang_code)
                    ),
                    "success",
                )
            else:
                flash(
                    get_text("flash_incorrect_audio").format(
                        current_number, correct_word or ""
                    ),
                    "error",
                )
            session["total_questions"] = session.get("total_questions", 0) + 1

        session.pop("current_number", None)
        session.pop("correct_answer", None)
        session["current_revealed"] = False

        if session.get("total_questions", 0) >= QUESTIONS_PER_QUIZ:
            return _results_redirect(lang_code)

        return redirect(url_for("listen_quiz", lang_code=lang_code))

    # End the quiz only once no question is still mounted. After a reveal the
    # current question stays in the session (with total already incremented) so
    # it must still render; the "next" POST is what clears it and ends the round.
    if (
        "current_number" not in session
        and session.get("total_questions", 0) >= QUESTIONS_PER_QUIZ
    ):
        return redirect(url_for("results", lang_code=lang_code))

    if "current_number" in session and "correct_answer" in session:
        number = session["current_number"]
        correct_answer = session["correct_answer"]
    else:
        asked_numbers = session.get("asked_numbers", [])
        number, correct_answer = quiz_logic.get_random_question(
            playable_numbers,
            asked_numbers,
            magnitude_level=session.get("magnitude_level", 1),
            usage_weights=_session_usage_weights(lang_code),
        )
        session["current_number"] = number
        session["correct_answer"] = correct_answer
        if "asked_numbers" not in session:
            session["asked_numbers"] = []
        session["asked_numbers"].append(number)

    audio_url = url_for("static", filename=f"audio/{lang_code}/{number}.mp3")
    revealed = bool(session.get("current_revealed"))

    return render_template(
        "quiz_listen.html",
        number=number,
        correct_answer=correct_answer,
        audio_url=audio_url,
        revealed=revealed,
        score=session.get("score", 0),
        total=session.get("total_questions", 0),
        max_questions=QUESTIONS_PER_QUIZ,
        lang_code=lang_code,
        get_text=get_text,
        notes=_notes_for(lang_code, number, "revealed" if revealed else "prompt"),
    )


def _start_preset_drill(lang_code, numbers):
    """Render the drill described by the query params, in this response.

    Deliberately not a redirect: the student must land in the configured quiz
    from one cold GET, and the parameterised URL itself has to carry the
    canonical/noindex tags. The quiz's own forms post to the real quiz route,
    so from question 2 the drill runs on its canonical URL.
    """
    mode, magnitude_level, num_range, system, notices = _parse_preset(
        lang_code, numbers
    )
    _seed_quiz_session(lang_code, mode, magnitude_level, num_range, system)

    g.preset_notices = notices
    g.no_store = True

    views = {
        "easy": quiz_easy,
        "advanced": quiz_advanced,
        "hardcore": quiz_hardcore,
        "audio": listen_quiz,
    }
    return views[mode](lang_code)


@app.route("/<lang_code>/results")
def results(lang_code):
    """Display final quiz results."""
    # Validate language
    if not is_language_ready(lang_code) or session.get("learn_language") != lang_code:
        return redirect(url_for("index"))

    score = session.get("score", 0)
    attempted = session.get("total_questions", 0)
    max_questions = QUESTIONS_PER_QUIZ

    score_ratio = (score / max_questions) if max_questions > 0 else 0
    percentage = score_ratio * 100

    mode = session.get("mode", "easy")
    speed_limits = {
        "easy": SPEED_BONUS_TIME_EASY,
        "advanced": SPEED_BONUS_TIME_ADVANCED,
        "hardcore": SPEED_BONUS_TIME_HARDCORE,
        "audio": SPEED_BONUS_TIME_ADVANCED,
    }
    quiz_start_time = session.get("quiz_start_time")
    elapsed = time.time() - quiz_start_time if quiz_start_time else None
    speed_limit = speed_limits.get(mode, SPEED_BONUS_TIME_EASY)
    is_speed_bonus = elapsed is not None and elapsed < speed_limit and percentage > 80

    show_splash = session.pop("show_speed_splash", False)
    show_perfect_splash = session.pop("show_perfect_splash", False)

    has_learn_materials = lang_code in get_languages_with_learn_materials()

    return render_template(
        "results.html",
        score=score,
        attempted=attempted,
        max_questions=max_questions,
        score_ratio=score_ratio,
        percentage=percentage,
        lang_code=lang_code,
        has_learn_materials=has_learn_materials,
        is_speed_bonus=is_speed_bonus,
        show_splash=show_splash,
        show_perfect_splash=show_perfect_splash,
        get_text=get_text,
        # The round is over, so every note about the numbers it asked is safe
        # to show — and this is the one surface easy mode ever reaches, since
        # it has no reveal step.
        notes=_notes_for(lang_code, session.get("asked_numbers") or [], "revealed"),
    )


@app.route("/restart", methods=["POST"])
def restart():
    """Restart the quiz."""
    ui_language = session.get("language", DEFAULT_UI_LANGUAGE)
    saved_user = session.get("user")
    session.clear()
    session["language"] = ui_language
    if saved_user is not None:
        session["user"] = saved_user
    return redirect(url_for("index"))


@app.route("/privacy")
def privacy():
    """Display privacy policy page."""
    return render_template("privacy.html", get_text=get_text)


@app.route("/imprint")
def imprint():
    """Display imprint/impressum page."""
    return render_template("imprint.html", get_text=get_text)


@app.route("/about")
def about():
    """Display about page."""
    return render_template("about.html", get_text=get_text)


@app.route("/<lang_code>/learn")
def learn(lang_code):
    """Display learn/tutorial page for a specific language."""
    # Validate language
    if not is_language_ready(lang_code):
        return redirect(url_for("index"))

    if lang_code not in get_languages_with_learn_materials():
        flash(get_text("flash_learn_not_available"), "info")
        return redirect(url_for("mode_selection", lang_code=lang_code))

    ui_lang = session.get("language", DEFAULT_UI_LANGUAGE)
    template = f"learn_{lang_code}_{ui_lang}.html"

    # Fallback to English if template doesn't exist
    try:
        return render_template(template, lang_code=lang_code, get_text=get_text)
    except jinja2.TemplateNotFound:
        template = f"learn_{lang_code}_en.html"
        return render_template(template, lang_code=lang_code, get_text=get_text)


@app.route("/<lang_code>/learn/conjugations")
def learn_conjugations(lang_code):
    """Display the verb-conjugation learn page for a language (Spanish only today)."""
    if not is_language_ready(lang_code):
        return redirect(url_for("index"))

    if lang_code not in get_languages_with_conjugation_materials():
        flash(get_text("flash_learn_not_available"), "info")
        return redirect(url_for("mode_selection", lang_code=lang_code))

    ui_lang = session.get("language", DEFAULT_UI_LANGUAGE)
    template = f"learn_conjugations_{lang_code}_{ui_lang}.html"

    # Fallback to English if the UI-language variant doesn't exist.
    try:
        return render_template(template, lang_code=lang_code, get_text=get_text)
    except jinja2.TemplateNotFound:
        template = f"learn_conjugations_{lang_code}_en.html"
        return render_template(template, lang_code=lang_code, get_text=get_text)


@app.route("/login")
def login():
    """Redirect the user to Auth0 Universal Login."""
    return oauth.auth0.authorize_redirect(
        redirect_uri=url_for("callback", _external=True)
    )


@app.route("/callback")
def callback():
    """Handle the Auth0 OIDC callback and store the user on the session."""
    # OAuthError covers both upstream errors relayed by Auth0 (?error=...) and
    # Authlib's state mismatch (double login tabs, back button, lost session
    # cookie). Redirect to the index rather than /login: with an active Auth0
    # SSO session a persistent failure would otherwise redirect-loop.
    try:
        token = oauth.auth0.authorize_access_token()
    except OAuthError as exc:
        app.logger.warning("Auth0 callback failed: %s", exc)
        flash(get_text("flash_login_failed"), "error")
        return redirect(url_for("index"))
    session["user"] = token["userinfo"]
    # If the user was sent to /login from a share URL, route them back to it.
    pending_token = session.pop("pending_import_token", None)
    if pending_token:
        return redirect(url_for("cards_import", token=pending_token))
    return redirect(url_for("cards"))


@app.route("/logout")
def logout():
    """Clear the local session and bounce through Auth0's /v2/logout."""
    session.pop("user", None)
    domain = os.environ.get("AUTH0_DOMAIN")
    client_id = os.environ.get("AUTH0_CLIENT_ID")
    if not domain or not client_id:
        return redirect(url_for("index"))
    params = urlencode(
        {
            "returnTo": url_for("index", _external=True),
            "client_id": client_id,
        },
        quote_via=quote_plus,
    )
    return redirect(f"https://{domain}/v2/logout?{params}")


def _current_user_sub() -> str:
    """Return the Auth0 sub for the logged-in user; login_required guarantees presence."""
    return session["user"]["sub"]


def _user_card_or_404(card_id: int) -> Card:
    """Fetch a card and 404 if it does not belong to the current user."""
    card = db.session.get(Card, card_id)
    if card is None or card.user_sub != _current_user_sub():
        from flask import abort

        abort(404)
    return card


def _find_duplicate_card(
    user_sub: str, front: str, back: str, exclude_id: int | None = None
) -> Card | None:
    """Return the user's existing card whose normalized (front, back) matches, or None.

    Mirrors the dedup used by the deck-import flow so all write paths share one rule.
    """
    target = (quiz_logic.normalize_text(front), quiz_logic.normalize_text(back))
    query = db.session.query(Card).filter(Card.user_sub == user_sub)
    if exclude_id is not None:
        query = query.filter(Card.id != exclude_id)
    for card in query.all():
        if (
            quiz_logic.normalize_text(card.front),
            quiz_logic.normalize_text(card.back),
        ) == target:
            return card
    return None


@app.route("/cards")
@login_required
def cards():
    """List the user's index cards + create form."""
    user_cards = (
        db.session.query(Card)
        .filter_by(user_sub=_current_user_sub())
        .order_by(Card.created_at.desc())
        .all()
    )
    edit_id = request.args.get("edit", type=int)
    edit_card = None
    if edit_id is not None:
        candidate = db.session.get(Card, edit_id)
        if candidate is not None and candidate.user_sub == _current_user_sub():
            edit_card = candidate
    practice_lang = session.get("learn_language")
    if practice_lang and is_language_ready(practice_lang):
        practice_numbers_url = url_for("mode_selection", lang_code=practice_lang)
    else:
        practice_numbers_url = url_for("index")
    stats = _build_cards_dashboard_stats(user_cards)
    importable = _importable_card_verbs(_current_user_sub(), user_cards)
    importable_verbs = {
        card.id: {"lang": lang, "infinitive": inf} for card, lang, inf in importable
    }
    return render_template(
        "cards.html",
        user=session["user"],
        cards=user_cards,
        edit_card=edit_card,
        practice_numbers_url=practice_numbers_url,
        get_text=get_text,
        stats=stats,
        importable_verbs=importable_verbs,
        importable_verb_count=len(importable),
    )


def _build_cards_dashboard_stats(user_cards: list[Card]) -> dict:
    """Derive aggregate dashboard stats from a user's cards."""
    total_cards = len(user_cards)
    total_attempts = sum(c.times_practiced for c in user_cards)
    total_correct = sum(c.times_correct for c in user_cards)
    overall_accuracy = total_correct / total_attempts if total_attempts else None

    buckets = {"unpracticed": 0, "weak": 0, "medium": 0, "strong": 0}
    for c in user_cards:
        s = c.score
        if s is None:
            buckets["unpracticed"] += 1
        elif s < 0.5:
            buckets["weak"] += 1
        elif s < 0.8:
            buckets["medium"] += 1
        else:
            buckets["strong"] += 1

    practiced = [c for c in user_cards if c.score is not None]
    # The three dashboard lists map to the three non-unpracticed buckets so each
    # is a well-defined, disjoint category (a card lives in exactly one). Each
    # list is shuffled so the on-page preview shows a *random* sample of the
    # category; the template caps the visible rows and folds out the rest.
    rng = secrets.SystemRandom()
    new_cards = [c for c in user_cards if c.score is None]
    weak_cards = [c for c in practiced if c.score < 0.5]
    needs_work = [c for c in practiced if 0.5 <= c.score < 0.8]
    strongest = [c for c in practiced if c.score >= 0.8]
    rng.shuffle(new_cards)
    rng.shuffle(weak_cards)
    rng.shuffle(needs_work)
    rng.shuffle(strongest)

    stats = {
        "total_cards": total_cards,
        "total_attempts": total_attempts,
        "total_correct": total_correct,
        "overall_accuracy": overall_accuracy,
        "unpracticed": buckets["unpracticed"],
        "buckets": buckets,
        "new_cards": new_cards,
        "weak_cards": weak_cards,
        "needs_work": needs_work,
        "strongest": strongest,
    }

    return stats


@app.route("/cards", methods=["POST"])
@login_required
def cards_create():
    """Create a new index card from the form on /cards."""
    front = (request.form.get("front") or "").strip()
    back = (request.form.get("back") or "").strip()
    if not front or not back:
        flash(get_text("cards_flash_both_sides_required"), "error")
        return redirect(url_for("cards"))
    user_sub = _current_user_sub()
    if _find_duplicate_card(user_sub, front, back) is not None:
        flash(get_text("cards_flash_duplicate_create"), "info")
        return redirect(url_for("cards"))
    card = Card(user_sub=user_sub, front=front, back=back)
    db.session.add(card)
    db.session.commit()
    flash(get_text("cards_flash_created"), "success")
    return redirect(url_for("cards"))


@app.route("/cards/<int:card_id>/edit", methods=["POST"])
@login_required
def cards_edit(card_id: int):
    """Update both sides of an existing card."""
    card = _user_card_or_404(card_id)
    front = (request.form.get("front") or "").strip()
    back = (request.form.get("back") or "").strip()
    if not front or not back:
        flash(get_text("cards_flash_both_sides_required"), "error")
        return redirect(url_for("cards", edit=card_id))
    if _find_duplicate_card(card.user_sub, front, back, exclude_id=card_id) is not None:
        flash(get_text("cards_flash_duplicate_edit"), "info")
        return redirect(url_for("cards"))
    card.front = front
    card.back = back
    db.session.commit()
    flash(get_text("cards_flash_updated"), "success")
    return redirect(url_for("cards"))


@app.route("/cards/<int:card_id>/delete", methods=["POST"])
@login_required
def cards_delete(card_id: int):
    """Permanently remove a card."""
    card = _user_card_or_404(card_id)
    db.session.delete(card)
    db.session.commit()
    flash(get_text("cards_flash_deleted"), "info")
    return redirect(url_for("cards"))


# ----- JSON cards API (in-place updates from /cards) -----------------------


@app.route("/api/cards", methods=["POST"])
@login_required
def api_cards_create():
    payload = request.get_json(silent=True) or {}
    front = (payload.get("front") or "").strip()
    back = (payload.get("back") or "").strip()
    if not front or not back:
        return jsonify(
            {"ok": False, "error": get_text("cards_flash_both_sides_required")}
        ), 400
    user_sub = _current_user_sub()
    existing = _find_duplicate_card(user_sub, front, back)
    if existing is not None:
        return jsonify(
            {
                "ok": True,
                "duplicate": True,
                "card": existing.to_dict(),
                **_verb_sync_fields(user_sub, existing),
            }
        )
    card = Card(user_sub=user_sub, front=front, back=back)
    db.session.add(card)
    db.session.commit()
    return jsonify(
        {
            "ok": True,
            "card": card.to_dict(),
            **_verb_sync_fields(user_sub, card),
        }
    )


@app.route("/api/cards/<int:card_id>", methods=["PATCH"])
@login_required
def api_cards_update(card_id: int):
    card = _user_card_or_404(card_id)
    payload = request.get_json(silent=True) or {}
    front = (payload.get("front") or "").strip()
    back = (payload.get("back") or "").strip()
    if not front or not back:
        return jsonify(
            {"ok": False, "error": get_text("cards_flash_both_sides_required")}
        ), 400
    if _find_duplicate_card(card.user_sub, front, back, exclude_id=card_id) is not None:
        return jsonify(
            {
                "ok": True,
                "duplicate": True,
                "card": card.to_dict(),
                **_verb_sync_fields(card.user_sub, card),
            }
        )
    card.front = front
    card.back = back
    db.session.commit()
    return jsonify(
        {
            "ok": True,
            "card": card.to_dict(),
            **_verb_sync_fields(card.user_sub, card),
        }
    )


@app.route("/api/cards/<int:card_id>", methods=["DELETE"])
@login_required
def api_cards_delete(card_id: int):
    card = _user_card_or_404(card_id)
    db.session.delete(card)
    db.session.commit()
    return jsonify({"ok": True})


# ----- Deck sharing --------------------------------------------------------

# Token length is 32 hex chars (128 bits of entropy) — long enough that
# guessing a valid share is computationally infeasible, short enough to
# paste into a chat.
SHARE_TOKEN_BYTES = 16


def _generate_share_token() -> str:
    return secrets.token_hex(SHARE_TOKEN_BYTES)


@app.route("/api/cards/share", methods=["POST"])
@login_required
def api_cards_share():
    """Snapshot the user's deck into a DeckShare and return its public URL."""
    user_sub = _current_user_sub()
    cards = (
        db.session.query(Card)
        .filter_by(user_sub=user_sub)
        .order_by(Card.created_at.asc())
        .all()
    )
    if not cards:
        return jsonify(
            {"ok": False, "error": get_text("cards_share_flash_empty_deck")}
        ), 400
    snapshot = [{"front": c.front, "back": c.back} for c in cards]
    user = session.get("user") or {}
    owner_name = user.get("name") or user.get("nickname") or user.get("email")
    share = DeckShare(
        token=_generate_share_token(),
        owner_sub=user_sub,
        owner_name=owner_name,
        cards_json=json.dumps(snapshot),
    )
    db.session.add(share)
    db.session.commit()
    url = url_for("cards_import", token=share.token, _external=True)
    return jsonify({"ok": True, "url": url, "count": len(snapshot)})


@app.route("/cards/import/<token>", methods=["GET"])
def cards_import(token: str):
    """Show a preview of a shared deck and offer to import it."""
    share = db.session.query(DeckShare).filter_by(token=token).first()
    if share is None:
        return render_template(
            "cards_import.html",
            share=None,
            get_text=get_text,
        ), 404
    if "user" not in session:
        # Stash the import target on the session so post-login we can route back.
        session["pending_import_token"] = token
        return redirect(url_for("login"))
    return render_template(
        "cards_import.html",
        share=share,
        card_count=len(share.cards),
        is_own=share.owner_sub == _current_user_sub(),
        get_text=get_text,
    )


@app.route("/cards/import/<token>", methods=["POST"])
@login_required
def cards_import_apply(token: str):
    """Copy the shared deck into the recipient's account, skipping duplicates."""
    share = db.session.query(DeckShare).filter_by(token=token).first()
    if share is None:
        flash(get_text("cards_share_flash_not_found"), "error")
        return redirect(url_for("cards"))
    user_sub = _current_user_sub()
    existing = (
        db.session.query(Card.front, Card.back).filter_by(user_sub=user_sub).all()
    )
    seen = {
        (quiz_logic.normalize_text(f), quiz_logic.normalize_text(b))
        for f, b in existing
    }
    imported = 0
    skipped = 0
    for entry in share.cards:
        front = (entry.get("front") or "").strip()
        back = (entry.get("back") or "").strip()
        if not front or not back:
            continue
        key = (quiz_logic.normalize_text(front), quiz_logic.normalize_text(back))
        if key in seen:
            skipped += 1
            continue
        seen.add(key)
        db.session.add(Card(user_sub=user_sub, front=front, back=back))
        imported += 1
    db.session.commit()
    flash(
        get_text("cards_share_flash_imported").format(imported, skipped),
        "success",
    )
    return redirect(url_for("cards"))


# ----- Feedback poll -------------------------------------------------------

_POLL_COLOR_SCHEMES = {"dark", "light", "no_preference"}
_POLL_AWARE = {"yes", "no"}
_POLL_DEVICES = {"mobile", "desktop"}
_POLL_FREEFORM_MAX = 2000


@app.route("/api/poll", methods=["POST"])
def api_poll_submit():
    payload = request.get_json(silent=True) or {}
    color = payload.get("color_scheme_pref")
    aware = payload.get("cards_aware")
    device = payload.get("device")
    if (
        color not in _POLL_COLOR_SCHEMES
        or aware not in _POLL_AWARE
        or device not in _POLL_DEVICES
    ):
        return jsonify({"ok": False, "error": "invalid"}), 400
    freeform = (payload.get("freeform") or "").strip()[:_POLL_FREEFORM_MAX] or None
    user = session.get("user") or {}
    user_sub = user.get("sub") if isinstance(user, dict) else None
    ua = (request.headers.get("User-Agent") or "")[:512] or None
    response = PollResponse(
        user_sub=user_sub,
        color_scheme_pref=color,
        cards_aware=aware,
        device=device,
        freeform=freeform,
        user_agent=ua,
    )
    db.session.add(response)
    db.session.commit()
    return jsonify({"ok": True})


# ----- Practice session ----------------------------------------------------

# Floor weight for the prioritized sampling strategy: a card with a perfect
# score still gets sampled with non-zero probability so review sessions don't
# completely exclude mastered vocabulary.
PRIORITIZED_EPSILON = 0.1


def _pick_prompt_side(direction: str) -> str:
    """Return 'front' or 'back' as the side to *show* the user as the prompt."""
    if direction == "front_to_back":
        return "front"
    if direction == "back_to_front":
        return "back"
    return "front" if secrets.randbelow(2) == 0 else "back"


def _acceptable_answers(card: Card, prompt_side: str) -> list[str]:
    """Every answer-side string accepted for the prompt of `card`.

    Includes the card itself plus any sibling owned by the same user
    whose prompt-side text normalizes to the same value. This lets two
    cards that share a prompt (e.g. "sometimes" → "a veces" and
    "sometimes" → "algunas veces") accept either back as a correct
    answer regardless of which one the sampler picked.
    """
    prompt_text = card.front if prompt_side == "front" else card.back
    target = quiz_logic.normalize_text(prompt_text)
    siblings = db.session.query(Card).filter_by(user_sub=card.user_sub).all()
    accepted = []
    for c in siblings:
        sib_prompt = c.front if prompt_side == "front" else c.back
        if quiz_logic.normalize_text(sib_prompt) == target:
            accepted.append(c.back if prompt_side == "front" else c.front)
    return accepted


def _pick_best_validation(results: list[dict]) -> dict:
    """Choose the partial-answer feedback that best fits what the user is
    typing. Prefer a complete-and-correct match; otherwise maximise the
    count of words marked correct/incomplete and minimise incorrect ones.
    """

    def key(r):
        words = r.get("words", [])
        correct = sum(1 for w in words if w["status"] == "correct")
        incomplete = sum(1 for w in words if w["status"] == "incomplete")
        incorrect = sum(1 for w in words if w["status"] == "incorrect")
        return (
            1 if r.get("is_correct") else 0,
            correct + incomplete,
            -incorrect,
        )

    return max(results, key=key)


def _pick_weighted_card(candidates: list[Card]) -> Card:
    """Pick a card weighted toward low scores and few practice attempts.

    Weight = (1 - score) + 1/(1 + times_practiced) + epsilon. The scarcity
    term keeps lightly-practiced cards in rotation: without it, a card
    answered correctly once (score 1.0) would drop to the epsilon floor and
    effectively never resurface, since its score can only change when it is
    sampled again. Unpracticed cards get the maximum weight (2 + epsilon).
    """
    weights = [
        (1.0 - (card.score if card.score is not None else 0.0))
        + 1.0 / (1.0 + card.times_practiced)
        + PRIORITIZED_EPSILON
        for card in candidates
    ]
    chosen = secrets.SystemRandom().choices(candidates, weights=weights, k=1)[0]
    if os.environ.get("LOG_CARD_SAMPLING"):
        breakdown = ", ".join(f"{c.id}:{w:.2f}" for c, w in zip(candidates, weights))
        app.logger.info("card_sampling chosen=%s from {%s}", chosen.id, breakdown)
    return chosen


def _load_next_card(state: dict) -> Card | None:
    """Pick the next unasked card for this practice session, advance state."""
    asked = set(state.get("asked_ids", []))
    candidates = (
        db.session.query(Card)
        .filter_by(user_sub=_current_user_sub())
        .filter(~Card.id.in_(asked) if asked else db.true())
        .all()
    )
    if state.get("weak_only"):
        # Score is a Python property, so filter in memory. Weak == practiced
        # cards with sub-50% accuracy in the rolling window; unpracticed cards
        # are excluded because they aren't "weak" — they're untouched.
        candidates = [c for c in candidates if c.score is not None and c.score < 0.5]
    allowed_ids = state.get("allowed_card_ids")
    if allowed_ids:
        allowed = set(allowed_ids)
        candidates = [c for c in candidates if c.id in allowed]
    if not candidates:
        return None
    if state.get("sampling_mode") == "prioritized":
        card = _pick_weighted_card(candidates)
    else:
        card = candidates[secrets.randbelow(len(candidates))]
    state["current_card_id"] = card.id
    state["current_prompt_side"] = _pick_prompt_side(state["direction"])
    state["current_revealed"] = False
    return card


@app.route("/cards/practice/start", methods=["POST"])
@login_required
def cards_practice_start():
    """Initialize a new practice session and redirect to the first question."""
    direction = request.form.get("direction", "back_to_front")
    if direction not in ("front_to_back", "back_to_front", "random"):
        direction = "back_to_front"
    sampling_mode = request.form.get("sampling_mode", "prioritized")
    if sampling_mode not in ("random", "prioritized"):
        sampling_mode = "prioritized"
    difficulty = request.form.get("difficulty", "advanced")
    if difficulty not in ("advanced", "hardcore"):
        difficulty = "advanced"
    reveal_mode = request.form.get("reveal_mode", "type")
    if reveal_mode not in ("type", "click"):
        reveal_mode = "type"
    try:
        count = int(request.form.get("count", 10))
    except (TypeError, ValueError):
        count = 10
    count = max(1, min(count, 100))
    recap = request.form.get("recap")
    # "weakest" is the legacy name for the "needs work" (medium) bucket.
    if recap == "weakest":
        recap = "needs_work"
    if recap not in ("new", "weak", "needs_work", "strongest"):
        recap = None
    # Legacy: weak_only=1 maps onto recap=weak so older callers keep working.
    if recap is None and request.form.get("weak_only") in ("1", "true", "on"):
        recap = "weak"
    weak_only = recap == "weak"
    allowed_card_ids: list[int] = []
    if recap is not None:
        all_cards = db.session.query(Card).filter_by(user_sub=_current_user_sub()).all()
        if recap == "new":
            pool = [c for c in all_cards if c.score is None]
            empty_flash = "cards_flash_need_cards"
        elif recap == "weak":
            pool = [c for c in all_cards if c.score is not None and c.score < 0.5]
            empty_flash = "cards_flash_no_weak_cards"
        elif recap == "needs_work":
            pool = [
                c for c in all_cards if c.score is not None and 0.5 <= c.score < 0.8
            ]
            empty_flash = "cards_flash_need_cards"
        else:  # strongest
            pool = [c for c in all_cards if c.score is not None and c.score >= 0.8]
            empty_flash = "cards_flash_need_cards"
        if not pool:
            flash(get_text(empty_flash), "info")
            return redirect(url_for("cards"))
        # Recap draws a random sample from the whole category. The session size
        # comes from the "Cards per round" setting (clamped to the pool), and
        # sampling is forced to random so every card in the bucket is fair game.
        allowed_card_ids = [c.id for c in pool]
        sampling_mode = "random"
        count = min(count, len(allowed_card_ids))
    else:
        have_any = (
            db.session.query(Card.id).filter_by(user_sub=_current_user_sub()).first()
            is not None
        )
        if not have_any:
            flash(get_text("cards_flash_need_cards"), "info")
            return redirect(url_for("cards"))
    session["card_practice"] = {
        "direction": direction,
        "sampling_mode": sampling_mode,
        "difficulty": difficulty,
        "reveal_mode": reveal_mode,
        "count": count,
        "weak_only": weak_only,
        "recap": recap,
        "allowed_card_ids": allowed_card_ids,
        "asked_ids": [],
        "score": 0,
        "total": 0,
        "current_card_id": None,
        "current_prompt_side": None,
        "current_revealed": False,
    }
    return redirect(url_for("cards_practice"))


def _get_practice_state() -> dict | None:
    return session.get("card_practice")


def _save_practice_state(state: dict) -> None:
    session["card_practice"] = state
    session.modified = True


@app.route("/cards/practice", methods=["GET", "POST"])
@login_required
def cards_practice():
    """Show the current practice card or process an answer/reveal."""
    state = _get_practice_state()
    if state is None:
        return redirect(url_for("cards"))

    if request.method == "POST":
        card = (
            db.session.get(Card, state["current_card_id"])
            if state.get("current_card_id")
            else None
        )
        if card is None or card.user_sub != _current_user_sub():
            session.pop("card_practice", None)
            return redirect(url_for("cards"))

        prompt_side = state["current_prompt_side"]
        correct_answer = card.back if prompt_side == "front" else card.front

        if "reveal" in request.form:
            # Two-step reveal: record the wrong attempt now, but keep the card
            # mounted so the next GET can render the answer prominently. The
            # user explicitly clicks Next to advance.
            state["total"] += 1
            card.times_practiced += 1
            card.record_attempt(False)
            state["current_revealed"] = True
            db.session.commit()
            _save_practice_state(state)
            return redirect(url_for("cards_practice"))

        if "next" in request.form:
            # Advance from a revealed card. DB writes already happened on reveal.
            # In "type" reveal mode the user must retype the shown answer before
            # advancing, so gate the advance on a correct typed answer (the
            # client enforces this too, but never trust the client). A wrong or
            # empty answer keeps the card mounted and revealed.
            if state.get("reveal_mode", "type") == "type":
                user_answer = (request.form.get("answer") or "").strip()
                acceptable = _acceptable_answers(card, prompt_side)
                if not (
                    user_answer
                    and any(
                        quiz_logic.check_answer_advanced(user_answer, a)
                        for a in acceptable
                    )
                ):
                    return redirect(url_for("cards_practice"))
            state["current_revealed"] = False
            state["asked_ids"].append(card.id)
            state["current_card_id"] = None
            _save_practice_state(state)
            return redirect(url_for("cards_practice"))

        # A revealed card has already recorded its (wrong) attempt; only a
        # `next` advances it. Ignore a stray answer POST so the question can't
        # be counted twice (the reveal-retype form must submit with `next`).
        if state.get("current_revealed"):
            return redirect(url_for("cards_practice"))

        user_answer = (request.form.get("answer") or "").strip()
        acceptable = _acceptable_answers(card, prompt_side)
        if user_answer and any(
            quiz_logic.check_answer_advanced(user_answer, a) for a in acceptable
        ):
            state["score"] += 1
            state["total"] += 1
            card.times_practiced += 1
            card.times_correct += 1
            card.record_attempt(True)
            flash(get_text("cards_flash_correct"), "success")
        else:
            # Wrong final submit: count as attempted, show correct answer.
            flash(
                get_text("cards_flash_incorrect").format(correct_answer),
                "error",
            )
            state["total"] += 1
            card.times_practiced += 1
            card.record_attempt(False)

        db.session.commit()
        state["asked_ids"].append(card.id)
        state["current_card_id"] = None
        _save_practice_state(state)
        return redirect(url_for("cards_practice"))

    # GET: load (or re-load) current card.
    count = state.get("count", 10)

    if state.get("current_card_id") is None:
        # End the round once the user has been asked `count` questions, even if
        # more unseen cards exist in their deck. Checked only when no card is
        # mounted: after a reveal the card stays mounted (with total already
        # incremented) so it must still render; the "next" POST clears it.
        if state["total"] >= count:
            return redirect(url_for("cards_practice_results"))
        next_card = _load_next_card(state)
        if next_card is None:
            _save_practice_state(state)
            return redirect(url_for("cards_practice_results"))
        _save_practice_state(state)
        card = next_card
    else:
        card = db.session.get(Card, state["current_card_id"])
        if card is None or card.user_sub != _current_user_sub():
            session.pop("card_practice", None)
            return redirect(url_for("cards"))

    prompt_side = state["current_prompt_side"]
    prompt_text = card.front if prompt_side == "front" else card.back
    correct_answer = card.back if prompt_side == "front" else card.front

    total_cards = (
        db.session.query(Card.id).filter_by(user_sub=_current_user_sub()).count()
    )

    difficulty = state.get("difficulty", "advanced")
    revealed = bool(state.get("current_revealed"))
    # If this card is a pool verb the user hasn't added to conjugation practice
    # yet, expose its infinitive + language so the page can offer a one-click add.
    verb_match = _importable_verb_for_card(_current_user_sub(), card)
    verb_lang, verb_infinitive = verb_match if verb_match else (None, None)
    # Only leak the correct answer to the page in hardcore mode (JS needs it
    # for client-side green/red feedback) or when the card has been revealed
    # (template renders it as the prominent study display).
    return render_template(
        "cards_practice.html",
        user=session["user"],
        prompt_text=prompt_text,
        correct_answer=correct_answer
        if (revealed or difficulty == "hardcore")
        else None,
        difficulty=difficulty,
        revealed=revealed,
        reveal_mode=state.get("reveal_mode", "type"),
        score=state["score"],
        total=state["total"],
        max_questions=min(count, total_cards),
        verb_infinitive=verb_infinitive,
        verb_lang=verb_lang,
        get_text=get_text,
    )


@app.route("/cards/practice/results")
@login_required
def cards_practice_results():
    """Show the final practice score and clear the session state."""
    state = session.pop("card_practice", None)
    if state is None:
        return redirect(url_for("cards"))
    score = state.get("score", 0)
    total = state.get("total", 0)
    percentage = (score / total * 100) if total else 0
    return render_template(
        "cards_results.html",
        user=session["user"],
        score=score,
        total=total,
        percentage=percentage,
        # Settings echoed back so "Try Again" can restart the same session.
        practice_settings={
            "direction": state.get("direction", "back_to_front"),
            "sampling_mode": state.get("sampling_mode", "prioritized"),
            "difficulty": state.get("difficulty", "advanced"),
            "reveal_mode": state.get("reveal_mode", "type"),
            "count": state.get("count", 10),
            "recap": state.get("recap"),
        },
        get_text=get_text,
    )


@app.route("/api/cards/validate", methods=["POST"])
@login_required
def cards_validate_api():
    """Live word-by-word validation for the current practice card."""
    state = _get_practice_state()
    if state is None or not state.get("current_card_id"):
        return jsonify({"error": "No active practice card"}), 400
    # Hardcore mode deliberately withholds intermediate feedback — refuse the
    # call so an inspect-and-fetch workaround can't bypass it.
    if state.get("difficulty") == "hardcore":
        return jsonify({"error": "Validation disabled in hardcore mode"}), 400

    card = db.session.get(Card, state["current_card_id"])
    if card is None or card.user_sub != _current_user_sub():
        return jsonify({"error": "Card not found"}), 404

    prompt_side = state["current_prompt_side"]

    user_input = (request.json or {}).get("input", "")
    # `lang_code="es"` forces the word_based strategy regardless of the card's
    # actual language — fine for free-form vocabulary.
    acceptable = _acceptable_answers(card, prompt_side)
    results = [
        quiz_logic.validate_partial_answer(user_input, a, "es") for a in acceptable
    ]
    return jsonify(_pick_best_validation(results))


# ----- Verb conjugation practice -------------------------------------------
#
# A third user-owned practice section (alongside cards) for conjugating verbs,
# per language (Spanish and German today). The user builds a personal pool of
# verbs drawn from the language's global pool
# (languages/<lang>/conjugations.json); a session asks them to conjugate
# verb + pronoun + tense. Mirrors the cards subsystem: VerbCard model, advanced/
# hardcore typed answers with live word highlighting, 10 questions by default.


def _user_verb_or_404(verb_id: int) -> VerbCard:
    """Fetch a VerbCard and 404 if it does not belong to the current user."""
    verb = db.session.get(VerbCard, verb_id)
    if verb is None or verb.user_sub != _current_user_sub():
        from flask import abort

        abort(404)
    return verb


def _user_verbs(lang_code: str) -> list[VerbCard]:
    return (
        db.session.query(VerbCard)
        .filter_by(user_sub=_current_user_sub(), lang=lang_code)
        .order_by(VerbCard.created_at.desc())
        .all()
    )


def _normalize_infinitive(value: str) -> str:
    return (value or "").strip().lower()


def _find_user_verb(user_sub: str, lang_code: str, infinitive: str) -> VerbCard | None:
    """Return the user's VerbCard for an infinitive (case-insensitive), or None."""
    key = _normalize_infinitive(infinitive)
    if not key:
        return None
    for verb in (
        db.session.query(VerbCard).filter_by(user_sub=user_sub, lang=lang_code).all()
    ):
        if _normalize_infinitive(verb.infinitive) == key:
            return verb
    return None


# ----- Cards <-> conjugation sync ------------------------------------------
# An index card and a conjugation verb are linked purely by value: a card whose
# front or back is an infinitive in one of the global pools can become a
# VerbCard, and a VerbCard whose infinitive isn't yet a card side can become a
# card. The sync is additive only — neither side is deleted when the other is.


def _card_verb_match(card: Card) -> tuple[str, str] | None:
    """Return (lang, normalized infinitive) for the pool matching this card.

    Either side may carry the verb (cards are free-form), so the front is
    checked first, then the back; per side, the conjugation languages are tried
    in registry order. Matching is exact against each global pool.
    """
    for side in (card.front, card.back):
        infinitive = _normalize_infinitive(side)
        if not infinitive:
            continue
        for lang_code in get_languages_with_conjugation():
            if _conj_pool(lang_code).verb_exists(infinitive):
                return lang_code, infinitive
    return None


def _owned_infinitives(user_sub: str) -> set[tuple[str, str]]:
    """(lang, normalized infinitive) pairs already in the user's verb pool."""
    return {
        (v.lang, _normalize_infinitive(v.infinitive))
        for v in db.session.query(VerbCard).filter_by(user_sub=user_sub).all()
    }


def _importable_card_verbs(
    user_sub: str, cards: list[Card], lang_code: str | None = None
) -> list[tuple[Card, str, str]]:
    """Cards whose verb side is a pool infinitive the user doesn't own yet.

    Returns (card, lang, infinitive) tuples, de-duped by (lang, infinitive)
    (the first card carrying it wins) so the same verb appearing on two cards
    is only offered once. ``lang_code`` restricts matches to one pool (used on
    /<lang>/conjugate); None offers verbs from every pool (used on /cards).
    """
    owned = _owned_infinitives(user_sub)
    seen: set[tuple[str, str]] = set()
    out: list[tuple[Card, str, str]] = []
    for card in cards:
        match = _card_verb_match(card)
        if match is None:
            continue
        if lang_code is not None and match[0] != lang_code:
            continue
        if match not in owned and match not in seen:
            seen.add(match)
            out.append((card, match[0], match[1]))
    return out


def _verbs_missing_from_cards(
    verbs: list[VerbCard], cards: list[Card]
) -> list[VerbCard]:
    """Owned verbs whose infinitive isn't a side of any of the user's cards."""
    card_sides = set()
    for card in cards:
        card_sides.add(_normalize_infinitive(card.front))
        card_sides.add(_normalize_infinitive(card.back))
    return [v for v in verbs if _normalize_infinitive(v.infinitive) not in card_sides]


def _importable_verb_for_card(user_sub: str, card: Card) -> tuple[str, str] | None:
    """The (lang, infinitive) a single card could add to conjugation, or None.

    Used by the JSON card API so the client can show the "verb" badge and
    "add to conjugation" button on a freshly created/edited card without a
    page reload. Returns None when the card isn't a verb or the user already
    owns it.
    """
    match = _card_verb_match(card)
    if match is None or _find_user_verb(user_sub, match[0], match[1]):
        return None
    return match


def _verb_sync_fields(user_sub: str, card: Card) -> dict:
    """JSON fields describing a card's importable verb (for the cards API)."""
    match = _importable_verb_for_card(user_sub, card)
    if match is None:
        return {"verb_infinitive": None, "verb_lang": None}
    return {"verb_infinitive": match[1], "verb_lang": match[0]}


# Practice-category buckets shared by the conjugate insights matrix. Mirrors the
# cards dashboard thresholds: unpracticed (no attempts), weak (<50%), needs work
# (50–80%). The strong bucket (≥80%) is intentionally omitted from the matrix.
CONJ_MATRIX_CATEGORIES = ("unpracticed", "weak", "needs_work")


def _conj_category(score: float | None) -> str | None:
    """Map a 0–1 accuracy (or None) onto a matrix category, or None if strong."""
    if score is None:
        return "unpracticed"
    if score < 0.5:
        return "weak"
    if score < 0.8:
        return "needs_work"
    return None


def _conj_build_matrix(
    lang_code: str,
    verbs: list[VerbCard],
    by_tense: dict,
    by_person: dict,
    selected_tenses: list[str],
    selected_persons: list[int],
) -> list[dict]:
    """Build the insights matrix scoped to the given practice selection.

    Only the *selected* tenses and persons populate their dimension rows; the
    verbs row always covers the user's whole verb list (verb scores are global —
    `ConjugationStat` isn't keyed by verb, so they can't be sliced per tense).
    Each cell carries the recap parameters for a focused session, where the two
    "other" dimensions inherit the current selection.
    """
    sel_tenses = [t for t in selected_tenses if t in conj_tense_keys(lang_code)]
    sel_persons = list(selected_persons)

    def _empty_cells() -> dict:
        return {cat: [] for cat in CONJ_MATRIX_CATEGORIES}

    tense_members = _empty_cells()
    for t in conj_tenses(lang_code):
        if t["key"] not in sel_tenses:
            continue
        counts = by_tense.get(t["key"], [0, 0])
        score = (counts[1] / counts[0]) if counts[0] else None
        cat = _conj_category(score)
        if cat is not None:
            tense_members[cat].append(t["key"])

    verb_members = _empty_cells()
    for v in verbs:
        cat = _conj_category(v.score)
        if cat is not None:
            verb_members[cat].append(v.id)

    person_members = _empty_cells()
    for p in conj_persons(lang_code):
        if p["index"] not in sel_persons:
            continue
        counts = by_person.get(p["index"], [0, 0])
        score = (counts[1] / counts[0]) if counts[0] else None
        cat = _conj_category(score)
        if cat is not None:
            person_members[cat].append(p["index"])

    def _cells(members: dict, *, tenses, verb_ids_for, persons_for) -> dict:
        out = {}
        for cat in CONJ_MATRIX_CATEGORIES:
            ids = members[cat]
            out[cat] = {
                "count": len(ids),
                "tenses": tenses(ids),
                "verb_ids": verb_ids_for(ids),
                "persons": persons_for(ids),
            }
        return out

    return [
        {
            "key": "tenses",
            "label": get_text("conjugate_stats_tenses"),
            "cells": _cells(
                tense_members,
                tenses=lambda ids: ids,
                verb_ids_for=lambda ids: [],
                persons_for=lambda ids: sel_persons,
            ),
        },
        {
            "key": "verbs",
            "label": get_text("conjugate_stats_verbs"),
            "cells": _cells(
                verb_members,
                tenses=lambda ids: sel_tenses,
                verb_ids_for=lambda ids: ids,
                persons_for=lambda ids: sel_persons,
            ),
        },
        {
            "key": "pronouns",
            "label": get_text("conjugate_stats_pronouns"),
            "cells": _cells(
                person_members,
                tenses=lambda ids: sel_tenses,
                verb_ids_for=lambda ids: [],
                persons_for=lambda ids: ids,
            ),
        },
    ]


def _build_conjugate_dashboard_stats(
    user_sub: str, verbs: list[VerbCard], lang_code: str
) -> dict:
    """Insights for the /conjugate dashboard, rendered as a matrix of
    dimensions (tenses, verbs, pronouns) × categories (unpracticed, weak,
    needs work).

    The matrix only reflects what's chosen in the practice settings below it:
    the server renders the initial state for the form defaults (the `default_on`
    tenses, vosotros off), and `conjugate.js` re-renders it live as the user
    ticks tenses / toggles vosotros / changes difficulty. The per-tense and
    per-person aggregates plus the verb list are emitted as JSON for that.

    Verbs are scored from `VerbCard`; tenses and pronouns are aggregated from
    `ConjugationStat` rows (per user/lang/tense/person).
    """
    total_attempts = sum(v.times_practiced for v in verbs)
    total_correct = sum(v.times_correct for v in verbs)
    overall_accuracy = total_correct / total_attempts if total_attempts else None

    stats_rows = (
        db.session.query(ConjugationStat)
        .filter_by(user_sub=user_sub, lang=lang_code)
        .all()
    )

    # Aggregate [practiced, correct] by tense and by person.
    by_tense: dict[str, list[int]] = {}
    by_person: dict[int, list[int]] = {}
    for row in stats_rows:
        t = by_tense.setdefault(row.tense_key, [0, 0])
        t[0] += row.times_practiced
        t[1] += row.times_correct
        p = by_person.setdefault(row.person_index, [0, 0])
        p[0] += row.times_practiced
        p[1] += row.times_correct

    # Initial selection mirrors the practice form's defaults.
    default_tenses = [t["key"] for t in conj_tenses(lang_code) if t["default_on"]]
    default_persons = [p["index"] for p in conj_persons(lang_code) if not p["optional"]]
    matrix = _conj_build_matrix(
        lang_code, verbs, by_tense, by_person, default_tenses, default_persons
    )

    # Client-side payload: full per-tense / per-person aggregates plus the verb
    # list, so conjugate.js can rebuild the matrix for any selection.
    data = {
        "categories": list(CONJ_MATRIX_CATEGORIES),
        "category_labels": {
            "unpracticed": get_text("cards_dashboard_bucket_unpracticed"),
            "weak": get_text("cards_dashboard_weak"),
            "needs_work": get_text("cards_dashboard_top_weak"),
        },
        "dimension_labels": {
            "tenses": get_text("conjugate_stats_tenses"),
            "verbs": get_text("conjugate_stats_verbs"),
            "pronouns": get_text("conjugate_stats_pronouns"),
        },
        "recap_label": get_text("cards_dashboard_recap_btn"),
        "start_url": url_for("conjugate_practice_start", lang_code=lang_code),
        "default_count": CONJ_QUESTIONS_DEFAULT,
        "tenses": [
            {
                "key": t["key"],
                "practiced": by_tense.get(t["key"], [0, 0])[0],
                "correct": by_tense.get(t["key"], [0, 0])[1],
            }
            for t in conj_tenses(lang_code)
        ],
        "persons": [
            {
                "index": p["index"],
                "optional": p["optional"],
                "practiced": by_person.get(p["index"], [0, 0])[0],
                "correct": by_person.get(p["index"], [0, 0])[1],
            }
            for p in conj_persons(lang_code)
        ],
        "verbs": [
            {
                "id": v.id,
                "score": v.score,
                "practiced": v.times_practiced,
                "correct": v.times_correct,
            }
            for v in verbs
        ],
    }
    data_json = json.dumps(data).replace("</", "<\\/")

    return {
        "total_verbs": len(verbs),
        "total_attempts": total_attempts,
        "total_correct": total_correct,
        "overall_accuracy": overall_accuracy,
        "matrix": matrix,
        "matrix_categories": list(CONJ_MATRIX_CATEGORIES),
        "data_json": data_json,
    }


def _require_conjugation_lang(lang_code: str) -> None:
    """404 for a language that has no verb-conjugation practice section."""
    if lang_code not in get_languages_with_conjugation():
        from flask import abort

        abort(404)


@app.route("/<lang_code>/conjugate")
@login_required
def conjugate(lang_code):
    """Manage page: add verbs (autocomplete) + practice settings + start."""
    _require_conjugation_lang(lang_code)
    verbs = _user_verbs(lang_code)
    # The back link follows the page's own language, not the session's learn
    # language — a German conjugation page must not point at the Spanish
    # overview. Every conjugation language is a ready numbers language.
    practice_numbers_url = url_for("mode_selection", lang_code=lang_code)
    practice_numbers_label = get_text(
        "cards_practice_numbers_btn", learn_language=lang_code
    )
    dashboard = _build_conjugate_dashboard_stats(_current_user_sub(), verbs, lang_code)
    user_sub = _current_user_sub()
    user_cards = db.session.query(Card).filter_by(user_sub=user_sub).all()
    card_import_count = len(_importable_card_verbs(user_sub, user_cards, lang_code))
    missing = _verbs_missing_from_cards(verbs, user_cards)
    missing_infinitives = {v.infinitive for v in missing}
    missing_in_cards_json = json.dumps(
        [{"infinitive": v.infinitive} for v in missing]
    ).replace("</", "<\\/")
    return render_template(
        "conjugate.html",
        user=session["user"],
        lang_code=lang_code,
        verbs=verbs,
        tenses=conj_tenses(lang_code),
        persons=conj_persons(lang_code),
        optional_person_index=conj_optional_person_index(lang_code),
        default_count=CONJ_QUESTIONS_DEFAULT,
        practice_numbers_url=practice_numbers_url,
        practice_numbers_label=practice_numbers_label,
        dashboard=dashboard,
        get_text=get_text,
        conj_text=lambda key: _conj_text(key, lang_code),
        card_import_count=card_import_count,
        missing_in_cards_count=len(missing),
        missing_in_cards_json=missing_in_cards_json,
        missing_infinitives=missing_infinitives,
    )


def _requested_conjugation_lang(value: str | None) -> str:
    """Validate a lang parameter on the un-namespaced /api/verbs* endpoints.

    Missing/unknown values fall back to "es" (the only pool that existed before
    the endpoints grew a lang parameter, so older clients keep working).
    """
    if value in get_languages_with_conjugation():
        return value
    return DEFAULT_CONJUGATION_LANG


@app.route("/api/verbs/search")
@login_required
def api_verbs_search():
    """Autocomplete: pool infinitives starting with ?q=, excluding owned verbs."""
    lang_code = _requested_conjugation_lang(request.args.get("lang"))
    query = (request.args.get("q") or "").strip()
    if not query:
        return jsonify({"ok": True, "results": []})
    owned = {_normalize_infinitive(v.infinitive) for v in _user_verbs(lang_code)}
    results = _conj_pool(lang_code).search_verbs(query, limit=8, exclude=owned)
    return jsonify({"ok": True, "results": results})


@app.route("/api/verbs", methods=["POST"])
@login_required
def api_verbs_create():
    """Add a verb. Rejects verbs not in the global pool with an 'unsupported' flag."""
    payload = request.get_json(silent=True) or {}
    lang_code = _requested_conjugation_lang(payload.get("lang"))
    infinitive = _normalize_infinitive(payload.get("infinitive"))
    if not infinitive:
        return jsonify(
            {"ok": False, "error": get_text("conjugate_flash_verb_required")}
        ), 400
    if not _conj_pool(lang_code).verb_exists(infinitive):
        return jsonify(
            {
                "ok": False,
                "unsupported": True,
                "error": _conj_text("conjugate_flash_unsupported", lang_code).format(
                    infinitive
                ),
            }
        ), 400
    user_sub = _current_user_sub()
    existing = _find_user_verb(user_sub, lang_code, infinitive)
    if existing is not None:
        return jsonify({"ok": True, "duplicate": True, "verb": existing.to_dict()})
    verb = VerbCard(user_sub=user_sub, lang=lang_code, infinitive=infinitive)
    db.session.add(verb)
    db.session.commit()
    return jsonify({"ok": True, "verb": verb.to_dict()})


@app.route("/<lang_code>/conjugate/add", methods=["POST"])
@login_required
def conjugate_verb_add(lang_code):
    """Form fallback for adding a verb (no-JS path, and the JS error fallback).

    Mirrors the cards `/cards` POST route: reads the form field, flashes, and
    redirects back to /<lang>/conjugate. The JS add flow uses the JSON `/api/verbs`.
    """
    _require_conjugation_lang(lang_code)
    infinitive = _normalize_infinitive(request.form.get("infinitive"))
    if not infinitive:
        flash(get_text("conjugate_flash_verb_required"), "error")
        return redirect(url_for("conjugate", lang_code=lang_code))
    if not _conj_pool(lang_code).verb_exists(infinitive):
        flash(
            _conj_text("conjugate_flash_unsupported", lang_code).format(infinitive),
            "error",
        )
        return redirect(url_for("conjugate", lang_code=lang_code))
    user_sub = _current_user_sub()
    if _find_user_verb(user_sub, lang_code, infinitive) is not None:
        flash(get_text("conjugate_flash_verb_duplicate"), "info")
        return redirect(url_for("conjugate", lang_code=lang_code))
    verb = VerbCard(user_sub=user_sub, lang=lang_code, infinitive=infinitive)
    db.session.add(verb)
    db.session.commit()
    flash(get_text("conjugate_flash_verb_added"), "success")
    return redirect(url_for("conjugate", lang_code=lang_code))


@app.route("/api/verbs/import-from-cards", methods=["POST"])
@login_required
def api_verbs_import_from_cards():
    """Add every index-card verb (front/back in a pool) not already owned.

    An optional `lang` in the JSON payload restricts the import to one pool
    (the /<lang>/conjugate page passes its own language); without it, every
    conjugation language's matches are imported (the /cards page's button).
    """
    payload = request.get_json(silent=True) or {}
    lang_filter = payload.get("lang")
    if lang_filter is not None and lang_filter not in get_languages_with_conjugation():
        lang_filter = DEFAULT_CONJUGATION_LANG
    user_sub = _current_user_sub()
    cards = db.session.query(Card).filter_by(user_sub=user_sub).all()
    importable = _importable_card_verbs(user_sub, cards, lang_filter)
    added = []
    for _card, verb_lang, infinitive in importable:
        verb = VerbCard(user_sub=user_sub, lang=verb_lang, infinitive=infinitive)
        db.session.add(verb)
        added.append(verb)
    if added:
        db.session.commit()
    return jsonify(
        {"ok": True, "added": len(added), "verbs": [v.to_dict() for v in added]}
    )


@app.route("/api/verbs/<int:verb_id>", methods=["DELETE"])
@login_required
def api_verbs_delete(verb_id: int):
    verb = _user_verb_or_404(verb_id)
    db.session.delete(verb)
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/<lang_code>/conjugate/<int:verb_id>/delete", methods=["POST"])
@login_required
def conjugate_verb_delete(lang_code, verb_id: int):
    """Form fallback for deleting a verb (no-JS path)."""
    _require_conjugation_lang(lang_code)
    verb = _user_verb_or_404(verb_id)
    db.session.delete(verb)
    db.session.commit()
    flash(get_text("conjugate_flash_verb_deleted"), "info")
    return redirect(url_for("conjugate", lang_code=lang_code))


def _form_available(
    lang_code: str, infinitive: str, tense_key: str, person_index: int
) -> str | None:
    """Return the conjugated form for a verb/tense/person, or None if absent."""
    forms = _conj_pool(lang_code).get_verb_forms(infinitive)
    if not forms:
        return None
    tense_forms = forms.get(tense_key)
    if not tense_forms or person_index >= len(tense_forms):
        return None
    return tense_forms[person_index]


def _build_conjugation_hint(
    lang_code: str, tense_key: str, person_index: int, ui_lang: str = "en"
) -> dict:
    """Build the practice "Hint" excerpt for a (tense, pronoun) prompt.

    Shows the tense's regular pattern via the language's model verbs (one per
    conjugation group) with the prompted pronoun's row flagged, plus a one-line
    blurb. Forms come straight from the committed global pool, so no answer is
    leaked (unless the verb under test is itself a model verb, which just shows
    the pattern).
    """
    pool = _conj_pool(lang_code)
    models = []
    for infinitive in conj_hint_model_verbs(lang_code):
        forms = pool.get_verb_forms(infinitive) or {}
        models.append(
            {
                "infinitive": infinitive,
                "forms": list(forms.get(tense_key) or []),
            }
        )
    persons = [
        {
            "label": person_label(lang_code, p["index"]),
            "highlight": p["index"] == person_index,
        }
        for p in conj_persons(lang_code)
    ]
    return {
        "blurb": tense_hint(lang_code, tense_key, ui_lang),
        "persons": persons,
        "models": models,
    }


def _record_conjugation_stat(
    user_sub: str, lang_code: str, tense_key: str, person_index: int, correct: bool
) -> None:
    """Upsert the per-(lang, tense, person) practice tally for the insights."""
    stat = (
        db.session.query(ConjugationStat)
        .filter_by(
            user_sub=user_sub,
            lang=lang_code,
            tense_key=tense_key,
            person_index=person_index,
        )
        .first()
    )
    if stat is None:
        stat = ConjugationStat(
            user_sub=user_sub,
            lang=lang_code,
            tense_key=tense_key,
            person_index=person_index,
            times_practiced=0,
            times_correct=0,
        )
        db.session.add(stat)
    stat.times_practiced += 1
    if correct:
        stat.times_correct += 1


@app.route("/<lang_code>/conjugate/practice/start", methods=["POST"])
@login_required
def conjugate_practice_start(lang_code):
    """Initialize a conjugation practice session and redirect to the first prompt."""
    _require_conjugation_lang(lang_code)
    selected_tenses = [
        t for t in request.form.getlist("tenses") if t in conj_tense_keys(lang_code)
    ]
    include_vosotros = request.form.get("include_vosotros") in ("1", "true", "on")
    # An explicit `persons` list (used by the insights-matrix recap buttons)
    # overrides the optional-person-toggle default. Values are validated
    # against the known person slots.
    valid_person_indices = {p["index"] for p in conj_persons(lang_code)}
    explicit_persons = []
    for raw in request.form.getlist("persons"):
        try:
            idx = int(raw)
        except (TypeError, ValueError):
            continue
        if idx in valid_person_indices:
            explicit_persons.append(idx)
    if explicit_persons:
        persons = sorted(set(explicit_persons))
    else:
        # The optional slot (Spanish vosotros; German has none) is included
        # only when the toggle is on.
        optional_index = conj_optional_person_index(lang_code)
        persons = [
            p["index"]
            for p in conj_persons(lang_code)
            if p["index"] != optional_index or include_vosotros
        ]
    # An explicit `verb_ids` list (also from recap buttons) restricts the verb
    # pool to those verbs; empty means all of the user's verbs.
    verb_ids = []
    for raw in request.form.getlist("verb_ids"):
        try:
            verb_ids.append(int(raw))
        except (TypeError, ValueError):
            continue
    difficulty = request.form.get("difficulty", "advanced")
    if difficulty not in ("advanced", "hardcore"):
        difficulty = "advanced"
    sampling_mode = request.form.get("sampling_mode", "prioritized")
    if sampling_mode not in ("random", "prioritized"):
        sampling_mode = "prioritized"
    reveal_mode = request.form.get("reveal_mode", "type")
    if reveal_mode not in ("type", "click"):
        reveal_mode = "type"
    try:
        count = int(request.form.get("count", CONJ_QUESTIONS_DEFAULT))
    except (TypeError, ValueError):
        count = CONJ_QUESTIONS_DEFAULT
    count = max(1, min(count, 100))

    user_verbs = _user_verbs(lang_code)
    if not user_verbs:
        flash(get_text("conjugate_flash_need_verbs"), "info")
        return redirect(url_for("conjugate", lang_code=lang_code))
    if not selected_tenses:
        flash(get_text("conjugate_flash_need_tenses"), "info")
        return redirect(url_for("conjugate", lang_code=lang_code))
    # If a recap restricted the verb pool, drop ids the user doesn't own and
    # fall back to "need verbs" if nothing is left.
    if verb_ids:
        owned_ids = {v.id for v in user_verbs}
        verb_ids = [vid for vid in verb_ids if vid in owned_ids]
        if not verb_ids:
            flash(get_text("conjugate_flash_need_verbs"), "info")
            return redirect(url_for("conjugate", lang_code=lang_code))

    session["conjugate_practice"] = {
        "lang": lang_code,
        "tenses": selected_tenses,
        "persons": persons,
        "verb_ids": verb_ids,
        "difficulty": difficulty,
        "sampling_mode": sampling_mode,
        "reveal_mode": reveal_mode,
        "count": count,
        "asked": [],
        "score": 0,
        "total": 0,
        "current": None,
        "current_revealed": False,
    }
    return redirect(url_for("conjugate_practice", lang_code=lang_code))


def _get_conjugate_state(lang_code: str | None = None) -> dict | None:
    """The active practice state; None when absent or started for another language."""
    state = session.get("conjugate_practice")
    if state is None:
        return None
    if (
        lang_code is not None
        and state.get("lang", DEFAULT_CONJUGATION_LANG) != lang_code
    ):
        return None
    return state


def _save_conjugate_state(state: dict) -> None:
    session["conjugate_practice"] = state
    session.modified = True


def _conj_asked_key(
    tenses: list[str], verb_id: int, tense_key: str, person_index: int
) -> str:
    """Compact key for the per-session ``asked`` set.

    Uses the tense's *index* within the session's selected tenses rather than the
    full tense key (which can be ~40 chars, e.g. ``indicativo/
    pretérito-perfecto-compuesto``). The state lives in the signed-cookie
    session, so keeping each key to a few characters keeps the asked list well
    under the ~4 KB cookie limit even at the maximum question count.
    """
    return f"{verb_id}:{tenses.index(tense_key)}:{person_index}"


def _conj_acceptable_answers(lang_code: str, current: dict) -> list[str]:
    """Every spelling accepted for the current conjugation question.

    The German Sie-imperative is stored with its obligatory inverted pronoun
    ("gehen Sie", "stehen Sie auf") since that's the grammatically complete
    form, but every other cell expects just the verb form — so accept the
    pronoun-less variant too.
    """
    correct = current["correct_answer"]
    answers = [correct]
    if (
        lang_code == "de"
        and current["tense_key"] == "imperativ"
        and current["person_index"] == 5
    ):
        bare = " ".join(w for w in correct.split() if w != "Sie")
        if bare:
            answers.append(bare)
    return answers


def _load_next_conjugation(state: dict) -> dict | None:
    """Pick the next unasked (verb, tense, person) question; advance state.

    Samples a verb (weighted toward weak/unpracticed verbs in prioritized mode),
    then a random available tense+person for that verb that hasn't been asked.
    Verbs whose questions are all exhausted are dropped and another is tried.
    """
    lang_code = state.get("lang", DEFAULT_CONJUGATION_LANG)
    asked = set(state.get("asked", []))
    verbs = _user_verbs(lang_code)
    verb_ids = state.get("verb_ids")
    if verb_ids:
        allowed = set(verb_ids)
        verbs = [v for v in verbs if v.id in allowed]
    tenses = state["tenses"]
    persons = state["persons"]

    # Verbs that still have at least one unasked, non-null question.
    def open_questions(verb: VerbCard) -> list[tuple[str, int]]:
        out = []
        for tense_key in tenses:
            for person_index in persons:
                key = _conj_asked_key(tenses, verb.id, tense_key, person_index)
                if key in asked:
                    continue
                if (
                    _form_available(lang_code, verb.infinitive, tense_key, person_index)
                    is None
                ):
                    continue
                out.append((tense_key, person_index))
        return out

    candidates = [v for v in verbs if open_questions(v)]
    if not candidates:
        return None
    if state.get("sampling_mode") == "prioritized":
        verb = _pick_weighted_card(candidates)
    else:
        verb = candidates[secrets.randbelow(len(candidates))]

    options = open_questions(verb)
    tense_key, person_index = options[secrets.randbelow(len(options))]
    correct = _form_available(lang_code, verb.infinitive, tense_key, person_index)
    current = {
        "verb_id": verb.id,
        "infinitive": verb.infinitive,
        "tense_key": tense_key,
        "person_index": person_index,
        "correct_answer": correct,
    }
    state["current"] = current
    state["current_revealed"] = False
    return current


def _conjugate_question_view(state: dict, current: dict, lang_code: str):
    """Render the practice page for the current question."""
    difficulty = state.get("difficulty", "advanced")
    revealed = bool(state.get("current_revealed"))
    correct = current["correct_answer"]
    ui_lang = session.get("language", DEFAULT_UI_LANGUAGE)
    # The pattern hint is an advanced-mode aid only; hardcore stays no-help.
    hint = (
        _build_conjugation_hint(
            lang_code, current["tense_key"], current["person_index"], ui_lang
        )
        if (difficulty != "hardcore" and not revealed)
        else None
    )
    return render_template(
        "conjugate_practice.html",
        user=session["user"],
        lang_code=lang_code,
        infinitive=current["infinitive"],
        pronoun=person_label(lang_code, current["person_index"]),
        tense_label=tense_label(lang_code, current["tense_key"], ui_lang),
        correct_answer=correct if (revealed or difficulty == "hardcore") else None,
        difficulty=difficulty,
        revealed=revealed,
        hint=hint,
        reveal_mode=state.get("reveal_mode", "type"),
        score=state["score"],
        total=state["total"],
        max_questions=state.get("count", CONJ_QUESTIONS_DEFAULT),
        get_text=get_text,
    )


@app.route("/<lang_code>/conjugate/practice", methods=["GET", "POST"])
@login_required
def conjugate_practice(lang_code):
    """Show the current conjugation question or process an answer/reveal."""
    _require_conjugation_lang(lang_code)
    state = _get_conjugate_state(lang_code)
    if state is None:
        return redirect(url_for("conjugate", lang_code=lang_code))

    if request.method == "POST":
        current = state.get("current")
        if not current:
            return redirect(url_for("conjugate_practice", lang_code=lang_code))
        verb = db.session.get(VerbCard, current["verb_id"])
        owns_verb = verb is not None and verb.user_sub == _current_user_sub()
        correct_answer = current["correct_answer"]

        if "reveal" in request.form:
            state["total"] += 1
            if owns_verb:
                verb.times_practiced += 1
                verb.record_attempt(False)
                _record_conjugation_stat(
                    verb.user_sub,
                    lang_code,
                    current["tense_key"],
                    current["person_index"],
                    False,
                )
                db.session.commit()
            state["current_revealed"] = True
            _save_conjugate_state(state)
            return redirect(url_for("conjugate_practice", lang_code=lang_code))

        if "next" in request.form:
            # Type-to-continue: in "type" reveal mode the user must retype the
            # shown answer before advancing (client enforces too; never trust it).
            if state.get("reveal_mode", "type") == "type":
                user_answer = (request.form.get("answer") or "").strip()
                acceptable = _conj_acceptable_answers(lang_code, current)
                if not (
                    user_answer
                    and any(
                        quiz_logic.check_answer_advanced(user_answer, a)
                        for a in acceptable
                    )
                ):
                    return redirect(url_for("conjugate_practice", lang_code=lang_code))
            state["asked"].append(
                _conj_asked_key(
                    state["tenses"],
                    current["verb_id"],
                    current["tense_key"],
                    current["person_index"],
                )
            )
            state["current"] = None
            state["current_revealed"] = False
            _save_conjugate_state(state)
            return redirect(url_for("conjugate_practice", lang_code=lang_code))

        # A revealed question has already recorded its (wrong) attempt; only a
        # `next` advances it. Ignore a stray answer POST so it can't be counted
        # twice (the reveal-retype form must submit with `next`).
        if state.get("current_revealed"):
            return redirect(url_for("conjugate_practice", lang_code=lang_code))

        # A hint is an advanced-mode aid; a correct answer after one earns half a
        # point and still counts as a miss for mastery tracking.
        hint_used = (
            state.get("difficulty") == "advanced"
            and request.form.get("hint_used") == "1"
        )
        user_answer = (request.form.get("answer") or "").strip()
        acceptable = _conj_acceptable_answers(lang_code, current)
        if user_answer and any(
            quiz_logic.check_answer_advanced(user_answer, a) for a in acceptable
        ):
            state["total"] += 1
            if hint_used:
                state["score"] += 0.5
                if owns_verb:
                    verb.times_practiced += 1
                    verb.record_attempt(False)
                    _record_conjugation_stat(
                        verb.user_sub,
                        lang_code,
                        current["tense_key"],
                        current["person_index"],
                        False,
                    )
                    db.session.commit()
                flash(get_text("conjugate_flash_correct_hint"), "success")
            else:
                state["score"] += 1
                if owns_verb:
                    verb.times_practiced += 1
                    verb.times_correct += 1
                    verb.record_attempt(True)
                    _record_conjugation_stat(
                        verb.user_sub,
                        lang_code,
                        current["tense_key"],
                        current["person_index"],
                        True,
                    )
                    db.session.commit()
                flash(get_text("cards_flash_correct"), "success")
        else:
            flash(
                get_text("cards_flash_incorrect").format(correct_answer),
                "error",
            )
            state["total"] += 1
            if owns_verb:
                verb.times_practiced += 1
                verb.record_attempt(False)
                _record_conjugation_stat(
                    verb.user_sub,
                    lang_code,
                    current["tense_key"],
                    current["person_index"],
                    False,
                )
                db.session.commit()
        state["asked"].append(
            _conj_asked_key(
                state["tenses"],
                current["verb_id"],
                current["tense_key"],
                current["person_index"],
            )
        )
        state["current"] = None
        _save_conjugate_state(state)
        return redirect(url_for("conjugate_practice", lang_code=lang_code))

    # GET: render current question, or load the next one.
    count = state.get("count", CONJ_QUESTIONS_DEFAULT)
    if state.get("current") is None:
        if state["total"] >= count:
            return redirect(url_for("conjugate_practice_results", lang_code=lang_code))
        nxt = _load_next_conjugation(state)
        if nxt is None:
            _save_conjugate_state(state)
            return redirect(url_for("conjugate_practice_results", lang_code=lang_code))
        _save_conjugate_state(state)
        current = nxt
    else:
        current = state["current"]
    return _conjugate_question_view(state, current, lang_code)


@app.route("/<lang_code>/conjugate/practice/results")
@login_required
def conjugate_practice_results(lang_code):
    """Show the final conjugation score and clear session state."""
    _require_conjugation_lang(lang_code)
    if _get_conjugate_state(lang_code) is None:
        # No session, or one started for another language — leave that one alone.
        return redirect(url_for("conjugate", lang_code=lang_code))
    state = session.pop("conjugate_practice")
    score = state.get("score", 0)
    total = state.get("total", 0)
    percentage = (score / total * 100) if total else 0
    return render_template(
        "conjugate_results.html",
        user=session["user"],
        lang_code=lang_code,
        score=score,
        total=total,
        percentage=percentage,
        has_conjugation_materials=lang_code
        in get_languages_with_conjugation_materials(),
        # Settings echoed back so "Try Again" can restart the same session.
        practice_settings={
            "tenses": state.get("tenses", []),
            "persons": state.get("persons", []),
            "verb_ids": state.get("verb_ids", []),
            "difficulty": state.get("difficulty", "advanced"),
            "sampling_mode": state.get("sampling_mode", "prioritized"),
            "reveal_mode": state.get("reveal_mode", "type"),
            "count": state.get("count", CONJ_QUESTIONS_DEFAULT),
        },
        get_text=get_text,
        conj_text=lambda key: _conj_text(key, lang_code),
    )


@app.route("/api/conjugate/validate", methods=["POST"])
@login_required
def conjugate_validate_api():
    """Live word-by-word validation for the current conjugation question."""
    state = _get_conjugate_state()
    current = state.get("current") if state else None
    if not current:
        return jsonify({"error": "No active conjugation question"}), 400
    if state.get("difficulty") == "hardcore":
        return jsonify({"error": "Validation disabled in hardcore mode"}), 400
    user_input = (request.json or {}).get("input", "")
    # `lang_code="es"` forces the word_based strategy regardless of the
    # session's conjugation language — right for conjugated forms too ("de"
    # would select the compound-number decomposer, which only fits numbers).
    acceptable = _conj_acceptable_answers(
        state.get("lang", DEFAULT_CONJUGATION_LANG), current
    )
    results = [
        quiz_logic.validate_partial_answer(user_input, a, "es") for a in acceptable
    ]
    return jsonify(_pick_best_validation(results))


@app.route("/robots.txt")
def robots_txt():
    """Serve robots.txt for search engine crawlers."""
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /api/",
        "Disallow: /set_language/",
        "Disallow: /restart",
        "Disallow: /*/quiz/",
        "Disallow: /*/results",
        "Disallow: /*/start",
        "Disallow: /login",
        "Disallow: /callback",
        "Disallow: /logout",
        "Disallow: /cards",
        "Disallow: /cards/",
        "Disallow: /cards/import/",
        "Disallow: /*/conjugate",
        "Disallow: /*/conjugate/",
        "",
        f"Sitemap: {SITE_URL.rstrip('/')}/sitemap.xml",
    ]
    return Response("\n".join(lines), mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    """Serve sitemap.xml for search engine crawlers."""
    base = SITE_URL.rstrip("/")
    lastmod = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    urls = [f"{base}/"]
    for lang_code, lang_info in AVAILABLE_LANGUAGES.items():
        if lang_info.get("ready"):
            urls.append(f"{base}/{lang_code}")
            # The worksheet setup form (no params) is a real landing page.
            urls.append(f"{base}/{lang_code}/worksheet")
    for lc in get_languages_with_learn_materials():
        urls.append(f"{base}/{lc}/learn")
    for lc in get_languages_with_conjugation_materials():
        urls.append(f"{base}/{lc}/learn/conjugations")
    urls.append(f"{base}/about")
    urls.append(f"{base}/privacy")
    urls.append(f"{base}/imprint")

    xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml_lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    for loc in urls:
        xml_lines.append("  <url>")
        xml_lines.append(f"    <loc>{loc}</loc>")
        xml_lines.append(f"    <lastmod>{lastmod}</lastmod>")
        xml_lines.append("  </url>")
    xml_lines.append("</urlset>")
    return Response("\n".join(xml_lines), mimetype="application/xml")


if __name__ == "__main__":
    app.run(debug=True)
