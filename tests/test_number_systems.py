"""Tests for languages with more than one numeral system.

Welsh is the first: decimal (what schools teach, what the deck has had all
along) and traditional/vigesimal (obligatory for the time, dates and age). The
same shape would fit Korean Sino vs native or Belgian French.

Two properties matter more than the feature itself:

* the other fourteen languages must not notice any of this exists;
* the traditional system must stay hidden until its deck is actually usable,
  so the control and the data can land in either order.
"""

import re

import pytest

from app import app as flask_app
from languages import (
    AVAILABLE_LANGUAGES,
    DEFAULT_NUMBER_SYSTEM,
    get_default_number_system,
    get_language_numbers,
    get_number_systems,
    get_ready_number_systems,
    is_number_system_ready,
    resolve_number_system,
)
from languages import config as languages_config
import quiz_logic


@pytest.fixture
def app():
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret-key"
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def incomplete_traditional():
    """Pretend the traditional deck has a hole in the range the gate checks.

    The real deck now passes the gate (1-21 is complete), so what has to be
    simulated is the state it was in before speakers filled that block — and
    the state any *future* second system starts in.
    """
    key = ("cy", "numbers_traditional")
    original = languages_config._SYSTEM_NUMBER_CACHE.get(key)
    languages_config._SYSTEM_NUMBER_CACHE[key] = {
        num: f"trad-{num}"
        for num in range(1, 21)  # 21 missing
    }
    yield languages_config._SYSTEM_NUMBER_CACHE[key]
    if original is None:
        languages_config._SYSTEM_NUMBER_CACHE.pop(key, None)
    else:
        languages_config._SYSTEM_NUMBER_CACHE[key] = original


class TestSingleSystemLanguagesAreUntouched:
    """The fourteen one-system languages must behave exactly as before."""

    def test_every_language_reports_at_least_one_system(self):
        for code in AVAILABLE_LANGUAGES:
            assert len(get_number_systems(code)) >= 1

    def test_undeclared_language_has_one_implicit_system(self):
        systems = get_number_systems("es")
        assert [s["key"] for s in systems] == [DEFAULT_NUMBER_SYSTEM]
        assert get_default_number_system("es") == DEFAULT_NUMBER_SYSTEM

    def test_one_argument_call_still_works_for_every_language(self):
        for code, info in AVAILABLE_LANGUAGES.items():
            if not info.get("ready"):
                continue
            numbers = get_language_numbers(code)
            assert numbers
            assert numbers == get_language_numbers(
                code, get_default_number_system(code)
            )

    def test_no_system_markup_for_a_single_system_language(self, client):
        response = client.get("/es/numbers")
        assert response.status_code == 200
        assert "number-system-toggle" not in response.get_data(as_text=True)
        assert "number-system-note" not in response.get_data(as_text=True)

    def test_unknown_system_falls_back_instead_of_raising(self):
        assert resolve_number_system("es", "traditional") == DEFAULT_NUMBER_SYSTEM
        assert resolve_number_system("es", "nonsense") == DEFAULT_NUMBER_SYSTEM


