"""Tests for the reference pages and what a crawler sees of the site.

/<lang>/numbers/1-100, /<lang>/numbers/1-1000 and /<lang>/conjugation-cheat-sheet
exist to be found by search. What matters most about them: the words are right,
a page exists only where its data is complete, they stay out of the session, and
nothing on them requires an account.

A crawler is a visitor with no session. So the sitemap-wide checks here use a
fresh client per request, which is how they would have caught every Learn page
telling Google it was about Spanish.
"""

import json
import re

import pytest
from app import (
    _available_audio_numbers,
    _conj_accepted_forms,
    _conj_sheet_verb,
    app as flask_app,
)
from config import SUPPORTED_UI_LANGUAGES
from conjugation_config import conj_persons, conj_tenses
from languages import (
    AVAILABLE_LANGUAGES,
    get_language_numbers,
    get_languages_with_audio_mode,
    get_languages_with_conjugation,
    get_languages_with_learn_materials,
)
from languages import number_reference as number_reference_module
from languages.en import conjugations as en_conjugations
from languages.es import conjugations as es_conjugations
from languages.notes_loader import get_notes
from languages.number_reference import (
    NUMBER_PATTERNS,
    get_reference_numbers,
    get_reference_slugs,
    render_pattern,
)
from tools import generate_number_reference

READY_LANGUAGES = [
    code for code, info in AVAILABLE_LANGUAGES.items() if info.get("ready")
]
LANGUAGES_WITH_1000 = [c for c in READY_LANGUAGES if "1-1000" in get_reference_slugs(c)]
NO_AUDIO_LANGUAGES = [
    c for c in READY_LANGUAGES if c not in get_languages_with_audio_mode()
]
CONJUGATION_LANGUAGES = list(get_languages_with_conjugation())


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


def cold_get(path):
    """A request from a visitor with no session, like a crawler's."""
    return flask_app.test_client().get(path)


def html_text(word):
    """A word as Jinja's autoescape writes it."""
    return word.replace("&", "&amp;").replace("'", "&#39;")


def page_title(html):
    return re.search(r"<title>(.*?)</title>", html, re.S).group(1).strip()


def meta_robots(html):
    match = re.search(r'<meta name="robots" content="(.*?)"', html)
    return match.group(1) if match else ""


def sitemap_paths():
    """The default-language pages. test_ui_language_urls.py sweeps the rest."""
    xml = cold_get("/sitemap.xml").get_data(as_text=True)
    paths = [
        re.sub(r"^https?://[^/]+", "", u) for u in re.findall(r"<loc>(.*?)</loc>", xml)
    ]
    return [path for path in paths if "?hl=" not in path]


