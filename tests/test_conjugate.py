"""Tests for the Spanish verb-conjugation practice section."""

import pytest

from app import app as flask_app
from languages.es import conjugations as es_conjugations
from models import VerbCard, db


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("AUTH0_DOMAIN", "test-tenant.eu.auth0.com")
    monkeypatch.setenv("AUTH0_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("AUTH0_CLIENT_SECRET", "test-client-secret")
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret-key"
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


SAMPLE_USER = {"sub": "auth0|user-1", "name": "Ada", "email": "ada@example.com"}
OTHER_USER = {"sub": "auth0|user-2", "name": "Grace", "email": "grace@example.com"}


def login(client, user=SAMPLE_USER):
    with client.session_transaction() as sess:
        sess["user"] = user


def add_verb(user_sub, infinitive):
    with flask_app.app_context():
        verb = VerbCard(user_sub=user_sub, infinitive=infinitive)
        db.session.add(verb)
        db.session.commit()
        return verb.id


# Sanity: the committed global pool must contain the verbs these tests rely on.
def test_global_pool_has_common_verbs():
    for v in ("comer", "hablar", "ser", "tener"):
        assert es_conjugations.verb_exists(v), v


class TestVerbManage:
    def test_logged_out_redirects_to_login(self, client):
        resp = client.get("/es/conjugate")
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")

    def test_page_renders_for_user(self, client):
        login(client)
        resp = client.get("/es/conjugate")
        assert resp.status_code == 200
        assert "Conjugate" in resp.data.decode("utf-8")


class TestAddVerb:
    def test_add_verb_in_pool(self, client):
        login(client)
        resp = client.post("/api/verbs", json={"infinitive": "comer"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["verb"]["infinitive"] == "comer"
        with flask_app.app_context():
            rows = (
                db.session.query(VerbCard).filter_by(user_sub=SAMPLE_USER["sub"]).all()
            )
            assert [r.infinitive for r in rows] == ["comer"]

    def test_add_verb_case_insensitive(self, client):
        login(client)
        resp = client.post("/api/verbs", json={"infinitive": "  Comer "})
        assert resp.status_code == 200
        assert resp.get_json()["verb"]["infinitive"] == "comer"

    def test_add_unsupported_verb_rejected(self, client):
        login(client)
        resp = client.post("/api/verbs", json={"infinitive": "xyzzyfoo"})
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False
        assert data["unsupported"] is True
        with flask_app.app_context():
            assert db.session.query(VerbCard).count() == 0

    def test_add_empty_rejected(self, client):
        login(client)
        resp = client.post("/api/verbs", json={"infinitive": "   "})
        assert resp.status_code == 400
        assert resp.get_json().get("unsupported") is None

    def test_add_duplicate_is_idempotent(self, client):
        login(client)
        client.post("/api/verbs", json={"infinitive": "comer"})
        resp = client.post("/api/verbs", json={"infinitive": "comer"})
        assert resp.status_code == 200
        assert resp.get_json()["duplicate"] is True
        with flask_app.app_context():
            assert db.session.query(VerbCard).count() == 1

    def test_delete_verb(self, client):
        verb_id = add_verb(SAMPLE_USER["sub"], "hablar")
        login(client)
        resp = client.delete(f"/api/verbs/{verb_id}")
        assert resp.status_code == 200
        with flask_app.app_context():
            assert db.session.get(VerbCard, verb_id) is None

    def test_cannot_delete_other_users_verb(self, client):
        verb_id = add_verb(OTHER_USER["sub"], "hablar")
        login(client)
        resp = client.delete(f"/api/verbs/{verb_id}")
        assert resp.status_code == 404


class TestAddVerbFormFallback:
    """The no-JS / JS-error fallback posts form-encoded data to /conjugate/add,
    which must add the verb and redirect (not return raw JSON)."""

    def test_form_add_redirects_and_persists(self, client):
        login(client)
        resp = client.post("/es/conjugate/add", data={"infinitive": "comer"})
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/es/conjugate")
        with flask_app.app_context():
            rows = (
                db.session.query(VerbCard).filter_by(user_sub=SAMPLE_USER["sub"]).all()
            )
            assert [r.infinitive for r in rows] == ["comer"]

    def test_form_add_unsupported_does_not_persist(self, client):
        login(client)
        resp = client.post("/es/conjugate/add", data={"infinitive": "xyzzyfoo"})
        assert resp.status_code == 302
        with flask_app.app_context():
            assert db.session.query(VerbCard).count() == 0

    def test_form_add_duplicate_does_not_duplicate(self, client):
        add_verb(SAMPLE_USER["sub"], "comer")
        login(client)
        resp = client.post("/es/conjugate/add", data={"infinitive": "Comer"})
        assert resp.status_code == 302
        with flask_app.app_context():
            assert db.session.query(VerbCard).count() == 1


class TestSearch:
    def test_search_returns_matches(self, client):
        login(client)
        resp = client.get("/api/verbs/search?q=habl")
        assert resp.status_code == 200
        results = resp.get_json()["results"]
        assert "hablar" in results

    def test_search_excludes_owned(self, client):
        add_verb(SAMPLE_USER["sub"], "hablar")
        login(client)
        results = client.get("/api/verbs/search?q=habl").get_json()["results"]
        assert "hablar" not in results

    def test_search_empty_query(self, client):
        login(client)
        results = client.get("/api/verbs/search?q=").get_json()["results"]
        assert results == []


class TestPracticeStart:
    def test_requires_verbs(self, client):
        login(client)
        resp = client.post(
            "/es/conjugate/practice/start",
            data={"tenses": ["indicativo/presente"]},
        )
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/es/conjugate")

    def test_requires_tenses(self, client):
        add_verb(SAMPLE_USER["sub"], "comer")
        login(client)
        resp = client.post("/es/conjugate/practice/start", data={})
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/es/conjugate")

    def test_builds_session(self, client):
        add_verb(SAMPLE_USER["sub"], "comer")
        login(client)
        resp = client.post(
            "/es/conjugate/practice/start",
            data={
                "tenses": ["indicativo/presente"],
                "difficulty": "advanced",
                "count": "5",
            },
        )
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/es/conjugate/practice")
        with client.session_transaction() as sess:
            state = sess["conjugate_practice"]
            assert state["tenses"] == ["indicativo/presente"]
            assert state["count"] == 5
            # vosotros excluded by default
            assert 4 not in state["persons"]

    def test_vosotros_toggle_includes_person(self, client):
        add_verb(SAMPLE_USER["sub"], "comer")
        login(client)
        client.post(
            "/es/conjugate/practice/start",
            data={
                "tenses": ["indicativo/presente"],
                "include_vosotros": "1",
            },
        )
        with client.session_transaction() as sess:
            assert 4 in sess["conjugate_practice"]["persons"]


class TestPracticeFlow:
    def _start(self, client, tense="indicativo/presente", difficulty="advanced"):
        client.post(
            "/es/conjugate/practice/start",
            data={"tenses": [tense], "difficulty": difficulty, "count": "10"},
        )

    def test_correct_answer_scores_and_updates_verb(self, client):
        verb_id = add_verb(SAMPLE_USER["sub"], "comer")
        login(client)
        self._start(client)
        # Render the question, then read the correct answer from session state.
        client.get("/es/conjugate/practice")
        with client.session_transaction() as sess:
            current = sess["conjugate_practice"]["current"]
            correct = current["correct_answer"]
        resp = client.post("/es/conjugate/practice", data={"answer": correct})
        assert resp.status_code == 302
        with client.session_transaction() as sess:
            state = sess["conjugate_practice"]
            assert state["score"] == 1
            assert state["total"] == 1
        with flask_app.app_context():
            verb = db.session.get(VerbCard, verb_id)
            assert verb.times_practiced == 1
            assert verb.times_correct == 1
            assert verb.score == 1.0

    def test_wrong_answer_counts_attempt_without_score(self, client):
        verb_id = add_verb(SAMPLE_USER["sub"], "comer")
        login(client)
        self._start(client)
        client.get("/es/conjugate/practice")
        resp = client.post("/es/conjugate/practice", data={"answer": "zzzwrong"})
        assert resp.status_code == 302
        with client.session_transaction() as sess:
            state = sess["conjugate_practice"]
            assert state["score"] == 0
            assert state["total"] == 1
        with flask_app.app_context():
            verb = db.session.get(VerbCard, verb_id)
            assert verb.times_practiced == 1
            assert verb.times_correct == 0

    def test_reveal_then_results(self, client):
        add_verb(SAMPLE_USER["sub"], "comer")
        login(client)
        self._start(client)
        client.get("/es/conjugate/practice")
        resp = client.post("/es/conjugate/practice", data={"reveal": "1"})
        assert resp.status_code == 302
        with client.session_transaction() as sess:
            assert sess["conjugate_practice"]["current_revealed"] is True

    def test_answer_post_after_reveal_does_not_double_count(self, client):
        # Regression: the type-to-continue retype form auto-submits via
        # form.submit(), which drops the Next button so the POST arrives with
        # `answer` but no `next`. A revealed question already recorded its
        # attempt, so a stray answer POST must not advance or re-count it —
        # otherwise a 10-question session ends after 5.
        add_verb(SAMPLE_USER["sub"], "comer")
        login(client)
        self._start(client)
        client.get("/es/conjugate/practice")
        client.post("/es/conjugate/practice", data={"reveal": "1"})
        with client.session_transaction() as sess:
            correct = sess["conjugate_practice"]["current"]["correct_answer"]

        # Buggy client: retyped answer without `next`.
        client.post("/es/conjugate/practice", data={"answer": correct})
        with client.session_transaction() as sess:
            state = sess["conjugate_practice"]
        assert state["total"] == 1  # not 2
        assert state["score"] == 0
        assert state["current_revealed"] is True
        assert state["current"] is not None

        # Correct `next` POST advances exactly once.
        client.post("/es/conjugate/practice", data={"answer": correct, "next": "1"})
        with client.session_transaction() as sess:
            state = sess["conjugate_practice"]
        assert state["total"] == 1
        assert state["current"] is None

    def test_accent_insensitive_answer_accepted(self, client):
        # "comió" should accept "comio" (normalize_text strips accents).
        add_verb(SAMPLE_USER["sub"], "comer")
        login(client)
        self._start(client, tense="indicativo/pretérito-perfecto-simple")
        client.get("/es/conjugate/practice")
        with client.session_transaction() as sess:
            correct = sess["conjugate_practice"]["current"]["correct_answer"]
        # Strip accents from the expected answer and submit that.
        import unicodedata

        ascii_answer = "".join(
            c
            for c in unicodedata.normalize("NFD", correct)
            if unicodedata.category(c) != "Mn"
        )
        client.post("/es/conjugate/practice", data={"answer": ascii_answer})
        with client.session_transaction() as sess:
            assert sess["conjugate_practice"]["score"] == 1


class TestHint:
    def _start(self, client, tense="indicativo/presente", difficulty="advanced"):
        client.post(
            "/es/conjugate/practice/start",
            data={"tenses": [tense], "difficulty": difficulty, "count": "10"},
        )

    def _current_answer(self, client):
        client.get("/es/conjugate/practice")
        with client.session_transaction() as sess:
            current = sess["conjugate_practice"]["current"]
        return current["correct_answer"], current["tense_key"], current["person_index"]

    def test_build_hint_structure(self):
        from app import _build_conjugation_hint

        hint = _build_conjugation_hint("es", "indicativo/presente", 1, "en")
        assert hint["blurb"]
        assert [m["infinitive"] for m in hint["models"]] == [
            "hablar",
            "comer",
            "vivir",
        ]
        assert all(len(m["forms"]) == 6 for m in hint["models"])
        assert len(hint["persons"]) == 6
        # Exactly the prompted pronoun's row is flagged.
        assert [p["highlight"] for p in hint["persons"]] == [
            False,
            True,
            False,
            False,
            False,
            False,
        ]

    def test_build_hint_handles_null_person_form(self):
        from app import _build_conjugation_hint

        # The imperative has no "yo" form (index 0 is null in the pool).
        hint = _build_conjugation_hint("es", "imperativo/afirmativo", 0, "en")
        assert hint["models"][0]["forms"][0] is None

    def test_correct_with_hint_awards_half_point(self, client):
        verb_id = add_verb(SAMPLE_USER["sub"], "comer")
        login(client)
        self._start(client)
        correct, tense, person = self._current_answer(client)
        resp = client.post(
            "/es/conjugate/practice", data={"answer": correct, "hint_used": "1"}
        )
        assert resp.status_code == 302
        with client.session_transaction() as sess:
            state = sess["conjugate_practice"]
            assert state["score"] == 0.5
            assert state["total"] == 1
        # Counts as a miss for mastery: no times_correct, recent_results ends '0'.
        with flask_app.app_context():
            verb = db.session.get(VerbCard, verb_id)
            assert verb.times_practiced == 1
            assert verb.times_correct == 0
            assert verb.recent_results.endswith("0")

    def test_hint_correct_records_stat_as_miss(self, client):
        from models import ConjugationStat

        add_verb(SAMPLE_USER["sub"], "comer")
        login(client)
        self._start(client)
        correct, tense, person = self._current_answer(client)
        client.post("/es/conjugate/practice", data={"answer": correct, "hint_used": "1"})
        with flask_app.app_context():
            row = (
                db.session.query(ConjugationStat)
                .filter_by(
                    user_sub=SAMPLE_USER["sub"],
                    tense_key=tense,
                    person_index=person,
                )
                .one()
            )
            assert row.times_practiced == 1
            assert row.times_correct == 0

    def test_correct_without_hint_still_full_point(self, client):
        add_verb(SAMPLE_USER["sub"], "comer")
        login(client)
        self._start(client)
        correct, _, _ = self._current_answer(client)
        client.post("/es/conjugate/practice", data={"answer": correct, "hint_used": "0"})
        with client.session_transaction() as sess:
            assert sess["conjugate_practice"]["score"] == 1

    def test_hint_ignored_in_hardcore(self, client):
        add_verb(SAMPLE_USER["sub"], "comer")
        login(client)
        self._start(client, difficulty="hardcore")
        correct, _, _ = self._current_answer(client)
        client.post("/es/conjugate/practice", data={"answer": correct, "hint_used": "1"})
        with client.session_transaction() as sess:
            assert sess["conjugate_practice"]["score"] == 1


class TestDashboard:
    def _start(self, client, tense="indicativo/presente"):
        client.post(
            "/es/conjugate/practice/start",
            data={"tenses": [tense], "difficulty": "advanced", "count": "10"},
        )

    def _answer_one(self, client, correct):
        client.get("/es/conjugate/practice")
        with client.session_transaction() as sess:
            current = sess["conjugate_practice"]["current"]
            answer = current["correct_answer"] if correct else "zzzwrong"
            tense = current["tense_key"]
            person = current["person_index"]
        client.post("/es/conjugate/practice", data={"answer": answer})
        return tense, person

    def test_attempt_records_conjugation_stat(self, client):
        from models import ConjugationStat

        add_verb(SAMPLE_USER["sub"], "comer")
        login(client)
        self._start(client)
        tense, person = self._answer_one(client, correct=True)
        with flask_app.app_context():
            row = (
                db.session.query(ConjugationStat)
                .filter_by(
                    user_sub=SAMPLE_USER["sub"],
                    tense_key=tense,
                    person_index=person,
                )
                .one()
            )
            assert row.times_practiced == 1
            assert row.times_correct == 1
            assert row.score == 1.0

    def test_dashboard_renders_after_practice(self, client):
        add_verb(SAMPLE_USER["sub"], "comer")
        login(client)
        self._start(client)
        self._answer_one(client, correct=False)
        html = client.get("/es/conjugate").data.decode("utf-8")
        assert "Your insights" in html
        assert "Tenses to practice" in html
        assert "Pronouns to practice" in html

    def test_matrix_renders_with_recap_forms(self, client):
        add_verb(SAMPLE_USER["sub"], "comer")
        login(client)
        self._start(client)
        self._answer_one(client, correct=False)
        html = client.get("/es/conjugate").data.decode("utf-8")
        # Matrix scaffold + category column headers + recap buttons.
        assert "conjugate-matrix" in html
        assert "Unpracticed" in html
        assert "Needs work" in html
        assert 'name="verb_ids"' in html
        assert 'name="persons"' in html

    def test_matrix_data_carries_all_tense_aggregates(self, client):
        import json as _json
        import re

        add_verb(SAMPLE_USER["sub"], "comer")
        login(client)
        # Practice a non-default tense; the default matrix render is scoped to
        # presente, but the embedded JSON must still carry every tense's tally
        # so the client can rebuild for any selection.
        self._start(client, tense="indicativo/futuro")
        self._answer_one(client, correct=False)
        html = client.get("/es/conjugate").data.decode("utf-8")
        blob = re.search(r'id="conjugate-stats-data">(.*?)</script>', html, re.S).group(
            1
        )
        data = _json.loads(blob)
        futuro = next(t for t in data["tenses"] if t["key"] == "indicativo/futuro")
        presente = next(t for t in data["tenses"] if t["key"] == "indicativo/presente")
        assert futuro["practiced"] == 1
        assert presente["practiced"] == 0
        # Verb list and person aggregates are present for client-side rebuilds.
        assert len(data["verbs"]) == 1
        assert any(p["optional"] for p in data["persons"])

    def test_recap_starts_focused_session(self, client):
        verb_id = add_verb(SAMPLE_USER["sub"], "comer")
        login(client)
        # A wrong answer makes "comer" weak and the practiced tense/person weak.
        self._start(client)
        tense, person = self._answer_one(client, correct=False)
        # Recap a single verb on a single tense/person: the session must be
        # restricted to exactly that verb, tense, and person.
        client.post(
            "/es/conjugate/practice/start",
            data={
                "tenses": [tense],
                "verb_ids": [str(verb_id)],
                "persons": [str(person)],
                "difficulty": "advanced",
            },
        )
        with client.session_transaction() as sess:
            state = sess["conjugate_practice"]
            assert state["verb_ids"] == [verb_id]
            assert state["persons"] == [person]
            assert state["tenses"] == [tense]

    def test_recap_rejects_unowned_verb_ids(self, client):
        add_verb(SAMPLE_USER["sub"], "comer")
        login(client)
        resp = client.post(
            "/es/conjugate/practice/start",
            data={
                "tenses": ["indicativo/presente"],
                "verb_ids": ["999999"],
                "difficulty": "advanced",
            },
            follow_redirects=False,
        )
        # Bounced back to /conjugate, no session created.
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/es/conjugate")
        with client.session_transaction() as sess:
            assert "conjugate_practice" not in sess

    def test_dashboard_hidden_without_practice(self, client):
        add_verb(SAMPLE_USER["sub"], "comer")
        login(client)
        html = client.get("/es/conjugate").data.decode("utf-8")
        assert "Your insights" not in html


class TestValidateApi:
    def test_validate_returns_word_feedback(self, client):
        add_verb(SAMPLE_USER["sub"], "comer")
        login(client)
        client.post(
            "/es/conjugate/practice/start",
            data={"tenses": ["indicativo/presente"], "difficulty": "advanced"},
        )
        client.get("/es/conjugate/practice")
        resp = client.post("/api/conjugate/validate", json={"input": "x"})
        assert resp.status_code == 200
        assert "words" in resp.get_json()

    def test_validate_disabled_in_hardcore(self, client):
        add_verb(SAMPLE_USER["sub"], "comer")
        login(client)
        client.post(
            "/es/conjugate/practice/start",
            data={"tenses": ["indicativo/presente"], "difficulty": "hardcore"},
        )
        client.get("/es/conjugate/practice")
        resp = client.post("/api/conjugate/validate", json={"input": "x"})
        assert resp.status_code == 400

    def test_validate_no_session(self, client):
        login(client)
        resp = client.post("/api/conjugate/validate", json={"input": "x"})
        assert resp.status_code == 400
