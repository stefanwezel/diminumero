"""Tests for friend challenges: one random round, shared by link, compared by score."""

import json
import random
from datetime import datetime, timedelta, timezone
import re
import shutil
import subprocess

import pytest
from itsdangerous import URLSafeSerializer

import app as app_module
import challenge
import quiz_logic
from app import app as flask_app
from config import CHALLENGE_SCORE_DAYS, QUESTIONS_PER_QUIZ
from languages import get_language_numbers
from models import ChallengeResult, QuizRun, db

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
    """Make a challenge; return its link, the one its creator sends.

    Making one lands on the creator's own page, at the link plus /share.
    """
    response = client.post(
        "/challenge",
        data={"lang": lang, "kind": kind, "difficulty": difficulty, "name": name},
    )
    assert response.status_code == 303
    assert response.location.endswith("/share")
    return response.location.removesuffix("/share")


def _sender_page(url):
    return f"{url}/share"


def _link(url):
    """The link a page offers to send: a sender's page or a result, minus its
    own last part. Only the link is ever opened by anyone else."""
    return re.sub(r"/(share|result)$", "", url)


def _scores(url):
    """The stored scoreboard of the challenge at `url`, in the order played."""
    seed = _decode(url).seed
    with flask_app.app_context():
        rows = ChallengeResult.query.filter_by(seed=seed).order_by(ChallengeResult.id)
        return [challenge.Result(r.name, r.score, r.seconds, r.id) for r in rows]


def _token(url):
    return url.rsplit("/challenge/", 1)[1].split("?")[0].split("/")[0]


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
    # The last answer goes to results, which ends the challenge on the
    # player's result page.
    assert response.status_code == 302 and response.location.endswith("/results")
    response = client.get(response.location)
    assert response.status_code == 302 and "/challenge/" in response.location
    assert response.location.endswith("/result")
    return response.location, asked


def _new_challenge_link(html):
    """The href of a page's New challenge button, or None."""
    actions = re.search(r'class="challenge-actions">(.*?)</div>', html, re.S)
    link = actions and re.search(r'<a href="([^"]+)"', actions.group(1))
    return link.group(1).replace("&amp;", "&") if link else None


def _checked(html, name):
    """The values of the checked radios or checkboxes called `name`."""
    return re.findall(
        r'<input type="(?:radio|checkbox)" name="%s" value="([^"]+)"[^>]*checked'
        % re.escape(name),
        html,
    )


def _invitation_body(html):
    """An invitation page's content, minus the name field's value, which is
    the one thing on it that depends on who is looking."""
    body = html[html.index('class="challenge-summary"') : html.index("<footer")]
    body = body.replace('<input type="hidden" name="name_offered" value="1">', "")
    return re.sub(r'(id="challenge-name"[^>]*value=)"[^"]*"', r"\1", body)


def _h1(html):
    return re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S).group(1).strip()


class TestToken:
    def test_round_trip(self):
        ch = challenge.Challenge("es", "audio", "abcdefgh", "Alex")
        again = challenge.Challenge.decode(ch.encode(SECRET), SECRET)
        assert again == ch

    def test_a_token_carries_no_scores(self):
        """Scores are stored, so a link never changes once it is sent."""
        token = challenge.Challenge("es", "easy", "abcdefgh", "Alex").encode(SECRET)
        data = URLSafeSerializer(SECRET, salt=challenge.TOKEN_SALT).loads(token)
        assert set(data) == {"v", "l", "m", "s", "h"}

    def test_scores_in_an_older_token_are_ignored(self):
        payload = {"v": 1, "l": "es", "m": "e", "s": "abcdefgh", "r": [["A", 7, 5]]}
        token = URLSafeSerializer(SECRET, salt=challenge.TOKEN_SALT).dumps(payload)
        assert challenge.Challenge.decode(token, SECRET) == challenge.Challenge(
            "es", "easy", "abcdefgh"
        )

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
            ["not", "a", "dict"],
        ],
    )
    def test_correctly_signed_but_malformed_is_rejected(self, payload):
        """The signature proves we made it, not that this version can read it."""
        token = URLSafeSerializer(SECRET, salt=challenge.TOKEN_SALT).dumps(payload)
        assert challenge.Challenge.decode(token, SECRET) is None

    def test_overlong_token_is_not_decoded(self):
        assert challenge.Challenge.decode("a" * 5000, SECRET) is None


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


def _login(client, **user):
    with client.session_transaction() as sess:
        sess["user"] = {"sub": "auth0|player", **user}


def _name_field(html):
    """The name field's value, and whether it's marked as a guess from the login."""
    tag = re.search(r'<input[^>]*id="challenge-name"[^>]*>', html).group(0)
    return re.search(r'value="([^"]*)"', tag).group(1), "data-name-suggested" in tag


