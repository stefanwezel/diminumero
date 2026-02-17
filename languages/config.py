"""Language configuration for diminumero multi-language support."""

# Available languages with metadata
AVAILABLE_LANGUAGES = {
    "es": {
        "name": "Spanish",
        "native_name": "Español",
        "flag": "🇪🇸",
        "ready": True,
        "description": "Learn Spanish numbers from 1 to 10 million",
        "validation_strategy": "word_based",  # Numbers separated by spaces
    },
    "ne": {
        "name": "Nepalese",
        "native_name": "नेपाली",
        "flag": "🇳🇵",
        "ready": False,  # Placeholder - coming soon
        "description": "Learn Nepalese numbers (Coming Soon)",
        "validation_strategy": "word_based",  # Numbers separated by spaces
    },
    "de": {
        "name": "German",
        "native_name": "Deutsch",
        "flag": "🇩🇪",
        "ready": True,
        "description": "Learn German numbers (Coming Soon)",
        "validation_strategy": "component_based",  # Compound words
    },
}


def get_language_numbers(lang_code):
    """
    Load and return the NUMBERS dictionary for a specific language.

    Args:
        lang_code: Language code (e.g., 'es', 'ne')

    Returns:
        Dictionary mapping numbers to their translations

    Raises:
        ValueError: If language code is invalid or not available
    """
    if not is_language_available(lang_code):
        raise ValueError(f"Language '{lang_code}' is not available")

    try:
        if lang_code == "es":
            from .es import NUMBERS
        elif lang_code == "ne":
            from .ne import NUMBERS
        elif lang_code == "de":
            from .de import NUMBERS
        else:
            raise ValueError(f"Language '{lang_code}' is not implemented")

        return NUMBERS
    except ImportError as e:
        raise ValueError(f"Failed to load numbers for language '{lang_code}': {e}")


def is_language_available(lang_code):
    """
    Check if a language code is valid and available.

    Args:
        lang_code: Language code to check

    Returns:
        Boolean indicating if language is available
    """
    return lang_code in AVAILABLE_LANGUAGES


def is_language_ready(lang_code):
    """
    Check if a language is ready for use (not just a placeholder).

    Args:
        lang_code: Language code to check

    Returns:
        Boolean indicating if language is ready for use
    """
    return lang_code in AVAILABLE_LANGUAGES and AVAILABLE_LANGUAGES[lang_code].get(
        "ready", False
    )


def get_language_info(lang_code):
    """
    Get metadata for a specific language.

    Args:
        lang_code: Language code

    Returns:
        Dictionary with language metadata, or None if not found
    """
    return AVAILABLE_LANGUAGES.get(lang_code)


def get_validation_strategy(lang_code):
    """
    Get the validation strategy for a specific language.

    Args:
        lang_code: Language code

    Returns:
        String indicating validation strategy: 'word_based' or 'component_based'
        Defaults to 'word_based' if not specified
    """
    lang_info = AVAILABLE_LANGUAGES.get(lang_code, {})
    return lang_info.get("validation_strategy", "word_based")


def get_component_decomposer(lang_code):
    """
    Get the component decomposer function for a specific language.

    Args:
        lang_code: Language code

    Returns:
        Decomposer function for component-based languages, or None for word-based
    """
    if get_validation_strategy(lang_code) == "component_based":
        if lang_code == "de":
            from .de import decompose_german_number

            return decompose_german_number
    return None
