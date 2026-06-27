"""Flask application for diminumero."""

import json
from datetime import datetime, timezone
from functools import wraps
from urllib.parse import quote_plus, urlencode

from flask import (
    Flask,
    Response,
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
import jinja2
import logging
import quiz_logic
import os
import re
import secrets
import sys
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
    RTL_UI_LANGUAGES,
)
from languages import (
    AVAILABLE_LANGUAGES,
    get_feedback_expression,
    get_language_numbers,
    get_language_ui_description,
    get_language_ui_name,
    get_languages_with_audio_mode,
    get_languages_with_conjugation,
    get_languages_with_conjugation_materials,
    get_languages_with_learn_materials,
    is_language_ready,
)
from translations import TRANSLATIONS
from conjugation_config import (
    CONJ_HINT_MODEL_VERBS,
    CONJ_PERSONS,
    CONJ_QUESTIONS_DEFAULT,
    CONJ_TENSES,
    CONJ_TENSE_KEYS,
    VOSOTROS_INDEX,
    person_label,
    tense_hint,
    tense_label,
)
from languages.es import conjugations as es_conjugations

# Language the conjugation section is offered for (Spanish only, for now).
CONJUGATION_LANG = "es"

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
        "site_url": SITE_URL,
        "canonical_url": canonical_url,
        "og_locale": og_locale,
        "og_locale_alternates": og_locale_alternates,
        "breadcrumbs": breadcrumbs,
        "user": session.get("user"),
        "conjugation_lang": CONJUGATION_LANG,
    }


