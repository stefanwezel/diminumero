"""Flask application for diminumero."""

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
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
from flask_migrate import Migrate
from werkzeug.middleware.proxy_fix import ProxyFix
import jinja2
import quiz_logic
import os
import secrets
import time

from models import Card, db
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
    get_languages_with_learn_materials,
    is_language_ready,
)
from translations import TRANSLATIONS

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
db.init_app(app)
migrate = Migrate(app, db)

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
    ):
        response.headers["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, max-age=0"
        )
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

    text = TRANSLATIONS.get(ui_language, {}).get(key, key)
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

    return render_template(
        "index.html",
        total_numbers=total_numbers,
        questions_per_quiz=QUESTIONS_PER_QUIZ,
        lang_code=lang_code,
        get_text=get_text,
        has_learn_materials=has_learn_materials,
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
    if session.get("total_questions", 0) >= QUESTIONS_PER_QUIZ:
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
        # Check if user gave up
        if "give_up" in request.form:
            correct_answer = session.get("correct_answer")
            flash(get_text("flash_gave_up").format(correct_answer), "info")
            session["total_questions"] = session.get("total_questions", 0) + 1

            # Clear current question so next GET generates a new one
            session.pop("current_number", None)
            session.pop("correct_answer", None)

            # Check if quiz is complete
            if session.get("total_questions", 0) >= QUESTIONS_PER_QUIZ:
                return redirect(url_for("results", lang_code=lang_code))

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

        # Check if quiz is complete
        if session.get("total_questions", 0) >= QUESTIONS_PER_QUIZ:
            return _results_redirect(lang_code)

        # Continue to next question
        return redirect(url_for("quiz_advanced", lang_code=lang_code))

    # GET request - display question
    # Check if quiz should end
    if session.get("total_questions", 0) >= QUESTIONS_PER_QUIZ:
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
        # Check if user gave up
        if "give_up" in request.form:
            correct_answer = session.get("correct_answer")
            flash(get_text("flash_gave_up").format(correct_answer), "info")
            session["total_questions"] = session.get("total_questions", 0) + 1

            # Clear current question so next GET generates a new one
            session.pop("current_number", None)
            session.pop("correct_answer", None)

            # Check if quiz is complete
            if session.get("total_questions", 0) >= QUESTIONS_PER_QUIZ:
                return redirect(url_for("results", lang_code=lang_code))

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

        # Check if quiz is complete
        if session.get("total_questions", 0) >= QUESTIONS_PER_QUIZ:
            return _results_redirect(lang_code)

        # Continue to next question
        return redirect(url_for("quiz_hardcore", lang_code=lang_code))

    # GET request - display question
    # Check if quiz should end
    if session.get("total_questions", 0) >= QUESTIONS_PER_QUIZ:
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
        score=score,
        total=total,
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


@app.route("/login")
def login():
    """Redirect the user to Auth0 Universal Login."""
    return oauth.auth0.authorize_redirect(
        redirect_uri=url_for("callback", _external=True)
    )


@app.route("/callback")
def callback():
    """Handle the Auth0 OIDC callback and store the user on the session."""
    token = oauth.auth0.authorize_access_token()
    session["user"] = token["userinfo"]
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
    return render_template(
        "cards.html",
        user=session["user"],
        cards=user_cards,
        edit_card=edit_card,
        practice_numbers_url=practice_numbers_url,
        get_text=get_text,
    )


@app.route("/cards", methods=["POST"])
@login_required
def cards_create():
    """Create a new index card from the form on /cards."""
    front = (request.form.get("front") or "").strip()
    back = (request.form.get("back") or "").strip()
    if not front or not back:
        flash(get_text("cards_flash_both_sides_required"), "error")
        return redirect(url_for("cards"))
    card = Card(user_sub=_current_user_sub(), front=front, back=back)
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
    card = Card(user_sub=_current_user_sub(), front=front, back=back)
    db.session.add(card)
    db.session.commit()
    return jsonify({"ok": True, "card": card.to_dict()})


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
    card.front = front
    card.back = back
    db.session.commit()
    return jsonify({"ok": True, "card": card.to_dict()})


@app.route("/api/cards/<int:card_id>", methods=["DELETE"])
@login_required
def api_cards_delete(card_id: int):
    card = _user_card_or_404(card_id)
    db.session.delete(card)
    db.session.commit()
    return jsonify({"ok": True})


# ----- Practice session ----------------------------------------------------


def _pick_prompt_side(direction: str) -> str:
    """Return 'front' or 'back' as the side to *show* the user as the prompt."""
    if direction == "front_to_back":
        return "front"
    if direction == "back_to_front":
        return "back"
    return "front" if secrets.randbelow(2) == 0 else "back"


def _load_next_card(state: dict) -> Card | None:
    """Pick the next unasked card for this practice session, advance state."""
    asked = set(state.get("asked_ids", []))
    candidates = (
        db.session.query(Card)
        .filter_by(user_sub=_current_user_sub())
        .filter(~Card.id.in_(asked) if asked else db.true())
        .all()
    )
    if not candidates:
        return None
    card = candidates[secrets.randbelow(len(candidates))]
    state["current_card_id"] = card.id
    state["current_prompt_side"] = _pick_prompt_side(state["direction"])
    state["current_revealed"] = False
    return card


@app.route("/cards/practice/start", methods=["POST"])
@login_required
def cards_practice_start():
    """Initialize a new practice session and redirect to the first question."""
    direction = request.form.get("direction", "front_to_back")
    if direction not in ("front_to_back", "back_to_front", "random"):
        direction = "front_to_back"
    try:
        count = int(request.form.get("count", 10))
    except (TypeError, ValueError):
        count = 10
    count = max(1, min(count, 100))
    have_any = (
        db.session.query(Card.id).filter_by(user_sub=_current_user_sub()).first()
        is not None
    )
    if not have_any:
        flash(get_text("cards_flash_need_cards"), "info")
        return redirect(url_for("cards"))
    session["card_practice"] = {
        "direction": direction,
        "count": count,
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
            flash(
                get_text("cards_flash_revealed").format(correct_answer),
                "info",
            )
            state["total"] += 1
        else:
            user_answer = (request.form.get("answer") or "").strip()
            if user_answer and quiz_logic.check_answer_advanced(
                user_answer, correct_answer
            ):
                state["score"] += 1
                state["total"] += 1
                flash(get_text("cards_flash_correct"), "success")
            else:
                # Wrong final submit: count as attempted, show correct answer.
                flash(
                    get_text("cards_flash_incorrect").format(correct_answer),
                    "error",
                )
                state["total"] += 1

        state["asked_ids"].append(card.id)
        state["current_card_id"] = None
        _save_practice_state(state)
        return redirect(url_for("cards_practice"))

    # GET: load (or re-load) current card.
    count = state.get("count", 10)
    # End the round once the user has been asked `count` questions, even if
    # more unseen cards exist in their deck.
    if state["total"] >= count:
        return redirect(url_for("cards_practice_results"))

    if state.get("current_card_id") is None:
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

    total_cards = (
        db.session.query(Card.id).filter_by(user_sub=_current_user_sub()).count()
    )

    return render_template(
        "cards_practice.html",
        user=session["user"],
        prompt_text=prompt_text,
        score=state["score"],
        total=state["total"],
        max_questions=min(count, total_cards),
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

    card = db.session.get(Card, state["current_card_id"])
    if card is None or card.user_sub != _current_user_sub():
        return jsonify({"error": "Card not found"}), 404

    prompt_side = state["current_prompt_side"]
    correct_answer = card.back if prompt_side == "front" else card.front

    user_input = (request.json or {}).get("input", "")
    # `lang_code="es"` forces the word_based strategy regardless of the card's
    # actual language — fine for free-form vocabulary.
    return jsonify(quiz_logic.validate_partial_answer(user_input, correct_answer, "es"))


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
        "",
        f"Sitemap: {SITE_URL.rstrip('/')}/sitemap.xml",
    ]
    return Response("\n".join(lines), mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    """Serve sitemap.xml for search engine crawlers."""
    base = SITE_URL.rstrip("/")
    urls = [
        (f"{base}/", "1.0"),
    ]
    for lang_code, lang_info in AVAILABLE_LANGUAGES.items():
        if lang_info.get("ready"):
            urls.append((f"{base}/{lang_code}", "0.8"))
    for lc in get_languages_with_learn_materials():
        urls.append((f"{base}/{lc}/learn", "0.7"))
    urls.append((f"{base}/about", "0.5"))
    urls.append((f"{base}/privacy", "0.3"))
    urls.append((f"{base}/imprint", "0.3"))

    xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml_lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    for loc, priority in urls:
        xml_lines.append("  <url>")
        xml_lines.append(f"    <loc>{loc}</loc>")
        xml_lines.append(f"    <priority>{priority}</priority>")
        xml_lines.append("  </url>")
    xml_lines.append("</urlset>")
    return Response("\n".join(xml_lines), mimetype="application/xml")


if __name__ == "__main__":
    app.run(debug=True)

# Enable debug mode by default
app.config["DEBUG"] = True
