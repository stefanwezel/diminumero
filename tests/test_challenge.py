"""Tests for friend challenges: one random round, shared by link, compared by score."""

import json
import random
import re
import shutil
import subprocess

import pytest
from itsdangerous import URLSafeSerializer

import challenge
import quiz_logic
from app import app as flask_app
from config import QUESTIONS_PER_QUIZ
from languages import get_language_numbers
from models import QuizRun, db

SECRET = "test-secret-key"

QUIZ_PATHS = {
    "easy": "/{lang}/quiz/easy",
    "advanced": "/{lang}/quiz/advanced",
    "hardcore": "/{lang}/quiz/hardcore",
    "audio": "/{lang}/listen",
}


@pytest.fixture
def app():
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = SECRET
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def friend(app):
    """A second, independent browser."""
    return app.test_client()


def _create(client, lang="es", kind="numbers", difficulty="advanced", name="Alex"):
    response = client.post(
        "/challenge",
        data={"lang": lang, "kind": kind, "difficulty": difficulty, "name": name},
    )
    assert response.status_code == 303
    return response.location


def _token(url):
    return url.rsplit("/challenge/", 1)[1].split("?")[0]


def _decode(url):
    return challenge.Challenge.decode(_token(url), SECRET)


def _play(client, answer_right=None):
    """Answer every question of the running challenge; return the result URL.

    `answer_right(i)` says whether question i is answered correctly; the
    default answers all of them right. Returns the asked numbers too.
    """
    answer_right = answer_right or (lambda i: True)
    asked = []
    for i in range(QUESTIONS_PER_QUIZ):
        with client.session_transaction() as sess:
            mode, lang = sess["mode"], sess["learn_language"]
        path = QUIZ_PATHS[mode].format(lang=lang)
        assert client.get(path).status_code == 200
        with client.session_transaction() as sess:
            number, word = sess["current_number"], sess["correct_answer"]
            options = sess.get("current_options")
        asked.append((number, options))
        if mode == "audio":
            answer = str(number) if answer_right(i) else "999999999"
        else:
            answer = word if answer_right(i) else "definitely wrong"
        response = client.post(path, data={"answer": answer})
    # The last answer goes to results, which ends the challenge on its page.
    assert response.status_code == 302 and response.location.endswith("/results")
    response = client.get(response.location)
    assert response.status_code == 302 and "/challenge/" in response.location
    return response.location, asked


def _h1(html):
    return re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S).group(1).strip()


class TestToken:
    def test_round_trip(self):
        ch = challenge.Challenge("es", "audio", "abcdefgh", "Alex").with_result(
            "Alex", 7, 52
        )
        again = challenge.Challenge.decode(ch.encode(SECRET), SECRET)
        assert again == ch

    def test_tampered_token_is_rejected(self):
        token = challenge.Challenge("es", "easy", "abcdefgh").encode(SECRET)
        flipped = token[:-1] + ("A" if token[-1] != "A" else "B")
        assert challenge.Challenge.decode(flipped, SECRET) is None

    def test_other_secret_is_rejected(self):
        token = challenge.Challenge("es", "easy", "abcdefgh").encode("other")
        assert challenge.Challenge.decode(token, SECRET) is None

    @pytest.mark.parametrize(
        "payload",
        [
            {"v": 2, "l": "es", "m": "e", "s": "abcdefgh"},
            {"v": 1, "l": "es", "m": "x", "s": "abcdefgh"},
            {"v": 1, "l": "es", "m": "e", "s": "short"},
            {"v": 1, "l": "ES!", "m": "e", "s": "abcdefgh"},
            {"v": 1, "l": "es", "m": "e", "s": "abcdefgh", "h": "x" * 40},
            {"v": 1, "l": "es", "m": "e", "s": "abcdefgh", "h": "‮evil"},
            {"v": 1, "l": "es", "m": "e", "s": "abcdefgh", "r": [["A", 11, 5]]},
            {"v": 1, "l": "es", "m": "e", "s": "abcdefgh", "r": [["A", True, 5]]},
            {"v": 1, "l": "es", "m": "e", "s": "abcdefgh", "r": [["A", 5, -1]]},
            {"v": 1, "l": "es", "m": "e", "s": "abcdefgh", "r": [["A", 5]]},
            {"v": 1, "l": "es", "m": "e", "s": "abcdefgh", "r": [["A", 5, 5]] * 6},
            ["not", "a", "dict"],
        ],
    )
    def test_correctly_signed_but_malformed_is_rejected(self, payload):
        """The signature proves we made it, not that this version can read it."""
        token = URLSafeSerializer(SECRET, salt=challenge.TOKEN_SALT).dumps(payload)
        assert challenge.Challenge.decode(token, SECRET) is None

    def test_overlong_token_is_not_decoded(self):
        assert challenge.Challenge.decode("a" * 5000, SECRET) is None

    def test_results_cap_keeps_the_creator(self):
        ch = challenge.Challenge("es", "easy", "abcdefgh", "Host")
        for i in range(8):
            ch = ch.with_result(f"P{i}", i, 10)
        names = [r.name for r in ch.results]
        assert len(names) == challenge.MAX_RESULTS
        assert names[0] == "P0"
        assert names[1:] == ["P4", "P5", "P6", "P7"]


