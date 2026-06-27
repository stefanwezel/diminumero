"""Tests for the bidirectional sync between index cards and conjugation verbs."""

import pytest

from app import (
    _card_verb_infinitive,
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
            assert _card_verb_infinitive(card) == "comer"

    def test_back_side_verb_detected(self, app):
        with app.app_context():
            card = Card(user_sub="x", front="to live", back="Vivir")
            assert _card_verb_infinitive(card) == "vivir"

    def test_non_verb_card_not_detected(self, app):
        with app.app_context():
            card = Card(user_sub="x", front="hola", back="hello")
            assert _card_verb_infinitive(card) is None

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
            assert [inf for _c, inf in importable] == ["comer"]

    def test_verbs_missing_from_cards(self, app):
        with app.app_context():
            sub = "auth0|user-1"
            verbs = [
                VerbCard(user_sub=sub, infinitive="comer"),
                VerbCard(user_sub=sub, infinitive="vivir"),
            ]
            cards = [Card(user_sub=sub, front="comer", back="to eat")]
            assert [v.infinitive for v in _verbs_missing_from_cards(verbs, cards)] == [
                "vivir"
            ]


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