class TestWelshDeclaration:
    def test_welsh_declares_two_systems_and_defaults_to_decimal(self):
        assert [s["key"] for s in get_number_systems("cy")] == [
            "decimal",
            "traditional",
        ]
        assert get_default_number_system("cy") == "decimal"

    def test_decimal_deck_is_the_original_deck(self):
        assert get_language_numbers("cy", "decimal") == get_language_numbers("cy")

    def test_traditional_deck_drops_unfilled_gaps(self):
        traditional = get_language_numbers("cy", "traditional")
        assert traditional
        assert all(word for word in traditional.values())
        # The forms the review thread actually gave us.
        assert traditional[20] == "ugain"
        assert traditional[21] == "un ar hugain"
        assert traditional[70] == "deg a thrigain"

    def test_traditional_contains_no_invented_forms(self):
        """Every filled entry was stated verbatim in the review thread.

        A pattern was described for 22-29 and 31-39 but the forms were never
        given, so those must stay empty: extrapolating a rule into a data file
        is how a learner ends up being taught something wrong with confidence.
        """
        verified = {
            1: "un",
            2: "dau",
            3: "tri",
            4: "pedwar",
            5: "pump",
            6: "chwech",
            7: "saith",
            8: "wyth",
            9: "naw",
            10: "deg",
            11: "un ar ddeg",
            12: "deuddeg",
            13: "tri ar ddeg",
            14: "pedwar ar ddeg",
            15: "pymtheg",
            16: "un ar bymtheg",
            17: "dau ar bymtheg",
            18: "deunaw",
            19: "pedwar ar bymtheg",
            20: "ugain",
            21: "un ar hugain",
            30: "deg ar hugain",
            40: "deugain",
            45: "pump ar ddeugain",
            50: "hanner cant",
            60: "trigain",
            70: "deg a thrigain",
            80: "pedwar ugain",
            90: "deg a phedwar ugain",
            100: "cant",
        }
        assert get_language_numbers("cy", "traditional") == verified


class TestCompletenessGate:
    """The system appears when its data is usable, and not one commit before."""

    def test_gate_is_open_now_that_1_to_21_is_complete(self):
        assert is_number_system_ready("cy", "traditional") is True
        assert [s["key"] for s in get_ready_number_systems("cy")] == [
            "decimal",
            "traditional",
        ]

    def test_toggle_is_rendered(self, client):
        body = client.get("/cy/numbers").get_data(as_text=True)
        assert "number-system-toggle" in body
        assert 'href="/cy/numbers?system=traditional"' in body

    def test_a_hole_in_the_gated_range_closes_it_again(self, incomplete_traditional):
        assert is_number_system_ready("cy", "traditional") is False
        assert resolve_number_system("cy", "traditional") == "decimal"

    def test_no_toggle_while_the_gate_is_shut(self, client, incomplete_traditional):
        body = client.get("/cy/numbers").get_data(as_text=True)
        assert "number-system-toggle" not in body
        # …but the page still says which system it is teaching.
        assert "number-system-note" in body


class TestHonestLabelling:
    """Say which system is being taught, before anyone asks.

    This was the actual question put to r/learnwelsh, and the answer was "you
    need both" — so the site has to stop implying that decimal is all there is.
    """

    def test_language_card_names_the_system(self, client):
        body = client.get("/").get_data(as_text=True)
        assert "modern decimal Welsh" in body

    def test_menu_page_offers_both_systems_on_the_tile(self, client):
        """With two systems live the tile is a picker, not a label.

        A badge naming the active system tells a learner which Welsh they are
        about to be drilled on but gives them no way to ask for the other one.
        """
        body = client.get("/cy").get_data(as_text=True)
        assert "menu-tile-badge" not in body
        assert 'href="/cy?system=decimal"' in body
        assert 'href="/cy?system=traditional"' in body
        assert "Degol" in body
        assert "Ugeiniol" in body

    def test_menu_page_marks_the_active_system(self, client):
        body = client.get("/cy?system=traditional").get_data(as_text=True)
        pills = re.findall(r'<a class="menu-tile-system.*?</a>', body, re.S)
        assert len(pills) == 2
        active = [pill for pill in pills if "menu-tile-system active" in pill]
        assert len(active) == 1
        assert "system=traditional" in active[0]
        assert 'aria-current="true"' in active[0]

    def test_menu_page_falls_back_to_the_badge_when_only_one_is_ready(
        self, client, incomplete_traditional
    ):
        """No choice to make, so no control — the badge and the notice explain."""
        body = client.get("/cy").get_data(as_text=True)
        assert "number-system-note" in body
        assert "menu-tile-badge" in body
        assert "menu-tile-system-options" not in body

    def test_menu_page_of_a_single_system_language_has_no_picker(self, client):
        body = client.get("/es").get_data(as_text=True)
        assert "menu-tile-system" not in body
        assert "menu-tile-badge" not in body

    def test_learn_page_explains_both_systems(self, client):
        body = client.get("/cy/learn").get_data(as_text=True)
        assert "Two ways to count in Welsh" in body
        # The usage table the review thread produced.
        assert "chwarter i ddeuddeg" in body
        assert "ugain mlynedd" in body

    def test_other_languages_get_no_such_copy(self, client):
        body = client.get("/es").get_data(as_text=True)
        assert "number-system-note" not in body