class TestGeneratedForms:
    """The forms the decks leave out are only as good as the check behind them."""

    @pytest.mark.parametrize("code", LANGUAGES_WITH_1000)
    def test_committed_file_matches_the_generator(self, code):
        """Also the drift check: build() aborts if a deck and generator disagree."""
        path = generate_number_reference.LANGUAGES / code / "numbers_reference.json"
        forms = generate_number_reference.build(code)
        assert path.read_text(encoding="utf-8") == (
            generate_number_reference.serialize(forms)
        )

    @pytest.mark.parametrize("code", LANGUAGES_WITH_1000)
    def test_file_covers_101_to_1000_and_agrees_with_the_deck(self, code):
        """All of 101-1000, so it doesn't depend on which 200 the deck drew."""
        path = generate_number_reference.LANGUAGES / code / "numbers_reference.json"
        forms = {
            int(n): word
            for n, word in json.loads(path.read_text(encoding="utf-8")).items()
        }
        assert set(forms) == set(range(101, 1001))
        deck = get_language_numbers(code)
        assert {n: forms[n] for n in deck if n in forms} == {
            n: word for n, word in deck.items() if n in forms
        }

    def test_a_redrawn_deck_leaves_no_hole(self, monkeypatch):
        """Regenerating a deck draws a different 200 of 101-1000."""
        deck = get_language_numbers("es")
        redrawn = {n: word for n, word in deck.items() if n <= 100 or n > 1000}
        monkeypatch.setattr(
            number_reference_module, "get_language_numbers", lambda code: redrawn
        )
        number_reference_module._reference_words.cache_clear()
        try:
            words = get_reference_numbers("es", "1-1000")
            assert words is not None
            assert words[347] == "trescientos cuarenta y siete"
        finally:
            number_reference_module._reference_words.cache_clear()

    def test_italian_accent_goes_on_the_end_of_the_word(self):
        """103 is centotré, as 23 is ventitré, but 23,000 is ventitremila."""
        generator = generate_number_reference.load_generator("it")
        assert generator(3) == "tre"
        assert generator(23) == "ventitré"
        assert generator(103) == "centotré"
        assert generator(1003) == "milletré"
        assert generator(5003) == "cinquemilatré"
        assert generator(23000) == "ventitremila"
        assert generator(503000) == "cinquecentotremila"
        assert generator(3000000) == "tre milioni"
        assert generator(23000000) == "ventitré milioni"

    def test_no_italian_word_is_accented_anywhere_else(self):
        """Checked on what is served: the deck and the reference forms."""
        words = list(get_language_numbers("it").values())
        words += list(get_reference_numbers("it", "1-1000").values())
        for word in " ".join(words).split():
            assert "tré" not in word[:-3], word
            assert not (word.endswith("tre") and word != "tre"), word

    def test_a_generator_that_drifted_from_its_deck_aborts(self, monkeypatch):
        deck = dict(generate_number_reference.load_deck("es"))
        deck[42] = "not forty-two"
        monkeypatch.setattr(generate_number_reference, "load_deck", lambda code: deck)
        with pytest.raises(SystemExit, match="no longer reproduces"):
            generate_number_reference.build("es")

    def test_loading_a_generator_does_not_rewrite_its_deck(self):
        """These scripts write numbers.py at module level; importing would run that."""
        path = generate_number_reference.LANGUAGES / "es" / "numbers.py"
        before = path.read_bytes()
        assert generate_number_reference.load_generator("es")(47) == (
            "cuarenta y siete"
        )
        assert path.read_bytes() == before

    def test_decks_are_not_widened(self):
        """Drills keep their sparse deck: 500 is in the reference, not the quiz."""
        assert 500 not in get_language_numbers("es")
        assert get_reference_numbers("es", "1-1000")[500] == "quinientos"


class TestAvailability:
    """A page exists where its data is complete, and is a real 404 otherwise."""

    @pytest.mark.parametrize("code", READY_LANGUAGES)
    def test_every_language_lists_1_to_100(self, client, code):
        response = client.get(f"/{code}/numbers/1-100")
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        deck = get_language_numbers(code)
        for number in range(1, 101):
            assert html_text(deck[number]) in html

    @pytest.mark.parametrize("code", LANGUAGES_WITH_1000)
    def test_long_list_has_every_number_once(self, client, code):
        html = client.get(f"/{code}/numbers/1-1000").get_data(as_text=True)
        full_list = html[html.index('id="full-list"') :]
        questions = re.findall(r'class="ref-word" data-q="(\d+)"', full_list)
        assert sorted(map(int, questions)) == list(range(1, 1001))

    def test_long_list_prefers_the_deck(self):
        deck = get_language_numbers("de")
        words = get_reference_numbers("de", "1-1000")
        for number, word in deck.items():
            if 1 <= number <= 1000:
                assert words[number] == word

    def test_a_language_without_a_generator_has_no_long_list(self, client):
        """Nepali's deck has holes above 100, so there is no honest 1-1000 page."""
        assert get_reference_slugs("ne") == ("1-100",)
        assert client.get("/ne/numbers/1-100").status_code == 200
        assert client.get("/ne/numbers/1-1000").status_code == 404
        assert "/ne/numbers/1-1000" not in sitemap_paths()

    @pytest.mark.parametrize(
        "path",
        [
            "/es/numbers/1-50",
            "/es/numbers/0-100",
            "/es/numbers/abc",
            "/xx/numbers/1-100",
            "/fr/conjugation-cheat-sheet",
            "/xx/conjugation-cheat-sheet",
        ],
    )
    def test_unknown_pages_are_real_404s(self, client, path):
        """Not a redirect home: to a crawler that reads as a soft 404."""
        assert client.get(path).status_code == 404


