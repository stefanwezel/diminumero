"""Tests for the Listening overview screen.

Listening used to have no configuration surface at all: the menu tile posted
straight into a drill, so the magnitude dial was whatever the number screen
had last set and a listening round could not be shared. /<lang>/listening is
the listening twin of /<lang>/numbers — same preset-link contract, minus the
mode picker, because the mode here is listening.
"""

import pytest
from app import app as flask_app
from app import _available_audio_numbers
from languages import get_language_numbers

# What a Spanish listening drill may actually ask: the deck narrowed to the
# numbers we have an MP3 for.
PLAYABLE_ES = sorted(set(get_language_numbers("es")) & _available_audio_numbers("es"))


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


class TestOverviewPage:
    def test_renders_the_config_screen_not_a_drill(self, client):
        response = client.get("/es/listening")
        assert response.status_code == 200
        data = response.data.decode("utf-8")

        assert "/es/listen/start" in data
        # No question is mounted: the page configures a drill, it isn't one.
        assert "<audio" not in data
        with client.session_transaction() as sess:
            assert "current_number" not in sess

    def test_has_the_magnitude_dial(self, client):
        data = client.get("/es/listening").data.decode("utf-8")
        assert 'id="magnitude-slider"' in data
        assert "magnitude-hidden-input" in data

    def test_has_the_share_builder_bounded_by_the_playable_deck(self, client):
        """Bounds are what can be *heard*, not what the deck holds: a range
        with no MP3s in it is a drill with nothing to play."""
        data = client.get("/es/listening").data.decode("utf-8")
        assert 'id="preset-share"' in data
        assert f'data-deck-min="{min(PLAYABLE_ES)}"' in data
        assert f'data-deck-max="{max(PLAYABLE_ES)}"' in data
        assert "js/preset_link.js" in data

    def test_share_builder_has_no_mode_picker(self, client):
        """This page shares listening drills; there is nothing to choose."""
        data = client.get("/es/listening").data.decode("utf-8")
        assert 'name="preset-mode"' not in data

    def test_is_indexable(self, client):
        data = client.get("/es/listening").data.decode("utf-8")
        assert "noindex" not in data

    def test_listed_in_the_sitemap(self, client):
        data = client.get("/sitemap.xml").data.decode("utf-8")
        assert "https://diminumero.com/es/listening" in data
        assert "https://diminumero.com/cy/listening" not in data


class TestAvailability:
    def test_language_without_audio_is_sent_back_to_its_menu(self, client):
        response = client.get("/it/listening")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/it")

    def test_unknown_language_goes_home(self, client):
        response = client.get("/xx/listening")
        assert response.status_code == 302
        assert response.headers["Location"] == "/"

    def test_menu_tile_opens_the_overview(self, client):
        """The tile used to POST straight into a round."""
        data = client.get("/es").data.decode("utf-8")
        assert 'href="/es/listening"' in data
        assert 'action="/es/listen/start"' not in data

    def test_landing_page_ear_opens_the_overview(self, client):
        """The ear badge on a language card used to POST straight into a round,
        so the drill it started was whatever the last session had configured."""
        data = client.get("/").data.decode("utf-8")
        assert 'href="/es/listening"' in data
        assert 'action="/es/listen/start"' not in data

    def test_quiz_without_a_session_lands_on_the_overview(self, client):
        response = client.get("/es/listen")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/es/listening")


class TestStartForm:
    def test_start_seeds_a_listening_session(self, client):
        client.post("/es/listen/start", data={"magnitude_level": "3"})
        with client.session_transaction() as sess:
            assert sess["mode"] == "audio"
            assert sess["magnitude_level"] == 3
            assert sess["learn_language"] == "es"

    def test_start_carries_the_range(self, client):
        """The hidden input the share builder writes into is honoured, so
        pressing Start gives the same drill as the link beside it."""
        assert "preset-range-hidden-input" in client.get("/es/listening").data.decode(
            "utf-8"
        )

        client.post("/es/listen/start", data={"magnitude_level": "1", "range": "1-20"})
        with client.session_transaction() as sess:
            assert sess["number_range"] == [1, 20]

        client.get("/es/listen")
        with client.session_transaction() as sess:
            assert 1 <= sess["current_number"] <= 20

    def test_start_ignores_a_bad_range(self, client):
        client.post("/es/listen/start", data={"range": "nonsense"})
        with client.session_transaction() as sess:
            assert "number_range" not in sess
            assert sess["mode"] == "audio"


