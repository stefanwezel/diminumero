"""Tests for the UI language in the URL (?hl=de).

The UI language lives in the session and a crawler has no session, so without
this a search engine sees only the English rendering of every page. What has to
hold: each translation has an address that serves it to a visitor with no cookie,
names itself as canonical, and lists its siblings; a page is only ever advertised
in a language it is really translated into; and none of it gets in a person's way.

The sweep at the bottom requests every sitemap URL with a cold client, since a
mistake in one language version is invisible to anyone browsing with a session.
"""

import json
import re
import xml.etree.ElementTree as ET

import pytest
from app import URL_UI_LANGUAGES, _page_versions, app as flask_app
from config import PARTIAL_UI_LANGUAGES, SUPPORTED_UI_LANGUAGES
from languages import AVAILABLE_LANGUAGES, get_language_ui_name
from translations import TRANSLATIONS

BASE = "https://diminumero.com"
NS = {
    "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
    "xhtml": "http://www.w3.org/1999/xhtml",
}
OTHER_LANGUAGES = [code for code in URL_UI_LANGUAGES if code != "en"]


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


def cold_html(path):
    return cold_get(path).get_data(as_text=True)


def page_title(html):
    return re.search(r"<title>(.*?)</title>", html, re.S).group(1).strip()


def canonical(html):
    return re.search(r'<link rel="canonical" href="([^"]+)">', html).group(1)


def hreflangs(html):
    """{code: url} from the page's <head>."""
    return dict(
        re.findall(r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)">', html)
    )


def html_lang(html):
    return re.search(r'<html lang="([^"]+)"', html).group(1)


def nav_links(html):
    """The reference-page links, which every language menu has."""
    block = html[html.index('class="learn-toc ref-links"') :]
    return re.findall(r'href="([^"]+)"', block[: block.index("</nav>")])


def switcher_links(html):
    """{ui language label's flag code: href} from the language dropdown."""
    block = html[html.index('id="langDropdown"') :]
    block = block[: block.index("lang-dropdown-footer")]
    return re.findall(r'<a href="([^"]+)"', block)


class TestReadingTheParam:
    def test_serves_the_language_to_a_visitor_with_no_session(self):
        html = cold_html("/es/learn?hl=de")
        assert html_lang(html) == "de"
        assert page_title(html).startswith("Spanische Zahlen lernen")
        assert "Grundbausteine" in html or "Zahlen" in html

    def test_right_to_left_comes_with_it(self):
        assert '<html lang="ar" dir="rtl">' in cold_html("/es/learn?hl=ar")

    def test_a_person_stays_in_that_language(self, client):
        """Land from a search result, then click on with no param in the URL."""
        client.get("/es/learn?hl=de")
        assert html_lang(client.get("/about").get_data(as_text=True)) == "de"

    def test_english_can_be_chosen_back(self, client):
        client.get("/es?hl=de")
        html = client.get("/es?hl=en").get_data(as_text=True)
        assert html_lang(html) == "en"
        assert canonical(html) == f"{BASE}/es"
        assert html_lang(client.get("/es").get_data(as_text=True)) == "en"

    @pytest.mark.parametrize(
        "value", ["xx", "", "DE", "de-DE", "<script>alert(1)</script>"]
    )
    def test_anything_unknown_is_ignored(self, client, value):
        response = client.get("/es", query_string={"hl": value})
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert html_lang(html) == "en"
        assert canonical(html) == f"{BASE}/es"
        assert "<script>alert(1)" not in html

    def test_a_session_language_is_not_overwritten_by_an_unknown_value(self, client):
        client.get("/es?hl=de")
        assert html_lang(client.get("/es?hl=xx").get_data(as_text=True)) == "de"

    def test_plain_url_still_follows_the_session(self, client):
        client.get("/set_language/fr")
        html = client.get("/es/learn").get_data(as_text=True)
        assert html_lang(html) == "fr"
        assert canonical(html) == f"{BASE}/es/learn"