class TestNames:
    @pytest.mark.parametrize(
        ("raw", "clean"),
        [
            ("  Alex  ", "Alex"),
            ("Ma\n\tria", "Ma ria"),
            ("‮evil‬", "evil"),
            ("x" * 50, "x" * challenge.NAME_MAX),
            (None, ""),
            ("زهرا‌ی", "زهرا‌ی"),
        ],
    )
    def test_clean_name(self, raw, clean):
        assert challenge.clean_name(raw) == clean


class TestRanking:
    def test_best_score_first_then_faster_time(self):
        ch = challenge.Challenge("es", "easy", "abcdefgh")
        ch = ch.with_result("Slow", 8, 90).with_result("Low", 5, 10)
        ch = ch.with_result("Fast", 8, 30)
        rows = ch.ranked()
        assert [r["name"] for r in rows] == ["Fast", "Slow", "Low"]
        assert [r["rank"] for r in rows] == [1, 2, 3]
        assert rows[0]["newest"] and rows[0]["time"] == "0:30"

    def test_exact_tie_shares_a_rank(self):
        ch = challenge.Challenge("es", "easy", "abcdefgh")
        ch = ch.with_result("A", 8, 30).with_result("B", 8, 30)
        assert [r["rank"] for r in ch.ranked()] == [1, 1]


class TestDeterminism:
    def test_same_seed_same_numbers(self):
        deck = get_language_numbers("es")
        first = challenge.draw_numbers(deck, "abcdefgh", "advanced")
        assert first == challenge.draw_numbers(deck, "abcdefgh", "advanced")
        assert len(first) == QUESTIONS_PER_QUIZ == len(set(first))
        assert all(num in deck for num in first)

    def test_different_seed_different_numbers(self):
        deck = get_language_numbers("es")
        assert challenge.draw_numbers(
            deck, "abcdefgh", "advanced"
        ) != challenge.draw_numbers(deck, "hgfedcba", "advanced")

    def test_seeded_options_repeat_and_contain_the_answer(self):
        deck = get_language_numbers("es")
        one = quiz_logic.generate_multiple_choice(
            deck, 42, deck[42], rng=challenge.options_rng("abcdefgh", 42)
        )
        two = quiz_logic.generate_multiple_choice(
            deck, 42, deck[42], rng=challenge.options_rng("abcdefgh", 42)
        )
        assert one == two and deck[42] in one and len(set(one)) == 4

    def test_unseeded_options_still_vary(self):
        deck = get_language_numbers("es")
        draws = {
            tuple(quiz_logic.generate_multiple_choice(deck, 42, deck[42]))
            for _ in range(20)
        }
        assert len(draws) > 1

    def test_magnitude_weight_matches_the_dial(self):
        assert quiz_logic.magnitude_weight(5, 1) == 1.0
        assert quiz_logic.magnitude_weight(500, 1) == pytest.approx(0.1)
        assert quiz_logic.magnitude_weight(5000, 5) == 1.0

    @pytest.mark.parametrize(
        ("kind", "difficulty"),
        [
            ("numbers", "easy"),
            ("numbers", "advanced"),
            ("numbers", "hardcore"),
            ("listening", None),
        ],
    )
    def test_two_players_get_the_same_round(self, client, friend, kind, difficulty):
        url = _create(client, kind=kind, difficulty=difficulty or "advanced")
        token = _token(url)
        client.post(f"/challenge/{token}/start")
        _, mine = _play(client)
        friend.post(f"/challenge/{token}/start")
        _, theirs = _play(friend)
        assert mine == theirs
        expected = _decode(url)
        deck_numbers = [n for n, _ in mine]
        with client.application.test_request_context():
            from app import _challenge_deck

            _, deck = _challenge_deck(expected)
        assert deck_numbers == challenge.draw_numbers(
            deck, expected.seed, expected.mode
        )


