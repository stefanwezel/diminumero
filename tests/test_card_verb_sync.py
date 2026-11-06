"""Tests for the bidirectional sync between index cards and conjugation verbs."""

import pytest

from app import (
    _card_verb_match,
    _importable_card_verbs,
    _verbs_missing_from_cards,
    app as flask_app,
)
from models import Card, VerbCard, db


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


def make_card(user_sub, front, back):
    with flask_app.app_context():
        card = Card(user_sub=user_sub, front=front, back=back)
        db.session.add(card)
        db.session.commit()
        return card.id


def add_verb(user_sub, infinitive):
    with flask_app.app_context():
        verb = VerbCard(user_sub=user_sub, infinitive=infinitive)
        db.session.add(verb)
        db.session.commit()
        return verb.id


class TestDetection:
    def test_front_side_verb_detected(self, app):
        with app.app_context():
            card = Card(user_sub="x", front="comer", back="to eat")
            assert _card_verb_match(card) == ("es", "comer")

    def test_back_side_verb_detected(self, app):
        with app.app_context():
            card = Card(user_sub="x", front="to live", back="Vivir")
            assert _card_verb_match(card) == ("es", "vivir")

    def test_german_verb_detected_with_lang(self, app):
        with app.app_context():
            card = Card(user_sub="x", front="machen", back="to do")
            assert _card_verb_match(card) == ("de", "machen")

    def test_non_verb_card_not_detected(self, app):
        with app.app_context():
            card = Card(user_sub="x", front="hola", back="hello")
            assert _card_verb_match(card) is None

    def test_importable_excludes_owned_and_dedupes(self, app):
        with app.app_context():
            sub = "auth0|user-1"
            db.session.add(VerbCard(user_sub=sub, infinitive="hablar"))
            cards = [
                Card(user_sub=sub, front="comer", back="to eat"),
                Card(user_sub=sub, front="to eat too", back="comer"),  # dup verb
                Card(user_sub=sub, front="hablar", back="to speak"),  # owned
                Card(user_sub=sub, front="hola", back="hello"),  # not a verb
            ]
            db.session.add_all(cards)
            db.session.commit()
            importable = _importable_card_verbs(sub, cards)
            assert [(lang, inf) for _c, lang, inf in importable] == [("es", "comer")]

    def test_importable_lang_filter(self, app):
        with app.app_context():
            sub = "auth0|user-1"
            cards = [
                Card(user_sub=sub, front="comer", back="to eat"),
                Card(user_sub=sub, front="machen", back="to do"),
            ]
            db.session.add_all(cards)
            db.session.commit()
            es_only = _importable_card_verbs(sub, cards, "es")
            de_only = _importable_card_verbs(sub, cards, "de")
            assert [inf for _c, _l, inf in es_only] == ["comer"]
            assert [inf for _c, _l, inf in de_only] == ["machen"]

    def test_verbs_missing_from_cards(self, app):
        with app.app_context():
            sub = "auth0|user-1"
            verbs = [
                VerbCard(user_sub=sub, infinitive="comer"),
                VerbCard(user_sub=sub, infinitive="vivir"),
            ]
            cards = [Card(user_sub=sub, front="comer", back="to eat")]
            assert [
                v.infinitive for v in _verbs_missing_from_cards(verbs, cards, "es")
            ] == ["vivir"]


class TestImportFromCards:
    def test_import_adds_all_importable(self, client):
        make_card(SAMPLE_USER["sub"], "comer", "to eat")
        make_card(SAMPLE_USER["sub"], "to live", "vivir")
        make_card(SAMPLE_USER["sub"], "hola", "hello")
        login(client)
        resp = client.post("/api/verbs/import-from-cards")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["added"] == 2
        with flask_app.app_context():
            owned = {
                v.infinitive
                for v in db.session.query(VerbCard).filter_by(
                    user_sub=SAMPLE_USER["sub"]
                )
            }
            assert owned == {"comer", "vivir"}

    def test_import_is_idempotent(self, client):
        make_card(SAMPLE_USER["sub"], "comer", "to eat")
        login(client)
        client.post("/api/verbs/import-from-cards")
        resp = client.post("/api/verbs/import-from-cards")
        assert resp.get_json()["added"] == 0
        with flask_app.app_context():
            assert (
                db.session.query(VerbCard)
                .filter_by(user_sub=SAMPLE_USER["sub"])
                .count()
                == 1
            )

    def test_import_requires_login(self, client):
        resp = client.post("/api/verbs/import-from-cards")
        assert resp.status_code == 302

    def test_import_ignores_other_users_cards(self, client):
        make_card(OTHER_USER["sub"], "comer", "to eat")
        login(client)
        resp = client.post("/api/verbs/import-from-cards")
        assert resp.get_json()["added"] == 0


