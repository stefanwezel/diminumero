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
        "description": "Learn Spanish numbers from 0 to 10 million",
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
            "en": "Learn Spanish numbers from 0 to 10 million",
            "de": "Lerne Spanische Zahlen von 0 bis 10 Millionen",
            "es": "Aprende los números en español del 0 al 10 millones",
            "it": "Impara i numeri in spagnolo da 0 a 10 milioni",
            "fr": "Apprenez les nombres en espagnol de 0 à 10 millions",
            "pt": "Aprenda os números em espanhol de 0 a 10 milhões",
            "ar": "تعلم الأرقام بالإسبانية من 0 إلى 10 ملايين",
            "uk": "Вивчайте іспанські числа від 0 до 10 мільйонів",
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
        "description": "Learn French numbers from 0 to 10 million",
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
            "en": "Learn French numbers from 0 to 10 million",
            "de": "Lerne Französische Zahlen von 0 bis 10 Millionen",
            "es": "Aprende los números en francés del 0 al 10 millones",
            "it": "Impara i numeri in francese da 0 a 10 milioni",
            "fr": "Apprenez les nombres en français de 0 à 10 millions",
            "pt": "Aprenda os números em francês de 0 a 10 milhões",
            "ar": "تعلم الأرقام بالفرنسية من 0 إلى 10 ملايين",
            "uk": "Вивчайте французькі числа від 0 до 10 мільйонів",
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
        "description": "Learn Japanese numbers from 0 to 10 million",
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
            "en": "Learn Japanese numbers from 0 to 10 million",
            "de": "Lerne Japanische Zahlen von 0 bis 10 Millionen",
            "es": "Aprende los números en japonés del 0 al 10 millones",
            "it": "Impara i numeri in giapponese da 0 a 10 milioni",
            "fr": "Apprenez les nombres en japonais de 0 à 10 millions",
            "pt": "Aprenda os números em japonês de 0 a 10 milhões",
            "ar": "تعلم الأرقام باليابانية من 0 إلى 10 ملايين",
            "uk": "Вивчайте японські числа від 0 до 10 мільйонів",
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
        "description": "Learn German numbers from 0 to 10 million",
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
            "en": "Learn German numbers from 0 to 10 million",
            "de": "Lerne Deutsche Zahlen von 0 bis 10 Millionen",
            "es": "Aprende los números en alemán del 0 al 10 millones",
            "it": "Impara i numeri in tedesco da 0 a 10 milioni",
            "fr": "Apprenez les nombres en allemand de 0 à 10 millions",
            "pt": "Aprenda os números em alemão de 0 a 10 milhões",
            "ar": "تعلم الأرقام بالألمانية من 0 إلى 10 ملايين",
            "uk": "Вивчайте німецькі числа від 0 до 10 мільйонів",
        },
        "feedback_expression": "Korrekt",
    },
    "ko": {
        "name": "Korean",
        "native_name": "한국어",
        "flag": "🇰🇷",
        "ready": True,
        "has_learn_materials": True,
        "description": "Learn Korean numbers from 0 to 10 million",
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
            "en": "Learn Korean numbers from 0 to 10 million",
            "de": "Lerne Koreanische Zahlen von 0 bis 10 Millionen",
            "es": "Aprende los números en coreano del 0 al 10 millones",
            "it": "Impara i numeri in coreano da 0 a 10 milioni",
            "fr": "Apprenez les nombres en coréen de 0 à 10 millions",
            "pt": "Aprenda os números em coreano de 0 a 10 milhões",
            "ar": "تعلم الأرقام بالكورية من 0 إلى 10 ملايين",
            "uk": "Вивчайте корейські числа від 0 до 10 мільйонів",
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
        "description": "Learn Italian numbers from 0 to 10 million",
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
            "en": "Learn Italian numbers from 0 to 10 million",
            "de": "Lerne Italienische Zahlen von 0 bis 10 Millionen",
            "es": "Aprende los números en italiano del 0 al 10 millones",
            "it": "Impara i numeri in italiano da 0 a 10 milioni",
            "fr": "Apprenez les nombres en italien de 0 à 10 millions",
            "pt": "Aprenda os números em italiano de 0 a 10 milhões",
            "ar": "تعلم الأرقام بالإيطالية من 0 إلى 10 ملايين",
            "uk": "Вивчайте італійські числа від 0 до 10 мільйонів",
        },
        "feedback_expression": "Corretto!",
    },
    "zh": {
        "name": "Chinese",
        "native_name": "中文",
        "flag": "🇨🇳",
        "ready": True,
        "has_learn_materials": True,
        "description": "Learn Chinese numbers from 0 to 10 million",
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
            "en": "Learn Chinese numbers from 0 to 10 million",
            "de": "Lerne Chinesische Zahlen von 0 bis 10 Millionen",
            "es": "Aprende los números en chino del 0 al 10 millones",
            "it": "Impara i numeri in cinese da 0 a 10 milioni",
            "fr": "Apprenez les nombres en chinois de 0 à 10 millions",
            "pt": "Aprenda os números em chinês de 0 a 10 milhões",
            "ar": "تعلم الأرقام بالصينية من 0 إلى 10 ملايين",
            "uk": "Вивчайте китайські числа від 0 до 10 мільйонів",
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
        "description": "Learn Portuguese numbers from 0 to 10 million",
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
            "en": "Learn Portuguese numbers from 0 to 10 million",
            "de": "Lerne Portugiesische Zahlen von 0 bis 10 Millionen",
            "es": "Aprende los números en portugués del 0 al 10 millones",
            "it": "Impara i numeri in portoghese da 0 a 10 milioni",
            "fr": "Apprenez les nombres en portugais de 0 à 10 millions",
            "pt": "Aprenda os números em português de 0 a 10 milhões",
            "ar": "تعلم الأرقام بالبرتغالية من 0 إلى 10 ملايين",
            "uk": "Вивчайте португальські числа від 0 до 10 мільйонів",
        },
        "feedback_expression": "Correto!",
    },
    "tr": {
        "name": "Turkish",
        "native_name": "Türkçe",
        "flag": "🇹🇷",
        "ready": True,
        "has_learn_materials": True,
        "description": "Learn Turkish numbers from 0 to 10 million",
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
            "en": "Learn Turkish numbers from 0 to 10 million",
            "de": "Lerne Türkische Zahlen von 0 bis 10 Millionen",
            "es": "Aprende los números en turco del 0 al 10 millones",
            "it": "Impara i numeri in turco da 0 a 10 milioni",
            "fr": "Apprenez les nombres en turc de 0 à 10 millions",
            "pt": "Aprenda os números em turco de 0 a 10 milhões",
            "ar": "تعلم الأرقام بالتركية من 0 إلى 10 ملايين",
            "uk": "Вивчайте турецькі числа від 0 до 10 мільйонів",
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
            "en": "Learn Nepalese numbers from 0 to 1000",
            "de": "Lerne Nepalesische Zahlen von 0 bis 1000",
            "es": "Aprende los números en nepalés del 0 al 1000",
            "it": "Impara i numeri in nepalese da 0 a 1000",
            "fr": "Apprenez les nombres en népalais de 0 à 1000",
            "pt": "Aprenda os números em nepalês de 0 a 1000",
            "ar": "تعلم الأرقام بالنيبالية من 0 إلى 1000",
            "uk": "Вивчайте непальські числа від 0 до 1000",
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
        "description": "Learn Swedish numbers from 0 to 10 million",
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
            "en": "Learn Swedish numbers from 0 to 10 million",
            "de": "Lerne Schwedische Zahlen von 0 bis 10 Millionen",
            "es": "Aprende los números en sueco del 0 al 10 millones",
            "it": "Impara i numeri in svedese da 0 a 10 milioni",
            "fr": "Apprenez les nombres en suédois de 0 à 10 millions",
            "pt": "Aprenda os números em sueco de 0 a 10 milhões",
            "ar": "تعلم الأرقام بالسويدية من 0 إلى 10 ملايين",
            "uk": "Вивчайте шведські числа від 0 до 10 мільйонів",
        },
        "feedback_expression": "Rätt!",
    },
    "da": {
        "name": "Danish",
        "native_name": "Dansk",
        "flag": "🇩🇰",
        "ready": True,
        "has_learn_materials": True,
        "description": "Learn Danish numbers from 0 to 10 million",
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
            "en": "Learn Danish numbers from 0 to 10 million",
            "de": "Lerne Dänische Zahlen von 0 bis 10 Millionen",
            "es": "Aprende los números en danés del 0 al 10 millones",
            "it": "Impara i numeri in danese da 0 a 10 milioni",
            "fr": "Apprenez les nombres en danois de 0 à 10 millions",
            "pt": "Aprenda os números em dinamarquês de 0 a 10 milhões",
            "ar": "تعلم الأرقام بالدنماركية من 0 إلى 10 ملايين",
            "uk": "Вивчайте данські числа від 0 до 10 мільйонів",
        },
        "feedback_expression": "Korrekt!",
    },
    "no": {
        "name": "Norwegian",
        "native_name": "Norsk",
        "flag": "🇳🇴",
        "ready": True,
        "has_learn_materials": True,
        "description": "Learn Norwegian numbers from 0 to 10 million",
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
            "en": "Learn Norwegian numbers from 0 to 10 million",
            "de": "Lerne Norwegische Zahlen von 0 bis 10 Millionen",
            "es": "Aprende los números en noruego del 0 al 10 millones",
            "it": "Impara i numeri in norvegese da 0 a 10 milioni",
            "fr": "Apprenez les nombres en norvégien de 0 à 10 millions",
            "pt": "Aprenda os números em norueguês de 0 a 10 milhões",
            "ar": "تعلم الأرقام بالنرويجية من 0 إلى 10 ملايين",
            "uk": "Вивчайте норвезькі числа від 0 до 10 мільйонів",
        },
        "feedback_expression": "Riktig!",
    },
    "cy": {
        "name": "Welsh",
        "native_name": "Cymraeg",
        "flag": "🏴󠁧󠁢󠁷󠁬󠁳󠁿",
        "ready": True,
        "has_learn_materials": True,
        "description": "Learn modern decimal Welsh numbers from 0 to 10 million",
        "validation_strategy": "word_based",
        # Welsh counts two ways. The decimal system ("cyfrif degol") is what
        # school teaches and what arithmetic uses; the traditional vigesimal
        # system is obligatory for the time, dates and age. Neither is a
        # dialect of the other, so both live under /cy — see
        # docs/plans/welsh-traditional-numbers.md.
        "number_systems": [
            {"key": "decimal", "module": "numbers", "default": True},
            {
                "key": "traditional",
                "module": "numbers_traditional",
                # Offered only once every number in this range is filled in;
                # the deck ships with verified forms and explicit gaps.
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
        # Names the system on the language card: the deck is decimal Welsh,
        # and saying so is the point of docs/plans/welsh-traditional-numbers.md
        # phase 0. Reworded rather than replaced so the toggle can drop the
        # qualifier again once the traditional deck is usable.
        "ui_descriptions": {
            "en": "Learn modern decimal Welsh numbers from 0 to 10 million",
            "de": "Lerne moderne dezimale walisische Zahlen von 0 bis 10 Millionen",
            "es": "Aprende los números galeses decimales modernos del 0 al 10 millones",
            "it": "Impara i numeri gallesi decimali moderni da 0 a 10 milioni",
            "fr": "Apprenez les nombres gallois décimaux modernes de 0 à 10 millions",
            "pt": "Aprenda os números galeses decimais modernos de 0 a 10 milhões",
            "ar": "تعلم الأرقام الويلزية العشرية الحديثة من 0 إلى 10 ملايين",
            "uk": "Вивчайте сучасні десяткові валлійські числа від 0 до 10 мільйонів",
        },
        "feedback_expression": "Da iawn!",
    },
    "ga": {
        "name": "Irish",
        "native_name": "Gaeilge",
        "flag": "🇮🇪",
        "ready": True,
        "has_learn_materials": True,
        "description": "Learn Irish numbers from 0 to 10 million",
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
            "en": "Learn Irish numbers from 0 to 10 million",
            "de": "Lerne Irische Zahlen von 0 bis 10 Millionen",
            "es": "Aprende los números en irlandés del 0 al 10 millones",
            "it": "Impara i numeri in irlandese da 0 a 10 milioni",
            "fr": "Apprenez les nombres en irlandais de 0 à 10 millions",
            "pt": "Aprenda os números em irlandês de 0 a 10 milhões",
            "ar": "تعلم الأرقام بالأيرلندية من 0 إلى 10 ملايين",
            "uk": "Вивчайте ірландські числа від 0 до 10 мільйонів",
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