class TestCreate:
    def test_form_renders_every_ready_language(self, client):
        html = client.get("/challenge").get_data(as_text=True)
        assert 'name="lang" value="es"' in html
        assert 'name="lang" value="ne"' in html
        assert "noindex" in html

    def test_listening_flags_follow_the_recordings(self, client):
        html = client.get("/challenge").get_data(as_text=True)
        assert re.search(r'value="es"[^>]*data-listening="1"', html)
        assert re.search(r'value="ne"[^>]*data-listening="0"', html)

    def test_preselects_the_language_being_learned(self, client):
        client.get("/fr")
        html = client.get("/challenge").get_data(as_text=True)
        assert re.search(r'value="fr"[^>]*checked', html)

    def test_numbers_challenge(self, client):
        ch = _decode(_create(client, difficulty="hardcore"))
        assert (ch.lang, ch.mode, ch.host, ch.results) == ("es", "hardcore", "Alex", ())

    def test_listening_challenge(self, client):
        assert _decode(_create(client, kind="listening")).mode == "audio"

    def test_listening_without_recordings_falls_back_to_numbers(self, client):
        ch = _decode(_create(client, lang="ne", kind="listening"))
        assert ch.mode == challenge.DEFAULT_NUMBER_MODE

    def test_surprise_is_always_playable(self, client):
        modes = {_decode(_create(client, kind="surprise")).mode for _ in range(30)}
        assert modes <= {"advanced", "audio"} and modes
        assert {_decode(_create(client, lang="ne", kind="surprise")).mode} == {
            "advanced"
        }

    def test_garbage_difficulty_falls_back(self, client):
        ch = _decode(_create(client, difficulty="impossible"))
        assert ch.mode == challenge.DEFAULT_NUMBER_MODE

    def test_unknown_language_goes_back_to_the_form(self, client):
        response = client.post("/challenge", data={"lang": "xx"})
        assert response.status_code == 302
        assert response.location.endswith("/challenge")

    def test_creator_sees_the_ready_view(self, client):
        html = client.get(_create(client)).get_data(as_text=True)
        assert _h1(html) == "Your challenge is ready"
        assert "Play it first" in html
        assert 'id="challenge-share-url"' in html