class TestCardApiVerbField:
    def test_create_verb_card_reports_infinitive(self, client):
        login(client)
        resp = client.post("/api/cards", json={"front": "abrir", "back": "to open"})
        assert resp.status_code == 200
        assert resp.get_json()["verb_infinitive"] == "abrir"

    def test_create_non_verb_card_reports_none(self, client):
        login(client)
        resp = client.post("/api/cards", json={"front": "hola", "back": "hello"})
        assert resp.get_json()["verb_infinitive"] is None

    def test_create_verb_already_owned_reports_none(self, client):
        add_verb(SAMPLE_USER["sub"], "abrir")
        login(client)
        resp = client.post("/api/cards", json={"front": "abrir", "back": "to open"})
        assert resp.get_json()["verb_infinitive"] is None

    def test_update_to_verb_reports_infinitive(self, client):
        card_id = make_card(SAMPLE_USER["sub"], "hola", "hello")
        login(client)
        resp = client.patch(
            f"/api/cards/{card_id}", json={"front": "abrir", "back": "to open"}
        )
        assert resp.get_json()["verb_infinitive"] == "abrir"


class TestCardsPageExposure:
    def test_verb_card_shows_badge(self, client):
        make_card(SAMPLE_USER["sub"], "comer", "to eat")
        login(client)
        html = client.get("/cards").data.decode("utf-8")
        assert "cards-verb-badge" in html
        assert "cards-verb-add-btn" in html

    def test_non_verb_card_has_no_badge(self, client):
        make_card(SAMPLE_USER["sub"], "hola", "hello")
        login(client)
        html = client.get("/cards").data.decode("utf-8")
        assert "cards-verb-add-btn" not in html

    def test_owned_verb_card_has_no_add_button(self, client):
        make_card(SAMPLE_USER["sub"], "comer", "to eat")
        add_verb(SAMPLE_USER["sub"], "comer")
        login(client)
        html = client.get("/cards").data.decode("utf-8")
        assert "cards-verb-add-btn" not in html


class TestPracticeExposure:
    def _start_and_load(self, client):
        client.post("/cards/practice/start", data={"direction": "front_to_back"})
        return client.get("/cards/practice")

    def test_practice_offers_verb_add(self, client):
        make_card(SAMPLE_USER["sub"], "comer", "to eat")
        login(client)
        html = self._start_and_load(client).data.decode("utf-8")
        assert "cards-practice-verb-add" in html
        assert 'data-infinitive="comer"' in html

    def test_practice_no_offer_when_owned(self, client):
        make_card(SAMPLE_USER["sub"], "comer", "to eat")
        add_verb(SAMPLE_USER["sub"], "comer")
        login(client)
        html = self._start_and_load(client).data.decode("utf-8")
        assert "cards-practice-verb-add" not in html

    def test_practice_no_offer_for_non_verb(self, client):
        make_card(SAMPLE_USER["sub"], "hola", "hello")
        login(client)
        html = self._start_and_load(client).data.decode("utf-8")
        assert "cards-practice-verb-add" not in html


