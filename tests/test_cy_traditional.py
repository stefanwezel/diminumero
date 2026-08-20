"""Tests for provenance-tracked number forms, and the Welsh traditional rules.

The project's rule is that a form no speaker has confirmed does not reach a
learner. That is easy to say and easy to erode, so it is asserted here from
several directions: the tier a form carries, what `build_numbers` will and will
not hand out, what the drill actually serves, and what happens when the rule
that generates the unconfirmed forms disagrees with a speaker.

The generator's own checks live in the generator (it aborts on a rule that
contradicts a confirmed form). These re-assert the important ones so a
refactor that never reruns the script still fails the build.
"""

import importlib

import pytest

from app import app as flask_app
from languages import get_language_numbers
from languages.cy import numbers_traditional as deck
from languages.cy.numbers_traditional import FORMS, SPEAKER_FORMS
from languages.provenance import (
    SOURCES,
    build_numbers,
    iter_forms,
    merge_forms,
    validate_forms,
)

generator = importlib.import_module("languages.cy.generate_numbers_traditional")


@pytest.fixture
def app():
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret-key"
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def sources_of(number):
    return {entry["source"] for entry in FORMS.get(number, [])}


class TestSchema:
    def test_deck_is_well_formed(self):
        assert validate_forms(FORMS) == []

    def test_every_form_declares_a_source(self):
        for _, entry in iter_forms(FORMS):
            assert entry["source"] in SOURCES

    def test_speaker_file_holds_no_generated_forms(self):
        """The hand-edited file is for what people told us.

        Its only reconstructed entries are the ones a human deliberately wrote
        down (0, the colloquial 12, 120) — never anything the generator emits.
        """
        hand_written_reconstructed = {0, 12, 120}
        for number, entries in SPEAKER_FORMS.items():
            for entry in entries:
                if entry["source"] == "reconstructed":
                    assert number in hand_written_reconstructed

    def test_generated_file_is_entirely_reconstructed(self):
        for number, entries in deck.GENERATED.items():
            for entry in entries:
                assert entry["source"] == "reconstructed", number


class TestWithholding:
    """Nothing unconfirmed reaches a learner while the flag is off."""

    def test_reconstructed_forms_are_not_served(self):
        served = get_language_numbers("cy", "traditional")
        for number, entry in iter_forms(FORMS):
            if entry["source"] == "reconstructed":
                assert served.get(number) != entry["text"]

    def test_numbers_with_only_reconstructed_forms_are_absent(self):
        """Skipped entirely — not blank, and not silently decimal."""
        served = get_language_numbers("cy", "traditional")
        assert sources_of(43) == {"reconstructed"}
        assert 43 not in served
        # …and the decimal word for 43 has not crept in as a substitute.
        assert get_language_numbers("cy", "decimal")[43] not in served.values()

    def test_a_speaker_form_wins_over_a_rule_that_disagrees(self):
        """45 is the live disagreement: speakers say `ar`, the rule says `a`."""
        assert {e["text"] for e in FORMS[45]} == {
            "pump ar ddeugain",
            "pump a deugain",
        }
        assert get_language_numbers("cy", "traditional")[45] == "pump ar ddeugain"

    def test_flag_flips_them_on_without_touching_the_data(self):
        withheld = build_numbers(FORMS, serve_reconstructed=False)
        served = build_numbers(FORMS, serve_reconstructed=True)
        assert 43 not in withheld
        assert served[43] == "tri a deugain"
        assert len(served) > len(withheld)

    def test_drill_never_shows_a_reconstructed_form(self, client):
        client.get("/cy/numbers?system=traditional")
        client.post("/cy/start", data={"mode": "advanced", "system": "traditional"})
        reconstructed = {
            entry["text"]
            for _, entry in iter_forms(FORMS)
            if entry["source"] == "reconstructed"
        }
        for _ in range(25):
            client.get("/cy/quiz/advanced")
            with client.session_transaction() as sess:
                assert sess["correct_answer"] not in reconstructed
                sess.pop("current_number", None)
                sess.pop("correct_answer", None)


