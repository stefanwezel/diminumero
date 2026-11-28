"""Tests for verb challenges: a friend challenge made from the creator's own verbs.

The creator's verbs travel in the signed token, the ten questions are drawn
from them with the seed, the round runs on the conjugation drill's routes
(without needing an account to play), and the challenge page lets a player
add the verbs they don't have yet.
"""

import re
from urllib.parse import parse_qs, urlparse

import pytest
from itsdangerous import URLSafeSerializer

import app as app_module
import challenge
from app import app as flask_app
from config import QUESTIONS_PER_QUIZ
from conjugation_config import conj_tenses
from languages.es import conjugations as es_conjugations
from models import ChallengeResult, ConjugationStat, DeckShare, VerbCard, db

SECRET = "test-secret-key"
ES_PRESENT = "indicativo/presente"
ES_PRETERITE = "indicativo/pretérito-perfecto-simple"
ES_IMPERATIVE = "imperativo/afirmativo"

CREATOR = {"sub": "auth0|creator", "name": "Ada", "email": "ada@example.com"}
FRIEND = {"sub": "auth0|friend", "name": "Grace", "email": "grace@example.com"}

COMMON_ES = [
    "ser", "estar", "tener", "hacer", "poder", "decir", "ir", "ver",
    "dar", "saber", "querer", "llegar", "pasar", "deber", "poner",
]  # fmt: skip


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


def login(client, user=CREATOR):
    with client.session_transaction() as sess:
        sess["user"] = user


def add_verbs(user_sub, infinitives, lang="es"):
    with flask_app.app_context():
        for infinitive in infinitives:
            db.session.add(
                VerbCard(user_sub=user_sub, lang=lang, infinitive=infinitive)
            )
        db.session.commit()


def user_verbs(user_sub, lang="es"):
    with flask_app.app_context():
        return sorted(
            v.infinitive
            for v in db.session.query(VerbCard).filter_by(user_sub=user_sub, lang=lang)
        )


def create(client, lang="es", tenses=(ES_PRESENT, ES_PRETERITE), **fields):
    """POST the create form for a verb challenge; return the response."""
    data = {"lang": lang, "kind": "verbs", "difficulty": "advanced", "name": "Ada"}
    data[f"tenses_{lang}"] = list(tenses)
    data.update(fields)
    return client.post("/challenge", data=data)


def created_url(client, **kwargs):
    """Make a verb challenge; return its link (its maker lands on link + /share)."""
    response = create(client, **kwargs)
    assert response.status_code == 303, response.headers.get("Location")
    assert "/challenge/" in response.location
    assert response.location.endswith("/share")
    return response.location.removesuffix("/share")


def scores(url):
    """The stored scoreboard of the challenge at `url`: (name, score), as played."""
    seed = decode(url).seed
    with flask_app.app_context():
        rows = ChallengeResult.query.filter_by(seed=seed).order_by(ChallengeResult.id)
        return [(r.name, r.score) for r in rows]


def token_of(url):
    return url.rsplit("/challenge/", 1)[1].split("?")[0].split("/")[0]


def decode(url):
    return challenge.Challenge.decode(token_of(url), SECRET)


def start(client, url, name=""):
    response = client.post(f"/challenge/{token_of(url)}/start", data={"name": name})
    assert response.status_code == 302
    assert response.location.endswith("/es/conjugate/practice")
    return response


def play(client, answer_right=None, lang="es"):
    """Answer every question of the running verb challenge; return (result URL, asked)."""
    answer_right = answer_right or (lambda i: True)
    asked = []
    for i in range(QUESTIONS_PER_QUIZ):
        response = client.get(f"/{lang}/conjugate/practice")
        assert response.status_code == 200, response.headers.get("Location")
        with client.session_transaction() as sess:
            current = sess["conjugate_practice"]["current"]
        asked.append(
            (current["infinitive"], current["tense_key"], current["person_index"])
        )
        answer = current["correct_answer"] if answer_right(i) else "zzz"
        client.post(f"/{lang}/conjugate/practice", data={"answer": answer})
    response = client.get(f"/{lang}/conjugate/practice")
    assert response.status_code == 302
    assert response.location.endswith(f"/{lang}/conjugate/practice/results")
    response = client.get(f"/{lang}/conjugate/practice/results")
    assert response.status_code == 302
    assert "/challenge/" in response.location
    return response.location, asked


def fake_login_callback(monkeypatch, user):
    monkeypatch.setattr(
        app_module.oauth.auth0,
        "authorize_access_token",
        lambda: {"userinfo": user},
    )


