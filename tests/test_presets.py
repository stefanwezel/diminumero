"""Tests for shareable drill preset links.

A teacher pastes /es/numbers?range=1-100&mode=listening&magnitude=2 into
Moodle; a student with no session, no cookies and no account must land in
that exact drill. These cover the happy path plus every way a pasted link
can be wrong.
"""

import pytest
from app import app as flask_app
from languages import get_language_numbers

NUMBERS_ES = get_language_numbers("es")


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


class TestValidParams:
    """A well-formed link produces exactly the configured drill."""

    def test_mode_and_magnitude_land_in_session(self, client):
        response = client.get("/es/numbers?mode=hardcore&magnitude=3")
        assert response.status_code == 200

        with client.session_transaction() as sess:
            assert sess["mode"] == "hardcore"
            assert sess["magnitude_level"] == 3
            assert sess["learn_language"] == "es"
            assert sess["score"] == 0
            assert sess["total_questions"] == 0

    def test_renders_the_drill_not_the_config_screen(self, client):
        """The response is the quiz itself — no redirect, no mode picker."""
        data = client.get("/es/numbers?mode=advanced").data.decode("utf-8")
        assert "Start Easy Mode" not in data
        assert "/es/quiz/advanced" in data

    def test_question_falls_inside_the_requested_range(self, client):
        client.get("/es/numbers?mode=easy&range=1-100")

        with client.session_transaction() as sess:
            assert sess["number_range"] == [1, 100]
            assert 1 <= sess["current_number"] <= 100

    def test_range_still_applies_to_later_questions(self, client):
        """The range is session state, not a one-shot filter on question 1."""
        client.get("/es/numbers?mode=easy&range=1-100")

        for _ in range(5):
            with client.session_transaction() as sess:
                answer = sess["correct_answer"]
            client.post("/es/quiz/easy", data={"answer": answer}, follow_redirects=True)
            with client.session_transaction() as sess:
                assert 1 <= sess["current_number"] <= 100

    def test_listening_mode_alias_maps_to_audio(self, client):
        response = client.get("/es/numbers?mode=listening")
        assert response.status_code == 200

        with client.session_transaction() as sess:
            assert sess["mode"] == "audio"
        assert "/es/listen" in response.data.decode("utf-8")

    def test_inverted_range_is_swapped(self, client):
        client.get("/es/numbers?mode=easy&range=100-1")
        with client.session_transaction() as sess:
            assert sess["number_range"] == [1, 100]

    def test_no_params_still_shows_the_config_screen(self, client):
        data = client.get("/es/numbers").data.decode("utf-8")
        assert "Start Easy Mode" in data
        with client.session_transaction() as sess:
            assert "mode" not in sess

    def test_unknown_params_do_not_start_a_drill(self, client):
        """A tracking param tacked onto the link must not launch a quiz."""
        data = client.get("/es/numbers?utm_source=moodle").data.decode("utf-8")
        assert "Start Easy Mode" in data


class TestOutOfRangeValues:
    """Ranges that parse but leave nothing usable fall back to the deck."""

    def test_range_beyond_the_deck_falls_back(self, client):
        response = client.get("/es/numbers?mode=easy&range=50000000-60000000")
        assert response.status_code == 200

        with client.session_transaction() as sess:
            assert "number_range" not in sess
            assert sess["current_number"] in NUMBERS_ES
        assert "using the full range" in response.data.decode("utf-8")

    def test_range_leaving_too_few_numbers_falls_back(self, client):
        """Nepali has exactly one number between 1000 and 10000 — not enough
        for distractors or the no-repeat rule."""
        response = client.get("/ne/numbers?mode=easy&range=1000-10000")
        assert response.status_code == 200

        with client.session_transaction() as sess:
            assert "number_range" not in sess
        assert "using the full range" in response.data.decode("utf-8")

    def test_range_wider_than_the_deck_is_kept(self, client):
        """Overshooting the top of the deck is harmless, not an error."""
        response = client.get("/es/numbers?mode=easy&range=1-99999999")
        assert response.status_code == 200
        assert "using the full range" not in response.data.decode("utf-8")

    def test_magnitude_out_of_bounds_resets_to_one(self, client):
        response = client.get("/es/numbers?magnitude=99")
        assert response.status_code == 200

        with client.session_transaction() as sess:
            assert sess["magnitude_level"] == 1
        assert "number-size setting" in response.data.decode("utf-8")


class TestGarbageValues:
    """Unparseable params never 500 and never blank the quiz."""

    @pytest.mark.parametrize(
        "query",
        [
            "range=abc",
            "range=-5-100",
            "range=1-",
            "range=",
            "range=1--100",
            "range=1;drop",
            "magnitude=x",
            "magnitude=",
            "magnitude=-2",
            "mode=telepathy",
            "mode=",
            "mode=easy&range=%%%&magnitude=NaN",
        ],
    )
    def test_garbage_renders_a_working_drill(self, client, query):
        response = client.get(f"/es/numbers?{query}")
        assert response.status_code == 200

        with client.session_transaction() as sess:
            assert sess["mode"] in ("easy", "advanced", "hardcore", "audio")
            assert sess["magnitude_level"] in range(1, 6)
            # A real question is mounted: the drill is not blank.
            assert sess["current_number"] in NUMBERS_ES

    def test_unknown_mode_notice_and_default(self, client):
        response = client.get("/es/numbers?mode=telepathy")
        with client.session_transaction() as sess:
            assert sess["mode"] == "easy"
        assert "didn&#39;t recognise the practice mode" in response.data.decode("utf-8")

    def test_bad_range_notice_and_default(self, client):
        response = client.get("/es/numbers?range=abc")
        with client.session_transaction() as sess:
            assert "number_range" not in sess
        assert "isn&#39;t valid" in response.data.decode("utf-8")


