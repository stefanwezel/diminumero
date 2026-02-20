"""Flask application for diminumero."""

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
)
from dotenv import load_dotenv
import quiz_logic
import os
from languages import AVAILABLE_LANGUAGES, get_language_numbers, is_language_ready

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY", "dev-secret-key-change-in-production"
)

# Configuration
QUESTIONS_PER_QUIZ = 10

LANGUAGE_NAME_PLACEHOLDERS = {
    "es": {"en": "Spanish", "de": "Spanisch"},
    "ne": {"en": "Nepalese", "de": "Nepalesisch"},
    "de": {"en": "German", "de": "Deutsch"},
    "fr": {"en": "French", "de": "Französisch"},
}

FEEDBACK_EXPRESSIONS = {
    "es": "¡Correcto",
    "ne": "सहि!",
    "de": "Korrekt",
    "fr": "Correct",
}


# Translations
TRANSLATIONS = {
    "en": {
        # General
        "app_title": "diminumero",
        "language_en": "English",
        "language_de": "German",
        # Language selection page
        "language_selection_title": "diminumero - Choose Your Language",
        "language_selection_subtitle": "Choose which language you want to learn!",
        "language_selection_description": "Select a language below to start practicing numbers. More languages coming soon!",
        "language_selection_start_btn": "Start Learning",
        "language_selection_coming_soon": "Coming Soon",
        "language_selection_back": "Change Language",
        "language_selection_contribute_title": "Language Missing?",
        "language_selection_contribute_description": "Help us add more languages!",
        "language_selection_contribute_btn": "Contribute on GitHub",
        # Language names and descriptions
        "lang_es_name": "Spanish",
        "lang_es_description": "Learn Spanish numbers from 1 to 10 million",
        "lang_ne_name": "Nepalese",
        "lang_ne_description": "Learn Nepalese numbers (Coming Soon)",
        "lang_de_name": "German",
        "lang_de_description": "Learn German numbers from 1 to 10 million",
        "lang_fr_name": "French",
        "lang_fr_description": "Learn French numbers from 1 to 10 million",
        # Home page (mode selection)
        "home_title": "diminumero - Home",
        "home_hero_title": "diminumero",
        "home_hero_subtitle": "Test your LANGUAGE_NAME_PLACEHOLDER number knowledge!",
        "home_hero_description": "Practice translating numbers from digits to LANGUAGE_NAME_PLACEHOLDER words. Choose your difficulty mode and start learning!",
        # Mode selection
        "mode_easy": "Easy",
        "mode_easy_desc": "Multiple choice with 4 options. Perfect for beginners!",
        "mode_easy_btn": "Start Easy Mode",
        "mode_advanced": "Advanced",
        "mode_advanced_desc": "Type the answer with live word-by-word feedback.",
        "mode_advanced_btn": "Start Advanced Mode",
        "mode_hardcore": "Hardcore",
        "mode_hardcore_desc": "Ultimate challenge mode.",
        "mode_hardcore_btn": "Start Hardcore Mode",
        # Info section
        "info_questions": "Questions",
        "info_numbers": "Numbers",
        # Learn section
        "learn_nav_text": "Learn LANGUAGE_NAME_PLACEHOLDER Numbers",
        "learn_nav_button": "Learn First",
        "learn_nav_desc": "Understand the patterns before you practice!",
        # Footer
        "footer_feedback": "Send Feedback",
        "footer_imprint": "Imprint",
        "footer_learn": "Learn",
        # Quiz interface
        "quiz_question": "Question",
        "quiz_score": "Score",
        "quiz_exit": "Exit Quiz",
        "quiz_easy_prompt": "What is this number in LANGUAGE_NAME_PLACEHOLDER?",
        "quiz_advanced_prompt": "Type this number in LANGUAGE_NAME_PLACEHOLDER:",
        "quiz_advanced_placeholder": "Type your answer here...",
        "quiz_skip": "Skip",
        "quiz_skip_tooltip": "Skip this question (no points awarded)",
        "quiz_give_up": "Give Up",
        # Results page
        "results_title": "Quiz Results",
        "results_complete": "Quiz Complete! 🎊",
        "results_correct": "Correct Answers",
        "results_perfect": "🌟 Perfect score! You're a numbers master!",
        "results_great": "🎉 Great job! You really know your numbers!",
        "results_good": "👍 Good work! Keep practicing to improve!",
        "results_keep_practicing": "📚 Keep practicing! You'll get better with time!",
        "results_try_again": "Try Again",
        "results_back_home": "Back to Home",
        # Flash messages
        "flash_invalid_mode": "Invalid mode selected.",
        "flash_invalid_language": "Invalid language selected.",
        "flash_language_load_error": "Failed to load language data.",
        "flash_learn_not_available": "Learning materials not yet available for this language.",
        "flash_hardcore_soon": "Hardcore mode is coming soon! Try Easy or Advanced mode.",
        "flash_correct": "{}! 🎉",
        "flash_incorrect": "Incorrect. The answer was: {}",
        "flash_gave_up": "The answer was: {}",
        # Imprint page
        "imprint_title": "Imprint - diminumero",
        "imprint_heading": "Imprint",
        "imprint_legal_info": "Information according to § 5 TMG",
        "imprint_contact": "Contact",
        "imprint_email": "Email",
        "imprint_disclaimer": "Disclaimer",
        "imprint_content_heading": "Liability for Content",
        "imprint_content_text": "As a service provider, we are responsible for our own content on these pages in accordance with general legislation pursuant to Section 7(1) of the German Telemedia Act (TMG). However, according to Sections 8 to 10 TMG, we are not obligated as a service provider to monitor transmitted or stored third-party information or to investigate circumstances that indicate illegal activity. Obligations to remove or block the use of information under general legislation remain unaffected. However, liability in this regard is only possible from the time of knowledge of a specific legal violation. Upon becoming aware of corresponding legal violations, we will remove this content immediately.",
        "imprint_links_heading": "Liability for Links",
        "imprint_links_text": "Our website contains links to external third-party websites over whose content we have no influence. Therefore, we cannot assume any liability for this external content. The respective provider or operator of the pages is always responsible for the content of the linked pages. The linked pages were checked for possible legal violations at the time of linking. Illegal content was not recognizable at the time of linking. However, permanent monitoring of the content of the linked pages is unreasonable without concrete evidence of a legal violation. Upon becoming aware of legal violations, we will remove such links immediately.",
        "imprint_copyright_heading": "Copyright",
        "imprint_copyright_text": "The content and works created by the site operators on these pages are subject to German copyright law. Reproduction, editing, distribution, and any kind of use outside the limits of copyright law require the written consent of the respective author or creator. Downloads and copies of this site are only permitted for private, non-commercial use. Insofar as the content on this site was not created by the operator, the copyrights of third parties are respected. In particular, third-party content is marked as such. Should you nevertheless become aware of a copyright infringement, please inform us accordingly. Upon becoming aware of legal violations, we will remove such content immediately.",
        "imprint_back_home": "Back to Home",
        # Email subject
        # Privacy policy
        "footer_privacy": "Privacy Policy",
        "privacy_title": "Privacy Policy - diminumero",
        "privacy_heading": "Privacy Policy",
        "privacy_intro_heading": "Introduction",
        "privacy_intro_text": "We take the protection of your personal data seriously. This privacy policy explains what data we collect and how we use it.",
        "privacy_cookies_heading": "Cookies and Similar Technologies",
        "privacy_cookies_text": "This website uses cookies to ensure proper functionality:",
        "privacy_session_cookies": "Session Cookies",
        "privacy_session_cookies_desc": "We use strictly necessary session cookies to make the quiz work. These cookies store your quiz progress, score, and language preference temporarily. They are essential for the website to function and are automatically deleted when you close your browser.",
        "privacy_data_collection_heading": "Data Collection and Storage",
        "privacy_data_collection_text": "We do NOT collect, store, or process any personal data. We do not track users, create profiles, or share any information with third parties (except as required for Google AdSense, see below). Your quiz answers and progress are stored only temporarily in your browser session and are not saved to any server.",
        "privacy_adsense_heading": "Google AdSense",
        "privacy_adsense_text": "This website displays advertisements through Google AdSense. Google may use cookies and similar technologies to show personalized ads based on your browsing activity.",
        "privacy_adsense_info": "For more information about how Google uses data, please visit: https://policies.google.com/technologies/partner-sites",
        "privacy_your_rights_heading": "Your Rights",
        "privacy_your_rights_text": "Since we do not collect or store personal data, there is no data to access, correct, or delete. You can clear your browser cookies at any time through your browser settings.",
        "privacy_contact_heading": "Contact",
        "privacy_contact_text": "If you have any questions about this privacy policy, please contact us:",
        "privacy_email": "Email",
        "privacy_back_home": "Back to Home",
        # Cookie banner
        "cookie_banner_text": "This website uses only essential session cookies to make the quiz work. We don't store, track, or share any personal data.",
        "cookie_banner_adsense": "Google AdSense may display personalized ads.",
        "cookie_banner_learn_more": "Learn more",
        "cookie_banner_accept": "Got it",
        # Privacy policy
        "footer_privacy": "Privacy Policy",
        "privacy_title": "Privacy Policy - diminumero",
        "privacy_heading": "Privacy Policy",
        "privacy_intro_heading": "Introduction",
        "privacy_intro_text": "We take the protection of your personal data seriously. This privacy policy explains what data we collect and how we use it.",
        "privacy_cookies_heading": "Cookies and Similar Technologies",
        "privacy_cookies_text": "This website uses cookies to ensure proper functionality:",
        "privacy_session_cookies": "Session Cookies",
        "privacy_session_cookies_desc": "We use strictly necessary session cookies to make the quiz work. These cookies store your quiz progress, score, and language preference temporarily. They are essential for the website to function and are automatically deleted when you close your browser.",
        "privacy_data_collection_heading": "Data Collection and Storage",
        "privacy_data_collection_text": "We do NOT collect, store, or process any personal data. We do not track users, create profiles, or share any information with third parties (except as required for Google AdSense, see below). Your quiz answers and progress are stored only temporarily in your browser session and are not saved to any server.",
        "privacy_adsense_heading": "Google AdSense",
        "privacy_adsense_text": "This website displays advertisements through Google AdSense. Google may use cookies and similar technologies to show personalized ads based on your browsing activity.",
        "privacy_adsense_info": "For more information about how Google uses data, please visit: https://policies.google.com/technologies/partner-sites",
        "privacy_your_rights_heading": "Your Rights",
        "privacy_your_rights_text": "Since we do not collect or store personal data, there is no data to access, correct, or delete. You can clear your browser cookies at any time through your browser settings.",
        "privacy_contact_heading": "Contact",
        "privacy_contact_text": "If you have any questions about this privacy policy, please contact us:",
        "privacy_email": "Email",
        "privacy_back_home": "Back to Home",
        # Cookie banner
        "cookie_banner_text": "This website uses only essential session cookies to make the quiz work. We don't store, track, or share any personal data.",
        "cookie_banner_adsense": "Google AdSense may display personalized ads.",
        "cookie_banner_learn_more": "Learn more",
        "cookie_banner_accept": "Got it",
        "feedback_subject": "diminumero Feedback",
    },
    "de": {
        # General
        "app_title": "diminumero",
        "language_en": "Englisch",
        "language_de": "Deutsch",
        # Language selection page
        "language_selection_title": "diminumero - Wähle deine Sprache",
        "language_selection_subtitle": "Wähle die Sprache, die du lernen möchtest!",
        "language_selection_description": "Wähle unten eine Sprache aus, um mit dem Üben von Zahlen zu beginnen. Weitere Sprachen folgen bald!",
        "language_selection_start_btn": "Lernen beginnen",
        "language_selection_coming_soon": "Demnächst",
        "language_selection_back": "Sprache wechseln",
        "language_selection_contribute_title": "Sprache fehlt?",
        "language_selection_contribute_description": "Hilf uns, weitere Sprachen hinzuzufügen!",
        "language_selection_contribute_btn": "Auf GitHub beitragen",
        # Language names and descriptions
        "lang_es_name": "Spanisch",
        "lang_es_description": "Lerne Spanische Zahlen von 1 bis 10 Millionen",
        "lang_ne_name": "Nepalesisch",
        "lang_ne_description": "Lerne Nepalesische Zahlen (Demnächst)",
        "lang_de_name": "Deutsch",
        "lang_de_description": "Lerne Deutsche Zahlen von 1 bis 10 Millionen",
        "lang_fr_name": "Französisch",
        "lang_fr_description": "Lerne Französische Zahlen von 1 bis 10 Millionen",
        # Home page (mode selection)
        "home_title": "diminumero - Startseite",
        "home_hero_title": "diminumero",
        "home_hero_subtitle": "Teste dein Wissen über LANGUAGE_NAME_PLACEHOLDERe Zahlen!",
        "home_hero_description": "Übe die Übersetzung von Zahlen in LANGUAGE_NAME_PLACEHOLDERe Wörter. Wähle deinen Schwierigkeitsgrad und fang an zu lernen!",
        # Mode selection
        "mode_easy": "Einfach",
        "mode_easy_desc": "Multiple Choice mit 4 Optionen. Perfekt für Anfänger!",
        "mode_easy_btn": "Einfachen Modus starten",
        "mode_advanced": "Schwierig",
        "mode_advanced_desc": "Tippe die Antwort mit Live-Feedback Wort für Wort.",
        "mode_advanced_btn": "Schwierigen Modus starten",
        "mode_hardcore": "Hardcore",
        "mode_hardcore_desc": "Ultimativer Modus.",
        "mode_hardcore_btn": "Hardcore-Modus starten",
        # Info section
        "info_questions": "Fragen",
        "info_numbers": "Zahlen",
        # Learn section
        "learn_nav_text": "LANGUAGE_NAME_PLACEHOLDER Zahlen lernen",
        "learn_nav_button": "Zuerst lernen",
        "learn_nav_desc": "Verstehe die Muster, bevor du übst!",
        # Footer
        "footer_feedback": "Feedback senden",
        "footer_imprint": "Impressum",
        "footer_learn": "Lernen",
        # Quiz interface
        "quiz_question": "Frage",
        "quiz_score": "Punktzahl",
        "quiz_exit": "Beenden",
        "quiz_easy_prompt": "Wie lautet diese Zahl auf LANGUAGE_NAME_PLACEHOLDER?",
        "quiz_advanced_prompt": "Schreibe diese Zahl auf LANGUAGE_NAME_PLACEHOLDER:",
        "quiz_advanced_placeholder": "Gib deine Antwort hier ein...",
        "quiz_skip": "Skippen",
        "quiz_skip_tooltip": "Diese Frage überspringen (keine Punkte)",
        "quiz_give_up": "Aufgeben",
        # Results page
        "results_title": "Quiz Ergebnisse",
        "results_complete": "Quiz abgeschlossen! 🎊",
        "results_correct": "Richtige Antworten",
        "results_perfect": "🌟 Perfekte Punktzahl! Du bist ein Meister der Zahlen!",
        "results_great": "🎉 Großartig! Du kennst deine Zahlen wirklich gut!",
        "results_good": "👍 Gute Arbeit! Übe weiter, um dich zu verbessern!",
        "results_keep_practicing": "📚 Weiter üben! Mit der Zeit wirst du besser!",
        "results_try_again": "Nochmal versuchen",
        "results_back_home": "Zurück zur Startseite",
        # Flash messages
        "flash_invalid_mode": "Ungültiger Modus ausgewählt.",
        "flash_invalid_language": "Ungültige Sprache ausgewählt.",
        "flash_language_load_error": "Laden der Sprachdaten fehlgeschlagen.",
        "flash_learn_not_available": "Lernmaterialien für diese Sprache sind noch nicht verfügbar.",
        "flash_hardcore_soon": "Hardcore-Modus kommt bald! Probiere den einfachen oder fortgeschrittenen Modus.",
        "flash_correct": "{}! 🎉",
        "flash_incorrect": "Falsch. Die Antwort war: {}",
        "flash_gave_up": "Die Antwort war: {}",
        # Imprint page
        "imprint_title": "Impressum - diminumero",
        "imprint_heading": "Impressum",
        "imprint_legal_info": "Angaben gemäß § 5 TMG",
        "imprint_contact": "Kontakt",
        "imprint_email": "E-Mail",
        "imprint_disclaimer": "Haftungsausschluss",
        "imprint_content_heading": "Haftung für Inhalte",
        "imprint_content_text": "Als Diensteanbieter sind wir gemäß § 7 Abs.1 TMG für eigene Inhalte auf diesen Seiten nach den allgemeinen Gesetzen verantwortlich. Nach §§ 8 bis 10 TMG sind wir als Diensteanbieter jedoch nicht verpflichtet, übermittelte oder gespeicherte fremde Informationen zu überwachen oder nach Umständen zu forschen, die auf eine rechtswidrige Tätigkeit hinweisen. Verpflichtungen zur Entfernung oder Sperrung der Nutzung von Informationen nach den allgemeinen Gesetzen bleiben hiervon unberührt. Eine diesbezügliche Haftung ist jedoch erst ab dem Zeitpunkt der Kenntnis einer konkreten Rechtsverletzung möglich. Bei Bekanntwerden von entsprechenden Rechtsverletzungen werden wir diese Inhalte umgehend entfernen.",
        "imprint_links_heading": "Haftung für Links",
        "imprint_links_text": "Unser Angebot enthält Links zu externen Websites Dritter, auf deren Inhalte wir keinen Einfluss haben. Deshalb können wir für diese fremden Inhalte auch keine Gewähr übernehmen. Für die Inhalte der verlinkten Seiten ist stets der jeweilige Anbieter oder Betreiber der Seiten verantwortlich. Die verlinkten Seiten wurden zum Zeitpunkt der Verlinkung auf mögliche Rechtsverstöße überprüft. Rechtswidrige Inhalte waren zum Zeitpunkt der Verlinkung nicht erkennbar. Eine permanente inhaltliche Kontrolle der verlinkten Seiten ist jedoch ohne konkrete Anhaltspunkte einer Rechtsverletzung nicht zumutbar. Bei Bekanntwerden von Rechtsverletzungen werden wir derartige Links umgehend entfernen.",
        "imprint_copyright_heading": "Urheberrecht",
        "imprint_copyright_text": "Die durch die Seitenbetreiber erstellten Inhalte und Werke auf diesen Seiten unterliegen dem deutschen Urheberrecht. Die Vervielfältigung, Bearbeitung, Verbreitung und jede Art der Verwertung außerhalb der Grenzen des Urheberrechtes bedürfen der schriftlichen Zustimmung des jeweiligen Autors bzw. Erstellers. Downloads und Kopien dieser Seite sind nur für den privaten, nicht kommerziellen Gebrauch gestattet. Soweit die Inhalte auf dieser Seite nicht vom Betreiber erstellt wurden, werden die Urheberrechte Dritter beachtet. Insbesondere werden Inhalte Dritter als solche gekennzeichnet. Sollten Sie trotzdem auf eine Urheberrechtsverletzung aufmerksam werden, bitten wir um einen entsprechenden Hinweis. Bei Bekanntwerden von Rechtsverletzungen werden wir derartige Inhalte umgehend entfernen.",
        "imprint_back_home": "Zurück zur Startseite",
        # Email subject
        # Privacy policy
        "footer_privacy": "Datenschutz",
        "privacy_title": "Datenschutzerklärung - diminumero",
        "privacy_heading": "Datenschutzerklärung",
        "privacy_intro_heading": "Einleitung",
        "privacy_intro_text": "Wir nehmen den Schutz Ihrer persönlichen Daten ernst. Diese Datenschutzerklärung erklärt, welche Daten wir sammeln und wie wir sie verwenden.",
        "privacy_cookies_heading": "Cookies und ähnliche Technologien",
        "privacy_cookies_text": "Diese Website verwendet Cookies, um ordnungsgemäß zu funktionieren:",
        "privacy_session_cookies": "Sitzungs-Cookies",
        "privacy_session_cookies_desc": "Wir verwenden ausschließlich notwendige Sitzungs-Cookies, damit das Quiz funktioniert. Diese Cookies speichern temporär Ihren Quizfortschritt, Punktestand und Spracheinstellung. Sie sind für die Funktionalität der Website unerlässlich und werden automatisch gelöscht, wenn Sie Ihren Browser schließen.",
        "privacy_data_collection_heading": "Datenerfassung und -speicherung",
        "privacy_data_collection_text": "Wir sammeln, speichern oder verarbeiten KEINE personenbezogenen Daten. Wir tracken keine Nutzer, erstellen keine Profile und teilen keine Informationen mit Dritten (außer wie für Google AdSense erforderlich, siehe unten). Ihre Quizantworten und Ihr Fortschritt werden nur temporär in Ihrer Browser-Sitzung gespeichert und nicht auf einem Server gesichert.",
        "privacy_adsense_heading": "Google AdSense",
        "privacy_adsense_text": "Diese Website zeigt Werbung über Google AdSense an. Google kann Cookies und ähnliche Technologien verwenden, um personalisierte Anzeigen basierend auf Ihrer Browsing-Aktivität zu schalten.",
        "privacy_adsense_info": "Für mehr Informationen darüber, wie Google Daten verwendet, besuchen Sie bitte: https://policies.google.com/technologies/partner-sites",
        "privacy_your_rights_heading": "Ihre Rechte",
        "privacy_your_rights_text": "Da wir keine personenbezogenen Daten sammeln oder speichern, gibt es keine Daten, auf die zugegriffen, die korrigiert oder gelöscht werden könnten. Sie können Ihre Browser-Cookies jederzeit über Ihre Browsereinstellungen löschen.",
        "privacy_contact_heading": "Kontakt",
        "privacy_contact_text": "Wenn Sie Fragen zu dieser Datenschutzerklärung haben, kontaktieren Sie uns bitte:",
        "privacy_email": "E-Mail",
        "privacy_back_home": "Zurück zur Startseite",
        # Cookie banner
        "cookie_banner_text": "Diese Website verwendet nur essentielle Sitzungs-Cookies, damit das Quiz funktioniert. Wir speichern, tracken oder teilen keine persönlichen Daten.",
        "cookie_banner_adsense": "Google AdSense kann personalisierte Werbung anzeigen.",
        "cookie_banner_learn_more": "Mehr erfahren",
        "cookie_banner_accept": "Verstanden",
        # Privacy policy
        "footer_privacy": "Datenschutz",
        "privacy_title": "Datenschutzerklärung - diminumero",
        "privacy_heading": "Datenschutzerklärung",
        "privacy_intro_heading": "Einleitung",
        "privacy_intro_text": "Wir nehmen den Schutz Ihrer persönlichen Daten ernst. Diese Datenschutzerklärung erklärt, welche Daten wir sammeln und wie wir sie verwenden.",
        "privacy_cookies_heading": "Cookies und ähnliche Technologien",
        "privacy_cookies_text": "Diese Website verwendet Cookies, um ordnungsgemäß zu funktionieren:",
        "privacy_session_cookies": "Sitzungs-Cookies",
        "privacy_session_cookies_desc": "Wir verwenden ausschließlich notwendige Sitzungs-Cookies, damit das Quiz funktioniert. Diese Cookies speichern temporär Ihren Quizfortschritt, Punktestand und Spracheinstellung. Sie sind für die Funktionalität der Website unerlässlich und werden automatisch gelöscht, wenn Sie Ihren Browser schließen.",
        "privacy_data_collection_heading": "Datenerfassung und -speicherung",
        "privacy_data_collection_text": "Wir sammeln, speichern oder verarbeiten KEINE personenbezogenen Daten. Wir tracken keine Nutzer, erstellen keine Profile und teilen keine Informationen mit Dritten (außer wie für Google AdSense erforderlich, siehe unten). Ihre Quizantworten und Ihr Fortschritt werden nur temporär in Ihrer Browser-Sitzung gespeichert und nicht auf einem Server gesichert.",
        "privacy_adsense_heading": "Google AdSense",
        "privacy_adsense_text": "Diese Website zeigt Werbung über Google AdSense an. Google kann Cookies und ähnliche Technologien verwenden, um personalisierte Anzeigen basierend auf Ihrer Browsing-Aktivität zu schalten.",
        "privacy_adsense_info": "Für mehr Informationen darüber, wie Google Daten verwendet, besuchen Sie bitte: https://policies.google.com/technologies/partner-sites",
        "privacy_your_rights_heading": "Ihre Rechte",
        "privacy_your_rights_text": "Da wir keine personenbezogenen Daten sammeln oder speichern, gibt es keine Daten, auf die zugegriffen, die korrigiert oder gelöscht werden könnten. Sie können Ihre Browser-Cookies jederzeit über Ihre Browsereinstellungen löschen.",
        "privacy_contact_heading": "Kontakt",
        "privacy_contact_text": "Wenn Sie Fragen zu dieser Datenschutzerklärung haben, kontaktieren Sie uns bitte:",
        "privacy_email": "E-Mail",
        "privacy_back_home": "Zurück zur Startseite",
        # Cookie banner
        "cookie_banner_text": "Diese Website verwendet nur essentielle Sitzungs-Cookies, damit das Quiz funktioniert. Wir speichern, tracken oder teilen keine persönlichen Daten.",
        "cookie_banner_adsense": "Google AdSense kann personalisierte Werbung anzeigen.",
        "cookie_banner_learn_more": "Mehr erfahren",
        "cookie_banner_accept": "Verstanden",
        "feedback_subject": "diminumero Feedback",
    },
}