class TestLoginName:
    """Someone logged in finds their first name in the name field by default."""

    @pytest.mark.parametrize(
        "user, first",
        [
            ({"given_name": "Stefan", "name": "Stefan Wezel"}, "Stefan"),
            ({"name": "Stefan Wezel"}, "Stefan"),
            # An email-and-password login has the address as its name.
            ({"name": "someone@example.com", "nickname": "someone"}, ""),
            ({}, ""),
        ],
    )
    def test_the_create_form_offers_the_first_name(self, client, user, first):
        _login(client, **user)
        html = client.get("/challenge").get_data(as_text=True)
        assert _name_field(html) == (first, bool(first))
        assert ('name="name_offered"' in html) == bool(first)

    def test_nobody_logged_in_gets_an_empty_field(self, client):
        html = client.get("/challenge").get_data(as_text=True)
        assert _name_field(html) == ("", False)
        assert 'name="name_offered"' not in html

    def test_starting_with_it_puts_it_on_the_scoreboard(self, client):
        _login(client, given_name="Stefan", name="Stefan Wezel")
        response = client.post(
            "/challenge",
            data={
                "lang": "es",
                "kind": "numbers",
                "difficulty": "advanced",
                "name": "Stefan",
                "name_offered": "1",
                "go": "1",
            },
        )
        assert response.status_code == 302
        result_url, _ = _play(client)
        assert [r.name for r in _scores(result_url)] == ["Stefan"]
        html = client.get(result_url).get_data(as_text=True)
        assert "<bdi>Stefan</bdi>" in html and "Anonymous" not in html

    def test_an_invited_player_is_offered_theirs(self, client, friend):
        url = _create(client, name="Alex")
        _login(friend, given_name="Maria")
        html = friend.get(url).get_data(as_text=True)
        assert _name_field(html)[0] == "Maria"
        assert 'name="name_offered"' in html

    def test_a_name_given_beats_the_login(self, client):
        _login(client, given_name="Stefan")
        _create(client, name="Tamandua")
        html = client.get("/challenge").get_data(as_text=True)
        assert _name_field(html) == ("Tamandua", False)

    def test_emptying_the_offered_name_is_remembered(self, client, friend):
        _login(client, given_name="Stefan")
        client.post(
            "/challenge",
            data={"lang": "es", "kind": "numbers", "name": "", "name_offered": "1"},
        )
        assert _name_field(client.get("/challenge").get_data(as_text=True)) == (
            "",
            False,
        )
        # Nor is it put back on someone else's challenge.
        url = _create(friend, name="Alex")
        assert _name_field(client.get(url).get_data(as_text=True))[0] == ""
        # Giving a name again ends it.
        _create(client, name="Stef")
        with client.session_transaction() as sess:
            assert "anonymous" not in sess["challenge_me"]

    def test_an_empty_field_that_showed_nothing_marks_nobody(self, client):
        """A form with no field, or one that was empty, decided nothing."""
        _login(client, given_name="Stefan")
        _create(client, name="")
        assert _name_field(client.get("/challenge").get_data(as_text=True)) == (
            "Stefan",
            True,
        )

    def test_the_logins_name_goes_with_the_login(self, client, friend):
        """Logging out leaves no login name in a field: the next person at
        this computer may not be the one who was logged in."""
        _login(client, given_name="Stefan", name="Stefan Wezel")
        html = client.get("/challenge").get_data(as_text=True)
        assert _name_field(html) == ("Stefan", True)
        assert 'data-login-name="Stefan"' in html
        url = _create(client, name="Stefan")
        client.post(f"/challenge/{_token(url)}/start", data={"name": "Stefan"})
        result_url, _ = _play(client)
        assert [r.name for r in _scores(result_url)] == ["Stefan"]

        client.get("/logout")
        html = client.get("/challenge").get_data(as_text=True)
        assert _name_field(html) == ("", False)
        assert "data-login-name" not in html
        other = _create(friend, name="Maria")
        assert _name_field(client.get(other).get_data(as_text=True))[0] == ""
        assert (
            _name_field(client.get(_link(result_url)).get_data(as_text=True))[0] == ""
        )

        # Back in, it's back.
        _login(client, given_name="Stefan", name="Stefan Wezel")
        assert _name_field(client.get("/challenge").get_data(as_text=True))[0] == (
            "Stefan"
        )

    def test_a_typed_name_stays_after_logging_out(self, client):
        _login(client, given_name="Stefan")
        _create(client, name="Tamandua")
        client.get("/logout")
        html = client.get("/challenge").get_data(as_text=True)
        assert _name_field(html) == ("Tamandua", False)

    def test_no_page_sends_a_name_it_does_not_show(self, client):
        """After a round, New challenge opens the form, whose field shows it."""
        _login(client, given_name="Stefan")
        url = _create(client, name="")
        client.post(f"/challenge/{_token(url)}/start", data={"name": ""})
        result_url, _ = _play(client)
        html = client.get(result_url).get_data(as_text=True)
        assert 'name="name"' not in html


class TestRanking:
    R = challenge.Result

    def test_best_score_first_then_faster_time(self):
        scores = [self.R("Slow", 8, 90, 1), self.R("Low", 5, 10, 2)]
        scores.append(self.R("Fast", 8, 30, 3))
        rows = challenge.ranked(scores, mine=3)
        assert [r["name"] for r in rows] == ["Fast", "Slow", "Low"]
        assert [r["rank"] for r in rows] == [1, 2, 3]
        assert rows[0]["mine"] and rows[0]["time"] == "0:30"
        assert not rows[1]["mine"]

    def test_exact_tie_shares_a_rank_in_the_order_played(self):
        rows = challenge.ranked([self.R("B", 8, 30, 2), self.R("A", 8, 30, 1)])
        assert [(r["name"], r["rank"]) for r in rows] == [("A", 1), ("B", 1)]

    def test_a_long_board_shows_the_best_and_your_own(self):
        scores = [self.R(f"P{i}", 10, 30, i) for i in range(1, 15)]
        mine = self.R("Me", 0, 30, 15)
        scores.append(mine)
        rows = challenge.ranked(scores, mine=mine.id)
        assert len(rows) == challenge.SCOREBOARD_ROWS + 1
        assert rows[-1]["mine"] and rows[-1]["name"] == mine.name
        assert len(challenge.ranked(scores)) == challenge.SCOREBOARD_ROWS


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
        url = _create(client, difficulty="hardcore")
        ch = _decode(url)
        assert (ch.lang, ch.mode, ch.host) == ("es", "hardcore", "Alex")
        assert _scores(url) == []

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

    @pytest.mark.parametrize(
        "lang, pick, mode",
        [
            ("es", "listening", "audio"),
            ("es", "numbers", "hardcore"),
            # The browser's pick can't conjure up recordings that don't exist.
            ("ne", "listening", "hardcore"),
        ],
    )
    def test_surprise_honours_the_browsers_pick(self, client, lang, pick, mode):
        """challenge.js decides Surprise on Start, to know whether to pjax."""
        response = client.post(
            "/challenge",
            data={
                "lang": lang,
                "kind": "surprise",
                "surprise_pick": pick,
                "difficulty": "hardcore",
            },
        )
        assert _decode(response.location).mode == mode

    def test_surprise_ignores_a_garbage_pick(self, client):
        response = client.post(
            "/challenge",
            data={"lang": "es", "kind": "surprise", "surprise_pick": "easy"},
        )
        assert _decode(response.location).mode in {"advanced", "audio"}

    def test_garbage_difficulty_falls_back(self, client):
        ch = _decode(_create(client, difficulty="impossible"))
        assert ch.mode == challenge.DEFAULT_NUMBER_MODE

    def test_unknown_language_goes_back_to_the_form(self, client):
        response = client.post("/challenge", data={"lang": "xx"})
        assert response.status_code == 302
        assert response.location.endswith("/challenge")

    def test_creator_lands_on_the_sender_page(self, client):
        url = _create(client)
        html = client.get(_sender_page(url)).get_data(as_text=True)
        assert _h1(html) == "Your challenge is ready"
        start = html[html.index('class="challenge-start"') :]
        assert re.search(
            r"<button[^>]*>\s*<span[^>]*>▶</span> Start\s*</button>", start
        )
        assert '<input type="hidden" name="sender" value="1">' in start
        assert "Play it first" not in html
        # The box holds the link, not this page's own address.
        shared = re.search(r'id="challenge-share-url"[^>]*value="([^"]+)"', html, re.S)
        assert shared.group(1) == f"http://localhost{url}"