class TestToken:
    def test_round_trip(self):
        ch = challenge.Challenge(
            "es",
            "hardcore",
            "abcdefgh",
            host="Ada",
            verbs=("ser", "tener"),
            tenses=(ES_PRESENT,),
            optional_person=True,
        )
        back = challenge.Challenge.decode(ch.encode(SECRET), SECRET)
        assert back == ch
        assert back.kind == challenge.KIND_VERBS
        assert back.is_verbs

    def test_a_numbers_token_is_unchanged(self):
        ch = challenge.Challenge("es", "advanced", "abcdefgh", host="Ada")
        payload = URLSafeSerializer(SECRET, salt=challenge.TOKEN_SALT).loads(
            ch.encode(SECRET)
        )
        assert set(payload) == {"v", "l", "m", "s", "h"}
        back = challenge.Challenge.decode(ch.encode(SECRET), SECRET)
        assert back.kind == challenge.KIND_NUMBERS and not back.is_verbs

    @pytest.mark.parametrize(
        "extra",
        [
            {"vb": "ser", "t": [ES_PRESENT]},
            {"vb": [], "t": [ES_PRESENT]},
            {"vb": ["ser", "ser"], "t": [ES_PRESENT]},
            {"vb": ["ser", 3], "t": [ES_PRESENT]},
            {"vb": [" ser"], "t": [ES_PRESENT]},
            {"vb": ["s‮er"], "t": [ES_PRESENT]},
            {"vb": ["x" * 41], "t": [ES_PRESENT]},
            {"vb": [f"v{i}" for i in range(QUESTIONS_PER_QUIZ + 1)], "t": [ES_PRESENT]},
            {"vb": ["ser"]},
            {"t": [ES_PRESENT]},
            {"vb": ["ser"], "t": []},
            {"vb": ["ser"], "t": [ES_PRESENT], "o": 2},
            {"vb": ["ser"], "t": [ES_PRESENT], "o": True},
            {"o": 1},
        ],
    )
    def test_correctly_signed_but_malformed_is_rejected(self, extra):
        payload = {"v": 1, "l": "es", "m": "a", "s": "abcdefgh", **extra}
        token = URLSafeSerializer(SECRET, salt=challenge.TOKEN_SALT).dumps(payload)
        assert challenge.Challenge.decode(token, SECRET) is None

    @pytest.mark.parametrize("mode", ["e", "l"])
    def test_a_verb_challenge_has_no_easy_or_listening_mode(self, mode):
        payload = {"v": 1, "l": "es", "m": mode, "s": "abcdefgh"}
        payload.update({"vb": ["ser"], "t": [ES_PRESENT]})
        token = URLSafeSerializer(SECRET, salt=challenge.TOKEN_SALT).dumps(payload)
        assert challenge.Challenge.decode(token, SECRET) is None

    @pytest.mark.parametrize("lang", ["es", "it", "de", "en"])
    def test_the_longest_realistic_token_fits(self, lang):
        # The ten longest verbs in the pool, every tense, a 24-character
        # Arabic host name: still a link a chat app will carry whole. (Scores
        # are stored, not carried, so they no longer add to it.)
        pool = app_module.CONJ_POOLS[lang]
        longest = sorted(pool.global_verbs, key=len)[-challenge.MAX_VERBS :]
        name = "ب" * challenge.NAME_MAX
        ch = challenge.Challenge(
            lang,
            "advanced",
            challenge.new_seed(),
            host=name,
            verbs=tuple(longest),
            tenses=tuple(t["key"] for t in conj_tenses(lang)),
            optional_person=True,
        )
        token = ch.encode(SECRET)
        assert len(token) <= challenge.TOKEN_MAX_LENGTH
        assert challenge.Challenge.decode(token, SECRET) == ch


class TestDraw:
    @staticmethod
    def _everything(verb, tense, person):
        return True

    def _draw(self, verbs, seed="abcdefgh", tenses=("a", "b"), persons=(0, 1, 2)):
        return challenge.draw_verb_questions(
            verbs, tenses, persons, self._everything, seed
        )

    def test_same_seed_same_round(self):
        verbs = ("ser", "tener", "ir")
        assert self._draw(verbs) == self._draw(verbs)
        assert len(self._draw(verbs)) == QUESTIONS_PER_QUIZ

    def test_another_seed_another_round(self):
        verbs = ("ser", "tener", "ir")
        assert self._draw(verbs, seed="abcdefgh") != self._draw(verbs, seed="hgfedcba")

    def test_no_question_is_asked_twice(self):
        picked = self._draw(("ser", "tener"))
        assert len(set(picked)) == len(picked)

    def test_every_verb_is_asked_before_any_repeats(self):
        verbs = ("ser", "tener", "ir")
        counts = [v for v, _, _ in self._draw(verbs)]
        assert {verbs.count(v) for v in verbs} == {1}
        assert max(map(counts.count, verbs)) - min(map(counts.count, verbs)) <= 1

    def test_ten_verbs_are_each_asked_once(self):
        verbs = tuple(COMMON_ES[:10])
        assert sorted(v for v, _, _ in self._draw(verbs)) == sorted(verbs)

    def test_cells_without_a_form_are_never_asked(self):
        def has_form(verb, tense, person):
            return not (tense == "b" or person == 0)

        picked = challenge.draw_verb_questions(
            ("ser", "tener", "ir", "ver", "dar"), ("a", "b"), (0, 1, 2), has_form, "x"
        )
        assert picked and all(t == "a" and p != 0 for _, t, p in picked)

    def test_too_few_cells_give_a_short_round(self):
        picked = challenge.draw_verb_questions(
            ("ser",), ("a",), (0, 1, 2), self._everything, "abcdefgh"
        )
        assert len(picked) == 3


