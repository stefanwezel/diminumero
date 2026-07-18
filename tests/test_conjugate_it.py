"""Tests for the Italian verb-conjugation practice section.

The generic conjugation mechanics are covered by tests/test_conjugate.py
(Spanish) and the multi-language plumbing by tests/test_conjugate_de.py; this
file covers what is Italian-specific: the committed Italian pool (auxiliary
choice, -isc- verbs, the imperative's missing io form) and the scoping of the
``it`` pool against the other two.
"""

import pytest

from app import app as flask_app
from languages.it import conjugations as it_conjugations
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


def add_verb(user_sub, infinitive, lang="it"):
    with flask_app.app_context():
        verb = VerbCard(user_sub=user_sub, lang=lang, infinitive=infinitive)
        db.session.add(verb)
        db.session.commit()
        return verb.id


# ----- The committed Italian pool --------------------------------------------


def test_global_pool_has_common_verbs():
    for v in ("essere", "avere", "fare", "parlare", "capire"):
        assert it_conjugations.verb_exists(v), v


def test_pool_forms_spot_checks():
    essere = it_conjugations.get_verb_forms("essere")
    assert essere["indicativo/presente"] == [
        "sono",
        "sei",
        "è",
        "siamo",
        "siete",
        "sono",
    ]
    # -isc- verbs insert the infix everywhere except noi/voi.
    capire = it_conjugations.get_verb_forms("capire")
    assert capire["indicativo/presente"] == [
        "capisco",
        "capisci",
        "capisce",
        "capiamo",
        "capite",
        "capiscono",
    ]
    # Composite tenses pick the right auxiliary, with plural agreement
    # for essere verbs.
    parlare = it_conjugations.get_verb_forms("parlare")
    assert parlare["indicativo/passato-prossimo"][0] == "ho parlato"
    andare = it_conjugations.get_verb_forms("andare")
    assert andare["indicativo/passato-prossimo"][0] == "sono andato"
    assert andare["indicativo/passato-prossimo"][3] == "siamo andati"
    # piacere/riuscire are essere verbs (verbecc's data wrongly says avere;
    # the generator forces the correct auxiliary).
    piacere = it_conjugations.get_verb_forms("piacere")
    assert piacere["indicativo/passato-prossimo"][2] == "è piaciuto"
    # The imperative has no io form.
    assert parlare["imperativo/affermativo"][0] is None
    assert parlare["imperativo/affermativo"][1] == "parla"


def test_search_ranks_frequency_order():
    # "parlare" is the most common pa* verb, so it comes back first.
    results = it_conjugations.search_verbs("pa")
    assert results[0] == "parlare"


# ----- Lang scoping -----------------------------------------------------------


class TestAddItalianVerb:
    def test_add_verb_with_lang(self, client):
        login(client)
        resp = client.post("/api/verbs", json={"infinitive": "parlare", "lang": "it"})
        assert resp.status_code == 200
        assert resp.get_json()["verb"]["lang"] == "it"
        with flask_app.app_context():
            verb = db.session.query(VerbCard).one()
            assert (verb.lang, verb.infinitive) == ("it", "parlare")

    def test_italian_verb_rejected_in_other_pools(self, client):
        login(client)
        for lang in ("es", "de"):
            resp = client.post(
                "/api/verbs", json={"infinitive": "parlare", "lang": lang}
            )
            assert resp.status_code == 400, lang
            assert resp.get_json()["unsupported"] is True

    def test_foreign_verbs_rejected_in_italian_pool(self, client):
        login(client)
        for verb in ("hablar", "machen"):
            resp = client.post("/api/verbs", json={"infinitive": verb, "lang": "it"})
            assert resp.status_code == 400, verb

    def test_search_italian_pool(self, client):
        login(client)
        results = client.get("/api/verbs/search?q=parl&lang=it").get_json()["results"]
        assert "parlare" in results


class TestManagePage:
    def test_italian_page_renders_without_optional_person_toggle(self, client):
        add_verb(SAMPLE_USER["sub"], "parlare")
        login(client)
        html = client.get("/it/conjugate").data.decode("utf-8")
        assert "Passato prossimo" in html
        assert "include_vosotros" not in html

    def test_verb_lists_are_isolated_per_lang(self, client):
        add_verb(SAMPLE_USER["sub"], "parlare", lang="it")
        add_verb(SAMPLE_USER["sub"], "comer", lang="es")
        add_verb(SAMPLE_USER["sub"], "machen", lang="de")
        login(client)
        it_html = client.get("/it/conjugate").data.decode("utf-8")
        assert "parlare" in it_html
        assert "comer" not in it_html and "machen" not in it_html


class TestItalianPractice:
    def _start(self, client, **overrides):
        data = {
            "tenses": "indicativo/presente",
            "difficulty": "hardcore",
            "sampling_mode": "random",
            "count": "3",
        }
        data.update(overrides)
        return client.post("/it/conjugate/practice/start", data=data)

    def test_start_records_lang_and_all_six_persons(self, client):
        add_verb(SAMPLE_USER["sub"], "parlare")
        login(client)
        resp = self._start(client)
        assert resp.status_code == 302
        with client.session_transaction() as sess:
            state = sess["conjugate_practice"]
            assert state["lang"] == "it"
            assert state["persons"] == [0, 1, 2, 3, 4, 5]

    def test_question_uses_italian_pool_and_scores(self, client):
        verb_id = add_verb(SAMPLE_USER["sub"], "parlare")
        login(client)
        self._start(client)
        assert client.get("/it/conjugate/practice").status_code == 200
        with client.session_transaction() as sess:
            current = sess["conjugate_practice"]["current"]
        forms = it_conjugations.get_verb_forms("parlare")
        assert (
            current["correct_answer"]
            == forms[current["tense_key"]][current["person_index"]]
        )
        resp = client.post(
            "/it/conjugate/practice", data={"answer": current["correct_answer"]}
        )
        assert resp.status_code == 302
        with flask_app.app_context():
            verb = db.session.get(VerbCard, verb_id)
            assert verb.times_practiced == 1
            assert verb.times_correct == 1
            stat = db.session.query(ConjugationStat).one()
            assert stat.lang == "it"

    def test_imperative_never_asks_io(self, client):
        add_verb(SAMPLE_USER["sub"], "parlare")
        login(client)
        self._start(client, tenses="imperativo/affermativo", count="5")
        for _ in range(5):
            client.get("/it/conjugate/practice")
            with client.session_transaction() as sess:
                current = sess["conjugate_practice"].get("current")
            if current is None:
                break
            assert current["person_index"] != 0
            client.post("/it/conjugate/practice", data={"answer": "x"})

    def test_advanced_mode_hint_uses_italian_model_verbs(self, client):
        add_verb(SAMPLE_USER["sub"], "parlare")
        login(client)
        self._start(client, difficulty="advanced")
        html = client.get("/it/conjugate/practice").data.decode("utf-8")
        assert "credere" in html and "dormire" in html


def test_sitemap_lists_italian_conjugation_learn_page(client):
    xml = client.get("/sitemap.xml").data.decode("utf-8")
    assert "/it/learn/conjugations" in xml


def test_learn_page_loads_english_and_italian_ui(client):
    resp = client.get("/it/learn/conjugations")
    assert resp.status_code == 200
    assert b"-are" in resp.data
    client.get("/set_language/it")
    resp = client.get("/it/learn/conjugations")
    assert resp.status_code == 200
    assert "coniugazione".encode() in resp.data