class TestFlow:
    def test_play_first_then_friend_then_back(self, client, friend):
        url = _create(client, name="Alex")
        client.post(f"/challenge/{_token(url)}/start", data={"name": "Alex"})
        alex_url, _ = _play(client, lambda i: i < 7)

        alex = _decode(alex_url)
        assert [(r.name, r.score) for r in alex.results] == [("Alex", 7)]
        html = client.get(alex_url).get_data(as_text=True)
        assert _h1(html) == "You scored 7/10"
        assert "Send your result back" in html
        assert "challenge-you" in html

        # The friend arrives from Alex's link.
        html = friend.get(alex_url).get_data(as_text=True)
        assert _h1(html) == "Alex scored 7/10. Can you beat it?"
        assert "Accept the challenge" in html
        assert 'id="challenge-share-url"' not in html

        friend.post(f"/challenge/{_token(alex_url)}/start", data={"name": "Maria"})
        maria_url, _ = _play(friend, lambda i: i < 9)
        maria = _decode(maria_url)
        assert [(r.name, r.score) for r in maria.results] == [
            ("Alex", 7),
            ("Maria", 9),
        ]
        html = friend.get(maria_url).get_data(as_text=True)
        assert "first place" in html

        # Maria sends it back: Alex has played these numbers, so no replay.
        html = client.get(maria_url).get_data(as_text=True)
        assert _h1(html) == "You&#39;ve already played this one"
        assert "Rematch with new numbers" in html
        assert "Accept the challenge" not in html

    def test_shared_without_playing(self, client, friend):
        url = _create(client, name="Alex")
        html = friend.get(url).get_data(as_text=True)
        assert _h1(html) == "Alex challenges you!"
        anon = _create(client, name="")
        assert (
            _h1(friend.get(anon).get_data(as_text=True))
            == "You&#39;ve been challenged!"
        )

    def test_exit_ends_the_challenge_with_the_score_so_far(self, client):
        url = _create(client)
        client.post(f"/challenge/{_token(url)}/start")
        client.get("/es/quiz/advanced")
        with client.session_transaction() as sess:
            word = sess["correct_answer"]
        client.post("/es/quiz/advanced", data={"answer": word})
        response = client.get("/es/results")
        assert "/challenge/" in response.location
        [result] = _decode(response.location).results
        assert result.score == 1
        with client.session_transaction() as sess:
            assert "challenge" not in sess and "mode" not in sess

    def test_rematch_mints_a_new_challenge(self, client):
        url = _create(client, kind="listening")
        client.post(f"/challenge/{_token(url)}/start")
        result_url, _ = _play(client)
        old = _decode(result_url)
        response = client.post(
            "/challenge", data={"lang": "es", "kind": old.kind, "name": "Alex"}
        )
        new = _decode(response.location)
        assert (new.lang, new.mode) == (old.lang, old.mode)
        assert new.seed != old.seed and new.results == ()

    def test_listening_start_form_anchors_back_to_the_challenge(self, client, friend):
        url = _create(client, kind="listening")
        html = friend.get(url).get_data(as_text=True)
        assert "data-listen-pjax" in html
        assert f'data-listen-back="/challenge/{_token(url)}"' in html
        assert "quiz_listen.js" in html


class TestInvalid:
    def test_garbage_token_is_a_friendly_404(self, client):
        response = client.get("/challenge/not-a-token")
        assert response.status_code == 404
        html = response.get_data(as_text=True)
        assert "This challenge link doesn&#39;t work" in html
        assert 'href="/challenge"' in html

    def test_listening_challenge_for_a_language_without_audio_is_invalid(self, client):
        token = challenge.Challenge("ne", "audio", "abcdefgh").encode(SECRET)
        assert client.get(f"/challenge/{token}").status_code == 404

    def test_starting_an_invalid_challenge_goes_to_the_form(self, client):
        response = client.post("/challenge/not-a-token/start")
        assert response.location.endswith("/challenge")


