"""Tests for the German verb-conjugation practice section.

The generic conjugation mechanics (practice flow, scoring, hints, dashboard)
are covered by tests/test_conjugate.py against Spanish; this file covers what
is German- or multi-language-specific: the committed German pool, the ``lang``
scoping of verbs/stats/API endpoints, and the isolation between the two pools.
"""

import pytest

from app import app as flask_app
from languages.de import conjugations as de_conjugations
from models import ConjugationStat, VerbCard, db


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


def login(client, user=SAMPLE_USER):
    with client.session_transaction() as sess:
        sess["user"] = user


def add_verb(user_sub, infinitive, lang="de"):
    with flask_app.app_context():
        verb = VerbCard(user_sub=user_sub, lang=lang, infinitive=infinitive)
        db.session.add(verb)
        db.session.commit()
        return verb.id


# ----- The committed German pool --------------------------------------------


def test_global_pool_has_common_verbs():
    for v in ("sein", "haben", "machen", "gehen", "aufstehen"):
        assert de_conjugations.verb_exists(v), v


def test_pool_forms_spot_checks():
    machen = de_conjugations.get_verb_forms("machen")
    assert machen["indikativ/praesens"] == [
        "mache",
        "machst",
        "macht",
        "machen",
        "macht",
        "machen",
    ]
    assert machen["indikativ/perfekt"][0] == "habe gemacht"
    # Separable verb: finite forms split, participle doesn't.
    aufstehen = de_conjugations.get_verb_forms("aufstehen")
    assert aufstehen["indikativ/praesens"][0] == "stehe auf"
    assert aufstehen["indikativ/perfekt"][0] == "bin aufgestanden"
    # Imperative has no ich/er/wir forms.
    assert machen["imperativ"][0] is None
    assert machen["imperativ"][1] == "mach"
    # Modals have no imperative at all.
    koennen = de_conjugations.get_verb_forms("können")
    assert koennen["imperativ"] == [None] * 6
    assert koennen["konjunktiv-2"][0] == "könnte"


def test_search_is_umlaut_insensitive():
    assert "können" in de_conjugations.search_verbs("konn")


# ----- Lang-scoped verb management ------------------------------------------