class TestSenderAndRecipient:
    """The link is always the page of someone who was sent it; its maker has
    their own page, so the two never mix, even in the same browser."""

    def test_the_link_is_an_invitation_even_to_its_maker(self, client):
        url = _create(client, name="Alex")
        html = client.get(url).get_data(as_text=True)
        assert _h1(html) == "Alex challenges you!"
        assert "Accept the challenge" in html
        assert "Your challenge is ready" not in html
        assert 'id="challenge-share-url"' not in html
        assert 'name="sender"' not in html

    def test_the_sender_page_is_only_its_makers(self, client, friend):
        url = _create(client)
        response = friend.get(_sender_page(url))
        assert response.status_code == 302 and response.location == url

    def test_the_sender_page_goes_to_the_link_once_played(self, client):
        url = _create(client)
        client.post(f"/challenge/{_token(url)}/start", data={"sender": "1"})
        _play(client)
        response = client.get(_sender_page(url))
        assert response.status_code == 302 and response.location == url

    def test_a_bad_token_is_a_404_on_the_sender_page_too(self, client):
        assert client.get("/challenge/nonsense/share").status_code == 404

    def test_playing_from_the_sender_page_reads_as_sent(self, client):
        url = _create(client)
        response = client.post(f"/challenge/{_token(url)}/start", data={"sender": "1"})
        quiz = client.get(response.location).get_data(as_text=True)
        assert "Your challenge has started" in quiz
        result_url, _ = _play(client)
        html = client.get(result_url).get_data(as_text=True)
        assert "Share the challenge with a friend" in html
        assert "Now send it to a friend and see who wins." in html
        assert "with your score to beat" in html
        assert "Send your result back" not in html

    def test_playing_from_the_link_reads_as_received(self, client):
        """Its maker opening the link plays it as anyone they sent it to would."""
        url = _create(client)
        response = client.post(f"/challenge/{_token(url)}/start")
        quiz = client.get(response.location).get_data(as_text=True)
        assert "Challenge accepted" in quiz
        result_url, _ = _play(client)
        html = client.get(result_url).get_data(as_text=True)
        assert "Send your result back" in html
        assert "Now send it back and see who wins." in html
        assert "send it back, or on to someone new" in html
        assert "Share the challenge with a friend" not in html
        # The result page keeps reading that way on a reload.
        assert "Send your result back" in client.get(result_url).get_data(as_text=True)

    def test_a_sender_who_plays_after_a_friend_sends_their_result_back(
        self, client, friend
    ):
        """Shared first, played after a friend: the link has gone out already,
        so there is a result to send back, not a challenge to share."""
        url = _create(client, name="Tati")
        friend.post(f"/challenge/{_token(url)}/start", data={"name": "Maria"})
        _play(friend)
        client.post(
            f"/challenge/{_token(url)}/start", data={"name": "Tati", "sender": "1"}
        )
        result_url, _ = _play(client, lambda i: i < 5)
        html = client.get(result_url).get_data(as_text=True)
        assert _h1(html) == "You scored 5/10"
        assert "Send your result back" in html
        assert "send it back, or on to someone new" in html
        assert "Share the challenge with a friend" not in html
        assert "with your score to beat" not in html

    def test_only_its_maker_can_start_as_the_sender(self, client, friend):
        url = _create(client)
        friend.post(f"/challenge/{_token(url)}/start", data={"sender": "1"})
        result_url, _ = _play(friend)
        html = friend.get(result_url).get_data(as_text=True)
        assert "Send your result back" in html

    def test_the_create_forms_start_reads_as_sent(self, client):
        client.post(
            "/challenge",
            data={"lang": "es", "kind": "numbers", "difficulty": "advanced", "go": "1"},
        )
        result_url, _ = _play(client)
        html = client.get(result_url).get_data(as_text=True)
        assert "Share the challenge with a friend" in html

    def test_the_link_on_a_result_page_opens_the_invitation(self, client):
        """Opening the link your result page offers shows what a friend sees,
        in the browser that just played it too, but for its button: Rematch,
        since this browser has had the challenge."""
        client.post(
            "/challenge",
            data={"lang": "es", "kind": "numbers", "name": "Stefan", "go": "1"},
        )
        result_url, _ = _play(client, lambda i: False)
        html = client.get(result_url).get_data(as_text=True)
        assert _h1(html) == "You scored 0/10"
        shared = re.search(r'id="challenge-share-url"[^>]*value="([^"]+)"', html, re.S)
        link = _link(result_url)
        assert shared.group(1) == f"http://localhost{link}"

        html = client.get(link).get_data(as_text=True)
        assert _h1(html) == "Stefan scored 0/10. Can you beat it?"
        assert "Rematch" in html and "Accept the challenge" not in html
        assert 'class="challenge-start"' in html
        assert 'id="challenge-share-url"' not in html
        assert "You scored" not in html
        # Nothing but Start, as a friend sees it, whose Start is an Accept.
        assert 'class="challenge-actions"' not in html
        friend = client.application.test_client()
        assert _invitation_body(friend.get(link).get_data(as_text=True)) == (
            _invitation_body(html).replace("Rematch", "Accept the challenge")
        )

    def test_the_link_says_rematch_to_whoever_played_it(self, client, friend):
        """A friend's result sent back lands on the link: for someone who has
        played it, Accept would be the wrong word."""
        url = _create(client, name="Stefan")
        client.post(
            f"/challenge/{_token(url)}/start", data={"name": "Stefan", "sender": "1"}
        )
        _play(client, lambda i: i < 4)
        friend.post(f"/challenge/{_token(url)}/start", data={"name": "Tati"})
        _play(friend, lambda i: i < 6)

        newcomer = client.application.test_client()
        assert "Accept the challenge" in newcomer.get(url).get_data(as_text=True)
        for player in (client, friend):
            html = player.get(url).get_data(as_text=True)
            assert _h1(html) == "Tati scored 6/10. Can you beat it?"
            start = html[html.index('class="challenge-start"') :]
            assert re.search(r"<button[^>]*>\s*Rematch\s*</button>", start)
            assert "Accept the challenge" not in html
            assert 'name="sender"' not in start

        # It plays the same challenge again, from the link, so the result is
        # one sent back, and the board keeps one score each.
        client.post(f"/challenge/{_token(url)}/start", data={"name": "Stefan"})
        result_url, _ = _play(client, lambda i: i < 8)
        assert "Send your result back" in client.get(result_url).get_data(as_text=True)
        assert sorted((r.name, r.score) for r in _scores(url)) == [
            ("Stefan", 8),
            ("Tati", 6),
        ]

    def test_playing_the_link_again_keeps_one_score(self, client):
        url = _create(client, name="Alex")
        client.post(f"/challenge/{_token(url)}/start", data={"name": "Alex"})
        first, _ = _play(client, lambda i: i < 3)
        client.post(f"/challenge/{_token(first)}/start", data={"name": "Alex"})
        second, _ = _play(client, lambda i: i < 8)
        assert [(r.name, r.score) for r in _scores(second)] == [("Alex", 8)]

    def test_a_result_page_is_only_its_players(self, client, friend):
        url = _create(client)
        client.post(f"/challenge/{_token(url)}/start")
        result_url, _ = _play(client)
        response = friend.get(result_url)
        assert response.status_code == 302
        assert response.location == _link(result_url)

    def test_a_result_page_lasts_until_the_next_drill(self, client):
        url = _create(client)
        client.post(f"/challenge/{_token(url)}/start")
        result_url, _ = _play(client)
        assert client.get(result_url).status_code == 200
        client.post("/es/start", data={"mode": "advanced"})
        response = client.get(result_url)
        assert response.status_code == 302
        assert response.location == _link(result_url)

    def test_a_bad_token_is_a_404_on_the_result_page_too(self, client):
        assert client.get("/challenge/nonsense/result").status_code == 404

    @pytest.mark.parametrize("sender", [True, False])
    def test_exit_before_answering_goes_back_where_it_started(self, client, sender):
        url = _create(client)
        data = {"sender": "1"} if sender else {}
        client.post(f"/challenge/{_token(url)}/start", data=data)
        client.get("/es/quiz/advanced")
        response = client.get("/es/results")
        assert response.location == (_sender_page(url) if sender else url)

    def test_a_rematch_lands_on_the_sender_page(self, client):
        url = _create(client)
        client.post(f"/challenge/{_token(url)}/start")
        _play(client)
        response = client.post(
            "/challenge", data={"lang": "es", "kind": "numbers", "name": ""}
        )
        assert response.status_code == 303 and response.location.endswith("/share")