class TestConjugatePageExposure:
    def test_missing_verb_offered_for_card_sync(self, client):
        add_verb(SAMPLE_USER["sub"], "vivir")
        login(client)
        html = client.get("/es/conjugate").data.decode("utf-8")
        assert "conjugate-missing-in-cards" in html
        assert '"infinitive": "vivir"' in html

    def test_import_from_cards_button_counts(self, client):
        make_card(SAMPLE_USER["sub"], "comer", "to eat")
        login(client)
        html = client.get("/es/conjugate").data.decode("utf-8")
        assert "conjugate-import-from-cards" in html
        # The button is visible (not hidden) when there is something to import.
        assert "conjugate-import-from-cards conjugate-sync-hidden" not in html

    def test_missing_verb_row_has_add_to_cards_button(self, client):
        add_verb(SAMPLE_USER["sub"], "vivir")
        login(client)
        html = client.get("/es/conjugate").data.decode("utf-8")
        assert "conjugate-verb-to-card-btn" in html
        assert 'data-infinitive="vivir"' in html

    def test_verb_already_in_cards_has_no_add_to_cards_button(self, client):
        make_card(SAMPLE_USER["sub"], "vivir", "to live")
        add_verb(SAMPLE_USER["sub"], "vivir")
        login(client)
        html = client.get("/es/conjugate").data.decode("utf-8")
        assert "conjugate-verb-to-card-btn" not in html


class TestAdditiveOnly:
    def test_deleting_card_keeps_verb(self, client):
        card_id = make_card(SAMPLE_USER["sub"], "comer", "to eat")
        login(client)
        client.post("/api/verbs", json={"infinitive": "comer"})
        client.delete(f"/api/cards/{card_id}")
        with flask_app.app_context():
            assert (
                db.session.query(VerbCard)
                .filter_by(user_sub=SAMPLE_USER["sub"])
                .count()
                == 1
            )

    def test_deleting_verb_keeps_card(self, client):
        make_card(SAMPLE_USER["sub"], "comer", "to eat")
        verb_id = add_verb(SAMPLE_USER["sub"], "comer")
        login(client)
        client.delete(f"/api/verbs/{verb_id}")
        with flask_app.app_context():
            assert (
                db.session.query(Card).filter_by(user_sub=SAMPLE_USER["sub"]).count()
                == 1
            )


class TestEnglishIsOptIn:
    """English is the side most cards carry as the translation, and its verbs
    are spelled like its nouns, so it must not join the automatic scan."""

    @pytest.mark.parametrize(
        "front, back, expected",
        [
            # The other side's verb is still the one found, whichever way round.
            ("live", "vivir", ("es", "vivir")),
            ("vivir", "live", ("es", "vivir")),
            ("go", "gehen", ("de", "gehen")),
            ("speak", "parlare", ("it", "parlare")),
            # A noun card is not a verb card because the noun doubles as a verb.
            ("book", "Buch", None),
            ("water", "agua", None),
            ("go", "go", None),
        ],
    )
    def test_automatic_scan_ignores_english(self, app, front, back, expected):
        with app.app_context():
            card = Card(user_sub="x", front=front, back=back)
            assert _card_verb_match(card) == expected

    @pytest.mark.parametrize(
        "front, back",
        [("go", "gehen"), ("gehen", "go"), ("to go", "gehen"), ("gehen", "To Go")],
    )
    def test_english_found_when_asked_for_by_name(self, app, front, back):
        with app.app_context():
            card = Card(user_sub="x", front=front, back=back)
            assert _card_verb_match(card, "en") == ("en", "go")

    def test_cards_page_offers_only_the_other_language(self, client):
        make_card(SAMPLE_USER["sub"], "go", "gehen")
        make_card(SAMPLE_USER["sub"], "book", "Buch")
        login(client)
        html = client.get("/cards").get_data(as_text=True)
        assert 'data-infinitive="gehen"' in html
        assert 'data-infinitive="go"' not in html
        assert 'data-infinitive="book"' not in html

    def test_cards_page_import_leaves_english_out(self, client):
        make_card(SAMPLE_USER["sub"], "go", "gehen")
        login(client)
        assert client.post("/api/verbs/import-from-cards").get_json()["added"] == 1
        with flask_app.app_context():
            verb = db.session.query(VerbCard).one()
            assert (verb.lang, verb.infinitive) == ("de", "gehen")

    def test_english_page_imports_english(self, client):
        make_card(SAMPLE_USER["sub"], "to go", "gehen")
        login(client)
        resp = client.post("/api/verbs/import-from-cards", json={"lang": "en"})
        assert resp.get_json()["added"] == 1
        with flask_app.app_context():
            verb = db.session.query(VerbCard).one()
            assert (verb.lang, verb.infinitive) == ("en", "go")

    def test_a_filtered_pool_is_not_hidden_by_an_earlier_side(self, app):
        """A front in another pool used to hide the back from this page's import."""
        with app.app_context():
            card = Card(user_sub="x", front="machen", back="comer")
            assert _card_verb_match(card) == ("de", "machen")
            assert _card_verb_match(card, "es") == ("es", "comer")

    def test_verb_cited_with_to_counts_as_already_on_a_card(self, app):
        with app.app_context():
            verbs = [VerbCard(user_sub="x", lang="en", infinitive="go")]
            cards = [Card(user_sub="x", front="to go", back="gehen")]
            assert _verbs_missing_from_cards(verbs, cards, "en") == []

    def test_to_only_means_a_citation_in_english(self, app):
        with app.app_context():
            verbs = [VerbCard(user_sub="x", lang="es", infinitive="comer")]
            cards = [Card(user_sub="x", front="to comer", back="essen")]
            assert _verbs_missing_from_cards(verbs, cards, "es") == verbs

    def test_ize_spelling_on_a_card_finds_the_stored_verb(self, app):
        with app.app_context():
            card = Card(user_sub="x", front="realize", back="erkennen")
            assert _card_verb_match(card, "en") == ("en", "realise")

    def test_ize_spelling_counts_as_already_on_a_card(self, app):
        """Otherwise the walk-through would offer a second card for the same verb."""
        with app.app_context():
            verbs = [VerbCard(user_sub="x", lang="en", infinitive="realise")]
            cards = [Card(user_sub="x", front="to realize", back="erkennen")]
            assert _verbs_missing_from_cards(verbs, cards, "en") == []


