"""Tests for per-number notes (the lightbulb).

Two jobs. The first is validation: every committed notes file has to parse,
point at numbers that exist, name systems that exist, and stay plain text —
a bad note is a failing build, not a wrong lesson.

The second is the answer-leak rule, which is the reason the feature needed a
design at all: a note saying "deg becomes deng before m-" next to the prompt
"10" hands over the answer. Notes may only sit beside an unanswered prompt if
they declare they reveal nothing *and* have been reviewed by someone who knows
the language.
"""

import textwrap

import pytest

from app import app as flask_app
from languages import notes_loader
from languages.notes_loader import (
    get_notes,
    languages_with_notes,
    load_notes,
    parse_applies_to,
    validate_notes,
)


@pytest.fixture
def app():
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret-key"
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def notes_file(tmp_path, monkeypatch):
    """Write a notes file for a real language and read it back.

    Used for the cases no committed file should ever contain — a note that
    lies about revealing the answer, a typo'd range, markup in the text.
    """

    def write(lang_code, body, ui_lang=None):
        directory = tmp_path / lang_code
        directory.mkdir(exist_ok=True)
        name = "notes.toml" if ui_lang is None else f"notes.{ui_lang}.toml"
        (directory / name).write_text(textwrap.dedent(body), encoding="utf-8")
        monkeypatch.setattr(notes_loader, "LANGUAGES_DIR", tmp_path)
        notes_loader.reset_cache()
        return directory / name

    yield write
    notes_loader.reset_cache()


class TestCommittedNotesAreValid:
    """Every notes file in the repo passes every rule."""

    def test_repo_ships_notes_for_several_languages(self):
        # Notes are not a Welsh mechanism: they earn their keep elsewhere too.
        assert set(languages_with_notes()) >= {"cy", "de", "es", "fr", "da"}

    @pytest.mark.parametrize("lang_code", languages_with_notes())
    def test_notes_file_is_valid(self, lang_code):
        assert validate_notes(lang_code) == []

    def test_welsh_notes_cover_the_thread_findings(self):
        ids = {note["id"] for note in load_notes("cy")}
        assert "cy-deg-before-m" in ids
        assert "cy-trad-ugain-after-ar" in ids

    def test_seed_notes_are_marked_unreviewed(self):
        """They were written from a forum thread, not by a native speaker.

        Saying so on the page is the honest state, and it is what keeps them
        away from a live prompt.
        """
        for lang_code in languages_with_notes():
            for note in load_notes(lang_code):
                assert note["reviewed"] is False


class TestScope:
    def test_single_number(self):
        assert parse_applies_to("20") == (False, [(20, 20)])

    def test_range(self):
        assert parse_applies_to("11-19") == (False, [(11, 19)])

    def test_list_of_numbers_and_ranges(self):
        assert parse_applies_to("11-19,30") == (False, [(11, 19), (30, 30)])

    def test_everything(self):
        assert parse_applies_to("all") == (True, [])

    def test_reversed_range_is_accepted(self):
        assert parse_applies_to("19-11") == (False, [(11, 19)])

    @pytest.mark.parametrize("value", ["", "twenty", "1..9", "1-", "-", "1-2-3"])
    def test_garbage_is_rejected(self, value):
        with pytest.raises(ValueError):
            parse_applies_to(value)

    def test_note_matches_only_its_numbers(self):
        matched = {note["id"] for note in get_notes("de", numbers=47, when="revealed")}
        assert "de-units-before-tens" in matched
        assert not get_notes("de", numbers=7, when="revealed")

    def test_system_scoping(self):
        """A traditional-only note stays out of a decimal drill."""
        decimal = {
            n["id"] for n in get_notes("cy", system="decimal", numbers=20, when="rev")
        }
        traditional = {
            n["id"]
            for n in get_notes("cy", system="traditional", numbers=20, when="rev")
        }
        assert "cy-trad-ugain-after-ar" not in decimal
        assert "cy-trad-ugain-after-ar" in traditional

    def test_unscoped_note_applies_to_every_system(self):
        for system in ("decimal", "traditional"):
            ids = {
                n["id"] for n in get_notes("cy", system=system, numbers=10, when="rev")
            }
            assert "cy-deg-before-m" in ids

    def test_several_notes_can_share_one_number(self):
        ids = [
            n["id"]
            for n in get_notes("cy", system="traditional", numbers=20, when="rev")
        ]
        assert len(ids) > 1
        assert len(ids) == len(set(ids))