class TestSessionIsolation:
    """Reading a reference page in another tab must not disturb a running drill."""

    @pytest.mark.parametrize(
        "path",
        ["/de/numbers/1-100", "/de/numbers/1-1000", "/de/conjugation-cheat-sheet"],
    )
    def test_session_is_left_alone(self, client, path):
        client.get("/fr/numbers?mode=advanced&range=1-100")
        with client.session_transaction() as sess:
            before = dict(sess)

        assert client.get(path).status_code == 200

        with client.session_transaction() as sess:
            assert dict(sess) == before

    def test_language_comes_from_the_url_not_the_session(self, client):
        client.get("/fr/numbers")
        html = client.get("/de/numbers/1-100").get_data(as_text=True)
        assert "German Numbers 1-100" in page_title(html)
        assert "French" not in page_title(html)


class TestPatterns:
    """The "how it works" paragraph: its number words come from the data."""

    @pytest.mark.parametrize("code", READY_LANGUAGES)
    def test_every_page_has_a_paragraph(self, code):
        for slug in get_reference_slugs(code):
            assert slug in NUMBER_PATTERNS[code], f"{code} has no {slug} paragraph"

    @pytest.mark.parametrize("code", READY_LANGUAGES)
    def test_every_token_resolves(self, code):
        for slug in get_reference_slugs(code):
            words = get_reference_numbers(code, slug)
            segments = render_pattern(code, slug, words)
            assert any("word" in segment for segment in segments)
            for segment in segments:
                if "word" in segment:
                    assert segment["word"] == words[segment["number"]]

    def test_no_token_sits_in_its_own_brackets(self):
        """A token renders as "word (n)", so "({16})" would print "(word (16))"."""
        for code, pages in NUMBER_PATTERNS.items():
            for slug, template in pages.items():
                assert not re.search(r"\(\{\d+\}", template), f"{code} {slug}"

    def test_paragraph_renders_with_the_deck_word(self, client):
        html = client.get("/fr/numbers/1-100").get_data(as_text=True)
        section = html[
            html.index('id="how-it-works"') : html.index('id="test-yourself"')
        ]
        assert '<strong lang="fr">quatre-vingts</strong> (80)' in section


class TestAudio:
    """Audio is offered only where a clip exists, and promised only where it can be."""

    def test_play_buttons_match_the_clips_on_disk(self, client):
        html = client.get("/es/numbers/1-1000").get_data(as_text=True)
        full_list = html[html.index('id="full-list"') :]
        buttons = {int(n) for n in re.findall(r'data-n="(\d+)"', full_list)}
        on_disk = {n for n in _available_audio_numbers("es") if n <= 1000}
        assert buttons == on_disk

    def test_a_number_without_a_clip_has_no_button(self, client):
        assert 500 not in _available_audio_numbers("es")
        html = client.get("/es/numbers/1-1000").get_data(as_text=True)
        assert 'data-n="500"' not in html
        assert 'data-q="500">quinientos' in html

    @pytest.mark.parametrize("code", NO_AUDIO_LANGUAGES)
    def test_no_audio_promised_without_clips(self, client, code):
        html = client.get(f"/{code}/numbers/1-100").get_data(as_text=True)
        assert "Audio" not in page_title(html)
        assert "audio" not in html[html.index('name="description"') :][:300]
        assert "ref-play" not in html
        assert "data-audio-base" not in html
        assert "data-ref-quiz-mode" not in html
        assert "/listening" not in html

    @pytest.mark.parametrize("code", sorted(get_languages_with_audio_mode()))
    def test_audio_languages_say_so(self, client, code):
        html = client.get(f"/{code}/numbers/1-100").get_data(as_text=True)
        assert "Audio" in page_title(html)
        assert f'data-audio-base="/static/audio/{code}/"' in html
        assert 'data-ref-quiz-mode="listen"' in html