class TestIsolation:
    def test_a_normal_drill_after_a_challenge_is_random_again(self, client):
        url = _create(client)
        client.post(f"/challenge/{_token(url)}/start")
        client.post("/es/start", data={"mode": "advanced"})
        with client.session_transaction() as sess:
            assert "challenge" not in sess
            assert "challenge_me" in sess
        client.get("/es/quiz/advanced")
        response = client.get("/es/results")
        assert response.status_code == 200

    def test_numeral_system_preference_survives(self, client):
        client.get("/cy/numbers?system=traditional")
        with client.session_transaction() as sess:
            assert sess["number_system"] == "traditional"
        url = _create(client, lang="cy")
        client.post(f"/challenge/{_token(url)}/start")
        with client.session_transaction() as sess:
            assert sess["number_system"] != "traditional"
        _play(client)
        with client.session_transaction() as sess:
            assert sess["number_system"] == "traditional"

    def test_magnitude_dial_is_not_overwritten(self, client):
        client.post("/es/start", data={"mode": "easy", "magnitude_level": "4"})
        url = _create(client)
        client.post(f"/challenge/{_token(url)}/start")
        with client.session_transaction() as sess:
            assert sess["magnitude_level"] == 4

    def test_drills_without_a_challenge_still_draw_at_random(self, client, monkeypatch):
        calls = []
        original = quiz_logic.get_random_question

        def spy(*args, **kwargs):
            calls.append(args)
            return original(*args, **kwargs)

        monkeypatch.setattr(quiz_logic, "get_random_question", spy)
        client.post("/es/start", data={"mode": "hardcore"})
        client.get("/es/quiz/hardcore")
        assert len(calls) == 1


class TestHeadersAndPrivacy:
    def test_challenge_pages_are_never_cached(self, client):
        url = _create(client)
        for path in ("/challenge", url, "/challenge/broken"):
            assert "no-store" in client.get(path).headers["Cache-Control"]

    def test_noindex_and_no_language_versions(self, client):
        html = client.get(_create(client)).get_data(as_text=True)
        assert '<meta name="robots" content="noindex, nofollow">' in html
        assert 'hreflang="' not in html.split("</head>")[0]

    def test_analytics_never_sees_the_token(self, client):
        url = _create(client)
        html = client.get(url).get_data(as_text=True)
        assert 'path: "/challenge/link"' in html

    def test_other_pages_keep_their_own_analytics_path(self, client):
        html = client.get("/").get_data(as_text=True)
        assert (
            "path:"
            not in html.split("data-goatcounter=")[0].split("window.goatcounter")[1]
        )

    @pytest.mark.skipif(shutil.which("node") is None, reason="needs node")
    def test_referrer_guard_strips_only_challenge_links(self, client):
        """count.js sends whatever the callback returns, so it must hand every
        other referrer back unchanged; returning null would erase them all."""
        html = client.get("/").get_data(as_text=True)
        script = re.search(
            r"<script>\s*(window\.goatcounter = \{.*?\};)\s*</script>", html, re.S
        ).group(1)
        program = (
            "var window = {};\n" + script + "\n"
            "var f = window.goatcounter.referrer;\n"
            "console.log(JSON.stringify(["
            "f('https://example.com/es/numbers'), f(''), "
            "f('https://example.com/challenge/eyJ2.abc'), "
            "f('https://example.com/challenge')]));"
        )
        result = subprocess.run(
            ["node", "-e", program], capture_output=True, text=True, check=True
        )
        assert json.loads(result.stdout) == [
            "https://example.com/es/numbers",
            "",
            "",
            "https://example.com/challenge",
        ]

    def test_preview_bots_see_the_invitation(self, client, friend):
        url = _create(client, name="Alex")
        html = friend.get(url).get_data(as_text=True)
        assert '<meta property="og:title" content="Alex challenges you!">' in html


class TestStats:
    def test_a_challenge_run_is_counted_as_one(self, client):
        url = _create(client)
        client.post(f"/challenge/{_token(url)}/start")
        _play(client)
        [run] = db.session.execute(db.select(QuizRun)).scalars().all()
        assert run.source == "chal" and run.finished_at is not None

    def test_report_names_the_source(self, client):
        import quiz_stats

        url = _create(client)
        client.post(f"/challenge/{_token(url)}/start")
        _play(client)
        stats = quiz_stats.summarize(1)
        assert ("challenge", 1, 1) in stats["by_source"]