class TestCreate:
    def test_needs_an_account(self, client):
        response = create(client)
        assert response.status_code == 302
        query = parse_qs(urlparse(response.location).query)
        assert query == {"lang": ["es"], "kind": ["verbs"]}
        with client.session_transaction() as sess:
            assert not (sess.get("challenge_me") or {}).get("created")

    def test_a_language_without_verb_practice_goes_back(self, client):
        login(client)
        response = create(client, lang="fr", tenses=())
        assert response.status_code == 302
        assert "/challenge/" not in response.location

    def test_needs_verbs_on_the_list(self, client):
        login(client)
        response = create(client)
        assert response.status_code == 302
        assert "/challenge/" not in response.location

    def test_too_few_questions_goes_back(self, client):
        # One verb in one tense, vosotros off: five questions, not ten.
        login(client)
        add_verbs(CREATOR["sub"], ["ser"])
        response = create(client, tenses=(ES_PRESENT,))
        assert response.status_code == 302
        assert "/challenge/" not in response.location

    def test_one_verb_in_two_tenses_is_enough(self, client):
        login(client)
        add_verbs(CREATOR["sub"], ["ser"])
        ch = decode(created_url(client))
        assert ch.verbs == ("ser",)
        assert ch.tenses == (ES_PRESENT, ES_PRETERITE)
        assert ch.mode == "advanced" and not ch.optional_person
        assert ch.host == "Ada"

    def test_no_tense_goes_back(self, client):
        login(client)
        add_verbs(CREATOR["sub"], COMMON_ES)
        response = create(client, tenses=("indicativo/made-up",))
        assert response.status_code == 302
        assert "/challenge/" not in response.location

    def test_tenses_are_kept_in_the_languages_order(self, client):
        login(client)
        add_verbs(CREATOR["sub"], COMMON_ES)
        ch = decode(created_url(client, tenses=(ES_PRETERITE, ES_PRESENT)))
        assert ch.tenses == (ES_PRESENT, ES_PRETERITE)

    def test_at_most_ten_of_the_creators_verbs(self, client):
        login(client)
        add_verbs(CREATOR["sub"], COMMON_ES)
        add_verbs(FRIEND["sub"], ["comer", "vivir"])
        add_verbs(CREATOR["sub"], ["gehen"], lang="de")
        ch = decode(created_url(client))
        assert len(ch.verbs) == challenge.MAX_VERBS
        assert set(ch.verbs) <= set(COMMON_ES)
        assert list(ch.verbs) == sorted(ch.verbs)

    def test_only_verbs_with_something_to_ask(self, client):
        # Imperative only: a verb whose pool entry has no imperative at all
        # can't be in the round. Every common verb has one, so check the set
        # is exactly those with a form.
        login(client)
        add_verbs(CREATOR["sub"], COMMON_ES)
        ch = decode(created_url(client, tenses=(ES_IMPERATIVE,)))
        for verb in ch.verbs:
            forms = es_conjugations.pool.get_verb_forms(verb)[ES_IMPERATIVE]
            assert any(forms)

    def test_easy_is_not_a_verb_mode(self, client):
        login(client)
        add_verbs(CREATOR["sub"], COMMON_ES)
        assert decode(created_url(client, difficulty="easy")).mode == "advanced"
        assert decode(created_url(client, difficulty="hardcore")).mode == "hardcore"

    def test_vosotros_from_the_create_form(self, client):
        login(client)
        add_verbs(CREATOR["sub"], COMMON_ES)
        ch = decode(created_url(client, include_vosotros_es="1"))
        assert ch.optional_person

    def test_start_goes_straight_into_the_round(self, client):
        login(client)
        add_verbs(CREATOR["sub"], COMMON_ES)
        response = create(client, go="1")
        assert response.status_code == 302
        assert response.location.endswith("/es/conjugate/practice")
        with client.session_transaction() as sess:
            state = sess["conjugate_practice"]
        assert state["challenge"]["token"]
        assert state["count"] == QUESTIONS_PER_QUIZ

    def test_share_opens_the_page_with_the_link_first(self, client):
        login(client)
        add_verbs(CREATOR["sub"], COMMON_ES)
        url = created_url(client, share="1")
        html = client.get(f"{url}/share").get_data(as_text=True)
        assert "data-share-focus" in html

    def test_surprise_never_picks_verbs(self, client):
        login(client)
        add_verbs(CREATOR["sub"], COMMON_ES)
        for _ in range(12):
            response = client.post(
                "/challenge", data={"lang": "es", "kind": "surprise", "name": ""}
            )
            assert not decode(response.location).is_verbs


class TestCreateForm:
    def test_anonymous_sees_verbs_disabled_and_a_login_link(self, client):
        html = client.get("/challenge?lang=es").get_data(as_text=True)
        radio = re.search(r'<input[^>]*name="kind" value="verbs"[^>]*>', html).group(0)
        assert "disabled" in radio
        note = re.search(r'<p[^>]*id="challenge-verbs-login"[^>]*>', html).group(0)
        assert "hidden" not in note
        assert "/challenge/login?next=" in html

    def test_logged_in_with_verbs_can_pick_verbs(self, client):
        login(client)
        add_verbs(CREATOR["sub"], ["ser", "tener"])
        html = client.get("/challenge?lang=es").get_data(as_text=True)
        radio = re.search(r'<input[^>]*name="kind" value="verbs"[^>]*>', html).group(0)
        assert "disabled" not in radio
        es = re.search(r'<input[^>]*name="lang" value="es"[^>]*>', html).group(0)
        assert 'data-verbs="2"' in es and 'data-conj="1"' in es
        fr = re.search(r'<input[^>]*name="lang" value="fr"[^>]*>', html).group(0)
        assert 'data-conj="0"' in fr and "data-verbs" not in fr

    def test_logged_in_without_verbs_is_pointed_at_the_list(self, client):
        login(client)
        html = client.get("/challenge?lang=es").get_data(as_text=True)
        note = re.search(r'<p[^>]*id="challenge-verbs-empty"[^>]*>', html).group(0)
        assert "hidden" not in note
        assert 'href="/es/conjugate"' in html

    def test_kind_in_the_url_preselects_verbs(self, client):
        login(client)
        add_verbs(CREATOR["sub"], ["ser"])
        html = client.get("/challenge?lang=es&kind=verbs").get_data(as_text=True)
        radio = re.search(r'<input[^>]*name="kind" value="verbs"[^>]*>', html).group(0)
        assert "checked" in radio
        assert 'data-kind-explicit="1"' in html
        tenses = re.search(r'<fieldset[^>]*id="challenge-tenses"[^>]*>', html).group(0)
        assert "hidden" not in tenses

    def test_kind_in_the_url_is_ignored_where_it_cant_be_made(self, client):
        html = client.get("/challenge?lang=es&kind=verbs").get_data(as_text=True)
        radio = re.search(r'<input[^>]*name="kind" value="surprise"[^>]*>', html).group(
            0
        )
        assert "checked" in radio
        assert "data-kind-explicit" not in html

    def test_one_tense_list_per_verb_language(self, client):
        html = client.get("/challenge").get_data(as_text=True)
        for code in ("es", "it", "de", "en"):
            assert f'data-tenses-lang="{code}"' in html
            assert f'name="tenses_{code}"' in html
        assert 'name="include_vosotros_es"' in html
        assert 'name="include_vosotros_it"' not in html

    def test_tenses_are_hidden_by_default(self, client):
        html = client.get("/challenge").get_data(as_text=True)
        radio = re.search(r'<input[^>]*name="kind" value="surprise"[^>]*>', html).group(
            0
        )
        assert "checked" in radio
        tenses = re.search(r'<fieldset[^>]*id="challenge-tenses"[^>]*>', html).group(0)
        assert "hidden" in tenses