class TestNumeralSystems:
    def test_welsh_lists_both_systems(self, client):
        html = client.get("/cy/numbers/1-100").get_data(as_text=True)
        assert ">Degol</th>" in html and ">Ugeiniol</th>" in html
        decimal = get_language_numbers("cy")
        traditional = get_language_numbers("cy", "traditional")
        for number in (19, 20, 84):
            assert html_text(decimal[number]) in html
            assert html_text(traditional[number]) in html

    def test_the_self_test_asks_only_the_default_system(self, client):
        """Two answers per prompt would mark half the right Welsh wrong."""
        html = client.get("/cy/numbers/1-100").get_data(as_text=True)
        row = re.search(r'data-q="19">([^<]+)</td><td>([^<]+)</td>', html)
        assert row.group(1) == get_language_numbers("cy")[19]
        assert row.group(2) == html_text(get_language_numbers("cy", "traditional")[19])

    def test_long_list_has_one_column(self, client):
        """The second system stops at 100, so a second column would be mostly empty."""
        html = client.get("/cy/numbers/1-1000").get_data(as_text=True)
        assert ">Ugeiniol</th>" not in html

    def test_notes_follow_the_columns(self, client):
        """A note about traditional Welsh describes nothing on a decimal-only page."""
        traditional_only = [
            note
            for note in get_notes("cy", numbers=range(1, 1001), ui_lang="en")
            if note["systems"] == ["traditional"]
        ]
        assert traditional_only
        long_list = client.get("/cy/numbers/1-1000").get_data(as_text=True)
        short_list = client.get("/cy/numbers/1-100").get_data(as_text=True)
        for note in traditional_only:
            assert html_text(note["text"]) not in long_list
        assert any(html_text(note["text"]) in short_list for note in traditional_only)

    def test_single_system_languages_have_one_word_column(self, client):
        html = client.get("/es/numbers/1-100").get_data(as_text=True)
        table = html[html.index('class="ref-table"') :]
        assert table[: table.index("</thead>")].count('scope="col"') == 2


class TestNoAccountNeeded:
    """Every route from these pages into practice works from a cold browser."""

    @pytest.mark.parametrize("code", READY_LANGUAGES)
    def test_drill_links_start_the_range_they_promise(self, code):
        for slug in get_reference_slugs(code):
            html = cold_get(f"/{code}/numbers/{slug}").get_data(as_text=True)
            href = re.search(r'href="([^"]*mode=advanced[^"]*)"', html).group(1)
            href = href.replace("&amp;", "&")
            assert f"range={slug}" in href

            response = cold_get(href)
            assert response.status_code == 200
            drill = response.get_data(as_text=True)
            assert "preset-notice" not in drill, f"{href} fell back to a default"

    @pytest.mark.parametrize("code", sorted(get_languages_with_audio_mode()))
    def test_listening_links_start_the_range_they_promise(self, code):
        for slug in get_reference_slugs(code):
            html = cold_get(f"/{code}/numbers/{slug}").get_data(as_text=True)
            response = cold_get(f"/{code}/listening?range={slug}")
            assert f'href="/{code}/listening?range={slug}"' in html
            assert response.status_code == 200
            assert "preset-notice" not in response.get_data(as_text=True)

    def test_the_self_test_is_on_every_page(self, client):
        for path in (
            "/es/numbers/1-100",
            "/es/numbers/1-1000",
            "/de/conjugation-cheat-sheet",
        ):
            html = client.get(path).get_data(as_text=True)
            assert "data-ref-quiz" in html
            assert "js/reference_page.js" in html

    def test_presets_are_nofollow(self, client):
        """They are noindex and start a session: nothing a crawler should walk."""
        html = client.get("/es/numbers/1-100").get_data(as_text=True)
        for link in re.findall(
            r"<a [^>]*(?:mode=advanced|listening\?range)[^>]*>", html
        ):
            assert 'rel="nofollow"' in link


