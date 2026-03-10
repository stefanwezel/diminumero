"""Application-level configuration for diminumero."""

import os

# Site URL for SEO (canonical URLs, sitemap, etc.)
SITE_URL = os.environ.get("SITE_URL", "https://diminumero.com")

# Number of questions per quiz session
QUESTIONS_PER_QUIZ = 10

# Default UI display language
DEFAULT_UI_LANGUAGE = "en"

# Supported UI language codes
SUPPORTED_UI_LANGUAGES = {"en", "de", "es", "it", "fr", "pt", "ar", "uk"}

# UI languages that use right-to-left text direction
RTL_UI_LANGUAGES = {"ar"}

# Speed bonus thresholds per quiz mode (seconds)
# Currently set to 60s for debugging; target production value is 30s
SPEED_BONUS_TIME_EASY = 25
SPEED_BONUS_TIME_ADVANCED = 45
SPEED_BONUS_TIME_HARDCORE = 45