class TestAnswerLeakRule:
    def test_seed_notes_are_all_kept_away_from_a_live_prompt(self):
        """Not one committed note is currently allowed beside a prompt."""
        for lang_code in languages_with_notes():
            assert get_notes(lang_code, numbers=None, when="prompt") == []

    def test_reviewed_non_revealing_note_may_sit_beside_a_prompt(self, notes_file):
        notes_file(
            "fr",
            """
            language = "fr"
            authored_in = "en"

            [[note]]
            id = "fr-safe"
            applies_to = "70-79"
            text = "Belgium and Switzerland have their own word for this one."
            reveals_answer = false
            reviewed = true
            """,
        )
        assert [n["id"] for n in get_notes("fr", numbers=70, when="prompt")] == [
            "fr-safe"
        ]

    def test_unreviewed_note_is_held_back_even_if_it_reveals_nothing(self, notes_file):
        """Reviewing is the human half of the rule.

        The mechanical check cannot see a note that gives the answer away by
        description, so nothing unreviewed goes next to a live prompt.
        """
        notes_file(
            "fr",
            """
            language = "fr"
            authored_in = "en"

            [[note]]
            id = "fr-unreviewed"
            applies_to = "70-79"
            text = "Belgium and Switzerland have their own word for this one."
            reveals_answer = false
            reviewed = false
            """,
        )
        assert get_notes("fr", numbers=70, when="prompt") == []
        assert get_notes("fr", numbers=70, when="revealed")

    def test_note_that_spells_out_the_answer_cannot_claim_otherwise(self, notes_file):
        notes_file(
            "fr",
            """
            language = "fr"
            authored_in = "en"

            [[note]]
            id = "fr-leaky"
            applies_to = "80"
            text = "quatre-vingts is literally four twenties."
            reveals_answer = false
            reviewed = true
            """,
        )
        errors = validate_notes("fr")
        assert any("reveals_answer is false" in error for error in errors)

    def test_leak_check_looks_at_examples_too(self, notes_file):
        notes_file(
            "fr",
            """
            language = "fr"
            authored_in = "en"

            [[note]]
            id = "fr-leaky-example"
            applies_to = "80"
            text = "This one counts in twenties."
            reveals_answer = false
            reviewed = true

              [[note.examples]]
              phrase = "quatre-vingts"
              gloss = "eighty"
            """,
        )
        assert any("reveals_answer is false" in error for error in validate_notes("fr"))

    def test_default_is_the_safe_direction(self, notes_file):
        notes_file(
            "fr",
            """
            language = "fr"
            authored_in = "en"

            [[note]]
            id = "fr-default"
            applies_to = "80"
            text = "Anything at all."
            """,
        )
        assert load_notes("fr")[0]["reveals_answer"] is True


class TestValidation:
    def test_missing_id_fails(self, notes_file):
        notes_file(
            "fr",
            """
            language = "fr"

            [[note]]
            applies_to = "1"
            text = "No id here."
            """,
        )
        assert validate_notes("fr")

    def test_duplicate_id_fails(self, notes_file):
        notes_file(
            "fr",
            """
            language = "fr"

            [[note]]
            id = "dup"
            applies_to = "1"
            text = "First."

            [[note]]
            id = "dup"
            applies_to = "2"
            text = "Second."
            """,
        )
        assert any("duplicate id" in error for error in validate_notes("fr"))

    def test_unknown_system_fails(self, notes_file):
        notes_file(
            "cy",
            """
            language = "cy"

            [[note]]
            id = "cy-bad-system"
            applies_to = "1"
            systems = ["vigesimal"]
            text = "Wrong system key."
            """,
        )
        assert any("unknown number system" in e for e in validate_notes("cy"))

    def test_number_outside_the_deck_fails(self, notes_file):
        notes_file(
            "cy",
            """
            language = "cy"

            [[note]]
            id = "cy-nowhere"
            applies_to = "99999999"
            text = "Points at nothing."
            """,
        )
        assert any("matches no number" in e for e in validate_notes("cy"))

    def test_sparse_range_is_allowed_to_overlap(self, notes_file):
        """Decks are sparse above 100 by design, so overlap is enough."""
        notes_file(
            "es",
            """
            language = "es"

            [[note]]
            id = "es-hundreds"
            applies_to = "100-199"
            text = "A hundred on its own is cien."
            """,
        )
        assert validate_notes("es") == []

    def test_markup_is_rejected(self, notes_file):
        notes_file(
            "fr",
            """
            language = "fr"

            [[note]]
            id = "fr-html"
            applies_to = "1"
            text = "Nice <b>try</b>."
            """,
        )
        assert any("plain text" in e for e in validate_notes("fr"))

    def test_translation_for_an_unknown_note_fails(self, notes_file):
        notes_file(
            "fr",
            """
            language = "fr"
            authored_in = "en"

            [[note]]
            id = "fr-real"
            applies_to = "1"
            text = "Real note."
            """,
        )
        notes_file(
            "fr",
            """
            [[note]]
            id = "fr-ghost"
            text = "Traduction d'une note inexistante."
            """,
            ui_lang="de",
        )
        assert any("no such note" in e for e in validate_notes("fr"))