class TestLeavingEverythingElseAlone:
    @pytest.mark.parametrize("path", ["/es/numbers", "/es/listening"])
    def test_does_not_start_a_drill(self, client, path):
        response = client.get(f"{path}?hl=de")
        assert response.status_code == 200
        with client.session_transaction() as sess:
            assert "mode" not in sess
        assert "noindex" not in response.get_data(as_text=True)

    def test_does_not_mint_a_worksheet(self, client):
        """A bare worksheet URL with a param would otherwise redirect to a seed."""
        response = client.get("/es/worksheet?hl=de")
        assert response.status_code == 200
        assert "noindex" not in response.get_data(as_text=True)

    def test_keeps_a_running_drill(self, client):
        client.get("/fr/numbers?mode=advanced&range=1-100")
        with client.session_transaction() as sess:
            before = dict(sess)

        client.get("/de/learn?hl=de")

        with client.session_transaction() as sess:
            after = dict(sess)
        assert after.pop("language") == "de"
        before.pop("language")
        assert after == before

    def test_a_drill_can_start_in_a_language(self, client):
        html = client.get("/es/numbers?mode=easy&hl=de").get_data(as_text=True)
        assert html_lang(html) == "de"
        with client.session_transaction() as sess:
            assert sess["mode"] == "easy"
            assert sess["language"] == "de"

    def test_a_returning_visitor_stays_cacheable(self, client):
        """Rewriting an unchanged language would set a cookie on every response."""
        client.get("/es/learn?hl=de")
        response = client.get("/es/learn?hl=de")
        assert "Set-Cookie" not in response.headers
        assert response.headers["Cache-Control"] == "public, max-age=3600"

    def test_a_language_change_is_never_shared(self, client):
        response = client.get("/es/learn?hl=de")
        assert "Set-Cookie" in response.headers
        assert response.headers["Cache-Control"].startswith("private")


class TestWhichVersionsExist:
    """A page is advertised only in languages it is really translated into."""

    def test_most_pages_have_every_complete_locale(self):
        html = cold_html("/es")
        assert set(hreflangs(html)) == set(URL_UI_LANGUAGES) | {"x-default"}

    def test_learn_page_needs_its_template(self):
        """Without learn_cy_de.html, ?hl=de would be English under German buttons."""
        assert hreflangs(cold_html("/cy/learn")) == {}
        assert canonical(cold_html("/cy/learn?hl=de")) == f"{BASE}/cy/learn"
        assert set(hreflangs(cold_html("/es/learn"))) == (
            set(URL_UI_LANGUAGES) | {"x-default"}
        )

    def test_conjugation_learn_page_needs_its_template(self):
        html = cold_html("/es/learn/conjugations")
        assert set(hreflangs(html)) == {"en", "de", "es", "x-default"}
        fallback = "/es/learn/conjugations?hl=fr"
        assert canonical(cold_html(fallback)) == f"{BASE}/es/learn/conjugations"

    @pytest.mark.parametrize(
        ("code", "versions"),
        [
            ("es", {"en", "es", "x-default"}),
            ("de", {"en", "de", "x-default"}),
            ("it", {"en", "it", "x-default"}),
            ("en", set()),
        ],
    )
    def test_cheat_sheet_only_where_its_tenses_are_named(self, code, versions):
        """Elsewhere, its tables would be headed in English."""
        assert set(hreflangs(cold_html(f"/{code}/conjugation-cheat-sheet"))) == versions

    def test_cheat_sheet_in_its_own_language_is_really_in_it(self):
        html = cold_html("/de/conjugation-cheat-sheet?hl=de")
        assert ">Präsens</th>" in html
        assert ">Present</th>" not in html

    def test_cheat_sheet_still_renders_when_not_advertised(self):
        response = cold_get("/es/conjugation-cheat-sheet?hl=fr")
        assert response.status_code == 200
        canonical_url = canonical(response.get_data(as_text=True))
        assert canonical_url == f"{BASE}/es/conjugation-cheat-sheet"

    def test_partial_locale_is_never_advertised(self):
        assert "cy" in SUPPORTED_UI_LANGUAGES and "cy" in PARTIAL_UI_LANGUAGES
        assert "cy" not in URL_UI_LANGUAGES
        assert "cy" not in hreflangs(cold_html("/es"))
        assert "?hl=cy" not in cold_get("/sitemap.xml").get_data(as_text=True)

    def test_partial_locale_can_still_be_chosen(self, client):
        html = client.get("/es?hl=cy").get_data(as_text=True)
        assert html_lang(html) == "cy"
        assert canonical(html) == f"{BASE}/es"
        assert "?hl=cy" not in " ".join(nav_links(html))

    def test_a_preset_drill_offers_no_versions(self):
        html = cold_html("/es/numbers?mode=easy&hl=de")
        assert hreflangs(html) == {}
        assert "noindex" in html
        assert 'property="og:locale:alternate"' not in html

    def test_a_session_bound_page_offers_no_versions(self, client):
        client.get("/es/numbers?mode=easy")
        html = client.get("/es/quiz/easy").get_data(as_text=True)
        assert hreflangs(html) == {}
        assert 'property="og:locale:alternate"' not in html

    def test_og_alternates_are_real_versions(self):
        html = cold_html("/es/learn/conjugations?hl=de")
        alternates = set(
            re.findall(r'<meta property="og:locale:alternate" content="([^"]+)"', html)
        )
        assert alternates == {"en_US", "es_ES"}