class TestLandingButton:
    def test_button_is_in_the_top_bar_not_the_page(self, client):
        html = client.get("/").get_data(as_text=True)
        top_bar = html.split('class="top-controls"')[1].split('class="container"')[0]
        assert 'class="btn-challenge"' in top_bar
        assert 'href="/challenge"' in top_bar
        hero = html.split('class="hero"')[1]
        assert "btn-challenge" not in hero

    @pytest.mark.parametrize("path", ["/es", "/es/numbers", "/about"])
    def test_only_on_the_landing_page(self, client, path):
        assert "btn-challenge" not in client.get(path).get_data(as_text=True)


def test_seed_alphabet_has_no_lookalikes():
    assert not set("01lo") & set(challenge.SEED_ALPHABET)
    seed = challenge.new_seed()
    assert len(seed) == challenge.SEED_LENGTH and set(seed) <= set(
        challenge.SEED_ALPHABET
    )


def test_draw_is_reproducible_with_a_fresh_interpreter_seed():
    """The global random state must not leak into a challenge's draw."""
    deck = get_language_numbers("de")
    random.seed(1)
    first = challenge.draw_numbers(deck, "k7x2pq3m", "audio")
    random.seed(2)
    assert first == challenge.draw_numbers(deck, "k7x2pq3m", "audio")


class TestStartNow:
    """The create page's Start: mint the challenge and play it at once."""

    def _go(self, client, **fields):
        data = {"lang": "es", "kind": "numbers", "difficulty": "advanced", "go": "1"}
        data.update(fields)
        return client.post("/challenge", data=data)

    def test_start_and_share_come_before_the_settings(self, client):
        html = client.get("/challenge").get_data(as_text=True)
        start = re.search(r"<button[^>]*id=\"challenge-go\"[^>]*>", html).group(0)
        share = re.search(
            r"<button[^>]*id=\"challenge-share-first\"[^>]*>", html
        ).group(0)
        assert 'form="challenge-form"' in start and 'name="go"' in start
        assert 'form="challenge-form"' in share and 'name="share"' in share
        settings = html.index('class="challenge-langs"')
        assert html.index('id="challenge-go"') < settings
        assert html.index('id="challenge-share-first"') < settings

    def test_the_pair_closes_the_form_too(self, client):
        html = client.get("/challenge").get_data(as_text=True)
        assert html.count('name="go"') == 2 and html.count('name="share"') == 2
        form = html[html.index('id="challenge-form"') : html.index("</form>")]
        assert 'name="go"' in form and 'name="share"' in form

    def test_start_explains_itself_only_as_a_tooltip(self, client):
        html = client.get("/challenge").get_data(as_text=True)
        tip = 'title="You get the link to send when you finish."'
        starts = re.findall(r'<button[^>]*name="go"[^>]*>', html)
        assert len(starts) == 2 and all(tip in b for b in starts)
        assert html.count("You get the link to send when you finish.") == 2

    def test_summary_names_the_preselected_settings(self, client):
        client.get("/de")
        html = client.get("/challenge").get_data(as_text=True)
        summary = re.search(r'id="challenge-go-summary">(.*?)</p>', html, re.S).group(1)
        assert "German" in summary and "Numbers" in summary and "Advanced" in summary

    def test_numbers_start_straight_into_the_round(self, client):
        response = self._go(client, difficulty="hardcore")
        assert response.status_code == 302
        assert response.location.endswith("/es/quiz/hardcore")
        with client.session_transaction() as sess:
            seed = sess["challenge"]["seed"]
            assert seed in sess["challenge_me"]["created"]
        html = client.get(response.location).get_data(as_text=True)
        assert "Your challenge has started" in html

    def test_listening_starts_the_listening_round(self, client):
        response = self._go(client, kind="listening")
        assert response.location.endswith("/es/listen")
        assert client.get(response.location).status_code == 200

    def test_finishing_gives_the_creator_the_link(self, client):
        self._go(client, name="Alex")
        result_url, _ = _play(client)
        html = client.get(result_url).get_data(as_text=True)
        assert _h1(html) == "You scored 10/10"
        assert 'id="challenge-share-url"' in html
        [result] = _decode(result_url).results
        assert result.name == "Alex"

    def test_share_opens_the_page_with_the_link_first(self, client):
        response = client.post(
            "/challenge", data={"lang": "es", "kind": "numbers", "share": "1"}
        )
        assert response.status_code == 303 and "/challenge/" in response.location
        html = client.get(response.location).get_data(as_text=True)
        assert _h1(html) == "Your challenge is ready"
        assert "data-share-focus" in html
        assert html.index('id="challenge-share-url"') < html.index(
            'class="challenge-start"'
        )
        # Once: a reload is the ordinary ready page again.
        html = client.get(response.location).get_data(as_text=True)
        assert "data-share-focus" not in html
        assert html.index('class="challenge-start"') < html.index(
            'id="challenge-share-url"'
        )

    def test_share_does_not_touch_the_link(self, client):
        response = client.post(
            "/challenge", data={"lang": "es", "kind": "numbers", "share": "1"}
        )
        assert "?" not in response.location
        html = client.get(response.location).get_data(as_text=True)
        url = re.search(r'id="challenge-share-url"[^>]*value="([^"]+)"', html, re.S)
        assert url and "share" not in url.group(1)

    def test_without_go_it_still_shows_the_ready_page(self, client):
        response = client.post("/challenge", data={"lang": "es", "kind": "numbers"})
        assert response.status_code == 303 and "/challenge/" in response.location

    def test_a_friend_accepting_is_told_so(self, client, friend):
        url = _create(client)
        friend.post(f"/challenge/{_token(url)}/start")
        html = friend.get("/es/quiz/advanced").get_data(as_text=True)
        assert "Challenge accepted" in html

    def test_create_page_can_start_a_listening_round_by_pjax(self, client):
        html = client.get("/challenge").get_data(as_text=True)
        assert 'data-listen-back="/challenge"' in html
        assert "js/quiz_listen.js" in html

    def test_a_language_in_the_url_outranks_remembered_defaults(self, client):
        explicit = client.get("/challenge?lang=fr").get_data(as_text=True)
        assert 'data-lang-explicit="1"' in explicit
        plain = client.get("/challenge").get_data(as_text=True)
        assert "data-lang-explicit" not in plain


