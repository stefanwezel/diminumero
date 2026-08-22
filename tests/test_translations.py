"""Tests for UI translation coverage.

Nothing guarded this before: the eight locales were kept at parity by hand, and
a feature that adds keys to `en` and forgets one of the others would only show
up as English text on a German page, months later. Two changes made that worth
fixing — the numeral-system and notes features added seventeen keys across
eight locales at once, and Welsh joined as a ninth locale that is deliberately
incomplete.

So: complete locales must be complete, the incomplete ones are declared as
such in config.py, and no locale may carry a key `en` doesn't have.
"""

import pytest

from config import PARTIAL_UI_LANGUAGES, SUPPORTED_UI_LANGUAGES
from translations import TRANSLATIONS

ENGLISH_KEYS = set(TRANSLATIONS["en"])
COMPLETE_LOCALES = sorted(SUPPORTED_UI_LANGUAGES - PARTIAL_UI_LANGUAGES)


class TestCoverage:
    @pytest.mark.parametrize("locale", COMPLETE_LOCALES)
    def test_complete_locale_has_every_key(self, locale):
        missing = ENGLISH_KEYS - set(TRANSLATIONS[locale])
        assert not missing, f"{locale} is missing {sorted(missing)}"

    @pytest.mark.parametrize("locale", sorted(SUPPORTED_UI_LANGUAGES))
    def test_no_locale_has_orphan_keys(self, locale):
        """A key `en` doesn't have can never be reached — it's dead weight."""
        extra = set(TRANSLATIONS[locale]) - ENGLISH_KEYS
        assert not extra, f"{locale} has keys English doesn't: {sorted(extra)}"

    @pytest.mark.parametrize("locale", sorted(SUPPORTED_UI_LANGUAGES))
    def test_every_supported_locale_exists(self, locale):
        assert locale in TRANSLATIONS

    def test_partial_locales_are_declared_not_discovered(self):
        """A locale is either complete or listed as partial. No third state."""
        for locale in SUPPORTED_UI_LANGUAGES:
            complete = ENGLISH_KEYS <= set(TRANSLATIONS[locale])
            assert complete != (locale in PARTIAL_UI_LANGUAGES), (
                f"{locale}: coverage and PARTIAL_UI_LANGUAGES disagree"
            )


class TestPlaceholders:
    """A translated string that loses its placeholder crashes at format time."""

    @pytest.mark.parametrize("locale", COMPLETE_LOCALES)
    def test_placeholder_counts_match_english(self, locale):
        for key, english in TRANSLATIONS["en"].items():
            translated = TRANSLATIONS[locale][key]
            assert english.count("{}") == translated.count("{}"), (
                f"{locale}/{key}: {english.count('{}')} placeholders in English, "
                f"{translated.count('{}')} here"
            )

    @pytest.mark.parametrize("locale", COMPLETE_LOCALES)
    def test_language_name_placeholder_is_kept_verbatim(self, locale):
        for key, english in TRANSLATIONS["en"].items():
            if "LANGUAGE_NAME_PLACEHOLDER" not in english:
                continue
            assert "LANGUAGE_NAME_PLACEHOLDER" in TRANSLATIONS[locale][key], (
                f"{locale}/{key} dropped LANGUAGE_NAME_PLACEHOLDER"
            )


class TestNewFeatureKeys:
    """The keys the numeral-system and notes features introduced."""

    NEW_KEYS = [
        "number_system_label",
        # Language-scoped: Welsh names its own systems, so a future Korean
        # `decimal` system cannot inherit a Welsh label.
        "number_system_name_cy_degol",
        "number_system_name_cy_ugeiniol",
        "number_system_desc_cy_degol",
        "number_system_desc_cy_ugeiniol",
        "number_system_only_note",
        "number_system_unavailable_note",
        "number_system_partial_range_note",
        "number_system_sparse_note",
        "number_system_wrong_system_flash",
        "preset_notice_system",
        "preset_share_system_label",
        "notes_toggle_label",
        "notes_panel_title",
        "notes_untranslated",
        "notes_unreviewed",
        "notes_source_label",
        "ui_language_partial_note",
    ]

    @pytest.mark.parametrize("key", NEW_KEYS)
    def test_key_exists_in_every_complete_locale(self, key):
        for locale in COMPLETE_LOCALES:
            assert key in TRANSLATIONS[locale], f"{locale} is missing {key}"

    def test_range_note_takes_three_values(self):
        rendered = TRANSLATIONS["en"]["number_system_partial_range_note"].format(
            "Ugeiniol", 1, 100
        )
        assert "Ugeiniol" in rendered and "100" in rendered

    def test_sparse_note_takes_four_values(self):
        """Count first: "covers 1-100" would overstate a 30-number deck."""
        rendered = TRANSLATIONS["en"]["number_system_sparse_note"].format(
            "Ugeiniol", 30, 1, 100
        )
        assert "30" in rendered and "Ugeiniol" in rendered

    def test_system_names_are_welsh_in_every_locale(self):
        """A learner meeting the traditional system needs the Welsh word for it."""
        for locale in COMPLETE_LOCALES:
            assert TRANSLATIONS[locale]["number_system_name_cy_degol"] == "Degol"
            assert TRANSLATIONS[locale]["number_system_name_cy_ugeiniol"] == "Ugeiniol"