def get_text(key):
    """Get translated text for the current language."""
    ui_language = session.get("language", DEFAULT_UI_LANGUAGE)
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
        "language_selection.html", languages=translated_languages, get_text=get_text
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

    # Load numbers for this language
    try:
        numbers = get_language_numbers(lang_code)
        total_numbers = len(numbers)
    except ValueError:
        flash(get_text("flash_language_load_error"), "error")
        return redirect(url_for("index"))

    has_learn_materials = lang_code in get_languages_with_learn_materials()
    has_audio_mode = lang_code in get_languages_with_audio_mode()
    has_conjugation_materials = lang_code in get_languages_with_conjugation_materials()

    return render_template(
        "index.html",
        total_numbers=total_numbers,
        questions_per_quiz=QUESTIONS_PER_QUIZ,
        lang_code=lang_code,
        get_text=get_text,
        has_learn_materials=has_learn_materials,
        has_audio_mode=has_audio_mode,
        has_conjugation_materials=has_conjugation_materials,
        magnitude_level=session.get("magnitude_level", 1),
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
    try:
        magnitude_level = int(request.form.get("magnitude_level", 1))
    except (TypeError, ValueError):
        magnitude_level = 1
    if magnitude_level not in range(1, 6):
        magnitude_level = 1

    # Clear quiz-related session data but keep UI language and any logged-in user
    ui_language = session.get("language", DEFAULT_UI_LANGUAGE)
    saved_user = session.get("user")
    session.clear()
    session["language"] = ui_language
    if saved_user is not None:
        session["user"] = saved_user
    session["learn_language"] = lang_code
    session["score"] = 0
    session["total_questions"] = 0
    session["asked_numbers"] = []
    session["mode"] = mode
    session["magnitude_level"] = magnitude_level
    session["quiz_start_time"] = time.time()

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

    # Load numbers for this language
    try:
        numbers = get_language_numbers(lang_code)
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
            numbers, asked_numbers, magnitude_level=session.get("magnitude_level", 1)
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

    # Load numbers for this language
    try:
        numbers = get_language_numbers(lang_code)
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
        # recorded; just clear the current question + reveal flag.
        if "next" in request.form:
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
            numbers, asked_numbers, magnitude_level=session.get("magnitude_level", 1)
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

    return render_template(
        "quiz_advanced.html",
        number=number,
        correct_answer=correct_answer,
        revealed=bool(session.get("current_revealed")),
        score=score,
        total=total,
        max_questions=QUESTIONS_PER_QUIZ,
        lang_code=lang_code,
        get_text=get_text,
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

    # Load numbers for this language
    try:
        numbers = get_language_numbers(lang_code)
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
        # recorded; just clear the current question + reveal flag.
        if "next" in request.form:
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
            numbers, asked_numbers, magnitude_level=session.get("magnitude_level", 1)
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

    return render_template(
        "quiz_hardcore.html",
        number=number,
        correct_answer=correct_answer,
        revealed=bool(session.get("current_revealed")),
        score=score,
        total=total,
        max_questions=QUESTIONS_PER_QUIZ,
        lang_code=lang_code,
        get_text=get_text,
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

    try:
        magnitude_level = int(request.form.get("magnitude_level", 1))
    except (TypeError, ValueError):
        magnitude_level = 1
    if magnitude_level not in range(1, 6):
        magnitude_level = 1

    ui_language = session.get("language", DEFAULT_UI_LANGUAGE)
    saved_user = session.get("user")
    session.clear()
    session["language"] = ui_language
    if saved_user is not None:
        session["user"] = saved_user
    session["learn_language"] = lang_code
    session["score"] = 0
    session["total_questions"] = 0
    session["asked_numbers"] = []
    session["mode"] = "audio"
    session["magnitude_level"] = magnitude_level
    session["quiz_start_time"] = time.time()

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
        numbers = get_language_numbers(lang_code)
    except ValueError:
        flash(get_text("flash_language_load_error"), "error")
        return redirect(url_for("mode_selection", lang_code=lang_code))

    available = _available_audio_numbers(lang_code)
    playable_numbers = {n: word for n, word in numbers.items() if n in available}
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
        )
        session["current_number"] = number
        session["correct_answer"] = correct_answer
        if "asked_numbers" not in session:
            session["asked_numbers"] = []
        session["asked_numbers"].append(number)

    audio_url = url_for("static", filename=f"audio/{lang_code}/{number}.mp3")

    return render_template(
        "quiz_listen.html",
        number=number,
        correct_answer=correct_answer,
        audio_url=audio_url,
        revealed=bool(session.get("current_revealed")),
        score=session.get("score", 0),
        total=session.get("total_questions", 0),
        max_questions=QUESTIONS_PER_QUIZ,
        lang_code=lang_code,
        get_text=get_text,
    )


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
    stats, stats_json = _build_cards_dashboard_stats(user_cards)
    importable = _importable_card_verbs(_current_user_sub(), user_cards)
    importable_verb_infinitives = {card.id: inf for card, inf in importable}
    return render_template(
        "cards.html",
        user=session["user"],
        cards=user_cards,
        edit_card=edit_card,
        practice_numbers_url=practice_numbers_url,
        get_text=get_text,
        stats=stats,
        stats_json=stats_json,
        importable_verb_infinitives=importable_verb_infinitives,
        importable_verb_count=len(importable),
    )


def _build_cards_dashboard_stats(user_cards: list[Card]) -> tuple[dict, str]:
    """Derive aggregate dashboard stats from a user's cards.

    Returns (stats_dict_for_jinja, json_blob_for_chart_js). The JSON blob is
    safe to drop into a <script type="application/json"> tag — Jinja's default
    autoescaping is bypassed for that element type, so we emit it ourselves
    with HTML-safe escaping.
    """
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

    # The "Top weak" bar chart stays a genuine ranking of the lowest scorers,
    # independent of the shuffled preview lists above.
    chart_weakest = sorted(practiced, key=lambda c: (c.score, -c.times_practiced))[:5]

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

    # Chart.js payload — keep it minimal and JSON-safe.
    json_payload = {
        "buckets": buckets,
        "weakest": [
            {
                "id": c.id,
                "front": c.front,
                "back": c.back,
                "score": c.score,
                "times_practiced": c.times_practiced,
            }
            for c in chart_weakest
        ],
    }
    stats_json = json.dumps(json_payload).replace("</", "<\\/")
    return stats, stats_json


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
                "verb_infinitive": _importable_infinitive_for_card(user_sub, existing),
            }
        )
    card = Card(user_sub=user_sub, front=front, back=back)
    db.session.add(card)
    db.session.commit()
    return jsonify(
        {
            "ok": True,
            "card": card.to_dict(),
            "verb_infinitive": _importable_infinitive_for_card(user_sub, card),
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
                "verb_infinitive": _importable_infinitive_for_card(card.user_sub, card),
            }
        )
    card.front = front
    card.back = back
    db.session.commit()
    return jsonify(
        {
            "ok": True,
            "card": card.to_dict(),
            "verb_infinitive": _importable_infinitive_for_card(card.user_sub, card),
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
    # If this card is a Spanish verb the user hasn't added to conjugation
    # practice yet, expose its infinitive so the page can offer a one-click add.
    verb_infinitive = _card_verb_infinitive(card)
    if verb_infinitive and _find_user_verb(_current_user_sub(), verb_infinitive):
        verb_infinitive = None
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
# A third user-owned practice section (alongside cards) for conjugating Spanish
# verbs. The user builds a personal pool of verbs drawn from the global pool
# (languages/es/conjugations.json); a session asks them to conjugate
# verb + pronoun + tense. Mirrors the cards subsystem: VerbCard model, advanced/
# hardcore typed answers with live word highlighting, 10 questions by default.


def _user_verb_or_404(verb_id: int) -> VerbCard:
    """Fetch a VerbCard and 404 if it does not belong to the current user."""
    verb = db.session.get(VerbCard, verb_id)
    if verb is None or verb.user_sub != _current_user_sub():
        from flask import abort

        abort(404)
    return verb


def _user_verbs() -> list[VerbCard]:
    return (
        db.session.query(VerbCard)
        .filter_by(user_sub=_current_user_sub())
        .order_by(VerbCard.created_at.desc())
        .all()
    )


def _normalize_infinitive(value: str) -> str:
    return (value or "").strip().lower()


def _find_user_verb(user_sub: str, infinitive: str) -> VerbCard | None:
    """Return the user's VerbCard for an infinitive (case-insensitive), or None."""
    key = _normalize_infinitive(infinitive)
    if not key:
        return None
    for verb in db.session.query(VerbCard).filter_by(user_sub=user_sub).all():
        if _normalize_infinitive(verb.infinitive) == key:
            return verb
    return None


# ----- Cards <-> conjugation sync ------------------------------------------
# An index card and a conjugation verb are linked purely by value: a card whose
# front or back is a Spanish infinitive in the global pool can become a VerbCard,
# and a VerbCard whose infinitive isn't yet a card side can become a card. The
# sync is additive only — neither side is deleted when the other is.


def _card_verb_infinitive(card: Card) -> str | None:
    """Return the normalized pool infinitive matching this card, or None.

    Either side may carry the Spanish verb (cards are free-form), so the front
    is checked first, then the back. Matching is exact against the global pool.
    """
    for side in (card.front, card.back):
        infinitive = _normalize_infinitive(side)
        if infinitive and es_conjugations.verb_exists(infinitive):
            return infinitive
    return None


def _owned_infinitives(user_sub: str) -> set[str]:
    """Normalized infinitives already in the user's conjugation pool."""
    return {
        _normalize_infinitive(v.infinitive)
        for v in db.session.query(VerbCard).filter_by(user_sub=user_sub).all()
    }


def _importable_card_verbs(user_sub: str, cards: list[Card]) -> list[tuple[Card, str]]:
    """Cards whose verb side is a pool infinitive the user doesn't own yet.

    De-duped by infinitive (the first card carrying it wins) so the same verb
    appearing on two cards is only offered once.
    """
    owned = _owned_infinitives(user_sub)
    seen: set[str] = set()
    out: list[tuple[Card, str]] = []
    for card in cards:
        infinitive = _card_verb_infinitive(card)
        if infinitive and infinitive not in owned and infinitive not in seen:
            seen.add(infinitive)
            out.append((card, infinitive))
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


def _importable_infinitive_for_card(user_sub: str, card: Card) -> str | None:
    """The pool infinitive a single card could add to conjugation, or None.

    Used by the JSON card API so the client can show the "verb" badge and
    "add to conjugation" button on a freshly created/edited card without a
    page reload. Returns None when the card isn't a verb or the user already
    owns it.
    """
    infinitive = _card_verb_infinitive(card)
    if not infinitive or _find_user_verb(user_sub, infinitive):
        return None
    return infinitive


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
    sel_tenses = [t for t in selected_tenses if t in CONJ_TENSE_KEYS]
    sel_persons = list(selected_persons)

    def _empty_cells() -> dict:
        return {cat: [] for cat in CONJ_MATRIX_CATEGORIES}

    tense_members = _empty_cells()
    for t in CONJ_TENSES:
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
    for p in CONJ_PERSONS:
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
    `ConjugationStat` rows (per user/tense/person).
    """
    total_attempts = sum(v.times_practiced for v in verbs)
    total_correct = sum(v.times_correct for v in verbs)
    overall_accuracy = total_correct / total_attempts if total_attempts else None

    stats_rows = db.session.query(ConjugationStat).filter_by(user_sub=user_sub).all()

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
    default_tenses = [t["key"] for t in CONJ_TENSES if t["default_on"]]
    default_persons = [p["index"] for p in CONJ_PERSONS if not p["optional"]]
    matrix = _conj_build_matrix(
        verbs, by_tense, by_person, default_tenses, default_persons
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
            for t in CONJ_TENSES
        ],
        "persons": [
            {
                "index": p["index"],
                "optional": p["optional"],
                "practiced": by_person.get(p["index"], [0, 0])[0],
                "correct": by_person.get(p["index"], [0, 0])[1],
            }
            for p in CONJ_PERSONS
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
    verbs = _user_verbs()
    practice_lang = session.get("learn_language")
    if practice_lang and is_language_ready(practice_lang):
        practice_numbers_url = url_for("mode_selection", lang_code=practice_lang)
    else:
        practice_numbers_url = url_for("mode_selection", lang_code=CONJUGATION_LANG)
    dashboard = _build_conjugate_dashboard_stats(_current_user_sub(), verbs, lang_code)
    user_sub = _current_user_sub()
    user_cards = db.session.query(Card).filter_by(user_sub=user_sub).all()
    card_import_count = len(_importable_card_verbs(user_sub, user_cards))
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
        tenses=CONJ_TENSES,
        persons=CONJ_PERSONS,
        vosotros_index=VOSOTROS_INDEX,
        default_count=CONJ_QUESTIONS_DEFAULT,
        practice_numbers_url=practice_numbers_url,
        dashboard=dashboard,
        get_text=get_text,
        card_import_count=card_import_count,
        missing_in_cards_count=len(missing),
        missing_in_cards_json=missing_in_cards_json,
        missing_infinitives=missing_infinitives,
    )


@app.route("/api/verbs/search")
@login_required
def api_verbs_search():
    """Autocomplete: pool infinitives starting with ?q=, excluding owned verbs."""
    query = (request.args.get("q") or "").strip()
    if not query:
        return jsonify({"ok": True, "results": []})
    owned = {_normalize_infinitive(v.infinitive) for v in _user_verbs()}
    results = es_conjugations.search_verbs(query, limit=8, exclude=owned)
    return jsonify({"ok": True, "results": results})


@app.route("/api/verbs", methods=["POST"])
@login_required
def api_verbs_create():
    """Add a verb. Rejects verbs not in the global pool with an 'unsupported' flag."""
    payload = request.get_json(silent=True) or {}
    infinitive = _normalize_infinitive(payload.get("infinitive"))
    if not infinitive:
        return jsonify(
            {"ok": False, "error": get_text("conjugate_flash_verb_required")}
        ), 400
    if not es_conjugations.verb_exists(infinitive):
        return jsonify(
            {
                "ok": False,
                "unsupported": True,
                "error": get_text("conjugate_flash_unsupported").format(infinitive),
            }
        ), 400
    user_sub = _current_user_sub()
    existing = _find_user_verb(user_sub, infinitive)
    if existing is not None:
        return jsonify({"ok": True, "duplicate": True, "verb": existing.to_dict()})
    verb = VerbCard(user_sub=user_sub, infinitive=infinitive)
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
    if not es_conjugations.verb_exists(infinitive):
        flash(get_text("conjugate_flash_unsupported").format(infinitive), "error")
        return redirect(url_for("conjugate", lang_code=lang_code))
    user_sub = _current_user_sub()
    if _find_user_verb(user_sub, infinitive) is not None:
        flash(get_text("conjugate_flash_verb_duplicate"), "info")
        return redirect(url_for("conjugate", lang_code=lang_code))
    verb = VerbCard(user_sub=user_sub, infinitive=infinitive)
    db.session.add(verb)
    db.session.commit()
    flash(get_text("conjugate_flash_verb_added"), "success")
    return redirect(url_for("conjugate", lang_code=lang_code))


@app.route("/api/verbs/import-from-cards", methods=["POST"])
@login_required
def api_verbs_import_from_cards():
    """Add every index-card verb (front/back in the pool) not already owned."""
    user_sub = _current_user_sub()
    cards = db.session.query(Card).filter_by(user_sub=user_sub).all()
    importable = _importable_card_verbs(user_sub, cards)
    added = []
    for _card, infinitive in importable:
        verb = VerbCard(user_sub=user_sub, infinitive=infinitive)
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


def _form_available(infinitive: str, tense_key: str, person_index: int) -> str | None:
    """Return the conjugated form for a verb/tense/person, or None if absent."""
    forms = es_conjugations.get_verb_forms(infinitive)
    if not forms:
        return None
    tense_forms = forms.get(tense_key)
    if not tense_forms or person_index >= len(tense_forms):
        return None
    return tense_forms[person_index]


def _build_conjugation_hint(
    tense_key: str, person_index: int, ui_lang: str = "en"
) -> dict:
    """Build the practice "Hint" excerpt for a (tense, pronoun) prompt.

    Shows the tense's regular pattern via the model verbs (one per -ar/-er/-ir
    group) with the prompted pronoun's row flagged, plus a one-line blurb. Forms
    come straight from the committed global pool, so no answer is leaked (unless
    the verb under test is itself a model verb, which just shows the pattern).
    """
    models = []
    for infinitive in CONJ_HINT_MODEL_VERBS:
        forms = es_conjugations.get_verb_forms(infinitive) or {}
        models.append(
            {
                "infinitive": infinitive,
                "forms": list(forms.get(tense_key) or []),
            }
        )
    persons = [
        {"label": person_label(p["index"]), "highlight": p["index"] == person_index}
        for p in CONJ_PERSONS
    ]
    return {
        "blurb": tense_hint(tense_key, ui_lang),
        "persons": persons,
        "models": models,
    }


def _record_conjugation_stat(
    user_sub: str, tense_key: str, person_index: int, correct: bool
) -> None:
    """Upsert the per-(tense, person) practice tally for the dashboard insights."""
    stat = (
        db.session.query(ConjugationStat)
        .filter_by(user_sub=user_sub, tense_key=tense_key, person_index=person_index)
        .first()
    )
    if stat is None:
        stat = ConjugationStat(
            user_sub=user_sub,
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
        t for t in request.form.getlist("tenses") if t in CONJ_TENSE_KEYS
    ]
    include_vosotros = request.form.get("include_vosotros") in ("1", "true", "on")
    # An explicit `persons` list (used by the insights-matrix recap buttons)
    # overrides the vosotros-toggle default. Values are validated against the
    # known person slots.
    valid_person_indices = {p["index"] for p in CONJ_PERSONS}
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
        persons = [
            p["index"]
            for p in CONJ_PERSONS
            if p["index"] != VOSOTROS_INDEX or include_vosotros
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

    user_verbs = _user_verbs()
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


def _get_conjugate_state() -> dict | None:
    return session.get("conjugate_practice")


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


def _load_next_conjugation(state: dict) -> dict | None:
    """Pick the next unasked (verb, tense, person) question; advance state.

    Samples a verb (weighted toward weak/unpracticed verbs in prioritized mode),
    then a random available tense+person for that verb that hasn't been asked.
    Verbs whose questions are all exhausted are dropped and another is tried.
    """
    asked = set(state.get("asked", []))
    verbs = _user_verbs()
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
                if _form_available(verb.infinitive, tense_key, person_index) is None:
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
    correct = _form_available(verb.infinitive, tense_key, person_index)
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
        _build_conjugation_hint(current["tense_key"], current["person_index"], ui_lang)
        if (difficulty != "hardcore" and not revealed)
        else None
    )
    return render_template(
        "conjugate_practice.html",
        user=session["user"],
        lang_code=lang_code,
        infinitive=current["infinitive"],
        pronoun=person_label(current["person_index"]),
        tense_label=tense_label(current["tense_key"], ui_lang),
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
    state = _get_conjugate_state()
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
                if not (
                    user_answer
                    and quiz_logic.check_answer_advanced(user_answer, correct_answer)
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
        if user_answer and quiz_logic.check_answer_advanced(
            user_answer, correct_answer
        ):
            state["total"] += 1
            if hint_used:
                state["score"] += 0.5
                if owns_verb:
                    verb.times_practiced += 1
                    verb.record_attempt(False)
                    _record_conjugation_stat(
                        verb.user_sub,
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
    state = session.pop("conjugate_practice", None)
    if state is None:
        return redirect(url_for("conjugate", lang_code=lang_code))
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
        get_text=get_text,
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
    result = quiz_logic.validate_partial_answer(
        user_input, current["correct_answer"], "es"
    )
    return jsonify(result)


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