class TestSharedLinks:
    """A pasted /es/listening?range=…&magnitude=… lands in the drill itself."""

    def test_params_render_the_drill_in_this_response(self, client):
        response = client.get("/es/listening?magnitude=3")
        assert response.status_code == 200
        data = response.data.decode("utf-8")

        assert "<audio" in data
        assert "/es/listen" in data
        with client.session_transaction() as sess:
            assert sess["mode"] == "audio"
            assert sess["magnitude_level"] == 3
            assert sess["score"] == 0

    def test_range_narrows_the_drill_and_persists(self, client):
        client.get("/es/listening?range=1-20")
        with client.session_transaction() as sess:
            assert sess["number_range"] == [1, 20]
            assert 1 <= sess["current_number"] <= 20

        client.get("/es/listen")
        with client.session_transaction() as sess:
            assert all(1 <= n <= 20 for n in sess["asked_numbers"])

    def test_cold_client_with_no_session_gets_a_question(self, client):
        response = client.get("/es/listening?range=1-100&magnitude=2")
        assert response.status_code == 200
        assert "<audio" in response.data.decode("utf-8")

    def test_range_with_nothing_playable_falls_back_with_a_notice(self, client):
        """Syntactically fine, but no MP3 in it — the student still gets a
        drill rather than a player with nothing to play."""
        response = client.get("/es/listening?range=2000000-2000100")
        assert response.status_code == 200
        data = response.data.decode("utf-8")

        with client.session_transaction() as sess:
            assert "number_range" not in sess
            assert sess["mode"] == "audio"
        assert "preset-notice" in data

    def test_garbage_magnitude_falls_back_with_a_notice(self, client):
        response = client.get("/es/listening?magnitude=nine")
        assert response.status_code == 200
        with client.session_transaction() as sess:
            assert sess["magnitude_level"] == 1
        assert "preset-notice" in response.data.decode("utf-8")

    def test_mode_alone_does_not_start_anything(self, client):
        """There is no mode to pick here, so `?mode=easy` is not a preset."""
        data = client.get("/es/listening?mode=easy").data.decode("utf-8")
        assert "/es/listen/start" in data
        assert "<audio" not in data

    def test_param_url_is_noindex_and_canonical(self, client):
        data = client.get("/es/listening?magnitude=2").data.decode("utf-8")
        assert '<meta name="robots" content="noindex, nofollow">' in data
        assert (
            '<link rel="canonical" href="https://diminumero.com/es/listening">' in data
        )

    def test_shared_drill_is_not_cacheable(self, client):
        response = client.get("/es/listening?magnitude=2")
        assert "no-store" in response.headers["Cache-Control"]

    def test_login_survives_a_shared_link(self, client):
        with client.session_transaction() as sess:
            sess["user"] = {"sub": "auth0|teacher-1", "name": "Ada"}

        client.get("/es/listening?magnitude=2")
        with client.session_transaction() as sess:
            assert sess["user"]["sub"] == "auth0|teacher-1"


class TestResultsBackToOverview:
    """The ask that started this: "back to overview" must return to the screen
    the round was configured on."""

    def test_listening_round_returns_to_the_listening_overview(self, client):
        client.post("/es/listen/start", data={"magnitude_level": "2"})
        data = client.get("/es/results").data.decode("utf-8")
        assert 'href="/es/listening"' in data
        assert 'href="/es/numbers"' not in data

    def test_number_round_still_returns_to_the_number_screen(self, client):
        client.post("/es/start", data={"mode": "easy"})
        data = client.get("/es/results").data.decode("utf-8")
        assert 'href="/es/numbers"' in data
        assert 'href="/es/listening"' not in data

    def test_try_again_keeps_the_range(self, client):
        client.get("/es/listening?range=1-20")
        data = client.get("/es/results").data.decode("utf-8")
        assert 'name="range" value="1-20"' in data