class TestConjugatePage:
    def test_has_a_challenge_button_on_the_practice_form(self, client):
        login(client)
        add_verbs(CREATOR["sub"], ["ser"])
        html = client.get("/es/conjugate").get_data(as_text=True)
        form = html[html.index('id="conjugate-practice-form"') :]
        form = form[: form.index("</form>")]
        button = re.search(r"<button[^>]*conjugate-challenge-btn[^>]*>", form).group(0)
        assert 'formaction="/challenge"' in button
        assert 'name="kind"' in button and 'value="verbs"' in button
        assert '<input type="hidden" name="lang" value="es">' in form

    def test_posting_the_practice_settings_makes_a_challenge(self, client):
        login(client)
        add_verbs(CREATOR["sub"], COMMON_ES)
        with client.session_transaction() as sess:
            sess["challenge_me"] = {"name": "Ada"}
        response = client.post(
            "/challenge",
            data={
                "lang": "es",
                "kind": "verbs",
                "tenses": [ES_PRESENT, ES_IMPERATIVE],
                "include_vosotros": "1",
                "difficulty": "hardcore",
                "sampling_mode": "prioritized",
                "count": "25",
            },
        )
        assert response.status_code == 303
        ch = decode(response.location)
        assert ch.tenses == (ES_PRESENT, ES_IMPERATIVE)
        assert ch.optional_person and ch.mode == "hardcore"
        # No name field on that form: the remembered name is kept.
        assert ch.host == "Ada"
        page = client.get(response.location).get_data(as_text=True)
        assert "Your challenge is ready" in page

    @pytest.mark.parametrize(
        "me, host",
        [
            ({"name": "Tamandua"}, "Tamandua"),
            # Never given one: the login's first name, as the field would show.
            (None, "Ada"),
            # Emptied one before: still none.
            ({"name": "", "anonymous": True}, ""),
        ],
    )
    def test_the_practice_form_names_the_host_as_the_field_would(
        self, client, me, host
    ):
        login(client)
        add_verbs(CREATOR["sub"], COMMON_ES)
        if me is not None:
            with client.session_transaction() as sess:
                sess["challenge_me"] = me
        response = client.post(
            "/challenge",
            data={"lang": "es", "kind": "verbs", "tenses": [ES_PRESENT]},
        )
        assert decode(response.location).host == host

    def test_the_practice_form_still_starts_practice(self, client):
        login(client)
        add_verbs(CREATOR["sub"], ["ser"])
        response = client.post(
            "/es/conjugate/practice/start",
            data={"lang": "es", "tenses": [ES_PRESENT], "difficulty": "advanced"},
        )
        assert response.location.endswith("/es/conjugate/practice")
        with client.session_transaction() as sess:
            assert "challenge" not in sess["conjugate_practice"]