class TestLinksKeepTheLanguage:
    """A crawler keeps no session, so the language has to be in the links."""

    def test_links_on_a_translated_page_carry_it(self):
        html = cold_html("/es?hl=de")
        for path in ("/es/learn", "/es/numbers", "/es/numbers/1-100", "/about"):
            assert f'href="{path}?hl=de"' in html
        assert 'href="/?hl=de"' in html

    def test_links_on_a_plain_page_do_not(self):
        html = cold_html("/es")
        assert 'hl=de"' in html  # the switcher, and nothing else
        assert not any("hl=" in link for link in nav_links(html))
        assert 'href="/es/learn"' in html

    def test_not_for_a_page_without_that_version(self):
        """A plain link beats one to a version that isn't advertised."""
        html = cold_html("/es?hl=it")
        assert 'href="/es/learn/conjugations"' in html
        assert 'href="/es/learn/conjugations?hl=it"' not in html
        assert 'href="/es/conjugation-cheat-sheet"' in html

    def test_not_for_session_bound_pages(self):
        html = cold_html("/es?hl=de")
        assert 'href="/login"' in html
        assert "/login?hl=" not in html

    def test_not_for_presets(self):
        html = cold_html("/es/numbers/1-100?hl=de")
        assert 'href="/es/numbers?mode=advanced&amp;range=1-100"' in html
        assert "mode=advanced&amp;range=1-100&amp;hl" not in html

    @pytest.mark.parametrize("path", ["/es/numbers", "/es/listening"])
    def test_not_in_the_share_link_builder(self, path):
        """The script appends "?magnitude=1" to this, so it can't have a query."""
        html = cold_html(f"{path}?hl=uk")
        assert f'data-base-url="http://localhost{path}"' in html

    def test_not_for_static_files(self):
        html = cold_html("/es?hl=de")
        assert not re.search(r'/static/[^"]*hl=', html)

    def test_not_in_a_printed_sheet_address(self):
        """Printed footers are shared across languages by the PDF cache."""
        response = cold_get("/es/worksheet?seed=abc123&hl=de")
        html = response.get_data(as_text=True)
        assert response.status_code == 200
        assert "seed=abc123" in html
        address = re.search(r"https?://[^\s<\"]*seed=abc123[^\s<\"]*", html).group(0)
        assert "hl=" not in address

    def test_a_page_still_does_not_link_to_itself(self):
        links = nav_links(cold_html("/es/numbers/1-100?hl=de"))
        assert "/es/numbers/1-100?hl=de" not in links
        assert "/es/numbers/1-1000?hl=de" in links


class TestSwitcher:
    def test_plain_links_where_the_page_has_that_version(self):
        links = switcher_links(cold_html("/es/learn"))
        for code in URL_UI_LANGUAGES:
            assert f"/es/learn?hl={code}" in links

    def test_falls_back_for_a_version_that_does_not_exist(self):
        links = switcher_links(cold_html("/es/learn"))
        assert "/set_language/cy" in links
        links = switcher_links(cold_html("/es/learn/conjugations"))
        assert "/es/learn/conjugations?hl=de" in links
        assert "/set_language/fr" in links

    def test_keeps_the_pages_other_params(self):
        links = switcher_links(cold_html("/cy/numbers?system=traditional"))
        assert "/cy/numbers?system=traditional&amp;hl=de" in links

    def test_does_not_restart_a_preset_drill(self):
        """A plain link would re-enter the preset and throw away the round."""
        links = switcher_links(cold_html("/es/numbers?mode=easy"))
        assert all(link.startswith("/set_language/") for link in links)

    def test_marks_the_active_language(self):
        html = cold_html("/es?hl=de")
        assert re.search(
            r'href="/es\?hl=de"\s+hreflang="de"\s+class="lang-option active"', html
        )


