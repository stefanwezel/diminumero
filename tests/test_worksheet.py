"""Tests for the printable worksheet generator.

A teacher configures a sheet at /<lang>/worksheet, prints it, and comes back a
term later expecting the identical sheet — answer key included. These cover
that promise, the anonymous/no-session guarantee, the "words only ever come
from the verified deck" rule, and the ways a pasted link can be wrong.
"""

import importlib.util
import re
import shutil
import subprocess

import pytest
from app import (
    WORKSHEET_COUNT_DEFAULT,
    WORKSHEET_COUNT_MAX,
    app as flask_app,
)
from languages import get_language_numbers

# WeasyPrint needs native libraries (pango/harfbuzz); a dev machine without
# them still runs every other worksheet test.
HAS_WEASYPRINT = importlib.util.find_spec("weasyprint") is not None


def extract_pdf_text(pdf_bytes):
    """The text layer of a PDF, via poppler.

    WeasyPrint embeds CID fonts, so the raw content stream holds glyph ids —
    reading the text back needs a real extractor and its ToUnicode map.
    """
    if not shutil.which("pdftotext"):
        pytest.skip("poppler-utils not installed")
    return subprocess.run(
        ["pdftotext", "-", "-"],
        input=pdf_bytes,
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8")


NUMBERS_ES = get_language_numbers("es")
NUMBERS_DE = get_language_numbers("de")


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


def sheet_html(client, query):
    """Fetch a sheet, following the seed-minting redirect if there is one."""
    response = client.get(f"/es/worksheet?{query}", follow_redirects=True)
    assert response.status_code == 200
    return response.data.decode("utf-8")


def _spans(page, css_class):
    """Text of every <span class="…"> on a page, in document order.

    Tolerates extra attributes: target-language text also carries lang=.
    """
    return re.findall(rf'<span class="{css_class}"[^>]*>(.*?)</span>', page)


def exercise_prompts(html):
    """The prompts printed on the exercise page, in sheet order."""
    page = html.split('class="ws-sheet ws-sheet-answers"')[0]
    return _spans(page, "ws-item-prompt")


def answer_key_rows(html):
    """The (digits, word) pairs printed on the answer key, in sheet order."""
    page = html.split('class="ws-sheet ws-sheet-answers"')[1]
    return list(zip(_spans(page, "ws-key-digits"), _spans(page, "ws-key-word")))


class TestSetupForm:
    """The bare URL is the teacher-facing setup page."""

    def test_bare_url_renders_the_form(self, client):
        response = client.get("/es/worksheet")
        assert response.status_code == 200

        html = response.data.decode("utf-8")
        assert 'name="direction"' in html
        assert 'name="count"' in html
        assert 'name="seed"' in html
        assert 'name="min"' in html and 'name="max"' in html

    def test_form_needs_no_javascript(self, client):
        """A plain GET form: submitting it is the same as pasting a link."""
        html = client.get("/es/worksheet").data.decode("utf-8")
        assert 'method="get"' in html

    def test_unknown_language_redirects_home(self, client):
        response = client.get("/xx/worksheet")
        assert response.status_code == 302
        assert response.headers["Location"] == "/"

    def test_utm_params_do_not_generate_a_sheet(self, client):
        """Only worksheet params start a sheet — tracking params must not."""
        html = client.get("/es/worksheet?utm_source=twitter").data.decode("utf-8")
        assert 'name="direction"' in html


class TestDeterminism:
    """The same seed must produce the identical sheet, forever."""

    def test_same_seed_same_sheet(self, client):
        first = sheet_html(client, "count=15&range=1-100&seed=abc123")
        second = sheet_html(client, "count=15&range=1-100&seed=abc123")
        assert exercise_prompts(first) == exercise_prompts(second)
        assert answer_key_rows(first) == answer_key_rows(second)

    def test_different_seed_different_sheet(self, client):
        first = sheet_html(client, "count=15&range=1-100&seed=abc123")
        second = sheet_html(client, "count=15&range=1-100&seed=zzz999")
        assert exercise_prompts(first) != exercise_prompts(second)

    def test_seed_survives_a_fresh_client_with_no_cookies(self, client, app):
        """Nothing about the sheet may come from the session."""
        first = sheet_html(client, "count=10&range=1-100&seed=abc123")
        cold = app.test_client()
        assert exercise_prompts(
            cold.get("/es/worksheet?count=10&range=1-100&seed=abc123").data.decode(
                "utf-8"
            )
        ) == exercise_prompts(first)

    def test_known_seed_pins_the_draw(self, client):
        """A hard-coded expectation, so a change to the draw can't slip by.

        If this fails, every sheet a teacher printed before the change now
        reprints differently.
        """
        html = sheet_html(client, "count=5&range=1-100&seed=diminumero")
        assert exercise_prompts(html) == ["82", "81", "68", "13", "31"]

    def test_count_only_changes_how_much_is_printed(self, client):
        """Same seed and range: a longer sheet extends the shorter one."""
        short = exercise_prompts(sheet_html(client, "count=8&range=1-100&seed=abc123"))
        long = exercise_prompts(sheet_html(client, "count=20&range=1-100&seed=abc123"))
        assert long[:8] == short

    def test_answer_key_matches_the_exercises(self, client):
        html = sheet_html(client, "count=20&range=1-1000&seed=abc123")
        prompts = exercise_prompts(html)
        key = answer_key_rows(html)

        assert len(key) == len(prompts) == 20
        for prompt, (digits, word) in zip(prompts, key):
            assert prompt == digits
            assert NUMBERS_ES[int(digits)] == word


class TestSeedMinting:
    """A sheet without a seed isn't reproducible, so one gets minted."""

    def test_missing_seed_redirects_to_a_seeded_url(self, client):
        response = client.get("/es/worksheet?count=10&range=1-100")
        assert response.status_code == 302

        location = response.headers["Location"]
        assert re.search(r"seed=[a-z0-9]{6}", location)
        assert "count=10" in location and "range=1-100" in location

    def test_blank_seed_from_the_form_is_treated_as_missing(self, client):
        response = client.get("/es/worksheet?count=10&seed=")
        assert response.status_code == 302
        assert re.search(r"seed=[a-z0-9]{6}", response.headers["Location"])

    def test_minted_seed_is_printed_on_the_sheet(self, client):
        response = client.get("/es/worksheet?count=5", follow_redirects=True)
        html = response.data.decode("utf-8")
        seed = re.search(r"seed=([a-z0-9]{6})", html).group(1)
        assert f"Sheet ID {seed}" in html

    def test_garbage_seed_is_replaced_rather_than_rendered(self, client):
        response = client.get("/es/worksheet?count=5&seed=<script>")
        assert response.status_code == 302
        assert "script" not in response.headers["Location"]

    def test_seeded_url_does_not_redirect_again(self, client):
        response = client.get("/es/worksheet?count=5&seed=abc123")
        assert response.status_code == 200


class TestVerifiedDataOnly:
    """Every word on a sheet comes out of the language's checked deck."""

    def test_words_are_deck_entries(self, client):
        html = sheet_html(client, "count=40&range=1-10000&seed=spread1")
        for digits, word in answer_key_rows(html):
            assert NUMBERS_ES[int(digits)] == word

    def test_numbers_are_deck_keys(self, client):
        html = sheet_html(client, "count=40&range=1-1000000&seed=spread2")
        for digits, _ in answer_key_rows(html):
            assert int(digits) in NUMBERS_ES

    def test_another_language_draws_from_its_own_deck(self, client):
        response = client.get(
            "/de/worksheet?count=15&range=1-100&seed=abc123", follow_redirects=True
        )
        html = response.data.decode("utf-8")
        page = html.split('class="ws-sheet ws-sheet-answers"')[1]
        rows = list(zip(_spans(page, "ws-key-digits"), _spans(page, "ws-key-word")))
        assert len(rows) == 15
        for number, word in rows:
            assert NUMBERS_DE[int(number)] == word

    def test_no_repeats_within_a_sheet(self, client):
        prompts = exercise_prompts(sheet_html(client, "count=50&range=1-100&seed=dupe"))
        assert len(prompts) == len(set(prompts)) == 50


class TestDirection:
    """Both directions print the same pairs, prompted from opposite sides."""

    def test_digits_to_words_prompts_with_digits(self, client):
        html = sheet_html(
            client, "count=6&range=1-100&direction=digits_to_words&seed=d1"
        )
        assert all(prompt.isdigit() for prompt in exercise_prompts(html))
        assert "Write each number in Spanish words." in html

    def test_words_to_digits_prompts_with_words(self, client):
        html = sheet_html(
            client, "count=6&range=1-100&direction=words_to_digits&seed=d1"
        )
        prompts = exercise_prompts(html)
        assert not any(prompt.isdigit() for prompt in prompts)
        assert all(prompt in NUMBERS_ES.values() for prompt in prompts)
        assert "Write each Spanish number in digits." in html

    def test_direction_does_not_change_which_numbers_are_drawn(self, client):
        """Same seed, same draw — only the side that gets shown differs."""
        forwards = sheet_html(
            client, "count=6&range=1-100&direction=digits_to_words&seed=d1"
        )
        backwards = sheet_html(
            client, "count=6&range=1-100&direction=words_to_digits&seed=d1"
        )
        assert [digits for digits, _ in answer_key_rows(forwards)] == [
            digits for digits, _ in answer_key_rows(backwards)
        ]

    def test_short_alias_works(self, client):
        html = sheet_html(client, "count=6&range=1-100&direction=to_digits&seed=d1")
        assert not any(prompt.isdigit() for prompt in exercise_prompts(html))


class TestRange:
    """Ranges are checked against the deck, which is sparse above 1000."""

    def test_exercises_stay_inside_the_range(self, client):
        html = sheet_html(client, "count=30&range=1-100&seed=r1")
        for digits, _ in answer_key_rows(html):
            assert 1 <= int(digits) <= 100

    def test_min_max_spelling_from_the_form(self, client):
        html = sheet_html(client, "count=10&min=1&max=50&seed=r2")
        for digits, _ in answer_key_rows(html):
            assert 1 <= int(digits) <= 50

    def test_one_sided_range_is_completed_from_the_deck(self, client):
        html = sheet_html(client, "count=10&min=5000&seed=r3")
        for digits, _ in answer_key_rows(html):
            assert int(digits) >= 5000

    def test_inverted_range_is_swapped(self, client):
        html = sheet_html(client, "count=10&range=100-1&seed=r4")
        for digits, _ in answer_key_rows(html):
            assert 1 <= int(digits) <= 100

    def test_garbage_range_falls_back_to_the_full_deck(self, client):
        html = sheet_html(client, "count=10&range=banana&seed=r5")
        assert "isn&#39;t valid" in html or "isn't valid" in html
        assert len(answer_key_rows(html)) == 10

    def test_range_with_no_numbers_falls_back(self, client):
        """Sparse deck: a syntactically fine range can still be empty."""
        html = sheet_html(client, "count=10&range=9000001-9000002&seed=r6")
        assert "no Spanish numbers in the range" in html
        assert len(answer_key_rows(html)) == 10


class TestCount:
    """The exercise count is clamped, never a crash and never an empty sheet."""

    def test_default_count(self, client):
        html = sheet_html(client, "range=1-100&seed=c1")
        assert len(answer_key_rows(html)) == WORKSHEET_COUNT_DEFAULT

    def test_blank_count_is_the_default_not_an_error(self, client):
        html = sheet_html(client, "count=&range=1-100&seed=c2")
        assert len(answer_key_rows(html)) == WORKSHEET_COUNT_DEFAULT
        assert "out of range" not in html

    def test_count_above_the_limit_is_clamped(self, client):
        html = sheet_html(client, "count=5000&range=1-1000&seed=c3")
        assert len(answer_key_rows(html)) == WORKSHEET_COUNT_MAX
        assert "out of range" in html

    def test_count_below_one_is_clamped(self, client):
        html = sheet_html(client, "count=0&range=1-100&seed=c4")
        assert len(answer_key_rows(html)) == 1

    def test_garbage_count_falls_back_to_the_default(self, client):
        html = sheet_html(client, "count=lots&range=1-100&seed=c5")
        assert len(answer_key_rows(html)) == WORKSHEET_COUNT_DEFAULT

    def test_count_capped_to_what_the_range_holds(self, client):
        """Ten numbers requested from a range holding fewer."""
        available = len([n for n in NUMBERS_ES if 1 <= n <= 10])
        html = sheet_html(client, "count=40&range=1-10&seed=c6")
        assert len(answer_key_rows(html)) == available
        assert "aren&#39;t that many" in html or "aren't that many" in html


@pytest.mark.skipif(not HAS_WEASYPRINT, reason="weasyprint not installed")
class TestPdfFormat:
    """`?format=pdf` renders the same sheet server-side.

    Font coverage is *not* checked here — CI machines have no CJK fonts, so
    that gate is `tools/check_worksheet_fonts.py`, run against the built image.
    """

    def test_pdf_response(self, client):
        response = client.get("/es/worksheet?count=10&range=1-100&seed=x1&format=pdf")
        assert response.status_code == 200
        assert response.mimetype == "application/pdf"
        assert response.data.startswith(b"%PDF-")

    def test_filename_identifies_the_sheet(self, client):
        response = client.get(
            "/es/worksheet?count=10&range=1-100&seed=x1"
            "&direction=words_to_digits&format=pdf"
        )
        disposition = response.headers["Content-Disposition"]
        assert "attachment" in disposition
        assert "diminumero-es-numbers-1-100-words-to-digits-x1.pdf" in disposition

    def test_same_url_gives_byte_identical_pdfs(self, client):
        """No timestamps in the output: a reprint is the same file.

        A WeasyPrint upgrade that starts embedding a creation date would break
        the promise that a sheet regenerates identically — catch it here.
        """
        url = "/es/worksheet?count=12&range=1-100&seed=x2&format=pdf"
        assert client.get(url).data == client.get(url).data

    def test_pdf_and_page_show_the_same_exercises(self, client):
        """One sheet, two renderings — they may never disagree."""
        params = "count=10&range=1-100&seed=x3"
        html = sheet_html(client, params)
        pdf = client.get(f"/es/worksheet?{params}&format=pdf").data

        # The PDF's text layer must contain every answer word on the page.
        text = extract_pdf_text(pdf)
        for _, word in answer_key_rows(html):
            assert word in text

    def test_pdf_carries_the_footer_url_and_licence(self, client):
        pdf = client.get("/es/worksheet?count=10&range=1-100&seed=x4&format=pdf").data
        text = extract_pdf_text(pdf)
        assert "CC BY-SA 4.0" in text
        assert "diminumero.com/es/worksheet" in text

    def test_pdf_has_the_answer_key_on_its_own_page(self, client):
        """The single-sided-printing promise, checked on the real output."""
        pdf = client.get("/es/worksheet?count=10&range=1-100&seed=x5&format=pdf").data
        pages = extract_pdf_text(pdf).split("\f")

        assert len(pages) >= 2
        assert "Answer key" not in pages[0]
        assert "Answer key" in pages[1]

    def test_pdf_renders_without_stylesheet_warnings(self, client, caplog):
        """Keeps the WeasyPrint log worth reading.

        Font-loading failures surface as warnings from the same logger, so
        routine CSS noise must not train anyone to ignore it.
        """
        with caplog.at_level("WARNING", logger="weasyprint"):
            client.get("/es/worksheet?count=10&range=1-100&seed=x9&format=pdf")
        assert caplog.messages == []

    def test_missing_seed_redirects_before_rendering_a_pdf(self, client):
        response = client.get("/es/worksheet?count=10&format=pdf")
        assert response.status_code == 302
        assert "format=pdf" in response.headers["Location"]

    def test_unknown_format_falls_back_to_the_page(self, client):
        response = client.get("/es/worksheet?count=10&seed=x6&format=docx")
        assert response.status_code == 200
        assert response.mimetype == "text/html"
        assert "didn&#39;t recognise the format" in response.data.decode("utf-8")

    def test_page_links_to_its_own_pdf(self, client):
        html = sheet_html(client, "count=10&range=1-100&seed=x7")
        assert "format=pdf" in html
        assert "seed=x7" in html

    def test_pdf_render_failure_degrades_to_the_page(self, client, monkeypatch):
        """A broken PDF stack must not take the worksheet down."""
        import app as app_module

        def boom(_html):
            raise RuntimeError("no pango here")

        monkeypatch.setattr(app_module, "_worksheet_pdf_bytes", boom)

        response = client.get("/es/worksheet?count=10&seed=x8&format=pdf")
        assert response.status_code == 200
        assert response.mimetype == "text/html"
        assert "couldn&#39;t be generated" in response.data.decode("utf-8")


class TestPrintableOutput:
    """The sheet is a document: no chrome, and it prints correctly."""

    def test_no_nav_ads_or_cookie_banner(self, client):
        html = sheet_html(client, "count=10&seed=p1")
        assert "adsbygoogle" not in html
        assert "cookie-banner" not in html
        assert "language-switcher" not in html
        assert "top-controls" not in html

    def test_links_the_print_stylesheet_and_nothing_else(self, client):
        html = sheet_html(client, "count=10&seed=p2")
        assert "css/worksheet.css" in html
        assert "css/style.css" not in html

    def test_answer_key_starts_on_its_own_page(self, client):
        html = sheet_html(client, "count=10&seed=p3")
        assert "ws-sheet-answers" in html

        css = client.get("/static/css/worksheet.css").data.decode("utf-8")
        answers_rule = css.split(".ws-sheet-answers")[1].split("}")[0]
        assert "break-before: page" in answers_rule
        assert "page-break-before: always" in answers_rule

    def test_stylesheet_hides_screen_chrome_when_printing(self, client):
        css = client.get("/static/css/worksheet.css").data.decode("utf-8")
        print_block = css.split("@media print")[1]
        assert ".no-print" in print_block
        assert "@page" in print_block

    def test_generated_sheet_is_not_indexed(self, client):
        html = sheet_html(client, "count=10&seed=p4")
        assert '<meta name="robots" content="noindex, nofollow">' in html

    def test_setup_page_is_indexable_and_in_the_sitemap(self, client):
        html = client.get("/es/worksheet").data.decode("utf-8")
        assert "noindex" not in html

        sitemap = client.get("/sitemap.xml").data.decode("utf-8")
        assert "/es/worksheet" in sitemap


class TestFooter:
    """The footer is the distribution mechanism — it may never be dropped."""

    def test_both_pages_carry_the_footer(self, client):
        html = sheet_html(client, "count=10&range=1-100&seed=f1")
        assert html.count('class="ws-footer"') == 2

    def test_footer_carries_the_attribution(self, client):
        html = sheet_html(client, "count=10&seed=f2")
        assert html.count("CC BY-SA 4.0") == 2

    def test_footer_url_reprints_the_same_sheet(self, client):
        html = sheet_html(client, "count=10&min=1&max=100&seed=f3")
        printed = re.search(r"(https://diminumero\.com/es/worksheet\?\S+?)</p>", html)
        assert printed, "no reprint URL in the footer"

        # The printed URL is the canonical spelling, and it must come back with
        # exactly the sheet that was printed.
        url = printed.group(1).replace("&amp;", "&")
        assert "range=1-100" in url
        reprint = client.get(url.replace("https://diminumero.com", ""))
        assert reprint.status_code == 200
        assert exercise_prompts(reprint.data.decode("utf-8")) == exercise_prompts(html)


class TestNoLoginOrSession:
    """Anonymous, cold, cookie-less GETs have to work."""

    def test_sheet_needs_no_login(self, client):
        response = client.get("/es/worksheet?count=10&seed=n1")
        assert response.status_code == 200

    def test_sheet_does_not_touch_quiz_state(self, client):
        """Printing a worksheet mid-quiz must not disturb the quiz."""
        client.post("/es/start", data={"mode": "easy", "magnitude_level": "1"})
        with client.session_transaction() as sess:
            before = dict(sess)

        client.get("/es/worksheet?count=10&seed=n2")

        with client.session_transaction() as sess:
            assert sess.get("mode") == before.get("mode")
            assert sess.get("current_number") == before.get("current_number")
            assert sess.get("learn_language") == before.get("learn_language")


class TestBatchGenerator:
    """tools/generate_worksheets.py — the OER upload corpus."""

    def test_seeds_are_stable_across_runs(self):
        """Regenerating the corpus must not mint a whole new set of sheets."""
        from tools.generate_worksheets import sheet_seed

        first = sheet_seed("es", 1, 100, 24, "digits_to_words", "v1")
        second = sheet_seed("es", 1, 100, 24, "digits_to_words", "v1")
        assert first == second
        assert re.fullmatch(r"[0-9a-f]{6}", first)

    def test_each_sheet_shape_gets_its_own_seed(self):
        from tools.generate_worksheets import sheet_seed

        seeds = {
            sheet_seed("es", low, high, count, direction, "v1")
            for low, high, count in [(1, 20, 20), (1, 100, 24)]
            for direction in ["digits_to_words", "words_to_digits"]
        }
        assert len(seeds) == 4

    def test_salt_mints_a_different_corpus(self):
        from tools.generate_worksheets import sheet_seed

        assert sheet_seed("es", 1, 100, 24, "digits_to_words", "v1") != sheet_seed(
            "es", 1, 100, 24, "digits_to_words", "v2"
        )

    def test_plan_covers_every_ready_language(self):
        from tools.generate_worksheets import (
            DIRECTIONS,
            STANDARD_RANGES,
            planned_sheets,
            ready_languages,
        )

        langs = ready_languages()
        plan = list(planned_sheets(langs, "v1"))
        assert len(plan) == len(langs) * len(STANDARD_RANGES) * len(DIRECTIONS)
        assert {lang for lang, _ in plan} == set(langs)

    def test_planned_urls_are_accepted_by_the_route(self, client):
        """Every planned sheet must render without a fallback notice."""
        from tools.generate_worksheets import planned_sheets

        for lang, params in planned_sheets(["es", "cy"], "v1"):
            query = "&".join(f"{key}={value}" for key, value in params.items())
            response = client.get(f"/{lang}/worksheet?{query}")
            assert response.status_code == 200, (lang, query)
            assert "ws-notice" not in response.data.decode("utf-8"), (lang, query)