class TestGenderSeries:
    def test_both_series_are_stored(self):
        genders = {e.get("gender") for e in FORMS[13]}
        assert genders == {"m", "f"}

    def test_the_drill_shows_masculine(self):
        assert build_numbers(FORMS, serve_reconstructed=True)[13] == "tri ar ddeg"

    def test_gender_propagates_into_compounds(self):
        """The split does not stop at 2/3/4."""
        texts = {e.get("gender"): e["text"] for e in FORMS[84]}
        assert texts["m"] == "pedwar a phedwar ugain"
        assert texts["f"] == "pedair a phedwar ugain"

    def test_only_the_unit_is_gendered_never_the_score(self):
        """84 feminine is `pedair a phedwar ugain` — the score keeps `pedwar`."""
        feminine = next(e["text"] for e in FORMS[84] if e.get("gender") == "f")
        assert feminine.endswith("phedwar ugain")

    def test_fused_units_have_no_feminine(self):
        for number in (12, 15, 18):
            assert {e.get("gender") for e in FORMS[number]} == {None}


class TestGeneratorRules:
    """The generator must reproduce what speakers confirmed."""

    @pytest.mark.parametrize(
        "number,expected",
        [
            (21, "un ar hugain"),
            (70, "deg a thrigain"),
            (90, "deg a phedwar ugain"),
        ],
    )
    def test_confirmed_forms_are_reproduced(self, number, expected):
        assert generator._rule_form(number) == expected

    @pytest.mark.parametrize(
        "number,expected",
        [
            (30, "deg ar hugain"),
            (41, "un a deugain"),
            (51, "un ar ddeg a deugain"),
            (99, "pedwar ar bymtheg a phedwar ugain"),
        ],
    )
    def test_rule_shape(self, number, expected):
        assert generator._rule_form(number) == expected

    def test_twenties_use_a_different_connective(self):
        """21-39 is `ar hugain`, not the `a` of the 40s and up."""
        assert generator._rule_form(35) == "pymtheg ar hugain"
        assert " a " not in generator._rule_form(35)

    def test_fifties_build_on_deugain_not_hanner_cant(self):
        for number in range(51, 60):
            assert generator._rule_form(number).endswith("a deugain")

    def test_aspirate_mutation_after_the_connective(self):
        assert generator.aspirate("trigain") == "thrigain"
        assert generator.aspirate("pedwar ugain") == "phedwar ugain"
        assert generator.aspirate("cant") == "chant"
        # d is unaffected, which is why "a deugain" looks unmutated.
        assert generator.aspirate("deugain") == "deugain"

    def test_soft_mutation_is_what_ar_would_take(self):
        assert generator.soft("deugain") == "ddeugain"
        assert generator.soft("trigain") == "drigain"

    def test_nothing_is_generated_outside_the_two_ranges(self):
        generated = generator.generate()
        for number in generated:
            assert number <= 21 or 22 <= number <= 39 or 41 <= number <= 99
            assert number not in (40, 60, 80, 100)

    def test_the_connective_switch_cannot_contradict_confirmed_data(self, monkeypatch):
        """Flipping it to `ar` must fail loudly, not emit 54 wrong forms."""
        monkeypatch.setattr(generator, "TENS_CONNECTIVE", "ar")
        with pytest.raises(SystemExit) as excinfo:
            generator.check()
        message = str(excinfo.value)
        assert "70" in message and "deg a thrigain" in message

    def test_regenerating_is_idempotent(self):
        """A rerun must not churn the committed file."""
        assert generator.generate() == deck.GENERATED

    def test_disagreements_are_reported_not_resolved(self):
        report = "\n".join(generator.report_disagreements(generator.generate()))
        assert "45" in report and "DISAGREES" in report
        # 50's idiomatic form is expected to differ from the regular one.
        assert "50" in report and "variant" in report


class TestMerge:
    def test_speaker_forms_come_first(self):
        merged = merge_forms(
            {1: [{"text": "un", "source": "confirmed"}]},
            {1: [{"text": "un arall", "source": "reconstructed"}]},
        )
        assert [e["text"] for e in merged[1]] == ["un", "un arall"]

    def test_agreement_is_not_stored_twice(self):
        """A rule reproducing a speaker's form is agreement, not a variant."""
        merged = merge_forms(
            {70: [{"text": "deg a thrigain", "source": "confirmed"}]},
            {
                70: [
                    {"text": "deg a thrigain", "gender": "m", "source": "reconstructed"}
                ]
            },
        )
        assert len(merged[70]) == 1
        assert merged[70][0]["source"] == "confirmed"