class TestSetLanguageFallback:
    def test_does_not_bounce_back_into_the_old_language(self, client):
        """?hl= left on the way back would switch straight back again."""
        response = client.get(
            "/set_language/fr", headers={"Referer": f"{BASE}/es/learn?hl=de"}
        )
        assert response.headers["Location"] == f"{BASE}/es/learn"

    def test_keeps_other_params(self, client):
        response = client.get(
            "/set_language/fr",
            headers={"Referer": f"{BASE}/cy/numbers?system=traditional&hl=de"},
        )
        assert response.headers["Location"] == f"{BASE}/cy/numbers?system=traditional"

    def test_no_referer_goes_home(self, client):
        assert client.get("/set_language/fr").headers["Location"] == "/"

    def test_the_language_changes(self, client):
        client.get("/es/learn?hl=de")
        response = client.get(
            "/set_language/fr",
            headers={"Referer": "http://localhost/es/learn?hl=de"},
            follow_redirects=True,
        )
        assert html_lang(response.get_data(as_text=True)) == "fr"


class TestNothingUntranslatedOnIndexablePages:
    """Strings a search result or a landing page shows must not be in English."""

    @pytest.mark.parametrize("locale", OTHER_LANGUAGES)
    def test_titles_and_descriptions(self, locale):
        english = TRANSLATIONS["en"]
        same = [
            key
            for key, value in english.items()
            if key.startswith(
                ("seo_title_", "meta_desc_", "home_new_feature_", "home_audio_mode_")
            )
            and TRANSLATIONS[locale][key] == value
        ]
        assert not same, f"{locale} left in English: {same}"


@pytest.fixture(scope="module")
def sitemap():
    """{url path: {code: url path}} parsed from the XML, so it must also be valid."""
    flask_app.config["TESTING"] = True
    root = ET.fromstring(cold_get("/sitemap.xml").get_data())
    entries = {}
    for url in root.findall("sm:url", NS):
        loc = url.find("sm:loc", NS).text
        entries[loc] = {
            link.get("hreflang"): link.get("href")
            for link in url.findall("xhtml:link", NS)
        }
    return entries


@pytest.fixture(scope="module")
def crawl(sitemap):
    """Every sitemap URL, each requested cold: {absolute url: html}."""
    pages = {}
    for url in sitemap:
        response = cold_get(url.removeprefix(BASE) or "/")
        assert response.status_code == 200, url
        pages[url] = response.get_data(as_text=True)
    return pages


class TestSitemap:
    def test_has_every_version_of_a_page(self, sitemap):
        assert f"{BASE}/es/learn" in sitemap
        for code in OTHER_LANGUAGES:
            assert f"{BASE}/es/learn?hl={code}" in sitemap

    def test_leaves_out_versions_that_do_not_exist(self, sitemap):
        assert f"{BASE}/cy/learn" in sitemap
        assert f"{BASE}/cy/learn?hl=de" not in sitemap
        assert f"{BASE}/es/learn/conjugations?hl=fr" not in sitemap
        assert f"{BASE}/es/conjugation-cheat-sheet?hl=de" not in sitemap
        assert f"{BASE}/ne/numbers/1-1000?hl=de" not in sitemap

    def test_every_entry_lists_itself_and_x_default(self, sitemap):
        for loc, alternates in sitemap.items():
            if not alternates:
                continue
            assert loc in alternates.values(), loc
            assert "?hl=" not in alternates["x-default"], loc

    def test_a_single_version_page_has_no_annotations(self, sitemap):
        assert sitemap[f"{BASE}/cy/learn"] == {}

    def test_versions_agree_with_each_other(self, sitemap):
        """Search engines ignore language annotations that aren't reciprocal."""
        for loc, alternates in sitemap.items():
            for url in alternates.values():
                assert sitemap[url] == alternates, f"{loc} vs {url}"


