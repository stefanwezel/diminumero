"""Application-level configuration for diminumero."""

import os

# Site URL for SEO (canonical URLs, sitemap, etc.)
SITE_URL = os.environ.get("SITE_URL", "https://diminumero.com")

# Number of questions per quiz session
QUESTIONS_PER_QUIZ = 10

# Whether number forms marked `reconstructed` may be served to learners.
#
# A reconstructed form was derived from a grammatical rule (by an LLM, or by a
# generator script) and has NOT been confirmed by any speaker of the language.
# They are committed so they can be exported for review
# (tools/export_unconfirmed_forms.py) and switched on in one line once they come
# back confirmed — never so they can quietly reach a learner in the meantime.
# With this False the drill skips those numbers entirely: it does not fall back
# to another system and it does not show a blank.
SERVE_RECONSTRUCTED = False

# Default UI display language
DEFAULT_UI_LANGUAGE = "en"

# Supported UI language codes
SUPPORTED_UI_LANGUAGES = {"en", "de", "es", "it", "fr", "pt", "ar", "uk", "cy"}

# UI languages that are still being translated. They are selectable, but most
# strings still fall back to English (see get_text in app.py), so the pages say
# so instead of quietly looking finished. Remove a code from here once its dict
# in translations.py is complete — nothing else has to change.
PARTIAL_UI_LANGUAGES = {"cy"}

# UI languages that use right-to-left text direction
RTL_UI_LANGUAGES = {"ar"}

# Speed bonus thresholds per quiz mode (seconds)
# Currently set to 60s for debugging; target production value is 30s
SPEED_BONUS_TIME_EASY = 25
SPEED_BONUS_TIME_ADVANCED = 45
SPEED_BONUS_TIME_HARDCORE = 45