class TestChoosingASystem:
    def test_system_param_renders_the_config_screen_not_a_drill(self, client):
        """`?system=` is deliberately not a preset param.

        If it were, this URL would skip the config screen into a drill and pick
        up a noindex along the way.
        """
        response = client.get("/cy/numbers?system=traditional")
        body = response.get_data(as_text=True)
        assert response.status_code == 200
        assert "mode-selection" in body
        assert "noindex" not in body

    def test_choice_is_remembered_for_the_session(self, client):
        client.get("/cy/numbers?system=traditional")
        with client.session_transaction() as sess:
            assert sess["number_system"] == "traditional"

    def test_menu_tile_picker_carries_into_the_config_screen(self, client):
        """Switching on the menu is the same switch, not a second setting."""
        client.get("/cy?system=traditional")
        with client.session_transaction() as sess:
            assert sess["number_system"] == "traditional"
        body = client.get("/cy/numbers").get_data(as_text=True)
        assert 'class="number-system-option active"' in body
        assert "Ugeiniol" in body

    def test_menu_tile_picker_switches_back(self, client):
        client.get("/cy?system=traditional")
        client.get("/cy?system=decimal")
        with client.session_transaction() as sess:
            assert sess["number_system"] == "decimal"

    def test_garbage_system_on_the_menu_is_ignored(self, client):
        response = client.get("/cy?system=nonsense")
        assert response.status_code == 200
        with client.session_transaction() as sess:
            assert sess["number_system"] == "decimal"

    def test_drill_runs_in_the_chosen_system(self, client):
        traditional = get_language_numbers("cy", "traditional")
        client.get("/cy/numbers?system=traditional")
        client.post("/cy/start", data={"mode": "advanced", "system": "traditional"})
        with client.session_transaction() as sess:
            assert sess["number_system"] == "traditional"
        client.get("/cy/quiz/advanced")
        with client.session_transaction() as sess:
            number = sess["current_number"]
            assert sess["correct_answer"] == traditional[number]

    def test_system_survives_the_session_reset_between_rounds(self, client):
        client.get("/cy/numbers?system=traditional")
        # A round started without an explicit system keeps the one in force.
        client.post("/cy/start", data={"mode": "easy"})
        with client.session_transaction() as sess:
            assert sess["number_system"] == "traditional"

    def test_another_language_never_inherits_the_choice(self, client):
        client.get("/cy/numbers?system=traditional")
        client.get("/es/numbers")
        with client.session_transaction() as sess:
            assert sess["number_system"] == DEFAULT_NUMBER_SYSTEM

    def test_shared_link_can_carry_a_system(self, client):
        response = client.get("/cy/numbers?mode=hardcore&system=traditional")
        assert response.status_code == 200
        with client.session_transaction() as sess:
            assert sess["mode"] == "hardcore"
            assert sess["number_system"] == "traditional"

    def test_shared_link_with_an_unusable_system_degrades_with_a_notice(
        self, client, incomplete_traditional
    ):
        """A link for a system whose deck regressed must still start a drill."""
        response = client.get("/cy/numbers?mode=advanced&system=traditional")
        assert response.status_code == 200
        with client.session_transaction() as sess:
            assert sess["number_system"] == "decimal"
        assert "preset-notice" in response.get_data(as_text=True)

    def test_garbage_system_in_a_link_is_ignored(self, client):
        response = client.get("/es/numbers?mode=easy&system=klingon")
        assert response.status_code == 200
        with client.session_transaction() as sess:
            assert sess["mode"] == "easy"


