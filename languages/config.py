"""Language configuration for diminumero multi-language support."""

import importlib

# Available languages with metadata
AVAILABLE_LANGUAGES = {
    "es": {
        "name": "Spanish",
        "native_name": "Español",
        "flag": "🇪🇸",
        "ready": True,
        "has_learn_materials": True,
        "has_audio_mode": True,
        "has_conjugation": True,
        "has_conjugation_materials": True,
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
        # Word shown to the user when they answer correctly (in the target language)
        "feedback_expression": "¡Correcto",
    },
    "fr": {
        "name": "French",
        "native_name": "Français",
        "flag": "🇫🇷",
        "ready": True,
        "has_learn_materials": True,
        "has_audio_mode": True,
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
        "feedback_expression": "Correct",
    },
    "ja": {
        "name": "Japanese",
        "native_name": "日本語",
        "flag": "🇯🇵",
        "ready": True,
        "has_learn_materials": True,
        "has_audio_mode": True,
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
        "feedback_expression": "正解!",
    },
    "de": {
        "name": "German",
        "native_name": "Deutsch",
        "flag": "🇩🇪",
        "ready": True,
        "has_learn_materials": True,
        "has_audio_mode": True,
        "has_conjugation": True,
        "has_conjugation_materials": True,
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
        "feedback_expression": "Korrekt",
    },
    "ko": {
        "name": "Korean",
        "native_name": "한국어",
        "flag": "🇰🇷",
        "ready": True,
        "has_learn_materials": True,
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
        "feedback_expression": "정답!",
    },
    "it": {
        "name": "Italian",
        "native_name": "Italiano",
        "flag": "🇮🇹",
        "ready": True,
        "has_learn_materials": True,
        "has_conjugation": True,
        "has_conjugation_materials": True,
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
        "feedback_expression": "Corretto!",
    },
    "zh": {
        "name": "Chinese",
        "native_name": "中文",
        "flag": "🇨🇳",
        "ready": True,
        "has_learn_materials": True,
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
        "feedback_expression": "正确!",
    },
    "pt": {
        "name": "Portuguese",
        "native_name": "Português",
        "flag": "🇧🇷",
        "ready": True,
        "has_learn_materials": True,
        "has_audio_mode": True,
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
        "feedback_expression": "Correto!",
    },
    "tr": {
        "name": "Turkish",
        "native_name": "Türkçe",
        "flag": "🇹🇷",
        "ready": True,
        "has_learn_materials": True,
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
        "feedback_expression": "Doğru!",
    },
    "ne": {
        "name": "Nepalese",
        "native_name": "नेपाली",
        "flag": "🇳🇵",
        "ready": True,
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
        "feedback_expression": "सहि!",
    },
    "sv": {
        "name": "Swedish",
        "native_name": "Svenska",
        "flag": "🇸🇪",
        "ready": True,
        "has_learn_materials": True,
        "has_audio_mode": True,
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
        "feedback_expression": "Rätt!",
    },
    "da": {
        "name": "Danish",
        "native_name": "Dansk",
        "flag": "🇩🇰",
        "ready": True,
        "has_learn_materials": True,
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
        "feedback_expression": "Korrekt!",
    },
    "no": {
        "name": "Norwegian",
        "native_name": "Norsk",
        "flag": "🇳🇴",
        "ready": True,
        "has_learn_materials": True,
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
        "feedback_expression": "Riktig!",
    },
    "cy": {
        "name": "Welsh",
        "native_name": "Cymraeg",
        "flag": "🏴󠁧󠁢󠁷󠁬󠁳󠁿",
        "ready": True,
        "has_learn_materials": True,
        "validation_strategy": "word_based",
        # Welsh counts two ways. The decimal system ("cyfrif degol") is what
        # school teaches and what arithmetic uses; the traditional vigesimal
        # system is obligatory for the time, dates and age. Neither is a
        # dialect of the other, so both live under /cy — see
        # docs/plans/welsh-traditional-numbers.md.
        "number_systems": [
            {
                "key": "decimal",
                "module": "numbers",
                "default": True,
                # UI strings live under number_system_{name,desc}_<label_key>.
                # Welsh names its own systems, so the buttons read "Degol" and
                # "Ugeiniol" rather than an English gloss — a learner meeting
                # the traditional system needs the Welsh word for it anyway.
                # Scoping the key by language also stops a future Korean
                # `decimal` system from inheriting a Welsh label.
                "label_key": "cy_degol",
            },
            {
                "key": "traditional",
                "module": "numbers_traditional",
                "label_key": "cy_ugeiniol",
                # 1-100 complete, since the August 2026 review round answered
                # the 41-99 connective with published sources and the forms it
                # settles are served (`attested` — see languages/provenance.py).
                # Forms with nothing but a script behind them are still withheld
                # (config.SERVE_RECONSTRUCTED) and so still cannot open a gate.
                "requires_complete": (1, 100),
                # No traditional MP3s exist, so Listening stays decimal-only.
                "has_audio": False,
            },
        ],
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
        "feedback_expression": "Da iawn!",
    },
    "ga": {
        "name": "Irish",
        "native_name": "Gaeilge",
        "flag": "🇮🇪",
        "ready": True,
        "has_learn_materials": True,
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


def get_languages_with_conjugation():
    """Return language codes that have a verb-conjugation practice section and are ready."""
    return [
        code
        for code, info in AVAILABLE_LANGUAGES.items()
        if info.get("has_conjugation", False) and info.get("ready", False)
    ]


def get_languages_with_conjugation_materials():
    """Return language codes that have verb-conjugation learn materials and are ready."""
    return [
        code
        for code, info in AVAILABLE_LANGUAGES.items()
        if info.get("has_conjugation_materials", False) and info.get("ready", False)
    ]


def get_languages_with_audio_mode():
    """Return language codes that have a pronunciation audio quiz available."""
    return [
        code
        for code, info in AVAILABLE_LANGUAGES.items()
        if info.get("has_audio_mode", False) and info.get("ready", False)
    ]


# ===== Numeral systems =====
# Most languages have one way of saying a number. Some have two: Welsh decimal
# vs traditional, Korean Sino vs native, standard vs Belgian/Swiss French. A
# language declares them with `number_systems`; one that declares nothing has
# exactly one implicit system and behaves exactly as it always has.

# The key reported for a language that declares no systems of its own. It never
# reaches the UI: the system control only renders when a language has two.
DEFAULT_NUMBER_SYSTEM = "default"

# Every field a system entry may carry, with the value assumed when omitted.
_NUMBER_SYSTEM_DEFAULTS = {
    "module": "numbers",
    # Which system a bare /<lang> URL drills.
    "default": False,
    # Numbers this system must cover before it is offered, as (low, high), or
    # None to accept any non-empty deck. Checked against the data itself so a
    # deck can be filled in gradually without a flag to remember to flip.
    "requires_complete": None,
    # Whether the Listening quiz may use this system's deck.
    "has_audio": True,
}

# Cache for decks loaded out of a non-default module.
_SYSTEM_NUMBER_CACHE = {}


def get_number_systems(lang_code):
    """Every numeral system a language declares, with defaults filled in.

    A language with no declaration reports a single implicit system, so callers
    never need to special-case the one-system majority.
    """
    lang_info = AVAILABLE_LANGUAGES.get(lang_code) or {}
    declared = lang_info.get("number_systems")
    if not declared:
        implicit = dict(_NUMBER_SYSTEM_DEFAULTS)
        implicit.update({"key": DEFAULT_NUMBER_SYSTEM, "default": True})
        return [implicit]

    systems = []
    for entry in declared:
        system = dict(_NUMBER_SYSTEM_DEFAULTS)
        system.update(entry)
        systems.append(system)
    return systems


def get_number_system(lang_code, system_key):
    """One declared system by key, or None if the language has no such system."""
    for system in get_number_systems(lang_code):
        if system["key"] == system_key:
            return system
    return None


def get_default_number_system(lang_code):
    """The system key a bare /<lang> URL drills."""
    systems = get_number_systems(lang_code)
    for system in systems:
        if system.get("default"):
            return system["key"]
    return systems[0]["key"]


def is_number_system_ready(lang_code, system_key):
    """Whether a declared system has enough data to be offered to a learner.

    Derived from the deck itself rather than a flag, the same way the Listening
    quiz derives its playable numbers from the MP3s actually on disk: a system
    whose deck is still full of gaps stays hidden, and the PR that fills the
    last gap turns it on with no code change.
    """
    system = get_number_system(lang_code, system_key)
    if system is None:
        return False

    try:
        numbers = get_language_numbers(lang_code, system_key)
    except ValueError:
        return False

    if not numbers:
        return False

    required = system.get("requires_complete")
    if not required:
        return True

    low, high = required
    return all(num in numbers for num in range(low, high + 1))


def get_ready_number_systems(lang_code):
    """Declared systems whose deck passes the completeness gate."""
    return [
        system
        for system in get_number_systems(lang_code)
        if is_number_system_ready(lang_code, system["key"])
    ]


def resolve_number_system(lang_code, requested):
    """Resolve a requested system key to one this language can actually drill.

    Never raises: an unknown key, a key belonging to another language, or a
    system whose deck is still incomplete all fall back to the default, exactly
    like an unusable range or magnitude in a shared drill link.
    """
    default = get_default_number_system(lang_code)
    if not requested or requested == default:
        return default
    if get_number_system(lang_code, requested) is None:
        return default
    if not is_number_system_ready(lang_code, requested):
        return default
    return requested


def _load_system_numbers(lang_code, module_name):
    """Load `NUMBERS` from a non-default deck module, dropping unfilled gaps.

    A deck under construction marks what it doesn't know yet as ``None`` (see
    languages/cy/numbers_traditional.py). Those entries are stripped here, so
    nothing downstream — quiz, worksheet, validation — can ever be handed a
    number without a word.
    """
    cache_key = (lang_code, module_name)
    if cache_key in _SYSTEM_NUMBER_CACHE:
        return _SYSTEM_NUMBER_CACHE[cache_key]

    try:
        module = importlib.import_module(f".{lang_code}.{module_name}", __package__)
    except ImportError as exc:
        raise ValueError(
            f"Failed to load numbers for language '{lang_code}' "
            f"system module '{module_name}': {exc}"
        )

    raw = getattr(module, "NUMBERS", None)
    if not isinstance(raw, dict):
        raise ValueError(
            f"Module '{module_name}' for language '{lang_code}' has no NUMBERS dict"
        )

    numbers = {num: word for num, word in raw.items() if word}
    _SYSTEM_NUMBER_CACHE[cache_key] = numbers
    return numbers


def get_number_usage_weights(lang_code, system=None):
    """How often each number in a deck is worth asking, or None.

    A deck module may declare ``USAGE_WEIGHTS`` — ``{number: multiplier}`` — for
    a system whose numbers are not used evenly in real life. Traditional Welsh
    is the case that motivated it: it holds 1-100, but dates keep 1-31 alive
    while `pedwar ar bymtheg ar hugain` (39) is a museum piece, and drilling
    them equally would spend a ten-question round in the wrong place.

    None for every deck that declares nothing, which is all of them but one, so
    the drill's weighting is untouched for every other language.
    """
    system_key = system or get_default_number_system(lang_code)
    declared = get_number_system(lang_code, system_key)
    module_name = (declared or {}).get("module", "numbers")
    try:
        module = importlib.import_module(f".{lang_code}.{module_name}", __package__)
    except ImportError:
        return None

    weights = getattr(module, "USAGE_WEIGHTS", None)
    if not isinstance(weights, dict) or not weights:
        return None
    return weights


def get_language_numbers(lang_code, system=None):
    """
    Load and return the NUMBERS dictionary for a specific language.

    Args:
        lang_code: Language code (e.g., 'es', 'ne')
        system: Optional numeral system key (e.g. 'traditional' for Welsh).
            Omitted means the language's default system, which is what every
            single-system language has.

    Returns:
        Dictionary mapping numbers to their translations

    Raises:
        ValueError: If language code is invalid or not available
    """
    if not is_language_available(lang_code):
        raise ValueError(f"Language '{lang_code}' is not available")

    system_key = system or get_default_number_system(lang_code)
    system_entry = get_number_system(lang_code, system_key)
    if system_entry is None:
        raise ValueError(f"Language '{lang_code}' has no number system '{system_key}'")

    module_name = system_entry.get("module", "numbers")
    if module_name != "numbers":
        return _load_system_numbers(lang_code, module_name)

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