class TestPlay:
    def _made(self, client):
        login(client)
        add_verbs(CREATOR["sub"], COMMON_ES)
        return created_url(client)

    def test_creator_then_anonymous_friend_get_the_same_round(self, client, friend):
        url = self._made(client)
        start(client, url, name="Ada")
        result_url, asked = play(client)
        ch = decode(result_url)
        assert scores(result_url) == [("Ada", 10)]

        start(friend, result_url, name="Grace")
        back_url, friend_asked = play(friend, answer_right=lambda i: i % 2 == 0)
        assert friend_asked == asked
        assert {v for v, _, _ in asked} == set(ch.verbs)
        assert scores(back_url) == [("Ada", 10), ("Grace", 5)]
        html = friend.get(back_url).get_data(as_text=True)
        assert "You scored 5/10" in html

    def test_a_verb_challenge_ends_an_unfinished_numbers_challenge(self, client):
        """Left running, the numbers round would post its 3/10 to the board
        the next time anyone opened its results page."""
        numbers = client.post(
            "/challenge", data={"lang": "es", "kind": "numbers", "name": "Ada"}
        ).location.removesuffix("/share")
        client.post(f"/challenge/{token_of(numbers)}/start", data={"name": "Ada"})
        for _ in range(3):
            client.get("/es/quiz/advanced")
            with client.session_transaction() as sess:
                word = sess["correct_answer"]
            client.post("/es/quiz/advanced", data={"answer": word})

        url = self._made(client)
        start(client, url, name="Ada")
        with client.session_transaction() as sess:
            assert "challenge" not in sess and "total_questions" not in sess
            # The player's own settings are theirs, and stay.
            assert sess["learn_language"] == "es" and "magnitude_level" in sess
        response = client.get("/es/results")
        assert "/challenge/" not in (response.location or "")
        assert scores(numbers) == []
        # The verb round runs on as if nothing had happened.
        result_url, _ = play(client)
        assert scores(result_url) == [("Ada", 10)]

    def test_a_round_is_scored_under_the_name_it_was_started_with(self, client):
        url = self._made(client)
        start(client, url, name="Ada")
        client.post(
            "/challenge",
            data={"lang": "es", "kind": "numbers", "name": "Robert", "share": "1"},
        )
        result_url, _ = play(client)
        assert scores(result_url) == [("Ada", 10)]

    @pytest.mark.parametrize("drill", ["verb challenge", "conjugation drill"])
    def test_another_drill_closes_the_last_result_page(self, client, drill):
        """As a number drill does: a result page is the session's until then."""
        numbers = client.post(
            "/challenge", data={"lang": "es", "kind": "numbers", "go": "1"}
        ).location
        client.get(numbers)
        for _ in range(QUESTIONS_PER_QUIZ):
            client.get("/es/quiz/advanced")
            client.post("/es/quiz/advanced", data={"answer": "zzz"})
        result_url = client.get("/es/results").location
        assert result_url.endswith("/result")
        assert client.get(result_url).status_code == 200

        url = self._made(client)
        if drill == "verb challenge":
            start(client, url, name="Ada")
        else:
            client.post(
                "/es/conjugate/practice/start",
                data={"tenses": [ES_PRESENT], "count": "5"},
            )
            with client.session_transaction() as sess:
                assert "challenge" not in sess["conjugate_practice"]
        response = client.get(result_url)
        assert response.status_code == 302
        assert response.location == result_url.removesuffix("/result")

    def test_without_a_challenge_practice_still_needs_a_login(self, client):
        for path in (
            "/es/conjugate/practice",
            "/es/conjugate/practice/results",
        ):
            response = client.get(path)
            assert response.status_code == 302
            assert response.location.endswith("/login")
        response = client.post("/api/conjugate/validate", json={"input": "x"})
        assert response.status_code == 302

    def test_a_challenge_in_one_language_opens_no_other(self, client, friend):
        url = self._made(client)
        start(friend, url)
        response = friend.get("/de/conjugate/practice")
        assert response.status_code == 302 and response.location.endswith("/login")

    def test_live_validation_works_without_an_account(self, client, friend):
        url = self._made(client)
        start(friend, url)
        friend.get("/es/conjugate/practice")
        response = friend.post("/api/conjugate/validate", json={"input": "x"})
        assert response.status_code == 200
        assert "words" in response.get_json()

    def test_no_hint_in_a_challenge(self, client, friend):
        url = self._made(client)
        start(friend, url)
        html = friend.get("/es/conjugate/practice").get_data(as_text=True)
        assert 'id="hintBtn"' not in html
        with friend.session_transaction() as sess:
            answer = sess["conjugate_practice"]["current"]["correct_answer"]
        friend.post("/es/conjugate/practice", data={"answer": answer, "hint_used": "1"})
        with friend.session_transaction() as sess:
            assert sess["conjugate_practice"]["score"] == 1

    def test_a_reveal_counts_as_wrong_and_moves_on(self, client, friend):
        url = self._made(client)
        start(friend, url)
        friend.get("/es/conjugate/practice")
        friend.post("/es/conjugate/practice", data={"reveal": "1"})
        with friend.session_transaction() as sess:
            state = sess["conjugate_practice"]
            first = state["current"]
        assert state["total"] == 1 and state["score"] == 0
        friend.post(
            "/es/conjugate/practice",
            data={"next": "1", "answer": first["correct_answer"]},
        )
        friend.get("/es/conjugate/practice")
        with friend.session_transaction() as sess:
            second = sess["conjugate_practice"]["current"]
        plan = app_module._verb_challenge_plan(decode(url))
        assert (first["infinitive"], first["tense_key"], first["person_index"]) == plan[
            0
        ]
        assert (
            second["infinitive"],
            second["tense_key"],
            second["person_index"],
        ) == plan[1]

    def test_exit_ends_the_challenge_with_the_score_so_far(self, client, friend):
        url = self._made(client)
        start(friend, url)
        for _ in range(3):
            friend.get("/es/conjugate/practice")
            with friend.session_transaction() as sess:
                answer = sess["conjugate_practice"]["current"]["correct_answer"]
            friend.post("/es/conjugate/practice", data={"answer": answer})
        response = friend.get("/es/conjugate/practice/results")
        assert response.status_code == 302
        assert scores(response.location) == [("", 3)]
        with friend.session_transaction() as sess:
            assert "conjugate_practice" not in sess

    def test_exit_before_answering_scores_nothing(self, client, friend):
        url = self._made(client)
        start(friend, url)
        friend.get("/es/conjugate/practice")
        response = friend.get("/es/conjugate/practice/results")
        assert response.location.endswith(f"/challenge/{token_of(url)}")
        with friend.session_transaction() as sess:
            assert "conjugate_practice" not in sess
            played = (sess.get("challenge_me") or {}).get("played", [])
            assert decode(url).seed not in played
        assert scores(url) == []
        # Still unplayed, so the friend can start it and their score counts.
        start(friend, url)
        result_url, _ = play(friend)
        assert len(scores(result_url)) == 1

    def test_the_session_holds_no_list_of_questions(self, client, friend):
        url = self._made(client)
        start(friend, url)
        friend.get("/es/conjugate/practice")
        with friend.session_transaction() as sess:
            state = sess["conjugate_practice"]
        assert set(state["challenge"]) == {"token", "seed", "sender", "name"}
        assert "plan" not in state and state["verb_ids"] == []

    def test_attempts_are_recorded_on_the_players_own_verbs(self, client, friend):
        url = self._made(client)
        start(client, url)
        play(client)
        with flask_app.app_context():
            practiced = {
                v.infinitive: v.times_practiced
                for v in db.session.query(VerbCard).filter_by(user_sub=CREATOR["sub"])
            }
            stats = db.session.query(ConjugationStat).filter_by(
                user_sub=CREATOR["sub"], lang="es"
            )
            assert sum(s.times_practiced for s in stats) == QUESTIONS_PER_QUIZ
        assert sum(practiced.values()) == QUESTIONS_PER_QUIZ
        assert {v for v, n in practiced.items() if n} == set(decode(url).verbs)

    def test_a_friend_without_those_verbs_gets_none_added(self, client, friend):
        url = self._made(client)
        login(friend, FRIEND)
        add_verbs(FRIEND["sub"], ["comer"])
        start(friend, url)
        play(friend)
        assert user_verbs(FRIEND["sub"]) == ["comer"]
        with flask_app.app_context():
            assert not db.session.query(ConjugationStat).count()

    def test_a_friend_who_has_one_of_them_records_it(self, client, friend):
        url = self._made(client)
        verb = decode(url).verbs[0]
        login(friend, FRIEND)
        add_verbs(FRIEND["sub"], [verb])
        start(friend, url)
        play(friend)
        with flask_app.app_context():
            mine = db.session.query(VerbCard).filter_by(user_sub=FRIEND["sub"]).one()
            assert mine.times_practiced >= 1

    def test_normal_practice_after_a_challenge_is_normal_again(self, client, friend):
        url = self._made(client)
        start(client, url)
        client.get("/es/conjugate/practice")
        client.post(
            "/es/conjugate/practice/start",
            data={"tenses": [ES_PRESENT], "difficulty": "advanced", "count": "3"},
        )
        with client.session_transaction() as sess:
            assert "challenge" not in sess["conjugate_practice"]
        client.get("/es/conjugate/practice")
        response = client.get("/es/conjugate/practice/results")
        assert response.status_code == 200

    def test_a_numbers_challenge_is_untouched(self, client):
        response = client.post(
            "/challenge",
            data={"lang": "es", "kind": "numbers", "difficulty": "advanced", "go": "1"},
        )
        assert response.location.endswith("/es/quiz/advanced")
        with client.session_transaction() as sess:
            assert sess["challenge"]["token"]
            assert "conjugate_practice" not in sess

    def test_a_pool_change_makes_the_link_a_friendly_404(
        self, client, friend, monkeypatch
    ):
        url = self._made(client)
        gone = decode(url).verbs[0]
        real = es_conjugations.pool.verb_exists
        monkeypatch.setattr(
            es_conjugations.pool, "verb_exists", lambda v: v != gone and real(v)
        )
        assert friend.get(url).status_code == 404
        response = friend.post(f"/challenge/{token_of(url)}/start")
        assert response.status_code == 302
        assert "/challenge/" not in response.location