class TestWhatACrawlerSeesInEachLanguage:
    def test_every_version_is_in_its_language(self, crawl):
        for url, html in crawl.items():
            match = re.search(r"\?hl=(\w+)$", url)
            assert html_lang(html) == (match.group(1) if match else "en"), url

    def test_every_version_names_itself_canonical(self, crawl):
        """Canonical pointing elsewhere tells a search engine to drop the page."""
        for url, html in crawl.items():
            assert canonical(html) == url

    def test_head_and_sitemap_agree(self, crawl, sitemap):
        for url, html in crawl.items():
            assert hreflangs(html) == sitemap[url], url

    def test_translated_title_differs_from_english(self, crawl):
        for url, html in crawl.items():
            if "?hl=" not in url:
                continue
            english = crawl[url.split("?")[0]]
            assert page_title(html) != page_title(english), url

    def test_no_two_pages_in_a_language_share_a_title(self, crawl):
        seen = {}
        for url, html in crawl.items():
            match = re.search(r"\?hl=(\w+)$", url)
            key = (match.group(1) if match else "en", page_title(html))
            seen.setdefault(key, []).append(url)
        assert {k: v for k, v in seen.items() if len(v) > 1} == {}

    def test_every_title_names_the_language_of_its_url(self, crawl):
        for url, html in crawl.items():
            path = url.removeprefix(BASE).split("?")[0]
            code = path.strip("/").split("/")[0]
            # These keys are written per language and inflect the name.
            if code not in AVAILABLE_LANGUAGES or path.endswith("/learn/conjugations"):
                continue
            match = re.search(r"\?hl=(\w+)$", url)
            name = get_language_ui_name(code, match.group(1) if match else "en")
            assert name.lower() in page_title(html).lower(), url

    def test_nothing_is_noindex(self, crawl):
        for url, html in crawl.items():
            assert 'name="robots"' not in html, url

    def test_nothing_is_blocked_by_robots(self, crawl):
        robots = cold_get("/robots.txt").get_data(as_text=True)
        rules = [
            re.compile(re.escape(rule).replace(r"\*", ".*"))
            for rule in re.findall(r"^Disallow: (.+)$", robots, re.M)
        ]
        for url in crawl:
            path = url.removeprefix(BASE)
            assert not [rule.pattern for rule in rules if rule.match(path)], url

    def test_structured_data_is_valid_and_not_html_escaped(self, crawl):
        """Entities aren't decoded in <script>, so French apostrophes would show."""
        for url, html in crawl.items():
            for block in re.findall(
                r'<script type="application/ld\+json">(.*?)</script>', html, re.S
            ):
                text = json.dumps(json.loads(block), ensure_ascii=False)
                assert "&#" not in text and "&amp;" not in text, url

    def test_structured_data_links_to_this_version(self, crawl):
        html = crawl[f"{BASE}/fr/numbers/1-100?hl=de"]
        blocks = [
            json.loads(block)
            for block in re.findall(
                r'<script type="application/ld\+json">(.*?)</script>', html, re.S
            )
        ]
        resource = next(b for b in blocks if b["@type"] == "LearningResource")
        assert resource["url"] == f"{BASE}/fr/numbers/1-100?hl=de"
        assert resource["inLanguage"] == "de"
        crumbs = next(b for b in blocks if b["@type"] == "BreadcrumbList")
        items = crumbs["itemListElement"]
        assert items[1]["name"] == "Französisch"
        assert items[1]["item"] == f"{BASE}/fr?hl=de"
        assert items[-1]["item"] == f"{BASE}/fr/numbers/1-100?hl=de"

    def test_learn_page_says_what_it_is_in_and_what_it_teaches(self, crawl):
        html = crawl[f"{BASE}/es/learn?hl=de"]
        blocks = [
            json.loads(block)
            for block in re.findall(
                r'<script type="application/ld\+json">(.*?)</script>', html, re.S
            )
        ]
        resource = next(b for b in blocks if b["@type"] == "LearningResource")
        assert resource["inLanguage"] == "de"
        assert resource["teaches"] == "es"

    @pytest.mark.parametrize("code", OTHER_LANGUAGES)
    def test_a_crawler_can_walk_the_whole_language(self, crawl, code):
        """From that language's home page, following links alone, with no session."""
        suffix = f"?hl={code}"
        wanted = {url for url in crawl if url.endswith(suffix)}
        start = f"{BASE}/{suffix}"
        reached, queue = {start}, [start]
        while queue:
            for href in re.findall(r'href="(/[^"]*)"', crawl[queue.pop()]):
                url = BASE + href.replace("&amp;", "&")
                if url in wanted and url not in reached:
                    reached.add(url)
                    queue.append(url)
        assert wanted - reached == set()

    def test_versions_come_from_data_not_from_a_list(self):
        assert _page_versions("cards") == ()
        assert _page_versions("learn", "cy") == ("en",)
        assert _page_versions("learn_conjugations", "it") == ("en", "it")
        assert _page_versions("mode_selection", "es") == URL_UI_LANGUAGES
