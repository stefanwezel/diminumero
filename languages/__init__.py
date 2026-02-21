"""Languages package for diminumero - multi-language learning support."""

from .config import (
    AVAILABLE_LANGUAGES,
    get_feedback_expression,
    get_language_numbers,
    get_language_ui_description,
    get_language_ui_name,
    is_language_available,
    is_language_ready,
)

__all__ = [
    "AVAILABLE_LANGUAGES",
    "get_feedback_expression",
    "get_language_numbers",
    "get_language_ui_description",
    "get_language_ui_name",
    "is_language_available",
    "is_language_ready",
]