class TestAddGermanVerb:
    def test_add_verb_with_lang(self, client):
        login(client)
        resp = client.post("/api/verbs", json={"infinitive": "machen", "lang": "de"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["verb"]["lang"] == "de"
        with flask_app.app_context():
            verb = db.session.query(VerbCard).one()
            assert (verb.lang, verb.infinitive) == ("de", "machen")

    def test_german_verb_rejected_in_spanish_pool(self, client):
        login(client)
        resp = client.post("/api/verbs", json={"infinitive": "machen", "lang": "es"})
        assert resp.status_code == 400
        assert resp.get_json()["unsupported"] is True

    def test_spanish_verb_rejected_in_german_pool(self, client):
        login(client)
        resp = client.post("/api/verbs", json={"infinitive": "comer", "lang": "de"})
        assert resp.status_code == 400
        assert resp.get_json()["unsupported"] is True

    def test_missing_lang_defaults_to_spanish(self, client):
        login(client)
        resp = client.post("/api/verbs", json={"infinitive": "comer"})
        assert resp.status_code == 200
        assert resp.get_json()["verb"]["lang"] == "es"

    def test_form_fallback_uses_route_lang(self, client):
        login(client)
        resp = client.post("/de/conjugate/add", data={"infinitive": "machen"})
        assert resp.status_code == 302
        with flask_app.app_context():
            assert db.session.query(VerbCard).one().lang == "de"

    def test_same_user_same_spelling_allowed_across_pools(self, client):
        # Not a real overlap today (es/de infinitive endings differ), but the
        # duplicate check must be per-pool.
        add_verb(SAMPLE_USER["sub"], "machen", lang="es")  # pretend-owned in es
        login(client)
        resp = client.post("/api/verbs", json={"infinitive": "machen", "lang": "de"})
        assert resp.status_code == 200
        assert "duplicate" not in resp.get_json()


class TestSearchLang:
    def test_search_german_pool(self, client):
        login(client)
        resp = client.get("/api/verbs/search?q=mach&lang=de")
        assert "machen" in resp.get_json()["results"]

    def test_search_excludes_owned_in_same_lang_only(self, client):
        add_verb(SAMPLE_USER["sub"], "machen", lang="de")
        login(client)
        results = client.get("/api/verbs/search?q=mach&lang=de").get_json()["results"]
        assert "machen" not in results

    def test_search_defaults_to_spanish_pool(self, client):
        login(client)
        results = client.get("/api/verbs/search?q=mach").get_json()["results"]
        assert "machen" not in results


class TestManagePage:
    def test_german_page_renders_without_vosotros_toggle(self, client):
        # The practice form (and thus the toggle) only renders once the user
        # owns at least one verb.
        add_verb(SAMPLE_USER["sub"], "machen", lang="de")
        login(client)
        html = client.get("/de/conjugate").data.decode("utf-8")
        assert "Präsens" in html
        assert "include_vosotros" not in html

    def test_spanish_page_keeps_vosotros_toggle(self, client):
        add_verb(SAMPLE_USER["sub"], "comer", lang="es")
        login(client)
        html = client.get("/es/conjugate").data.decode("utf-8")
        assert "include_vosotros" in html

    def test_verb_lists_are_isolated_per_lang(self, client):
        add_verb(SAMPLE_USER["sub"], "machen", lang="de")
        add_verb(SAMPLE_USER["sub"], "comer", lang="es")
        login(client)
        de_html = client.get("/de/conjugate").data.decode("utf-8")
        es_html = client.get("/es/conjugate").data.decode("utf-8")
        assert "machen" in de_html and "comer" not in de_html
        assert "comer" in es_html


# ----- German practice flow --------------------------------------------------


class TestGermanPractice:
    def _start(self, client, **overrides):
        data = {
            "tenses": "indikativ/praesens",
            "difficulty": "hardcore",
            "sampling_mode": "random",
            "count": "3",
        }
        data.update(overrides)
        return client.post("/de/conjugate/practice/start", data=data)

    def test_start_records_lang_and_all_six_persons(self, client):
        add_verb(SAMPLE_USER["sub"], "machen")
        login(client)
        resp = self._start(client)
        assert resp.status_code == 302
        with client.session_transaction() as sess:
            state = sess["conjugate_practice"]
            assert state["lang"] == "de"
            # No optional person in German: all six slots are always in play.
            assert state["persons"] == [0, 1, 2, 3, 4, 5]

    def test_question_uses_german_pool_and_scores(self, client):
        verb_id = add_verb(SAMPLE_USER["sub"], "machen")
        login(client)
        self._start(client)
        assert client.get("/de/conjugate/practice").status_code == 200
        with client.session_transaction() as sess:
            current = sess["conjugate_practice"]["current"]
        forms = de_conjugations.get_verb_forms("machen")
        assert (
            current["correct_answer"]
            == forms[current["tense_key"]][current["person_index"]]
        )
        resp = client.post(
            "/de/conjugate/practice", data={"answer": current["correct_answer"]}
        )
        assert resp.status_code == 302
        with flask_app.app_context():
            verb = db.session.get(VerbCard, verb_id)
            assert verb.times_practiced == 1
            assert verb.times_correct == 1
            stat = db.session.query(ConjugationStat).one()
            assert stat.lang == "de"
            assert stat.tense_key == current["tense_key"]

    def test_practice_only_draws_from_german_verbs(self, client):
        add_verb(SAMPLE_USER["sub"], "machen", lang="de")
        add_verb(SAMPLE_USER["sub"], "comer", lang="es")
        login(client)
        self._start(client, count="10")
        for _ in range(5):
            client.get("/de/conjugate/practice")
            with client.session_transaction() as sess:
                current = sess["conjugate_practice"].get("current")
            if current is None:
                break
            assert current["infinitive"] == "machen"
            client.post("/de/conjugate/practice", data={"answer": "x"})

    def test_advanced_mode_hint_uses_german_model_verbs(self, client):
        add_verb(SAMPLE_USER["sub"], "machen")
        login(client)
        self._start(client, difficulty="advanced")
        html = client.get("/de/conjugate/practice").data.decode("utf-8")
        # The pattern-hint table is built from the German model verbs.
        assert "arbeiten" in html and "fahren" in html
        assert "ich" in html and "ihr" in html

    def test_session_for_other_lang_is_not_shared(self, client):
        add_verb(SAMPLE_USER["sub"], "comer", lang="es")
        login(client)
        client.post(
            "/es/conjugate/practice/start",
            data={"tenses": "indicativo/presente", "count": "3"},
        )
        # A German practice request must not consume the Spanish session.
        resp = client.get("/de/conjugate/practice")
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/de/conjugate")
        with client.session_transaction() as sess:
            assert sess["conjugate_practice"]["lang"] == "es"

    def test_results_for_other_lang_leave_session_alone(self, client):
        add_verb(SAMPLE_USER["sub"], "comer", lang="es")
        login(client)
        client.post(
            "/es/conjugate/practice/start",
            data={"tenses": "indicativo/presente", "count": "3"},
        )
        client.get("/de/conjugate/practice/results")
        with client.session_transaction() as sess:
            assert "conjugate_practice" in sess


class TestDashboardLangScope:
    def test_stats_are_scoped_per_lang(self, client):
        add_verb(SAMPLE_USER["sub"], "machen", lang="de")
        login(client)
        client.post(
            "/de/conjugate/practice/start",
            data={"tenses": "indikativ/praesens", "count": "1"},
        )
        client.get("/de/conjugate/practice")
        with client.session_transaction() as sess:
            answer = sess["conjugate_practice"]["current"]["correct_answer"]
        client.post("/de/conjugate/practice", data={"answer": answer})
        # The German dashboard shows the attempt; the Spanish one is untouched.
        de_html = client.get("/de/conjugate").data.decode("utf-8")
        es_html = client.get("/es/conjugate").data.decode("utf-8")
        assert "conjugate-stats-section" in de_html
        assert "conjugate-stats-section" not in es_html


def test_sitemap_lists_german_conjugation_learn_page(client):
    xml = client.get("/sitemap.xml").data.decode("utf-8")
    assert "/de/learn/conjugations" in xml
    assert "/es/learn/conjugations" in xml