def get_text(key):
    """Get translated text for the current language."""
    ui_language = session.get("language", "de")  # Default to German
    name = TRANSLATIONS.get(ui_language, {}).get(key, key)
    name = name.replace(
        "LANGUAGE_NAME_PLACEHOLDER",
        LANGUAGE_NAME_PLACEHOLDERS[session.get("learn_language", "es")][ui_language],
    )
    return name


@app.route("/")
def index():
    """Language selection landing page."""
    # Initialize UI language if not set
    if "language" not in session:
        session["language"] = "de"  # Default to German

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
    # Initialize UI language if not set
    if "language" not in session:
        session["language"] = "de"

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

    # Currently only Spanish has learning materials
    has_learn_materials = lang_code == "es"

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
    if lang in ["en", "de"]:
        session["language"] = lang
    # Redirect back to the referring page or index
    return redirect(request.referrer or url_for("index"))


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
    ui_language = session.get("language", "de")
    session.clear()
    session["language"] = ui_language
    session["learn_language"] = lang_code
    session["score"] = 0
    session["total_questions"] = 0
    session["asked_numbers"] = []
    session["mode"] = mode

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
        current_number = session.get("current_number")

        if user_answer and correct_answer:
            is_correct = quiz_logic.check_answer(user_answer, correct_answer)

            if is_correct:
                session["score"] = session.get("score", 0) + 1
                flash(
                    get_text("flash_correct").format(
                        FEEDBACK_EXPRESSIONS.get(lang_code)
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
            return redirect(url_for("results", lang_code=lang_code))

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
                        FEEDBACK_EXPRESSIONS.get(lang_code)
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
            return redirect(url_for("results", lang_code=lang_code))

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
                        FEEDBACK_EXPRESSIONS.get(lang_code)
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
            return redirect(url_for("results", lang_code=lang_code))

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

    return render_template(
        "results.html",
        score=score,
        attempted=attempted,
        max_questions=max_questions,
        score_ratio=score_ratio,
        percentage=percentage,
        lang_code=lang_code,
        get_text=get_text,
    )


@app.route("/restart", methods=["POST"])
def restart():
    """Restart the quiz."""
    session.clear()
    return redirect(url_for("index"))


@app.route("/privacy")
def privacy():
    """Display privacy policy page."""
    return render_template("privacy.html", get_text=get_text)


@app.route("/imprint")
def imprint():
    """Display imprint/impressum page."""
    return render_template("imprint.html", get_text=get_text)


@app.route("/<lang_code>/learn")
def learn(lang_code):
    """Display learn/tutorial page for a specific language."""
    # Validate language
    if not is_language_ready(lang_code):
        return redirect(url_for("index"))

    # Currently only Spanish has learn pages
    if lang_code != "es":
        flash(get_text("flash_learn_not_available"), "info")
        return redirect(url_for("mode_selection", lang_code=lang_code))

    ui_lang = session.get("language", "de")
    template = f"learn_{lang_code}_{ui_lang}.html"

    # Fallback to English if template doesn't exist
    try:
        return render_template(template, lang_code=lang_code, get_text=get_text)
    except:
        template = f"learn_{lang_code}_en.html"
        return render_template(template, lang_code=lang_code, get_text=get_text)


if __name__ == "__main__":
    app.run(debug=True)

# Enable debug mode by default
app.config["DEBUG"] = True