def learn(client, lang):
    with client.session_transaction() as sess:
        sess["learn_language"] = lang


class TestLearningEnglish:
    """For someone learning English, English is the verb, not the translation."""

    @pytest.mark.parametrize(
        "front, back", [("go", "gehen"), ("gehen", "go"), ("to go", "gehen")]
    )
    def test_cards_page_offers_the_english_side(self, client, front, back):
        make_card(SAMPLE_USER["sub"], front, back)
        login(client)
        learn(client, "en")
        html = client.get("/cards").get_data(as_text=True)
        assert 'data-infinitive="go"' in html
        assert 'data-infinitive="gehen"' not in html

    def test_a_card_with_no_english_verb_still_finds_the_other_one(self, client):
        make_card(SAMPLE_USER["sub"], "gehen", "laufen zu Fuß")
        login(client)
        learn(client, "en")
        html = client.get("/cards").get_data(as_text=True)
        assert 'data-infinitive="gehen"' in html

    def test_owning_the_english_verb_does_not_offer_the_other_side(self, client):
        make_card(SAMPLE_USER["sub"], "go", "gehen")
        with flask_app.app_context():
            db.session.add(
                VerbCard(user_sub=SAMPLE_USER["sub"], lang="en", infinitive="go")
            )
            db.session.commit()
        login(client)
        learn(client, "en")
        assert "cards-verb-add-btn" not in client.get("/cards").get_data(as_text=True)

    def test_card_api_reports_the_english_verb(self, client):
        login(client)
        learn(client, "en")
        data = client.post("/api/cards", json={"front": "go", "back": "gehen"})
        assert data.get_json()["verb_infinitive"] == "go"
        assert data.get_json()["verb_lang"] == "en"

    def test_practice_offers_the_english_verb(self, client):
        make_card(SAMPLE_USER["sub"], "go", "gehen")
        login(client)
        learn(client, "en")
        client.post("/cards/practice/start", data={"direction": "front_to_back"})
        html = client.get("/cards/practice").get_data(as_text=True)
        assert 'data-infinitive="go"' in html
        assert 'data-verb-lang="en"' in html

    @pytest.mark.parametrize("lang", ["de", "es", "fr"])
    def test_learning_anything_else_keeps_english_out(self, client, lang):
        make_card(SAMPLE_USER["sub"], "go", "gehen")
        login(client)
        learn(client, lang)
        html = client.get("/cards").get_data(as_text=True)
        assert 'data-infinitive="gehen"' in html
        assert 'data-infinitive="go"' not in html