class TestFlow:
    def test_play_first_then_friend_then_back(self, client, friend):
        url = _create(client, name="Alex")
        # Start on Alex's own page, which sends `sender`.
        client.post(
            f"/challenge/{_token(url)}/start", data={"name": "Alex", "sender": "1"}
        )
        alex_url, _ = _play(client, lambda i: i < 7)

        assert [(r.name, r.score) for r in _scores(alex_url)] == [("Alex", 7)]
        html = client.get(alex_url).get_data(as_text=True)
        assert _h1(html) == "You scored 7/10"
        # Alex made it, so there is nobody to send it "back" to: the link is
        # the challenge, with Alex's score on it.
        assert "Share the challenge with a friend" in html
        assert "Send your result back" not in html
        assert "plays the same 10 questions, with your score to beat" in html
        assert "challenge-you" in html

        # The friend arrives from the link on Alex's result page.
        shared = re.search(r'id="challenge-share-url"[^>]*value="([^"]+)"', html, re.S)
        assert shared.group(1) == f"http://localhost{_link(alex_url)}"
        html = friend.get(_link(alex_url)).get_data(as_text=True)
        assert _h1(html) == "Alex scored 7/10. Can you beat it?"
        assert "Accept the challenge" in html
        assert 'id="challenge-share-url"' not in html

        friend.post(f"/challenge/{_token(alex_url)}/start", data={"name": "Maria"})
        maria_url, _ = _play(friend, lambda i: i < 9)
        assert [(r.name, r.score) for r in _scores(maria_url)] == [
            ("Alex", 7),
            ("Maria", 9),
        ]
        html = friend.get(maria_url).get_data(as_text=True)
        assert "first place" in html
        # Maria was sent it, so hers goes back, or on to someone new.
        assert "Send your result back" in html
        assert "send it back, or on to someone new" in html
        assert "with your score to beat" not in html

        # Maria sends it back: the same link Alex sent, since scores don't
        # change it. Alex's own result page now has Maria on its board.
        assert _link(maria_url) == _link(alex_url)
        html = client.get(alex_url).get_data(as_text=True)
        assert _h1(html) == "You scored 7/10"
        assert "<bdi>Maria</bdi>" in html
        # The link itself is the invitation, like anyone's: Start, nothing
        # else, which says Rematch to Alex, who has played it.
        html = client.get(_link(maria_url)).get_data(as_text=True)
        assert _h1(html) == "Maria scored 9/10. Can you beat it?"
        assert "Rematch" in html and "Accept the challenge" not in html
        assert _new_challenge_link(html) is None
        assert 'id="challenge-share-url"' not in html

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
        [result] = _scores(response.location)
        assert result.score == 1
        with client.session_transaction() as sess:
            assert "challenge" not in sess and "mode" not in sess

    @pytest.mark.parametrize(
        "kind, path", [("numbers", "/es/quiz/advanced"), ("listening", "/es/listen")]
    )
    def test_exit_before_answering_scores_nothing(self, client, friend, kind, path):
        """A 0/10 nobody played would take a scoreboard place and the Start."""
        url = _create(client, kind=kind)
        friend.post(f"/challenge/{_token(url)}/start", data={"name": "Maria"})
        friend.get(path)
        response = friend.get("/es/results")
        assert response.location.endswith(f"/challenge/{_token(url)}")
        with friend.session_transaction() as sess:
            assert "challenge" not in sess and "mode" not in sess
            played = (sess.get("challenge_me") or {}).get("played", [])
            assert _decode(url).seed not in played
        assert _scores(url) == []
        html = friend.get(url).get_data(as_text=True)
        assert "Accept the challenge" in html
        # The round can still be played, and then counts as usual.
        friend.post(f"/challenge/{_token(url)}/start", data={"name": "Maria"})
        _play(friend)
        [result] = _scores(url)
        assert result.name == "Maria"

    def test_a_link_sent_before_its_maker_played_shows_their_score(
        self, client, friend
    ):
        """The link copied from the sender's page is the one friends have; a
        score played after it was sent must reach them all the same."""
        response = client.post(
            "/challenge",
            data={"lang": "es", "kind": "numbers", "name": "Alex", "share": "1"},
        )
        sender_page = client.get(response.location).get_data(as_text=True)
        sent = re.search(
            r'id="challenge-share-url"[^>]*value="http://localhost([^"]+)"',
            sender_page,
            re.S,
        ).group(1)
        # Sent; then Alex plays, from their own page.
        client.post(
            f"/challenge/{_token(sent)}/start", data={"name": "Alex", "sender": "1"}
        )
        alex_result, _ = _play(client, lambda i: i < 6)
        assert _link(alex_result) == sent

        html = friend.get(sent).get_data(as_text=True)
        assert _h1(html) == "Alex scored 6/10. Can you beat it?"
        friend.post(f"/challenge/{_token(sent)}/start", data={"name": "Maria"})
        maria_result, _ = _play(friend, lambda i: i < 8)
        html = friend.get(maria_result).get_data(as_text=True)
        assert "<bdi>Alex</bdi>" in html and "<bdi>Maria</bdi>" in html
        # And Alex, back on the same link, sees Maria's.
        html = client.get(sent).get_data(as_text=True)
        assert _h1(html) == "Maria scored 8/10. Can you beat it?"

    def test_every_score_is_kept_not_just_the_first_five(self, client, app):
        url = _create(client, name="Alex")
        for i in range(7):
            player = app.test_client()
            player.post(f"/challenge/{_token(url)}/start", data={"name": f"P{i}"})
            _play(player, lambda q, i=i: q < i)
        assert [r.name for r in _scores(url)] == [f"P{i}" for i in range(7)]
        html = client.get(url).get_data(as_text=True)
        assert html.count("<bdi>P") == 7

    @pytest.mark.parametrize(
        "kind, difficulty, path, empty",
        [
            ("numbers", "easy", "/es/quiz/easy", {}),
            ("numbers", "advanced", "/es/quiz/advanced", {"answer": ""}),
            ("numbers", "hardcore", "/es/quiz/hardcore", {"answer": ""}),
            ("listening", "advanced", "/es/listen", {"answer": ""}),
            ("listening", "advanced", "/es/listen", {"next": "1"}),
        ],
    )
    def test_a_question_cleared_without_an_answer_comes_back(
        self, client, kind, difficulty, path, empty
    ):
        """Skipping must not walk past the planned numbers to the random draw."""
        url = _create(client, kind=kind, difficulty=difficulty)
        client.post(f"/challenge/{_token(url)}/start")
        planned = challenge.draw_numbers(
            *self._deck_and_seed(client, url), _decode(url).mode
        )
        for _ in range(QUESTIONS_PER_QUIZ + 2):
            client.get(path)
            with client.session_transaction() as sess:
                assert sess["current_number"] == planned[0]
            client.post(path, data=empty)
        with client.session_transaction() as sess:
            assert sess["total_questions"] == 0

    @staticmethod
    def _deck_and_seed(client, url):
        from app import _challenge_deck

        ch = _decode(url)
        with client.application.test_request_context():
            _, deck = _challenge_deck(ch)
        return deck, ch.seed

    def test_the_session_holds_no_list_of_numbers(self, client):
        url = _create(client, kind="listening")
        client.post(f"/challenge/{_token(url)}/start")
        with client.session_transaction() as sess:
            assert set(sess["challenge"]) == {"token", "seed", "sender", "name"}

    def test_a_missing_planned_number_gets_a_stand_in_not_a_later_one(
        self, client, monkeypatch
    ):
        import app as app_module

        url = _create(client, difficulty="hardcore")
        client.post(f"/challenge/{_token(url)}/start")
        planned = challenge.draw_numbers(*self._deck_and_seed(client, url), "hardcore")
        real = app_module._session_numbers

        def without_first(lang_code):
            deck = dict(real(lang_code))
            del deck[planned[0]]
            return deck

        levels = []
        original = quiz_logic.get_random_question

        def spy(*args, **kwargs):
            levels.append(kwargs.get("magnitude_level"))
            return original(*args, **kwargs)

        monkeypatch.setattr(app_module, "_session_numbers", without_first)
        monkeypatch.setattr(quiz_logic, "get_random_question", spy)
        for _ in range(20):
            client.get("/es/quiz/hardcore")
            with client.session_transaction() as sess:
                stand_in = sess.pop("current_number")
                sess.pop("correct_answer")
                sess["asked_numbers"] = []
            assert stand_in not in planned
        assert set(levels) == {challenge.CHALLENGE_MAGNITUDE["hardcore"]}

    def test_restart_remembers_what_was_played(self, client):
        """Its maker's page stays closed once they've played, past /restart."""
        url = _create(client)
        client.post(f"/challenge/{_token(url)}/start")
        _play(client)
        client.post("/restart")
        assert client.get(_sender_page(url)).location == url

    @pytest.mark.parametrize(
        "kind, difficulty, query",
        [
            ("numbers", "hardcore", "lang=es&kind=numbers&difficulty=hardcore"),
            # Listening has no difficulty to ask for.
            ("listening", "advanced", "lang=es&kind=listening"),
        ],
    )
    def test_new_challenge_opens_the_form_set_to_the_same_round(
        self, client, kind, difficulty, query
    ):
        """One button after a round, where there were two (Rematch, New): the
        form, ready to Start or Share the same kind of round, or to change it."""
        url = _create(client, kind=kind, difficulty=difficulty)
        client.post(f"/challenge/{_token(url)}/start")
        result_url, _ = _play(client)
        html = client.get(result_url).get_data(as_text=True)
        assert (
            re.findall(r'class="challenge-actions">(.*?)</div>', html, re.S)[0].count(
                "<a "
            )
            == 1
        )
        assert "Rematch" not in html
        link = _new_challenge_link(html)
        assert link == f"/challenge?{query}"

        form = client.get(link).get_data(as_text=True)
        assert _checked(form, "lang") == ["es"]
        assert _checked(form, "kind") == [kind]
        assert 'data-kind-explicit="1"' in form
        if kind == "numbers":
            assert _checked(form, "difficulty") == [difficulty]
            assert 'data-difficulty-explicit="1"' in form
        old = _decode(result_url)
        response = client.post(
            "/challenge", data={"lang": "es", "kind": kind, "difficulty": difficulty}
        )
        new = _decode(response.location)
        assert (new.lang, new.mode) == (old.lang, old.mode)
        assert new.seed != old.seed and _scores(response.location) == []

    def test_a_first_invitation_has_nothing_but_start(self, client, friend):
        url = _create(client, name="Alex")
        html = friend.get(url).get_data(as_text=True)
        assert 'class="challenge-start"' in html
        assert 'class="challenge-actions"' not in html
        assert "Create your own challenge" not in html
        assert _new_challenge_link(html) is None

    def test_no_rules_line(self, client, friend):
        url = _create(client)
        for html in (
            client.get("/challenge").get_data(as_text=True),
            client.get(_sender_page(url)).get_data(as_text=True),
            friend.get(url).get_data(as_text=True),
        ):
            assert "challenge-rules" not in html
            assert "breaks a tie" not in html

    def test_the_name_field_offers_no_browser_suggestions(self, client, friend):
        """A browser's form history would offer every name typed on this
        machine, other people's included, and anything else it has kept."""
        url = _create(client)
        for html in (
            client.get("/challenge").get_data(as_text=True),
            client.get(_sender_page(url)).get_data(as_text=True),
            friend.get(url).get_data(as_text=True),
        ):
            field = re.search(r'<input[^>]*id="challenge-name"[^>]*>', html, re.S)
            assert 'autocomplete="off"' in field.group(0)

    @pytest.mark.parametrize(
        "query, level, explicit",
        [
            ("kind=numbers&difficulty=easy", "easy", True),
            ("kind=numbers&difficulty=impossible", "advanced", False),
            ("", "advanced", False),
        ],
    )
    def test_the_form_takes_a_difficulty_from_the_url(
        self, client, query, level, explicit
    ):
        html = client.get(f"/challenge?{query}").get_data(as_text=True)
        assert _checked(html, "difficulty") == [level]
        assert ('data-difficulty-explicit="1"' in html) == explicit

    def test_listening_start_form_anchors_back_to_the_challenge(self, client, friend):
        url = _create(client, kind="listening")
        html = friend.get(url).get_data(as_text=True)
        assert "data-listen-pjax" in html
        assert f'data-listen-back="/challenge/{_token(url)}"' in html
        assert "quiz_listen.js" in html