class TestWrongSystemFeedback:
    def test_other_system_answer_is_named_not_just_marked_wrong(self, client):
        """A decimal answer in a traditional drill is not wrong Welsh.

        It is the wrong system, and saying so is the difference between a
        correction and a lie.
        """
        client.get("/cy/numbers?system=traditional")
        client.post("/cy/start", data={"mode": "advanced", "system": "traditional"})
        with client.session_transaction() as sess:
            sess["current_number"] = 20
            sess["correct_answer"] = "ugain"

        # "dau ddeg" is 20 in decimal Welsh: right word, wrong system.
        response = client.post(
            "/cy/quiz/advanced", data={"answer": "dau ddeg"}, follow_redirects=True
        )
        assert "Degol" in response.get_data(as_text=True)

    def test_plainly_wrong_answer_gets_no_system_nudge(self, client):
        client.get("/cy/numbers?system=traditional")
        client.post("/cy/start", data={"mode": "advanced", "system": "traditional"})
        with client.session_transaction() as sess:
            sess["current_number"] = 20
            sess["correct_answer"] = "ugain"

        response = client.post(
            "/cy/quiz/advanced", data={"answer": "qqqq"}, follow_redirects=True
        )
        assert "Degol" not in response.get_data(as_text=True)


class TestPartialRange:
    def test_deck_confined_to_one_band_hides_the_magnitude_dial(self):
        """A dial that cannot change anything must not be drawn."""
        assert quiz_logic.spans_multiple_magnitudes({1: "a", 99: "b"}) is False
        assert quiz_logic.spans_multiple_magnitudes({1: "a", 100: "b"}) is True

    def test_range_notice_when_a_system_covers_less(self, client):
        body = client.get("/cy/numbers?system=traditional").get_data(as_text=True)
        assert "number-system-range" in body
        # The range inputs clamp to what this system actually has.
        assert 'max="100"' in body

    def test_no_range_notice_on_the_full_deck(self, client):
        body = client.get("/cy/numbers").get_data(as_text=True)
        assert "number-system-range" not in body

    def test_sparse_deck_still_yields_four_options(self):
        """Easy mode must not degrade to one option on a small deck.

        A deck capped at 100 has exactly one three-digit number, so the
        same-digit-length distractor pool for 100 is empty.
        """
        deck = {num: f"w{num}" for num in range(1, 101)}
        options = quiz_logic.generate_multiple_choice(deck, 100, "w100")
        assert len(options) == 4
        assert "w100" in options


class TestListeningStaysOnADeckItCanPronounce:
    def test_system_without_audio_is_not_used_for_listening(self, client):
        """Traditional Welsh has no MP3s, and audio is stored per language."""
        client.get("/cy/numbers?system=traditional")
        response = client.get("/cy/numbers?mode=listening&system=traditional")
        assert response.status_code == 200
        with client.session_transaction() as sess:
            # Welsh has no audio at all yet, so this degrades to a typed drill.
            assert sess["mode"] != "audio"


class TestWorksheets:
    def test_sheet_url_carries_a_non_default_system(self, client):
        response = client.get(
            "/cy/worksheet?range=1-20&count=10&seed=abc123&system=traditional"
        )
        body = response.get_data(as_text=True)
        assert response.status_code == 200
        assert "system=traditional" in body
        # The traditional word for 20, not the decimal "dau ddeg".
        assert "ugain" in body
        assert "dau ddeg" not in body

    def test_default_system_sheets_keep_their_old_urls(self, client):
        body = client.get("/cy/worksheet?range=1-20&count=10&seed=abc123").get_data(
            as_text=True
        )
        assert "system=" not in body

    def test_pdf_cache_key_separates_systems(self, client):
        """Two systems are two documents; one must never be served for the other."""
        from app import _worksheet_pdf_cache_key

        with flask_app.test_request_context("/cy/worksheet"):
            sheet = {
                "direction": "digits_to_words",
                "count": 10,
                "range_low": 1,
                "range_high": 20,
                "seed": "abc123",
            }
            decimal_key = _worksheet_pdf_cache_key("cy", {**sheet, "system": "decimal"})
            traditional_key = _worksheet_pdf_cache_key(
                "cy", {**sheet, "system": "traditional"}
            )
        assert decimal_key != traditional_key
