"""Language configuration for diminumero multi-language support."""

# Available languages with metadata
AVAILABLE_LANGUAGES = {
    "es": {
        "name": "Spanish",
        "native_name": "Español",
        "flag": "🇪🇸",
        "ready": True,
        "has_learn_materials": True,
        "description": "Learn Spanish numbers from 1 to 10 million",
        "validation_strategy": "word_based",  # Numbers separated by spaces
        # UI display names keyed by UI language code
        "ui_names": {
            "en": "Spanish",
            "de": "Spanisch",
            "es": "Español",
            "it": "Spagnolo",
            "fr": "Espagnol",
            "pt": "Espanhol",
            "ar": "الإسبانية",
            "uk": "Іспанська",
        },
        # Translated descriptions shown on the language selection page
        "ui_descriptions": {
            "en": "Learn Spanish numbers from 1 to 10 million",
            "de": "Lerne Spanische Zahlen von 1 bis 10 Millionen",
            "es": "Aprende los números en español del 1 al 10 millones",
            "it": "Impara i numeri in spagnolo da 1 a 10 milioni",
            "fr": "Apprenez les nombres en espagnol de 1 à 10 millions",
            "pt": "Aprenda os números em espanhol de 1 a 10 milhões",
            "ar": "تعلم الأرقام بالإسبانية من 1 إلى 10 ملايين",
            "uk": "Вивчайте іспанські числа від 1 до 10 мільйонів",
        },
        # Word shown to the user when they answer correctly (in the target language)
        "feedback_expression": "¡Correcto",
    },
    "fr": {
        "name": "French",
        "native_name": "Français",
        "flag": "🇫🇷",
        "ready": True,
        "has_learn_materials": True,
        "description": "Learn French numbers from 1 to 10 million",
        "validation_strategy": "word_based",  # Numbers separated by spaces/hyphens
        "ui_names": {
            "en": "French",
            "de": "Französisch",
            "es": "Francés",
            "it": "Francese",
            "fr": "Français",
            "pt": "Francês",
            "ar": "الفرنسية",
            "uk": "Французька",
        },
        "ui_descriptions": {
            "en": "Learn French numbers from 1 to 10 million",
            "de": "Lerne Französische Zahlen von 1 bis 10 Millionen",
            "es": "Aprende los números en francés del 1 al 10 millones",
            "it": "Impara i numeri in francese da 1 a 10 milioni",
            "fr": "Apprenez les nombres en français de 1 à 10 millions",
            "pt": "Aprenda os números em francês de 1 a 10 milhões",
            "ar": "تعلم الأرقام بالفرنسية من 1 إلى 10 ملايين",
            "uk": "Вивчайте французькі числа від 1 до 10 мільйонів",
        },
        "feedback_expression": "Correct",
    },
    "ja": {
        "name": "Japanese",
        "native_name": "日本語",
        "flag": "🇯🇵",
        "ready": True,
        "has_learn_materials": True,
        "description": "Learn Japanese numbers from 1 to 10 million",
        "validation_strategy": "word_based",
        "ui_names": {
            "en": "Japanese",
            "de": "Japanisch",
            "es": "Japonés",
            "it": "Giapponese",
            "fr": "Japonais",
            "pt": "Japonês",
            "ar": "اليابانية",
            "uk": "Японська",
        },
        "ui_descriptions": {
            "en": "Learn Japanese numbers from 1 to 10 million",
            "de": "Lerne Japanische Zahlen von 1 bis 10 Millionen",
            "es": "Aprende los números en japonés del 1 al 10 millones",
            "it": "Impara i numeri in giapponese da 1 a 10 milioni",
            "fr": "Apprenez les nombres en japonais de 1 à 10 millions",
            "pt": "Aprenda os números em japonês de 1 a 10 milhões",
            "ar": "تعلم الأرقام باليابانية من 1 إلى 10 ملايين",
            "uk": "Вивчайте японські числа від 1 до 10 мільйонів",
        },
        "feedback_expression": "正解!",
    },
    "de": {
        "name": "German",
        "native_name": "Deutsch",
        "flag": "🇩🇪",
        "ready": True,
        "has_learn_materials": True,
        "description": "Learn German numbers from 1 to 10 million",
        "validation_strategy": "component_based",  # Compound words
        "ui_names": {
            "en": "German",
            "de": "Deutsch",
            "es": "Alemán",
            "it": "Tedesco",
            "fr": "Allemand",
            "pt": "Alemão",
            "ar": "الألمانية",
            "uk": "Німецька",
        },
        "ui_descriptions": {
            "en": "Learn German numbers from 1 to 10 million",
            "de": "Lerne Deutsche Zahlen von 1 bis 10 Millionen",
            "es": "Aprende los números en alemán del 1 al 10 millones",
            "it": "Impara i numeri in tedesco da 1 a 10 milioni",
            "fr": "Apprenez les nombres en allemand de 1 à 10 millions",
            "pt": "Aprenda os números em alemão de 1 a 10 milhões",
            "ar": "تعلم الأرقام بالألمانية من 1 إلى 10 ملايين",
            "uk": "Вивчайте німецькі числа від 1 до 10 мільйонів",
        },
        "feedback_expression": "Korrekt",
    },
    "ko": {
        "name": "Korean",
        "native_name": "한국어",
        "flag": "🇰🇷",
        "ready": True,
        "has_learn_materials": True,
        "description": "Learn Korean numbers from 1 to 10 million",
        "validation_strategy": "word_based",
        "ui_names": {
            "en": "Korean",
            "de": "Koreanisch",
            "es": "Coreano",
            "it": "Coreano",
            "fr": "Coréen",
            "pt": "Coreano",
            "ar": "الكورية",
            "uk": "Корейська",
        },
        "ui_descriptions": {
            "en": "Learn Korean numbers from 1 to 10 million",
            "de": "Lerne Koreanische Zahlen von 1 bis 10 Millionen",
            "es": "Aprende los números en coreano del 1 al 10 millones",
            "it": "Impara i numeri in coreano da 1 a 10 milioni",
            "fr": "Apprenez les nombres en coréen de 1 à 10 millions",
            "pt": "Aprenda os números em coreano de 1 a 10 milhões",
            "ar": "تعلم الأرقام بالكورية من 1 إلى 10 ملايين",
            "uk": "Вивчайте корейські числа від 1 до 10 мільйонів",
        },
        "feedback_expression": "정답!",
    },
    "it": {
        "name": "Italian",
        "native_name": "Italiano",
        "flag": "🇮🇹",
        "ready": True,
        "has_learn_materials": True,
        "description": "Learn Italian numbers from 1 to 10 million",
        "validation_strategy": "word_based",
        "ui_names": {
            "en": "Italian",
            "de": "Italienisch",
            "es": "Italiano",
            "it": "Italiano",
            "fr": "Italien",
            "pt": "Italiano",
            "ar": "الإيطالية",
            "uk": "Італійська",
        },
        "ui_descriptions": {
            "en": "Learn Italian numbers from 1 to 10 million",
            "de": "Lerne Italienische Zahlen von 1 bis 10 Millionen",
            "es": "Aprende los números en italiano del 1 al 10 millones",
            "it": "Impara i numeri in italiano da 1 a 10 milioni",
            "fr": "Apprenez les nombres en italien de 1 à 10 millions",
            "pt": "Aprenda os números em italiano de 1 a 10 milhões",
            "ar": "تعلم الأرقام بالإيطالية من 1 إلى 10 ملايين",
            "uk": "Вивчайте італійські числа від 1 до 10 мільйонів",
        },
        "feedback_expression": "Corretto!",
    },
    "zh": {
        "name": "Chinese",
        "native_name": "中文",
        "flag": "🇨🇳",
        "ready": True,
        "has_learn_materials": True,
        "description": "Learn Chinese numbers from 1 to 10 million",
        "validation_strategy": "word_based",
        "ui_names": {
            "en": "Chinese",
            "de": "Chinesisch",
            "es": "Chino",
            "it": "Cinese",
            "fr": "Chinois",
            "pt": "Chinês",
            "ar": "الصينية",
            "uk": "Китайська",
        },
        "ui_descriptions": {
            "en": "Learn Chinese numbers from 1 to 10 million",
            "de": "Lerne Chinesische Zahlen von 1 bis 10 Millionen",
            "es": "Aprende los números en chino del 1 al 10 millones",
            "it": "Impara i numeri in cinese da 1 a 10 milioni",
            "fr": "Apprenez les nombres en chinois de 1 à 10 millions",
            "pt": "Aprenda os números em chinês de 1 a 10 milhões",
            "ar": "تعلم الأرقام بالصينية من 1 إلى 10 ملايين",
            "uk": "Вивчайте китайські числа від 1 до 10 мільйонів",
        },
        "feedback_expression": "正确!",
    },
    "pt": {
        "name": "Portuguese",
        "native_name": "Português",
        "flag": "🇧🇷",
        "ready": True,
        "has_learn_materials": True,
        "description": "Learn Portuguese numbers from 1 to 10 million",
        "validation_strategy": "word_based",
        "ui_names": {
            "en": "Portuguese",
            "de": "Portugiesisch",
            "es": "Portugués",
            "it": "Portoghese",
            "fr": "Portugais",
            "pt": "Português",
            "ar": "البرتغالية",
            "uk": "Португальська",
        },
        "ui_descriptions": {
            "en": "Learn Portuguese numbers from 1 to 10 million",
            "de": "Lerne Portugiesische Zahlen von 1 bis 10 Millionen",
            "es": "Aprende los números en portugués del 1 al 10 millones",
            "it": "Impara i numeri in portoghese da 1 a 10 milioni",
            "fr": "Apprenez les nombres en portugais de 1 à 10 millions",
            "pt": "Aprenda os números em português de 1 a 10 milhões",
            "ar": "تعلم الأرقام بالبرتغالية من 1 إلى 10 ملايين",
            "uk": "Вивчайте португальські числа від 1 до 10 мільйонів",
        },
        "feedback_expression": "Correto!",
    },
    "tr": {
        "name": "Turkish",
        "native_name": "Türkçe",
        "flag": "🇹🇷",
        "ready": True,
        "has_learn_materials": True,
        "description": "Learn Turkish numbers from 1 to 10 million",
        "validation_strategy": "word_based",
        "ui_names": {
            "en": "Turkish",
            "de": "Türkisch",
            "es": "Turco",
            "it": "Turco",
            "fr": "Turc",
            "pt": "Turco",
            "ar": "التركية",
            "uk": "Турецька",
        },
        "ui_descriptions": {
            "en": "Learn Turkish numbers from 1 to 10 million",
            "de": "Lerne Türkische Zahlen von 1 bis 10 Millionen",
            "es": "Aprende los números en turco del 1 al 10 millones",
            "it": "Impara i numeri in turco da 1 a 10 milioni",
            "fr": "Apprenez les nombres en turc de 1 à 10 millions",
            "pt": "Aprenda os números em turco de 1 a 10 milhões",
            "ar": "تعلم الأرقام بالتركية من 1 إلى 10 ملايين",
            "uk": "Вивчайте турецькі числа від 1 до 10 мільйонів",
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
        "ui_names": {
            "en": "Nepalese",
            "de": "Nepalesisch",
            "es": "Nepalés",
            "it": "Nepalese",
            "fr": "Népalais",
            "pt": "Nepalês",
            "ar": "النيبالية",
            "uk": "Непальська",
        },
        "ui_descriptions": {
            "en": "Learn Nepalese numbers from 1 to 1000",
            "de": "Lerne Nepalesische Zahlen von 1 bis 1000",
            "es": "Aprende los números en nepalés del 1 al 1000",
            "it": "Impara i numeri in nepalese da 1 a 1000",
            "fr": "Apprenez les nombres en népalais de 1 à 1000",
            "pt": "Aprenda os números em nepalês de 1 a 1000",
            "ar": "تعلم الأرقام بالنيبالية من 1 إلى 1000",
            "uk": "Вивчайте непальські числа від 1 до 1000",
        },
        "feedback_expression": "सहि!",
    },
    "sv": {
        "name": "Swedish",
        "native_name": "Svenska",
        "flag": "🇸🇪",
        "ready": True,
        "has_learn_materials": True,
        "description": "Learn Swedish numbers from 1 to 10 million",
        "validation_strategy": "word_based",
        "ui_names": {
            "en": "Swedish",
            "de": "Schwedisch",
            "es": "Sueco",
            "it": "Svedese",
            "fr": "Suédois",
            "pt": "Sueco",
            "ar": "السويدية",
            "uk": "Шведська",
        },
        "ui_descriptions": {
            "en": "Learn Swedish numbers from 1 to 10 million",
            "de": "Lerne Schwedische Zahlen von 1 bis 10 Millionen",
            "es": "Aprende los números en sueco del 1 al 10 millones",
            "it": "Impara i numeri in svedese da 1 a 10 milioni",
            "fr": "Apprenez les nombres en suédois de 1 à 10 millions",
            "pt": "Aprenda os números em sueco de 1 a 10 milhões",
            "ar": "تعلم الأرقام بالسويدية من 1 إلى 10 ملايين",
            "uk": "Вивчайте шведські числа від 1 до 10 мільйонів",
        },
        "feedback_expression": "Rätt!",
    },
    "da": {
        "name": "Danish",
        "native_name": "Dansk",
        "flag": "🇩🇰",
        "ready": True,
        "has_learn_materials": True,
        "description": "Learn Danish numbers from 1 to 10 million",
        "validation_strategy": "word_based",
        "ui_names": {
            "en": "Danish",
            "de": "Dänisch",
            "es": "Danés",
            "it": "Danese",
            "fr": "Danois",
            "pt": "Dinamarquês",
            "ar": "الدنماركية",
            "uk": "Данська",
        },
        "ui_descriptions": {
            "en": "Learn Danish numbers from 1 to 10 million",
            "de": "Lerne Dänische Zahlen von 1 bis 10 Millionen",
            "es": "Aprende los números en danés del 1 al 10 millones",
            "it": "Impara i numeri in danese da 1 a 10 milioni",
            "fr": "Apprenez les nombres en danois de 1 à 10 millions",
            "pt": "Aprenda os números em dinamarquês de 1 a 10 milhões",
            "ar": "تعلم الأرقام بالدنماركية من 1 إلى 10 ملايين",
            "uk": "Вивчайте данські числа від 1 до 10 мільйонів",
        },
        "feedback_expression": "Korrekt!",
    },
    "no": {
        "name": "Norwegian",
        "native_name": "Norsk",
        "flag": "🇳🇴",
        "ready": True,
        "has_learn_materials": True,
        "description": "Learn Norwegian numbers from 1 to 10 million",
        "validation_strategy": "word_based",
        "ui_names": {
            "en": "Norwegian",
            "de": "Norwegisch",
            "es": "Noruego",
            "it": "Norvegese",
            "fr": "Norvégien",
            "pt": "Norueguês",
            "ar": "النرويجية",
            "uk": "Норвезька",
        },
        "ui_descriptions": {
            "en": "Learn Norwegian numbers from 1 to 10 million",
            "de": "Lerne Norwegische Zahlen von 1 bis 10 Millionen",
            "es": "Aprende los números en noruego del 1 al 10 millones",
            "it": "Impara i numeri in norvegese da 1 a 10 milioni",
            "fr": "Apprenez les nombres en norvégien de 1 à 10 millions",
            "pt": "Aprenda os números em norueguês de 1 a 10 milhões",
            "ar": "تعلم الأرقام بالنرويجية من 1 إلى 10 ملايين",
            "uk": "Вивчайте норвезькі числа від 1 до 10 мільйонів",
        },
        "feedback_expression": "Riktig!",
    },
    "cy": {
        "name": "Welsh",
        "native_name": "Cymraeg",
        "flag": "🏴󠁧󠁢󠁷󠁬󠁳󠁿",
        "ready": True,
        "has_learn_materials": True,
        "description": "Learn Welsh numbers from 1 to 10 million",
        "validation_strategy": "word_based",
        "ui_names": {
            "en": "Welsh",
            "de": "Walisisch",
            "es": "Galés",
            "it": "Gallese",
            "fr": "Gallois",
            "pt": "Galês",
            "ar": "الويلزية",
            "uk": "Валлійська",
        },
        "ui_descriptions": {
            "en": "Learn Welsh numbers from 1 to 10 million",
            "de": "Lerne Walisische Zahlen von 1 bis 10 Millionen",
            "es": "Aprende los números en galés del 1 al 10 millones",
            "it": "Impara i numeri in gallese da 1 a 10 milioni",
            "fr": "Apprenez les nombres en gallois de 1 à 10 millions",
            "pt": "Aprenda os números em galês de 1 a 10 milhões",
            "ar": "تعلم الأرقام بالويلزية من 1 إلى 10 ملايين",
            "uk": "Вивчайте валлійські числа від 1 до 10 мільйонів",
        },
        "feedback_expression": "Da iawn!",
    },
    "ga": {
        "name": "Irish",
        "native_name": "Gaeilge",
        "flag": "🇮🇪",
        "ready": True,
        "has_learn_materials": True,
        "description": "Learn Irish numbers from 1 to 10 million",
        "validation_strategy": "word_based",
        "ui_names": {
            "en": "Irish",
            "de": "Irisch",
            "es": "Irlandés",
            "it": "Irlandese",
            "fr": "Irlandais",
            "pt": "Irlandês",
            "ar": "الأيرلندية",
            "uk": "Ірландська",
        },
        "ui_descriptions": {
            "en": "Learn Irish numbers from 1 to 10 million",
            "de": "Lerne Irische Zahlen von 1 bis 10 Millionen",
            "es": "Aprende los números en irlandés del 1 al 10 millones",
            "it": "Impara i numeri in irlandese da 1 a 10 milioni",
            "fr": "Apprenez les nombres en irlandais de 1 à 10 millions",
            "pt": "Aprenda os números em irlandês de 1 a 10 milhões",
            "ar": "تعلم الأرقام بالأيرلندية من 1 إلى 10 ملايين",
            "uk": "Вивчайте ірландські числа від 1 до 10 мільйонів",
        },
        "feedback_expression": "Maith thú!",
    },
}


def get_languages_with_learn_materials():
    """Return language codes that have learn materials and are ready."""
    return [
        code
        for code, info in AVAILABLE_LANGUAGES.items()
        if info.get("has_learn_materials", False) and info.get("ready", False)
    ]


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
        elif lang_code == "cy":
            from .cy import NUMBERS
        elif lang_code == "ga":
            from .ga import NUMBERS
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
