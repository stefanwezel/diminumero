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
        # UI display names keyed by UI language code
        "ui_names": {"en": "Spanish", "de": "Spanisch"},
        # Translated descriptions shown on the language selection page
        "ui_descriptions": {
            "en": "Learn Spanish numbers from 1 to 10 million",
            "de": "Lerne Spanische Zahlen von 1 bis 10 Millionen",
        },
        # Word shown to the user when they answer correctly (in the target language)
        "feedback_expression": "¡Correcto",
    },
    "fr": {
        "name": "French",
        "native_name": "Français",
        "flag": "🇫🇷",
        "ready": True,
        "description": "Learn French numbers from 1 to 10 million",
        "validation_strategy": "word_based",  # Numbers separated by spaces/hyphens
        "ui_names": {"en": "French", "de": "Französisch"},
        "ui_descriptions": {
            "en": "Learn French numbers from 1 to 10 million",
            "de": "Lerne Französische Zahlen von 1 bis 10 Millionen",
        },
        "feedback_expression": "Correct",
    },
    "ja": {
        "name": "Japanese",
        "native_name": "日本語",
        "flag": "🇯🇵",
        "ready": True,
        "description": "Learn Japanese numbers from 1 to 10 million",
        "validation_strategy": "word_based",
        "ui_names": {"en": "Japanese", "de": "Japanisch"},
        "ui_descriptions": {
            "en": "Learn Japanese numbers from 1 to 10 million",
            "de": "Lerne Japanische Zahlen von 1 bis 10 Millionen",
        },
        "feedback_expression": "正解!",
    },
    "de": {
        "name": "German",
        "native_name": "Deutsch",
        "flag": "🇩🇪",
        "ready": True,
        "description": "Learn German numbers from 1 to 10 million",
        "validation_strategy": "component_based",  # Compound words
        "ui_names": {"en": "German", "de": "Deutsch"},
        "ui_descriptions": {
            "en": "Learn German numbers from 1 to 10 million",
            "de": "Lerne Deutsche Zahlen von 1 bis 10 Millionen",
        },
        "feedback_expression": "Korrekt",
    },
    "ko": {
        "name": "Korean",
        "native_name": "한국어",
        "flag": "🇰🇷",
        "ready": True,
        "description": "Learn Korean numbers from 1 to 10 million",
        "validation_strategy": "word_based",
        "ui_names": {"en": "Korean", "de": "Koreanisch"},
        "ui_descriptions": {
            "en": "Learn Korean numbers from 1 to 10 million",
            "de": "Lerne Koreanische Zahlen von 1 bis 10 Millionen",
        },
        "feedback_expression": "정답!",
    },
    "it": {
        "name": "Italian",
        "native_name": "Italiano",
        "flag": "🇮🇹",
        "ready": True,
        "description": "Learn Italian numbers from 1 to 10 million",
        "validation_strategy": "word_based",
        "ui_names": {"en": "Italian", "de": "Italienisch"},
        "ui_descriptions": {
            "en": "Learn Italian numbers from 1 to 10 million",
            "de": "Lerne Italienische Zahlen von 1 bis 10 Millionen",
        },
        "feedback_expression": "Corretto!",
    },
    "zh": {
        "name": "Chinese",
        "native_name": "中文",
        "flag": "🇨🇳",
        "ready": True,
        "description": "Learn Chinese numbers from 1 to 10 million",
        "validation_strategy": "word_based",
        "ui_names": {"en": "Chinese", "de": "Chinesisch"},
        "ui_descriptions": {
            "en": "Learn Chinese numbers from 1 to 10 million",
            "de": "Lerne Chinesische Zahlen von 1 bis 10 Millionen",
        },
        "feedback_expression": "正确!",
    },
    "pt": {
        "name": "Portuguese",
        "native_name": "Português",
        "flag": "🇧🇷",
        "ready": True,
        "description": "Learn Portuguese numbers from 1 to 10 million",
        "validation_strategy": "word_based",
        "ui_names": {"en": "Portuguese", "de": "Portugiesisch"},
        "ui_descriptions": {
            "en": "Learn Portuguese numbers from 1 to 10 million",
            "de": "Lerne Portugiesische Zahlen von 1 bis 10 Millionen",
        },
        "feedback_expression": "Correto!",
    },
    "tr": {
        "name": "Turkish",
        "native_name": "Türkçe",
        "flag": "🇹🇷",
        "ready": True,
        "description": "Learn Turkish numbers from 1 to 10 million",
        "validation_strategy": "word_based",
        "ui_names": {"en": "Turkish", "de": "Türkisch"},
        "ui_descriptions": {
            "en": "Learn Turkish numbers from 1 to 10 million",
            "de": "Lerne Türkische Zahlen von 1 bis 10 Millionen",
        },
        "feedback_expression": "Doğru!",
    },
    "ne": {
        "name": "Nepalese",
        "native_name": "नेपाली",
        "flag": "🇳🇵",
        "ready": True,
        "description": "Learn Nepalese numbers",
        "validation_strategy": "word_based",  # Numbers separated by spaces
        "ui_names": {"en": "Nepalese", "de": "Nepalesisch"},
        "ui_descriptions": {
            "en": "Learn Nepalese numbers from 1 to 1000",
            "de": "Lerne Nepalesische Zahlen von 1 bis 1000",
        },
        "feedback_expression": "सहि!",
    },
    "sv": {
        "name": "Swedish",
        "native_name": "Svenska",
        "flag": "🇸🇪",
        "ready": True,
        "description": "Learn Swedish numbers from 1 to 10 million",
        "validation_strategy": "word_based",
        "ui_names": {"en": "Swedish", "de": "Schwedisch"},
        "ui_descriptions": {
            "en": "Learn Swedish numbers from 1 to 10 million",
            "de": "Lerne Schwedische Zahlen von 1 bis 10 Millionen",
        },
        "feedback_expression": "Rätt!",
    },
    "da": {
        "name": "Danish",
        "native_name": "Dansk",
        "flag": "🇩🇰",
        "ready": True,
        "description": "Learn Danish numbers from 1 to 10 million",
        "validation_strategy": "word_based",
        "ui_names": {"en": "Danish", "de": "Dänisch"},
        "ui_descriptions": {
            "en": "Learn Danish numbers from 1 to 10 million",
            "de": "Lerne Dänische Zahlen von 1 bis 10 Millionen",
        },
        "feedback_expression": "Korrekt!",
    },
    "no": {
        "name": "Norwegian",
        "native_name": "Norsk",
        "flag": "🇳🇴",
        "ready": True,
        "description": "Learn Norwegian numbers from 1 to 10 million",
        "validation_strategy": "word_based",
        "ui_names": {"en": "Norwegian", "de": "Norwegisch"},
        "ui_descriptions": {
            "en": "Learn Norwegian numbers from 1 to 10 million",
            "de": "Lerne Norwegische Zahlen von 1 bis 10 Millionen",
        },
        "feedback_expression": "Riktig!",
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
        elif lang_code == "fr":
            from .fr import NUMBERS
        elif lang_code == "da":
            from .da import NUMBERS
        elif lang_code == "it":
            from .it import NUMBERS
        elif lang_code == "tr":
            from .tr import NUMBERS
        elif lang_code == "ko":
            from .ko import NUMBERS
        elif lang_code == "no":
            from .no import NUMBERS
        elif lang_code == "pt":
            from .pt import NUMBERS
        elif lang_code == "sv":
            from .sv import NUMBERS
        elif lang_code == "ja":
            from .ja import NUMBERS
        elif lang_code == "zh":
            from .zh import NUMBERS
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


def get_feedback_expression(lang_code):
    """
    Get the word shown to the user when they answer correctly.

    Args:
        lang_code: Language code

    Returns:
        String expression in the target language (e.g. '¡Correcto' for Spanish)
    """
    lang_info = AVAILABLE_LANGUAGES.get(lang_code, {})
    return lang_info.get("feedback_expression", "Correct")


def get_language_ui_name(lang_code, ui_lang):
    """
    Get the display name of a learning language in the given UI language.

    Args:
        lang_code: Learning language code (e.g. 'es')
        ui_lang: UI language code (e.g. 'en' or 'de')

    Returns:
        Translated name string (falls back to the English name)
    """
    lang_info = AVAILABLE_LANGUAGES.get(lang_code, {})
    ui_names = lang_info.get("ui_names", {})
    return ui_names.get(ui_lang, lang_info.get("name", lang_code))


def get_language_ui_description(lang_code, ui_lang):
    """
    Get the description of a learning language in the given UI language.

    Args:
        lang_code: Learning language code (e.g. 'es')
        ui_lang: UI language code (e.g. 'en' or 'de')

    Returns:
        Translated description string (falls back to the default description)
    """
    lang_info = AVAILABLE_LANGUAGES.get(lang_code, {})
    ui_descriptions = lang_info.get("ui_descriptions", {})
    return ui_descriptions.get(ui_lang, lang_info.get("description", ""))


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