class TestCheatSheet:
    @pytest.mark.parametrize("code", CONJUGATION_LANGUAGES)
    def test_page_renders(self, client, code):
        assert client.get(f"/{code}/conjugation-cheat-sheet").status_code == 200

    def test_forms_are_read_from_the_pool(self, client):
        html = client.get("/es/conjugation-cheat-sheet").get_data(as_text=True)
        forms = es_conjugations.pool.get_verb_forms("ser")
        tense = conj_tenses("es")[0]["key"]
        for form in forms[tense]:
            assert f">{form}</td>" in html

    def test_has_model_verbs_and_the_most_common_ones(self, client):
        html = client.get("/es/conjugation-cheat-sheet").get_data(as_text=True)
        for verb in ("hablar", "comer", "vivir", "ser", "estar", "tener"):
            assert f'<h3 lang="es">{verb}</h3>' in html

    def test_common_list_excludes_the_model_verbs(self):
        pool = en_conjugations.pool
        assert "go" not in pool.top_verbs(20, exclude={"go"})
        assert len(pool.top_verbs(20, exclude={"go"})) == 20
        assert pool.top_verbs(3) == list(pool._data)[:3]

    def test_every_person_gets_a_row(self):
        verb = _conj_sheet_verb("es", "hablar", "en")
        assert [row["person"] for row in verb["rows"]] == [
            person["label"] for person in conj_persons("es")
        ]

    def test_a_modal_has_no_empty_columns(self):
        """Nothing teaches less than a column of dashes under "Present continuous"."""
        verb = _conj_sheet_verb("en", "can", "en")
        assert 0 < len(verb["tenses"]) < 5
        for column in range(len(verb["tenses"])):
            assert any(row["cells"][column]["form"] for row in verb["rows"])

    def test_english_verbs_are_cited_with_to(self, client):
        html = client.get("/en/conjugation-cheat-sheet").get_data(as_text=True)
        assert '<h3 lang="en">to go</h3>' in html

    def test_but_not_a_modal(self, client):
        """A modal has no infinitive: there is no "to can"."""
        html = client.get("/en/conjugation-cheat-sheet").get_data(as_text=True)
        assert '<h3 lang="en">can</h3>' in html
        assert "to can" not in html and "to may" not in html

    def test_self_test_accepts_what_a_drill_accepts(self, monkeypatch):
        """A drill takes the German Sie-imperative without its "Sie", so this must.

        No sheet shows the imperative today, so put it in the first column.
        """
        import app as app_module

        imperative = next(t for t in conj_tenses("de") if t["key"] == "imperativ")
        monkeypatch.setattr(app_module, "conj_tenses", lambda lang: [imperative])
        sie = _conj_sheet_verb("de", "gehen", "de")["rows"][5]["cells"][0]
        assert sie["form"] == "gehen Sie"
        accepted = _conj_accepted_forms("de", "gehen", "imperativ", 5, "gehen Sie")
        assert sie["alternatives"].split("|") == accepted[1:]
        assert "gehen" in accepted

    def test_british_variants_are_accepted_by_the_self_test(self):
        verb = _conj_sheet_verb("en", "learn", "en")
        cells = [cell for row in verb["rows"] for cell in row["cells"]]
        assert any("learned" in cell["alternatives"].split("|") for cell in cells)

    def test_practice_link_is_marked_as_needing_an_account(self, client):
        html = client.get("/es/conjugation-cheat-sheet").get_data(as_text=True)
        assert (
            '<a class="btn btn-secondary" href="/es/conjugate" rel="nofollow">' in html
        )
        assert "free account" in html

    def test_not_caught_by_the_no_store_rule_for_conjugate(self, client):
        """`/conjugate` in a path means no-store; this path must not match it."""
        response = client.get("/es/conjugation-cheat-sheet")
        assert "no-store" not in response.headers["Cache-Control"]


class TestLocalization:
    @pytest.mark.parametrize("locale", sorted(SUPPORTED_UI_LANGUAGES))
    @pytest.mark.parametrize(
        "path",
        ["/es/numbers/1-100", "/es/numbers/1-1000", "/es/conjugation-cheat-sheet"],
    )
    def test_no_placeholder_or_raw_key_leaks(self, client, locale, path):
        client.get(f"/set_language/{locale}")
        response = client.get(path)
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert "LANGUAGE_NAME_PLACEHOLDER" not in html
        assert not re.search(r">\s*(ref|conj_sheet)_[a-z0-9_]+\s*<", html)

    def test_title_follows_the_ui_language(self, client):
        client.get("/set_language/de")
        html = client.get("/es/numbers/1-1000").get_data(as_text=True)
        assert page_title(html).startswith("Bis 1.000 zählen auf Spanisch")

    def test_english_paragraph_says_so_elsewhere(self, client):
        client.get("/set_language/ar")
        html = client.get("/es/numbers/1-100").get_data(as_text=True)
        assert '<p lang="en" dir="ltr">' in html
        assert "ref-untranslated" in html

    def test_english_paragraph_needs_no_marker_in_english(self, client):
        html = client.get("/es/numbers/1-100").get_data(as_text=True)
        assert "ref-untranslated" not in html
        assert '<p lang="en"' not in html