def _store_score(seed, name, days_ago):
    """A stored score, played `days_ago` days ago."""
    with flask_app.app_context():
        played = datetime.now(timezone.utc) - timedelta(days=days_ago)
        db.session.add(
            ChallengeResult(
                seed=seed, name=name, score=5, seconds=60, created_at=played
            )
        )
        db.session.commit()


def _stored_names():
    with flask_app.app_context():
        return sorted(r.name for r in ChallengeResult.query.all())


class TestRetention:
    """Challenge scores are ephemeral: gone CHALLENGE_SCORE_DAYS after play,
    whether or not anyone plays anything in the meantime."""

    @pytest.fixture(autouse=True)
    def _purge_on_every_request_unless_told(self):
        saved = app_module._last_challenge_purge
        yield
        app_module._last_challenge_purge = saved
        flask_app.config.pop("CHALLENGE_PURGE_INTERVAL", None)

    def test_scores_past_the_period_are_not_shown(self, client, friend):
        url = _create(client, name="Alex")
        seed = _decode(url).seed
        _store_score(seed, "Ancient", CHALLENGE_SCORE_DAYS + 1)
        _store_score(seed, "Recent", CHALLENGE_SCORE_DAYS - 1)
        # However recently the store was last purged.
        app_module._last_challenge_purge = float("inf")
        html = friend.get(url).get_data(as_text=True)
        assert "<bdi>Recent</bdi>" in html and "Ancient" not in html
        assert _h1(html) == "Recent scored 5/10. Can you beat it?"

    def test_purge_deletes_exactly_the_expired(self):
        _store_score("aaaaaaaa", "Old", CHALLENGE_SCORE_DAYS + 1)
        _store_score("aaaaaaaa", "New", CHALLENGE_SCORE_DAYS - 1)
        with flask_app.app_context():
            assert app_module.purge_expired_challenge_scores() == 1
        assert _stored_names() == ["New"]

    def test_requests_purge_without_anyone_playing(self, client):
        """Any page will do, at most once an interval per process."""
        app_module._last_challenge_purge = None
        _store_score("aaaaaaaa", "First", CHALLENGE_SCORE_DAYS + 1)
        client.get("/")
        assert _stored_names() == []
        _store_score("aaaaaaaa", "Second", CHALLENGE_SCORE_DAYS + 1)
        client.get("/")
        assert _stored_names() == ["Second"]
        flask_app.config["CHALLENGE_PURGE_INTERVAL"] = 0
        client.get("/")
        assert _stored_names() == []

    def test_a_new_score_purges_the_expired(self, client):
        app_module._last_challenge_purge = float("inf")
        _store_score("aaaaaaaa", "Old", CHALLENGE_SCORE_DAYS + 1)
        url = _create(client)
        client.post(f"/challenge/{_token(url)}/start", data={"name": "New"})
        _play(client)
        assert _stored_names() == ["New"]

    def test_the_purge_command(self):
        _store_score("aaaaaaaa", "Old", CHALLENGE_SCORE_DAYS + 1)
        result = flask_app.test_cli_runner().invoke(args=["challenge-purge"])
        assert result.exit_code == 0 and "Deleted 1" in result.output
        assert _stored_names() == []

    def test_static_files_never_wait_on_the_purge(self, client):
        app_module._last_challenge_purge = None
        _store_score("aaaaaaaa", "Old", CHALLENGE_SCORE_DAYS + 1)
        assert client.get("/static/css/challenge.css").status_code == 200
        assert _stored_names() == ["Old"]
        client.get("/")
        assert _stored_names() == []

    def test_a_failing_purge_never_costs_a_page(self, client, monkeypatch):
        app_module._last_challenge_purge = None

        def broken():
            raise RuntimeError("database away")

        monkeypatch.setattr(app_module, "purge_expired_challenge_scores", broken)
        assert client.get("/").status_code == 200

    def test_a_result_whose_score_has_gone_shows_the_link(self, client):
        url = _create(client)
        client.post(f"/challenge/{_token(url)}/start")
        result_url, _ = _play(client)
        with flask_app.app_context():
            row = ChallengeResult.query.one()
            row.created_at = datetime.now(timezone.utc) - timedelta(
                days=CHALLENGE_SCORE_DAYS + 1
            )
            db.session.commit()
        response = client.get(result_url)
        assert response.status_code == 302 and response.location == url

    def test_the_privacy_policy_says_so(self, client):
        html = client.get("/privacy").get_data(as_text=True)
        assert "Friend Challenges" in html
        assert f"deleted automatically after {CHALLENGE_SCORE_DAYS} days" in html
        # The one other thing stored with a score, and why.
        assert "a random code, different for every challenge" in html