class TestTranslations:
    def test_untranslated_note_is_shown_not_hidden(self, notes_file):
        """Requiring eight translations per note would kill contribution.

        A reader who doesn't read the authoring language still gets the fact,
        with a marker saying it hasn't been translated.
        """
        notes_file(
            "fr",
            """
            language = "fr"
            authored_in = "en"

            [[note]]
            id = "fr-one"
            applies_to = "1"
            text = "Written in English."
            """,
        )
        note = get_notes("fr", numbers=1, when="rev", ui_lang="de")[0]
        assert note["text"] == "Written in English."
        assert note["translated"] is False

    def test_override_replaces_the_text(self, notes_file):
        notes_file(
            "fr",
            """
            language = "fr"
            authored_in = "en"

            [[note]]
            id = "fr-one"
            applies_to = "1"
            text = "Written in English."

              [[note.examples]]
              phrase = "un"
              gloss = "one"
            """,
        )
        notes_file(
            "fr",
            """
            [[note]]
            id = "fr-one"
            text = "Auf Deutsch."

              [[note.examples]]
              phrase = "un"
              gloss = "eins"
            """,
            ui_lang="de",
        )
        note = get_notes("fr", numbers=1, when="rev", ui_lang="de")[0]
        assert note["text"] == "Auf Deutsch."
        assert note["translated"] is True
        # The phrase stays in the language being learned; only the gloss moves.
        assert note["examples"][0]["phrase"] == "un"
        assert note["examples"][0]["gloss"] == "eins"


class TestNeverBreaksADrill:
    def test_malformed_file_costs_the_notes_not_the_quiz(self, notes_file, client):
        notes_file("cy", "this is not valid toml =")
        assert get_notes("cy", numbers=10, when="revealed") == []
        assert validate_notes("cy")  # CI still fails on it
        assert client.get("/cy/numbers").status_code == 200

    def test_language_without_notes_returns_nothing(self):
        assert get_notes("ja", numbers=10, when="revealed") == []


class TestRendering:
    def test_no_lightbulb_beside_an_unanswered_prompt(self, client):
        client.post("/cy/start", data={"mode": "advanced"})
        with client.session_transaction() as sess:
            sess["current_number"] = 10
            sess["correct_answer"] = "deg"
        body = client.get("/cy/quiz/advanced").get_data(as_text=True)
        assert "number-notes-toggle" not in body
        assert "deng" not in body

    def test_note_appears_once_the_answer_is_revealed(self, client):
        client.post("/cy/start", data={"mode": "advanced"})
        with client.session_transaction() as sess:
            sess["current_number"] = 10
            sess["correct_answer"] = "deg"
        client.post("/cy/quiz/advanced", data={"reveal": "1"})
        body = client.get("/cy/quiz/advanced").get_data(as_text=True)
        assert "number-notes-toggle" in body
        assert "deg becomes deng" in body
        assert "deng munud" in body

    def test_results_page_carries_the_round_s_notes(self, client):
        """Easy mode has no reveal step, so this is its only surface."""
        client.post("/cy/start", data={"mode": "easy"})
        with client.session_transaction() as sess:
            sess["asked_numbers"] = [10]
            sess["total_questions"] = 10
        body = client.get("/cy/results").get_data(as_text=True)
        assert "deg becomes deng" in body

    def test_worksheet_notes_are_on_the_key_and_not_the_exercises(self, client):
        body = client.get("/cy/worksheet?range=1-20&count=20&seed=abc123").get_data(
            as_text=True
        )
        exercises, key = body.split("ws-sheet-answers")
        assert "number-note-text" not in exercises
        assert "ws-notes" in key

    def test_toggle_is_a_real_button_with_aria_state(self, client):
        client.post("/cy/start", data={"mode": "advanced"})
        with client.session_transaction() as sess:
            sess["current_number"] = 10
            sess["correct_answer"] = "deg"
        client.post("/cy/quiz/advanced", data={"reveal": "1"})
        body = client.get("/cy/quiz/advanced").get_data(as_text=True)
        assert '<button type="button"' in body
        assert 'aria-expanded="false"' in body
        assert "aria-controls=" in body