class TestBrowserStorageDisclosure:
    """Remembered defaults live in localStorage, which the privacy policy names."""

    # Every file that writes to the browser's local storage. A new one is a new
    # thing kept on the visitor's device: say so in privacy_local_settings_desc
    # (all locales), then add it here.
    DISCLOSED = {
        "templates/base.html",  # colour scheme
        "static/js/cards_practice_prefs.js",
        "static/js/conjugate_practice_prefs.js",
        "static/js/cards_sort.js",
        "static/js/poll.js",  # the poll is switched off
        "static/js/challenge.js",  # friend-challenge defaults
    }

    def test_every_storage_writer_is_disclosed(self):
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent
        writers = {
            str(path.relative_to(root))
            for pattern in ("static/js/*.js", "templates/*.html")
            for path in root.glob(pattern)
            if "localStorage.setItem" in path.read_text(encoding="utf-8")
        }
        assert writers == self.DISCLOSED

    def test_privacy_page_lists_browser_storage(self, client):
        html = client.get("/privacy").get_data(as_text=True)
        assert "Settings saved in your browser" in html
        assert "friend challenge" in html

    def test_challenge_defaults_never_reach_the_server_as_a_cookie(self, client):
        client.get("/challenge")
        response = client.post(
            "/challenge", data={"lang": "es", "kind": "numbers", "go": "1"}
        )
        cookies = response.headers.getlist("Set-Cookie")
        assert all(c.startswith("session=") for c in cookies)
        assert not any("Expires" in c or "Max-Age" in c for c in cookies)