def _fill_board(seed, count, score=5, seconds=60):
    """`count` stored scores from other players, all alike."""
    with flask_app.app_context():
        for i in range(count):
            db.session.add(
                ChallengeResult(seed=seed, name=f"P{i}", score=score, seconds=seconds)
            )
        db.session.commit()


def _board_size(url):
    return len(_scores(url))


class TestOnePlayerOneScore:
    """A board holds one score per player, and a bounded number of players,
    so neither a double tap nor a link passed round a class can grow it."""

    def test_a_better_round_replaces_the_score_a_worse_one_keeps_it(self, client):
        url = _create(client, name="Alex")
        client.post(f"/challenge/{_token(url)}/start", data={"name": "Alex"})
        _play(client, lambda i: i < 8)
        client.post(f"/challenge/{_token(url)}/start", data={"name": "Alex"})
        worse, _ = _play(client, lambda i: i < 3)
        assert [(r.name, r.score) for r in _scores(url)] == [("Alex", 8)]

        html = client.get(worse).get_data(as_text=True)
        # The heading is the round just played; the board keeps the best.
        assert _h1(html) == "You scored 3/10"
        assert re.search(r"Your best, 8/10 in 0:\d\d, stays on the scoreboard\.", html)
        assert "Now send it back and see who wins." in html
        assert re.search(r'class="is-you">.*?<td>8/10</td>', html, re.S)
        # What they send is what a friend will find on the board.
        assert "I scored 8/10" in html

        client.post(f"/challenge/{_token(url)}/start", data={"name": "Alex"})
        better, _ = _play(client)
        assert [(r.name, r.score) for r in _scores(url)] == [("Alex", 10)]
        html = client.get(better).get_data(as_text=True)
        assert _h1(html) == "You scored 10/10" and "Your best" not in html

    def test_a_round_is_scored_under_the_name_it_was_started_with(self, client):
        """Making another challenge mid-round (another tab) gives a new name to
        remember, not to the round: it is Bob's, and replaces Bob's score."""
        url = _create(client, name="Alex")
        client.post(f"/challenge/{_token(url)}/start", data={"name": "Bob"})
        _play(client, lambda i: i < 3)
        client.post(f"/challenge/{_token(url)}/start", data={"name": "Bob"})
        assert client.get("/es/quiz/advanced").status_code == 200
        mid_round = client.post(
            "/challenge",
            data={"lang": "es", "kind": "numbers", "name": "Robert", "share": "1"},
        )
        assert mid_round.location.endswith("/share")
        _play(client)
        assert [(r.name, r.score) for r in _scores(url)] == [("Bob", 10)]
        with client.session_transaction() as sess:
            assert sess["challenge_me"]["name"] == "Robert"

    def test_a_round_from_before_the_name_was_kept_with_it_still_counts(self, client):
        url = _create(client, name="Alex")
        client.post(f"/challenge/{_token(url)}/start", data={"name": "Bob"})
        with client.session_transaction() as sess:
            sess["challenge"] = {
                k: v for k, v in sess["challenge"].items() if k != "name"
            }
        _play(client)
        assert [(r.name, r.score) for r in _scores(url)] == [("Bob", 10)]

    def test_same_score_counts_as_better_only_when_faster(self, app):
        with app.app_context():
            record = app_module._record_challenge_score
            first = record("aaaaaaaa", "k", "Alex", 7, 60)
            assert record("aaaaaaaa", "k", "Alex", 7, 90) == first
            assert ChallengeResult.query.one().seconds == 60
            assert record("aaaaaaaa", "k", "Alex", 7, 45) == first
            assert ChallengeResult.query.one().seconds == 45
            assert record("aaaaaaaa", "k", "Alex", 6, 10) == first
            row = ChallengeResult.query.one()
            assert (row.score, row.seconds) == (7, 45)

    def test_a_replaced_score_is_kept_from_when_it_was_played(self, app):
        with app.app_context():
            record = app_module._record_challenge_score
            record("aaaaaaaa", "k", "Alex", 3, 60)
            row = ChallengeResult.query.one()
            row.created_at = datetime.now(timezone.utc) - timedelta(days=20)
            db.session.commit()
            record("aaaaaaaa", "k", "Alex", 9, 60)
            age = datetime.now(timezone.utc).replace(
                tzinfo=None
            ) - ChallengeResult.query.one().created_at.replace(tzinfo=None)
            assert age < timedelta(minutes=1)

    def test_people_taking_turns_on_one_phone_keep_a_score_each(self, client):
        url = _create(client, name="Alex")
        for name, right in (("Alex", 4), ("Sam", 7), ("alex", 6)):
            client.post(f"/challenge/{_token(url)}/start", data={"name": name})
            _play(client, lambda i, right=right: i < right)
        # "alex" is Alex again: the name is matched without case.
        assert sorted((r.name, r.score) for r in _scores(url)) == [
            ("Sam", 7),
            ("alex", 6),
        ]

    def test_the_same_name_in_another_browser_is_another_player(self, client, friend):
        url = _create(client, name="Alex")
        for player in (client, friend):
            player.post(f"/challenge/{_token(url)}/start", data={"name": "Alex"})
            _play(player, lambda i: i < 5)
        assert [r.name for r in _scores(url)] == ["Alex", "Alex"]

    def test_a_last_answer_sent_twice_is_one_score(self, client):
        """A double tap sends the end of the round twice, each request still
        seeing it running."""
        url = _create(client)
        client.post(f"/challenge/{_token(url)}/start", data={"name": "Alex"})
        for i in range(QUESTIONS_PER_QUIZ):
            client.get("/es/quiz/advanced")
            with client.session_transaction() as sess:
                word = sess["correct_answer"]
            client.post("/es/quiz/advanced", data={"answer": word})
        with client.session_transaction() as sess:
            before = dict(sess)
        first = client.get("/es/results")
        with client.session_transaction() as sess:
            sess.clear()
            sess.update(before)
        second = client.get("/es/results")
        assert first.location == second.location
        assert [r.score for r in _scores(url)] == [10]

    def test_two_requests_racing_for_the_row_end_on_one(self, app, monkeypatch):
        """Both looked, neither found it, both insert: the unique key turns
        the second insert into the first's row."""
        from sqlalchemy.orm import Query

        with app.app_context():
            existing = app_module._record_challenge_score(
                "aaaaaaaa", "k", "Alex", 7, 60
            )
            real_first = Query.first
            misses = []

            def first_misses_once(query):
                if not misses:
                    misses.append(query)
                    return None
                return real_first(query)

            monkeypatch.setattr(Query, "first", first_misses_once)
            assert (
                app_module._record_challenge_score("aaaaaaaa", "k", "Alex", 7, 60)
                == existing
            )
            assert misses and ChallengeResult.query.count() == 1

    def test_a_full_board_drops_its_lowest_for_a_new_player(self, client):
        url = _create(client)
        seed = _decode(url).seed
        _fill_board(seed, app_module.CHALLENGE_MAX_SCORES - 1, score=6)
        _fill_board(seed, 1, score=2)
        client.post(f"/challenge/{_token(url)}/start", data={"name": "New"})
        result_url, _ = _play(client, lambda i: i < 4)
        scores = _scores(url)
        assert len(scores) == app_module.CHALLENGE_MAX_SCORES
        assert sorted(r.score for r in scores)[:2] == [4, 6]
        # Even the lowest stays, while its player looks at their rank.
        friend = client.application.test_client()
        friend.post(f"/challenge/{_token(url)}/start", data={"name": "Last"})
        last_url, _ = _play(friend, lambda i: False)
        assert _board_size(url) == app_module.CHALLENGE_MAX_SCORES
        html = friend.get(last_url).get_data(as_text=True)
        assert f"You&#39;re number 50 of {app_module.CHALLENGE_MAX_SCORES}." in html
        assert "New" not in [r.name for r in _scores(url)]

    def test_the_board_ranks_a_player_far_down(self, client):
        url = _create(client)
        _fill_board(_decode(url).seed, 12, score=5, seconds=60)
        client.post(f"/challenge/{_token(url)}/start", data={"name": "Me"})
        result_url, _ = _play(client, lambda i: False)
        html = client.get(result_url).get_data(as_text=True)
        assert "You&#39;re number 13 of 13." in html
        # The best ten, then the viewer's own row.
        assert html.count("<tr") == 1 + challenge.SCOREBOARD_ROWS + 1
        assert re.search(r'class="is-you">\s*<td>13</td>', html)

    def test_ties_on_the_board_share_a_rank(self, client):
        url = _create(client)
        _fill_board(_decode(url).seed, 3, score=0, seconds=challenge.MAX_SECONDS)
        _fill_board(_decode(url).seed, 11, score=9, seconds=60)
        html = client.get(url).get_data(as_text=True)
        ranks = re.findall(r"<tr>\s*<td>(\d+)</td>", html)
        assert ranks == ["1"] * challenge.SCOREBOARD_ROWS


