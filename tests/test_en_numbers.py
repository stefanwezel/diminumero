"""Tests for the English deck.

English is listed under the UK flag, so it serves British forms. The rule that
separates them from American ones, "and" before the tens and units, is easy to
over-apply (1200 takes none), so it is pinned form by form.
"""

import re
from pathlib import Path

import pytest
from app import app as flask_app
from config import SUPPORTED_UI_LANGUAGES
from languages import AVAILABLE_LANGUAGES, get_language_numbers
from languages.en.generate_numbers import number_to_english

NUMBERS_EN = get_language_numbers("en")
LEARN_UI_LANGUAGES = ["en", "de", "es", "it", "fr", "pt", "ar", "uk"]


def learn_page_examples(ui_lang):
    """(number, word) for every worked example on one Learn page.

    Digit grouping follows the reader's locale (1,000 / 1.000 / 1&nbsp;000), so
    it is stripped; the English words themselves must not change between pages.
    """
    path = Path(flask_app.root_path) / "templates" / f"learn_en_{ui_lang}.html"
    examples = re.findall(
        r"<strong>(\d(?:[\d.,\s]|&nbsp;)*)</strong>(?: =)? ([a-z -]+)",
        path.read_text(encoding="utf-8"),
    )
    return [(int(re.sub(r"\D", "", n)), word.strip()) for n, word in examples]


@pytest.fixture
def app():
    """Create application for testing."""
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret-key"
    return flask_app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


class TestBritishForms:
    """The words themselves, including the cases the "and" rule gets wrong."""

    @pytest.mark.parametrize(
        "number, word",
        [
            (0, "zero"),
            (12, "twelve"),
            (13, "thirteen"),
            (15, "fifteen"),
            (18, "eighteen"),
            (40, "forty"),
            (80, "eighty"),
            (90, "ninety"),
            (21, "twenty-one"),
            (99, "ninety-nine"),
            (100, "one hundred"),
            (101, "one hundred and one"),
            (110, "one hundred and ten"),
            (234, "two hundred and thirty-four"),
            (1000, "one thousand"),
            (1001, "one thousand and one"),
            (1099, "one thousand and ninety-nine"),
            (1100, "one thousand one hundred"),
            (1234, "one thousand two hundred and thirty-four"),
            (20015, "twenty thousand and fifteen"),
            (101000, "one hundred and one thousand"),
            (100001, "one hundred thousand and one"),
            (1000000, "one million"),
            (1000001, "one million and one"),
            (1000100, "one million one hundred"),
            (1005000, "one million five thousand"),
            (
                2345678,
                "two million three hundred and forty-five thousand "
                "six hundred and seventy-eight",
            ),
        ],
    )
    def test_form(self, number, word):
        assert number_to_english(number) == word

    def test_committed_deck_matches_the_generator(self):
        """A hand edit to numbers.py would be lost on the next regeneration."""
        assert NUMBERS_EN == {n: number_to_english(n) for n in NUMBERS_EN}

    def test_deck_covers_zero_to_one_hundred(self):
        assert all(n in NUMBERS_EN for n in range(0, 101))

    @pytest.mark.parametrize("ui_lang", LEARN_UI_LANGUAGES)
    def test_learn_page_examples_match_the_generator(self, ui_lang):
        """Every worked example, in every translation, is what the quiz accepts."""
        examples = learn_page_examples(ui_lang)
        assert examples == learn_page_examples("en")
        assert len(examples) > 40
        for number, word in examples:
            assert word == number_to_english(number)


class TestReachable:
    """The language shows up under its flag and works through the quiz routes."""

    def test_listed_under_the_uk_flag(self, client):
        assert AVAILABLE_LANGUAGES["en"]["flag"] == "🇬🇧"
        html = client.get("/").get_data(as_text=True)
        assert '<div class="language-flag">🇬🇧</div>' in html
        assert 'href="/en"' in html

    @pytest.mark.parametrize("ui_lang", sorted(SUPPORTED_UI_LANGUAGES))
    def test_pages_render_in_every_ui_language(self, client, ui_lang):
        client.get(f"/set_language/{ui_lang}")
        for path in ("/en", "/en/numbers", "/en/learn"):
            assert client.get(path).status_code == 200, path

        with client.session_transaction() as sess:
            assert sess["language"] == ui_lang
            assert sess["learn_language"] == "en"

    @pytest.mark.parametrize(
        "ui_lang, heading",
        [
            ("en", "Learn English Numbers"),
            ("de", "Englische Zahlen lernen"),
            ("es", "Aprende los números en inglés"),
            ("it", "Impara i numeri in inglese"),
            ("fr", "Apprendre les nombres en anglais"),
            ("pt", "Aprenda os números em inglês"),
            ("ar", "تعلّم الأرقام بالإنجليزية"),
            ("uk", "Вчимо числа англійською"),
            # Welsh is a partial locale with no page of its own yet.
            ("cy", "Learn English Numbers"),
        ],
    )
    def test_learn_page_language(self, client, ui_lang, heading):
        client.get(f"/set_language/{ui_lang}")
        assert f"<h1>{heading}</h1>" in client.get("/en/learn").get_data(as_text=True)

    @pytest.mark.parametrize(
        "typed, score",
        [
            ("two hundred and thirty-four", 1),
            ("Two Hundred And Thirty-Four", 1),
            ("two hundred thirty-four", 0),
            ("two hundred and thirty four", 0),
        ],
    )
    def test_typed_answer_in_a_drill(self, client, typed, score):
        client.post("/en/start", data={"mode": "advanced"})
        with client.session_transaction() as sess:
            sess["current_number"] = 234
            sess["correct_answer"] = number_to_english(234)

        client.post("/en/quiz/advanced", data={"answer": typed})

        with client.session_transaction() as sess:
            assert sess["score"] == score
            assert sess["total_questions"] == 1