class TestInternalLinks:
    """A page nothing links to isn't found, whatever the sitemap says."""

    @pytest.mark.parametrize(
        "path", ["/fr", "/fr/numbers", "/fr/listening", "/fr/learn"]
    )
    def test_existing_pages_link_in(self, client, path):
        html = client.get(path).get_data(as_text=True)
        assert 'href="/fr/numbers/1-100"' in html
        assert 'href="/fr/numbers/1-1000"' in html

    def test_conjugation_pages_link_to_the_cheat_sheet(self, client):
        html = client.get("/de/learn/conjugations").get_data(as_text=True)
        assert 'href="/de/conjugation-cheat-sheet"' in html

    def test_languages_without_conjugation_offer_no_cheat_sheet(self, client):
        html = client.get("/fr").get_data(as_text=True)
        assert "conjugation-cheat-sheet" not in html

    def test_a_page_does_not_link_to_itself(self, client):
        html = client.get("/es/numbers/1-100").get_data(as_text=True)
        links = html[html.index('class="learn-toc ref-links"') :]
        links = links[: links.index("</nav>")]
        assert 'href="/es/numbers/1-100"' not in links
        assert 'href="/es/numbers/1-1000"' in links
        assert 'href="/es/conjugation-cheat-sheet"' in links
        assert 'href="/es/learn"' in links
        assert 'href="/es/worksheet"' in links

    def test_pages_link_across_languages(self, client):
        html = client.get("/es/numbers/1-100").get_data(as_text=True)
        section = html[html.index('id="other-languages"') :]
        for code in READY_LANGUAGES:
            expected = f'href="/{code}/numbers/1-100"'
            assert (expected in section) == (code != "es")

    def test_long_list_skips_languages_without_one(self, client):
        html = client.get("/es/numbers/1-1000").get_data(as_text=True)
        section = html[html.index('id="other-languages"') :]
        assert "/ne/numbers/" not in section


class TestWhatACrawlerSees:
    """The whole sitemap, each page requested the way Googlebot requests it."""

    @pytest.fixture(scope="class")
    def pages(self):
        flask_app.config["TESTING"] = True
        responses = {path: cold_get(path) for path in sitemap_paths()}
        return {
            path: (response.status_code, response.get_data(as_text=True))
            for path, response in responses.items()
        }

    def test_new_pages_are_in_the_sitemap(self):
        paths = sitemap_paths()
        for code in READY_LANGUAGES:
            assert f"/{code}/numbers" in paths
            assert f"/{code}/numbers/1-100" in paths
        for code in LANGUAGES_WITH_1000:
            assert f"/{code}/numbers/1-1000" in paths
        for code in CONJUGATION_LANGUAGES:
            assert f"/{code}/conjugation-cheat-sheet" in paths

    def test_every_page_answers(self, pages):
        assert {
            path: status for path, (status, _) in pages.items() if status != 200
        } == {}

    def test_no_two_pages_share_a_title(self, pages):
        """Fifteen Learn pages all called "Learn Spanish Numbers" is how this started."""
        seen = {}
        for path, (_, html) in pages.items():
            seen.setdefault(page_title(html), []).append(path)
        assert {t: p for t, p in seen.items() if len(p) > 1} == {}

    def test_every_title_names_the_language_of_its_url(self, pages):
        for path, (_, html) in pages.items():
            code = path.strip("/").split("/")[0]
            if code in AVAILABLE_LANGUAGES:
                name = AVAILABLE_LANGUAGES[code]["name"]
                assert name in page_title(html), f"{path}: {page_title(html)}"

    def test_nothing_in_the_sitemap_is_noindex(self, pages):
        for path, (_, html) in pages.items():
            assert "noindex" not in meta_robots(html), path

    def test_nothing_in_the_sitemap_is_blocked_by_robots(self, pages):
        robots = cold_get("/robots.txt").get_data(as_text=True)
        rules = [
            re.compile(re.escape(rule).replace(r"\*", ".*"))
            for rule in re.findall(r"^Disallow: (.+)$", robots, re.M)
        ]
        for path in pages:
            blocked = [rule.pattern for rule in rules if rule.match(path)]
            assert not blocked, f"{path} blocked by {blocked}"

    def test_structured_data_is_valid_and_not_html_escaped(self, pages):
        """Entities aren't decoded inside <script>, so "&amp;" would be literal."""
        for path, (_, html) in pages.items():
            for block in re.findall(
                r'<script type="application/ld\+json">(.*?)</script>', html, re.S
            ):
                data = json.loads(block)
                assert "&amp;" not in json.dumps(data), path
                assert "&#" not in json.dumps(data), path

    def test_reference_pages_describe_themselves(self, pages):
        html = pages["/fr/numbers/1-100"][1]
        data = [
            json.loads(block)
            for block in re.findall(
                r'<script type="application/ld\+json">(.*?)</script>', html, re.S
            )
        ]
        resource = next(d for d in data if d["@type"] == "LearningResource")
        assert resource["url"].endswith("/fr/numbers/1-100")
        assert resource["teaches"] == "French numbers 1-100"
        crumbs = next(d for d in data if d["@type"] == "BreadcrumbList")
        assert crumbs["itemListElement"][-1]["name"] == "French Numbers 1–100"

    def test_description_is_in_the_page(self, pages):
        html = pages["/de/conjugation-cheat-sheet"][1]
        assert '<meta name="description" content="The 20 most common German' in html