class TestScoreNotSaved:
    def test_a_failed_save_still_shows_the_score(self, client, monkeypatch):
        def broken(*args, **kwargs):
            raise RuntimeError("database away")

        monkeypatch.setattr(app_module, "_record_challenge_score", broken)
        url = _create(client)
        client.post(f"/challenge/{_token(url)}/start", data={"name": "Alex"})
        result_url, _ = _play(client, lambda i: i < 7)
        response = client.get(result_url)
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert _h1(html) == "You scored 7/10"
        assert "Your score couldn&#39;t be saved" in html
        assert 'class="is-you"' not in html
        assert "I scored 7/10" in html
        # The round is over all the same: Back can't play on into it.
        with client.session_transaction() as sess:
            assert "challenge" not in sess and "current_number" not in sess


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
        # The round is in the default system; the preference is left alone.
        decimal = get_language_numbers("cy")
        client.get("/cy/quiz/advanced")
        with client.session_transaction() as sess:
            assert sess["number_system"] == "traditional"
            assert sess["correct_answer"] == decimal[sess["current_number"]]
        _play(client)
        with client.session_transaction() as sess:
            assert sess["number_system"] == "traditional"

    def test_numeral_system_survives_an_abandoned_challenge(self, client):
        client.get("/cy/numbers?system=traditional")
        url = _create(client, lang="cy")
        client.post(f"/challenge/{_token(url)}/start")
        client.get("/cy/quiz/advanced")
        # Left mid-round for an ordinary drill.
        client.post("/cy/start", data={"mode": "advanced"})
        with client.session_transaction() as sess:
            assert "challenge" not in sess
            assert sess["number_system"] == "traditional"

    def test_numeral_system_survives_overlapping_challenges(self, client):
        client.get("/cy/numbers?system=traditional")
        first = _create(client, lang="cy")
        second = _create(client, lang="cy")
        client.post(f"/challenge/{_token(first)}/start")
        client.post(f"/challenge/{_token(second)}/start")
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

    @pytest.mark.parametrize("played", [False, True])
    def test_analytics_never_sees_the_title(self, client, friend, played):
        """count.js sends document.title, and this one names the players."""
        url = _create(client, name="Alex")
        if played:
            client.post(f"/challenge/{_token(url)}/start", data={"name": "Alex"})
            url = _link(_play(client)[0])
        html = friend.get(url).get_data(as_text=True)
        assert "Alex" in html.split("<title>")[1].split("</title>")[0]
        settings = html.split("window.goatcounter")[1].split("</script>")[0]
        assert 'title: "Challenge"' in settings
        assert "Alex" not in settings

    def test_a_broken_link_reports_the_same_title(self, client):
        html = client.get("/challenge/not-a-token").get_data(as_text=True)
        settings = html.split("window.goatcounter")[1].split("</script>")[0]
        assert 'path: "/challenge/link"' in settings
        assert 'title: "Challenge"' in settings

    def test_other_pages_keep_their_own_analytics_path(self, client):
        html = client.get("/").get_data(as_text=True)
        settings = html.split("data-goatcounter=")[0].split("window.goatcounter")[1]
        assert "path:" not in settings and "title:" not in settings

    @pytest.mark.skipif(shutil.which("node") is None, reason="needs node")
    def test_referrer_guard_strips_only_challenge_links(self, client):
        """count.js sends whatever the callback returns, so it must hand every
        other referrer back unchanged; returning null would erase them all.
        Another site's /challenge/ page is someone else's, and stays."""
        html = client.get("/").get_data(as_text=True)
        script = re.search(
            r"<script>\s*(window\.goatcounter = \{.*?\};)\s*</script>", html, re.S
        ).group(1)
        program = (
            "var window = {};\n"
            "var location = {origin: 'https://example.com'};\n" + script + "\n"
            "var f = window.goatcounter.referrer;\n"
            "console.log(JSON.stringify(["
            "f('https://example.com/es/numbers'), f(''), "
            "f('https://example.com/challenge/eyJ2.abc'), "
            "f('https://example.com/challenge'), "
            "f('https://forum.example/challenge/weekly-thread'), "
            "f('newsletter')]));"
        )
        result = subprocess.run(
            ["node", "-e", program], capture_output=True, text=True, check=True
        )
        assert json.loads(result.stdout) == [
            "https://example.com/es/numbers",
            "",
            "",
            "https://example.com/challenge",
            "https://forum.example/challenge/weekly-thread",
            "newsletter",
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

    @pytest.mark.parametrize("lang", ["es", "de", "cy"])
    def test_on_each_language_menu_for_that_language(self, client, lang):
        html = client.get(f"/{lang}").get_data(as_text=True)
        top_bar = html.split('class="top-controls"')[1].split('class="container"')[0]
        assert 'class="btn-challenge"' in top_bar
        assert f'href="/challenge?lang={lang}"' in top_bar
        assert "css/challenge-button.css" in html
        hero = html.split('class="container"')[1]
        assert "btn-challenge" not in hero

    def test_the_landing_page_leaves_the_language_to_the_form(self, client):
        html = client.get("/").get_data(as_text=True)
        assert 'href="/challenge"' in html and "/challenge?lang=" not in html
        assert "css/challenge-button.css" in html

    @pytest.mark.parametrize("path", ["/es/numbers", "/es/learn", "/about"])
    def test_not_on_other_pages(self, client, path):
        html = client.get(path).get_data(as_text=True)
        assert "btn-challenge" not in html
        assert "challenge-button.css" not in html


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
        assert "German" in summary and "Surprise me" in summary

    def test_surprise_me_is_the_default(self, client):
        html = client.get("/challenge").get_data(as_text=True)
        checked = re.findall(r'<input[^>]*name="kind" value="(\w+)"[^>]*checked', html)
        assert checked == ["surprise"]
        kinds = re.findall(r'<input[^>]*name="kind" value="(\w+)"', html)
        assert kinds == ["surprise", "numbers", "listening", "verbs"]
        # Difficulty stays on offer: Surprise me can turn out to be numbers.
        level = re.search(r'<fieldset[^>]*id="challenge-difficulty"[^>]*>', html)
        assert "hidden" not in level.group(0)

    def test_a_kind_in_the_url_replaces_the_default(self, client):
        html = client.get("/challenge?kind=numbers").get_data(as_text=True)
        checked = re.findall(r'<input[^>]*name="kind" value="(\w+)"[^>]*checked', html)
        assert checked == ["numbers"]

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
        [result] = _scores(result_url)
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