class TestPage:
    def _made(self, client):
        login(client)
        add_verbs(CREATOR["sub"], COMMON_ES)
        return created_url(client)

    def test_the_invitation_lists_the_verbs_and_tenses(self, client, friend):
        url = self._made(client)
        html = friend.get(url).get_data(as_text=True)
        for verb in decode(url).verbs:
            assert f'lang="es">{verb}</span>' in html
        assert "Present" in html and "Preterite" in html
        assert "challenge-verb-add" not in html
        login_links = re.findall(r'href="(/challenge/login\?[^"]*)"', html)
        assert [
            parse_qs(urlparse(link.replace("&amp;", "&")).query)["next"]
            for link in login_links
        ] == [[urlparse(url).path]]

    def test_a_friend_sees_which_verbs_they_lack(self, client, friend):
        url = self._made(client)
        verbs = decode(url).verbs
        login(friend, FRIEND)
        add_verbs(FRIEND["sub"], [verbs[0]])
        html = friend.get(url).get_data(as_text=True)
        assert html.count('class="challenge-verb is-owned"') == 1
        assert html.count('class="challenge-verb-add"') == len(verbs) - 1
        assert f"Add all to my verbs ({len(verbs) - 1})" in html

    def test_add_one_verb(self, client, friend):
        url = self._made(client)
        verb = decode(url).verbs[0]
        login(friend, FRIEND)
        response = friend.post(f"/challenge/{token_of(url)}/verbs", data={"verb": verb})
        assert response.status_code == 303
        assert response.location.endswith(urlparse(url).path)
        assert user_verbs(FRIEND["sub"]) == [verb]

    def test_add_all_verbs_once(self, client, friend):
        url = self._made(client)
        login(friend, FRIEND)
        friend.post(f"/challenge/{token_of(url)}/verbs")
        assert user_verbs(FRIEND["sub"]) == sorted(decode(url).verbs)
        friend.post(f"/challenge/{token_of(url)}/verbs")
        assert user_verbs(FRIEND["sub"]) == sorted(decode(url).verbs)
        html = friend.get(url).get_data(as_text=True)
        assert "All of these are on your list." in html

    def test_a_verb_not_in_the_challenge_is_not_added(self, client, friend):
        url = self._made(client)
        assert "comer" not in decode(url).verbs
        login(friend, FRIEND)
        response = friend.post(
            f"/challenge/{token_of(url)}/verbs", data={"verb": "comer"}
        )
        assert user_verbs(FRIEND["sub"]) == []
        html = friend.get(response.location).get_data(as_text=True)
        assert "already on your list" not in html

    def test_adding_owned_verbs_says_so(self, client, friend):
        url = self._made(client)
        verb = decode(url).verbs[0]
        login(friend, FRIEND)
        add_verbs(FRIEND["sub"], [verb])
        response = friend.post(f"/challenge/{token_of(url)}/verbs", data={"verb": verb})
        html = friend.get(response.location).get_data(as_text=True)
        assert "Those verbs are already on your list." in html

    def test_adding_after_finishing_keeps_the_result_view(self, client, friend):
        url = self._made(client)
        login(friend, FRIEND)
        start(friend, url)
        result_url, _ = play(friend)
        page = friend.get(result_url).get_data(as_text=True)
        assert '<input type="hidden" name="back" value="result">' in page
        response = friend.post(
            f"/challenge/{token_of(result_url)}/verbs", data={"back": "result"}
        )
        assert response.location == result_url
        html = friend.get(response.location).get_data(as_text=True)
        assert "You scored 10/10" in html

    def test_adding_from_the_sender_page_comes_back_to_it(self, client):
        url = self._made(client)
        # A verb taken off the list after making the challenge, the one way
        # its maker can lack one of its verbs.
        with flask_app.app_context():
            VerbCard.query.filter_by(
                user_sub=CREATOR["sub"], infinitive=decode(url).verbs[0]
            ).delete()
            db.session.commit()
        page = client.get(f"{url}/share").get_data(as_text=True)
        assert '<input type="hidden" name="back" value="share">' in page
        response = client.post(
            f"/challenge/{token_of(url)}/verbs", data={"back": "share"}
        )
        assert response.location == f"{url}/share"

    def test_adding_from_the_link_comes_back_to_it(self, client, friend):
        url = self._made(client)
        login(friend, FRIEND)
        page = friend.get(url).get_data(as_text=True)
        assert 'name="back"' not in page
        # An unknown `back` is the link too.
        response = friend.post(f"/challenge/{token_of(url)}/verbs", data={"back": "x"})
        assert response.location == url

    def test_adding_without_an_account_logs_in_and_comes_back(
        self, client, friend, monkeypatch
    ):
        url = self._made(client)
        response = friend.post(f"/challenge/{token_of(url)}/verbs")
        assert response.status_code == 302 and response.location.endswith("/login")
        fake_login_callback(monkeypatch, FRIEND)
        response = friend.get("/callback")
        assert response.location.endswith(urlparse(url).path)
        assert user_verbs(FRIEND["sub"]) == []

    def test_the_login_link_comes_back_to_the_challenge(
        self, client, friend, monkeypatch
    ):
        url = self._made(client)
        path = urlparse(url).path
        response = friend.get(f"/challenge/login?next={path}")
        assert response.location.endswith("/login")
        fake_login_callback(monkeypatch, FRIEND)
        assert friend.get("/callback").location.endswith(path)

    def test_the_login_link_comes_back_to_the_sender_page(self, client, monkeypatch):
        """A sender whose login has lapsed still has the challenge in hand."""
        url = self._made(client)
        path = urlparse(url).path + "/share"
        client.get(f"/challenge/login?next={path}")
        fake_login_callback(monkeypatch, CREATOR)
        assert client.get("/callback").location.endswith(path)

    def test_the_create_forms_login_link_keeps_the_round_it_was_set_to(
        self, friend, monkeypatch
    ):
        """New challenge after a verb round opens the form with its language,
        difficulty and tenses; logging in from there mustn't lose them."""
        asked = {
            "lang": ["de"],
            "kind": ["verbs"],
            "difficulty": ["hardcore"],
            "tenses": ["indikativ/praesens", "indikativ/perfekt"],
        }
        html = friend.get("/challenge", query_string=asked).get_data(as_text=True)
        link = re.search(r'href="(/challenge/login\?next=[^"]+)"', html).group(1)
        friend.get(link.replace("&amp;", "&"))
        fake_login_callback(monkeypatch, FRIEND)
        back = urlparse(friend.get("/callback").location)
        assert back.path == "/challenge"
        assert parse_qs(back.query) == asked

    @pytest.mark.parametrize(
        "query", ["lang=es", "lang=es&kind=numbers", "_external=1&lang=es"]
    )
    def test_the_create_forms_login_link_is_for_verbs_and_stays_here(
        self, friend, monkeypatch, query
    ):
        html = friend.get(f"/challenge?{query}").get_data(as_text=True)
        link = re.search(r'href="(/challenge/login\?next=[^"]+)"', html).group(1)
        friend.get(link.replace("&amp;", "&"))
        fake_login_callback(monkeypatch, FRIEND)
        back = urlparse(friend.get("/callback").location)
        assert back.netloc in ("", "localhost") and back.path == "/challenge"
        assert parse_qs(back.query)["kind"] == ["verbs"]
        assert parse_qs(back.query)["lang"] == ["es"]

    @pytest.mark.parametrize(
        "target",
        [
            "https://evil.example/",
            "//evil.example/challenge",
            "/cards",
            "/challenge/a/../../x",
            "/challenge/a/share/x",
            "/challenge/a/start",
            "/challenge?next=//evil.example",
            "/challenge?a=b#x",
        ],
    )
    def test_the_login_link_is_not_an_open_redirect(self, friend, monkeypatch, target):
        friend.get("/challenge/login", query_string={"next": target})
        fake_login_callback(monkeypatch, FRIEND)
        location = friend.get("/callback").location
        assert urlparse(location).path == "/challenge"
        assert urlparse(location).netloc in ("", "localhost")

    def _deck_share(self):
        with flask_app.app_context():
            db.session.add(
                DeckShare(
                    token="deck123", owner_sub="other", owner_name="Bo", cards_json="[]"
                )
            )
            db.session.commit()
        return "/cards/import/deck123"

    def test_the_latest_login_errand_wins_over_a_deck_import(
        self, client, friend, monkeypatch
    ):
        """A deck import abandoned at Auth0 mustn't swallow the challenge."""
        url = self._made(client)
        friend.get(self._deck_share())
        friend.post(f"/challenge/{token_of(url)}/verbs")
        fake_login_callback(monkeypatch, FRIEND)
        assert friend.get("/callback").location.endswith(urlparse(url).path)
        with friend.session_transaction() as sess:
            assert "pending_import_token" not in sess

    def test_a_later_deck_import_wins_over_a_challenge(
        self, client, friend, monkeypatch
    ):
        url = self._made(client)
        friend.get(f"/challenge/login?next={urlparse(url).path}")
        deck = self._deck_share()
        friend.get(deck)
        fake_login_callback(monkeypatch, FRIEND)
        assert friend.get("/callback").location.endswith(deck)
        with friend.session_transaction() as sess:
            assert "pending_challenge_next" not in sess

    def test_a_plain_login_still_lands_on_cards(self, friend, monkeypatch):
        fake_login_callback(monkeypatch, FRIEND)
        assert friend.get("/callback").location.endswith("/cards")

    def _new_challenge_form(self, client, url, hardcore=False):
        """Play the challenge at `url`; open its New challenge button's form."""
        start(client, url, name="Grace")
        result_url, _ = play(client)
        html = client.get(result_url).get_data(as_text=True)
        actions = re.search(r'class="challenge-actions">(.*?)</div>', html, re.S)
        link = re.search(r'<a href="([^"]+)"', actions.group(1)).group(1)
        link = link.replace("&amp;", "&")
        return link, client.get(link).get_data(as_text=True)

    def test_new_challenge_asks_for_the_same_tenses(self, client, friend):
        login(client)
        add_verbs(CREATOR["sub"], COMMON_ES)
        url = created_url(
            client,
            tenses=(ES_PRESENT, ES_IMPERATIVE),
            difficulty="hardcore",
            include_vosotros="1",
        )
        ch = decode(url)
        login(friend, FRIEND)
        add_verbs(FRIEND["sub"], ["comer", "vivir", "hablar"])
        link, form = self._new_challenge_form(friend, url)
        query = parse_qs(urlparse(link).query)
        assert query["kind"] == ["verbs"] and query["difficulty"] == ["hardcore"]
        assert tuple(query["tenses"]) == ch.tenses and query["vosotros"] == ["1"]
        # The form shows them, and says the browser's remembered ones mustn't
        # replace them.
        ticked = re.findall(r'name="tenses_es" value="([^"]+)"[^>]*checked', form)
        assert tuple(ticked) == ch.tenses
        assert re.search(r'name="include_vosotros_es" value="1"[^>]*checked', form)
        assert 'data-tenses-explicit="es"' in form
        assert re.search(r'name="difficulty" value="hardcore"[^>]*checked', form)
        # Submitting it makes the friend's own verb challenge.
        response = friend.post(
            "/challenge",
            data={
                "lang": "es",
                "kind": "verbs",
                "difficulty": "hardcore",
                "tenses_es": list(ticked),
                "include_vosotros_es": "1",
                "name": "Grace",
            },
        )
        made = decode(response.location)
        assert set(made.verbs) <= {"comer", "vivir", "hablar"}
        assert made.host == "Grace" and made.tenses == ch.tenses
        assert made.optional_person and made.mode == "hardcore"

    def test_new_challenge_without_an_account_says_to_log_in(self, client, friend):
        url = self._made(client)
        _, form = self._new_challenge_form(friend, url)
        radio = re.search(r'<input[^>]*name="kind" value="verbs"[^>]*>', form).group(0)
        assert "disabled" in radio
        note = re.search(r'<p[^>]*id="challenge-verbs-login"[^>]*>', form).group(0)
        assert "hidden" not in note

    def test_tenses_in_the_url_count_only_for_a_verb_challenge(self, client):
        login(client)
        add_verbs(CREATOR["sub"], COMMON_ES)
        html = client.get(
            f"/challenge?lang=es&kind=numbers&tenses={ES_IMPERATIVE}"
        ).get_data(as_text=True)
        assert "data-tenses-explicit" not in html
        html = client.get("/challenge?lang=es&kind=verbs&tenses=nonsense").get_data(
            as_text=True
        )
        assert "data-tenses-explicit" not in html

    def test_the_type_label_names_verbs(self, client, friend):
        url = self._made(client)
        html = friend.get(url).get_data(as_text=True)
        assert "Verbs · Advanced" in html

    def test_challenge_pages_are_never_cached(self, client, friend):
        url = self._made(client)
        assert "no-store" in friend.get(url).headers["Cache-Control"]
        response = friend.get("/challenge/login?next=/challenge")
        assert "no-store" in response.headers["Cache-Control"]