class TestLearnPageTitles:
    """The bug behind all of the above: the title followed the session, not the URL."""

    @pytest.mark.parametrize("code", sorted(get_languages_with_learn_materials()))
    def test_cold_visit_names_the_language_in_the_url(self, code):
        html = cold_get(f"/{code}/learn").get_data(as_text=True)
        name = AVAILABLE_LANGUAGES[code]["name"]
        assert f"Learn {name} Numbers" in page_title(html)

    def test_url_beats_a_session_learning_something_else(self, client):
        client.get("/de/numbers")
        html = client.get("/fr/learn").get_data(as_text=True)
        assert "Learn French Numbers" in page_title(html)
        assert "German" not in page_title(html)

    def test_structured_data_matches(self):
        html = cold_get("/fr/learn").get_data(as_text=True)
        block = re.search(
            r'<script type="application/ld\+json">\s*(\{\s*"@context": "https://schema.org",\s*"@type": "LearningResource".*?)</script>',
            html,
            re.S,
        ).group(1)
        assert "French" in json.loads(block)["name"]

    def test_listening_and_practice_screens_name_their_language(self):
        for path, name in (("/fr/listening", "French"), ("/it/numbers", "Italian")):
            assert name in page_title(cold_get(path).get_data(as_text=True))

    @pytest.mark.parametrize("path", ["/es/numbers?hl=de", "/es/listening?hl=de"])
    def test_practice_screens_have_their_own_share_preview(self, path):
        """Pasted into a chat, the link shows its title, not "diminumero"."""
        html = cold_get(path).get_data(as_text=True)
        og_title = re.search(r'<meta property="og:title" content="([^"]*)"', html)
        assert og_title.group(1) == page_title(html)
        assert "Spanisch" in og_title.group(1)
        for tag in ('property="og:description"', 'name="twitter:description"'):
            assert tag in html, tag


class TestCaching:
    def test_returning_visitor_gets_a_shared_cache_header(self, client):
        client.get("/es/numbers/1-100")  # first hit sets the cookie
        response = client.get("/es/numbers/1-100")
        assert response.headers["Cache-Control"] == "public, max-age=3600"
        response = client.get("/es/conjugation-cheat-sheet")
        assert response.headers["Cache-Control"] == "public, max-age=3600"

    def test_login_is_never_shared(self, client):
        with client.session_transaction() as sess:
            sess["user"] = {"sub": "u1", "name": "A Learner"}
        response = client.get("/es/numbers/1-100")
        assert response.headers["Cache-Control"].startswith("private")

    @pytest.mark.parametrize(
        "path",
        [
            "/es/numbers/9-9",
            "/ne/numbers/1-1000",
            "/fr/conjugation-cheat-sheet",
            "/zz/numbers/1-100",
        ],
    )
    def test_a_missing_page_is_not_cached(self, client, path):
        """A 404 here lasts until the data is complete; a cached one would outlive it."""
        client.get("/es/numbers/1-100")  # a returning visitor, so no Set-Cookie
        response = client.get(path)
        assert response.status_code == 404
        assert response.headers["Cache-Control"] == "no-store"