class TestImportChecklist:
    """Nothing is imported until the person who wrote the cards has seen the list."""

    def test_candidates_come_with_their_card(self, client):
        make_card(SAMPLE_USER["sub"], "Land", "country")
        login(client)
        data = client.get("/api/verbs/import-from-cards?lang=en").get_json()
        assert data["verbs"] == [
            {"lang": "en", "infinitive": "land", "front": "Land", "back": "country"}
        ]

    def test_listing_candidates_adds_nothing(self, client):
        make_card(SAMPLE_USER["sub"], "comer", "to eat")
        login(client)
        client.get("/api/verbs/import-from-cards")
        with flask_app.app_context():
            assert db.session.query(VerbCard).count() == 0

    def test_candidates_require_login(self, client):
        assert client.get("/api/verbs/import-from-cards").status_code == 302

    def test_candidates_leave_out_other_users_cards(self, client):
        make_card(OTHER_USER["sub"], "comer", "to eat")
        login(client)
        assert client.get("/api/verbs/import-from-cards").get_json()["verbs"] == []

    def test_only_ticked_verbs_are_imported(self, client):
        make_card(SAMPLE_USER["sub"], "to go", "gehen")
        make_card(SAMPLE_USER["sub"], "Land", "country")
        login(client)
        data = client.post(
            "/api/verbs/import-from-cards",
            json={"lang": "en", "verbs": [{"lang": "en", "infinitive": "go"}]},
        ).get_json()
        assert (data["added"], data["remaining"]) == (1, 1)
        assert [v["infinitive"] for v in data["verbs"]] == ["go"]
        with flask_app.app_context():
            assert db.session.query(VerbCard).one().infinitive == "go"

    def test_an_unticked_verb_is_still_offered_afterwards(self, client):
        make_card(SAMPLE_USER["sub"], "to go", "gehen")
        make_card(SAMPLE_USER["sub"], "Land", "country")
        login(client)
        client.post(
            "/api/verbs/import-from-cards",
            json={"lang": "en", "verbs": [{"lang": "en", "infinitive": "go"}]},
        )
        left = client.get("/api/verbs/import-from-cards?lang=en").get_json()["verbs"]
        assert [v["infinitive"] for v in left] == ["land"]

    def test_an_empty_list_imports_nothing(self, client):
        """Not the same as leaving the list out."""
        make_card(SAMPLE_USER["sub"], "comer", "to eat")
        login(client)
        data = client.post("/api/verbs/import-from-cards", json={"verbs": []})
        assert data.get_json()["added"] == 0

    @pytest.mark.parametrize(
        "junk",
        [
            [{"lang": "en", "infinitive": "fly"}],
            [{"lang": "xx", "infinitive": "comer"}],
            ["comer", 3, None],
            [{"lang": [], "infinitive": {}}],
        ],
    )
    def test_a_verb_that_is_not_a_candidate_is_ignored(self, client, junk):
        make_card(SAMPLE_USER["sub"], "comer", "to eat")
        login(client)
        data = client.post("/api/verbs/import-from-cards", json={"verbs": junk})
        assert data.get_json()["added"] == 0
        with flask_app.app_context():
            assert db.session.query(VerbCard).count() == 0

    @pytest.mark.parametrize("page", ["/cards", "/en/conjugate", "/es/conjugate"])
    def test_pages_with_an_import_button_carry_the_checklist(self, client, page):
        make_card(SAMPLE_USER["sub"], "comer", "to eat")
        login(client)
        html = client.get(page).get_data(as_text=True)
        assert 'id="verb-import-modal"' in html
        assert "js/verb_import_picker.js" in html
