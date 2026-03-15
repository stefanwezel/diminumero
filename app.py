"""Flask application for diminumero."""

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
from dotenv import load_dotenv
import jinja2
import quiz_logic
import os
import time
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
app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY", "dev-secret-key-change-in-production"
)


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
    elif "/quiz/" in path or "/results" in path or path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
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
            breadcrumbs.append(
                {"name": lang_name, "url": f"{base}/{parts[0]}"}
            )
            if len(parts) >= 2:
                sub = "/".join(parts[1:])
                breadcrumbs.append(
                    {"name": sub.replace("/", " - ").title(), "url": f"{base}/{path}"}
                )
        elif parts[0] in ("about", "privacy", "imprint"):
            breadcrumbs.append(
                {"name": parts[0].title(), "url": f"{base}/{parts[0]}"}
            )

    return {
        "ui_language": ui_language,
        "ui_dir": "rtl" if ui_language in RTL_UI_LANGUAGES else "ltr",
        "site_url": SITE_URL,
        "canonical_url": canonical_url,
        "og_locale": og_locale,
        "og_locale_alternates": og_locale_alternates,
        "breadcrumbs": breadcrumbs,
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

    # Clear quiz-related session data but keep UI language
    ui_language = session.get("language", DEFAULT_UI_LANGUAGE)
    session.clear()
    session["language"] = ui_language
    session["learn_language"] = lang_code
    session["score"] = 0
    session["total_questions"] = 0
    session["asked_numbers"] = []
    session["mode"] = mode
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
        number, correct_answer = quiz_logic.get_random_question(numbers, asked_numbers)

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
        number, correct_answer = quiz_logic.get_random_question(numbers, asked_numbers)

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
        number, correct_answer = quiz_logic.get_random_question(numbers, asked_numbers)

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
    session.clear()
    session["language"] = ui_language
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
