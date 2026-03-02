"""Application-level configuration for diminumero."""

# Number of questions per quiz session
QUESTIONS_PER_QUIZ = 10

# Default UI display language
DEFAULT_UI_LANGUAGE = "en"

# Speed bonus thresholds per quiz mode (seconds)
# Currently set to 60s for debugging; target production value is 30s
SPEED_BONUS_TIME_EASY = 25
SPEED_BONUS_TIME_ADVANCED = 45
SPEED_BONUS_TIME_HARDCORE = 45