class TestListeningWithoutAudio:
    """Listening on a language with no MP3s degrades to a working text mode."""

    @pytest.mark.parametrize("lang", ["cy", "ga", "ko", "it"])
    def test_degrades_to_advanced_with_a_notice(self, client, lang):
        response = client.get(f"/{lang}/numbers?mode=listening")
        assert response.status_code == 200
        data = response.data.decode("utf-8")

        with client.session_transaction() as sess:
            assert sess["mode"] == "advanced"
        assert f"/{lang}/quiz/advanced" in data
        assert "Listening practice isn&#39;t available" in data

    def test_no_audio_player_is_rendered(self, client):
        data = client.get("/cy/numbers?mode=listening").data.decode("utf-8")
        assert "<audio" not in data
        assert "audio-play-btn" not in data

    def test_audio_language_keeps_listening(self, client):
        data = client.get("/es/numbers?mode=listening").data.decode("utf-8")
        assert "<audio" in data
        assert "Listening practice isn&#39;t available" not in data


class TestNoSessionAccess:
    """The point of the feature: a cold browser lands in the drill."""

    def test_cold_client_gets_a_question(self, client):
        """No prior request, no cookies, no login."""
        response = client.get("/es/numbers?mode=advanced&range=1-100&magnitude=2")
        assert response.status_code == 200
        data = response.data.decode("utf-8")
        assert "/es/quiz/advanced" in data
        assert "Question 1" in data or "1 / " in data

    def test_stale_session_from_another_drill_is_replaced(self, client):
        """A student who already played must get the teacher's config, not
        their own leftovers."""
        client.post("/de/start", data={"mode": "hardcore", "magnitude_level": 5})
        client.get("/de/quiz/hardcore")

        client.get("/es/numbers?mode=easy&range=1-100&magnitude=2")
        with client.session_transaction() as sess:
            assert sess["learn_language"] == "es"
            assert sess["mode"] == "easy"
            assert sess["magnitude_level"] == 2
            assert sess["number_range"] == [1, 100]
            assert sess["score"] == 0
            assert sess["asked_numbers"] == [sess["current_number"]]

    def test_login_survives_a_preset_link(self, client):
        """Following a shared link must not log a signed-in user out."""
        with client.session_transaction() as sess:
            sess["user"] = {"sub": "auth0|teacher-1", "name": "Ada"}

        client.get("/es/numbers?mode=easy")
        with client.session_transaction() as sess:
            assert sess["user"]["sub"] == "auth0|teacher-1"


class TestPresetSeo:
    """Parameterised URLs must not fragment the index."""

    def test_param_url_is_noindex(self, client):
        data = client.get("/es/numbers?mode=easy").data.decode("utf-8")
        assert '<meta name="robots" content="noindex, nofollow">' in data

    def test_param_url_canonical_points_at_the_clean_route(self, client):
        data = client.get("/es/numbers?mode=easy&range=1-100").data.decode("utf-8")
        assert '<link rel="canonical" href="https://diminumero.com/es/numbers">' in data
        assert "range=1-100" not in data.split("<body")[0]

    def test_clean_config_screen_is_indexable(self, client):
        data = client.get("/es/numbers").data.decode("utf-8")
        assert "noindex" not in data

    def test_preset_response_is_not_cacheable(self, client):
        """It carries a live question and a Set-Cookie."""
        response = client.get("/es/numbers?mode=easy")
        assert "no-store" in response.headers["Cache-Control"]


class TestShareLinkControl:
    """The copy-link control on the config screen."""

    def test_builder_is_rendered_with_deck_bounds(self, client):
        """Bounds come from the deck, so they can't drift out of date here."""
        data = client.get("/es/numbers").data.decode("utf-8")
        assert 'id="preset-share"' in data
        assert f'data-deck-min="{min(NUMBERS_ES)}"' in data
        assert f'data-deck-max="{max(NUMBERS_ES)}"' in data
        assert "js/preset_link.js" in data

    def test_listening_option_only_for_audio_languages(self, client):
        assert 'value="listening"' in client.get("/es/numbers").data.decode("utf-8")
        assert 'value="listening"' not in client.get("/cy/numbers").data.decode("utf-8")

    def test_start_form_carries_the_range(self, client):
        """The hidden input the builder writes into is present and honoured."""
        data = client.get("/es/numbers").data.decode("utf-8")
        assert "preset-range-hidden-input" in data

        client.post("/es/start", data={"mode": "easy", "range": "1-100"})
        with client.session_transaction() as sess:
            assert sess["number_range"] == [1, 100]

    def test_start_form_ignores_a_bad_range(self, client):
        client.post("/es/start", data={"mode": "easy", "range": "nonsense"})
        with client.session_transaction() as sess:
            assert "number_range" not in sess
            assert sess["mode"] == "easy"
