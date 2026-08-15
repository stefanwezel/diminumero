"""Shared test setup.

Forces a temp-file SQLite DB so tests never touch the dev `instance/` DB
and creates/drops the schema around each test for isolation.
"""

import os
import tempfile

# Override the DB URI before app.py is imported by any test module.
_db_fd, _db_path = tempfile.mkstemp(suffix="-diminumero-test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"

# Auth0 vars must be set before app import so oauth.register() runs and
# creates the `auth0` client that the auth tests mock. CI has no .env, so
# load_dotenv() finds nothing — without these defaults the registration
# is skipped and oauth.auth0 raises "No such client".
os.environ.setdefault("AUTH0_DOMAIN", "test-tenant.eu.auth0.com")
os.environ.setdefault("AUTH0_CLIENT_ID", "test-client-id")
os.environ.setdefault("AUTH0_CLIENT_SECRET", "test-client-secret")

import pytest  # noqa: E402

from app import app as flask_app  # noqa: E402
from models import db  # noqa: E402

# Render every worksheet PDF for real. A cache hit would let a test pass on
# bytes an earlier test produced — the degradation test in particular patches
# the renderer to raise and would silently be served a cached PDF instead. The
# budget is off for the same reason: the suite renders more sheets per minute
# than a browsing human ever would.
flask_app.config["WORKSHEET_PDF_CACHE_DIR"] = None
flask_app.config["WORKSHEET_PDF_BUDGET"] = 0


@pytest.fixture(autouse=True)
def _db_setup():
    """Recreate tables around every test for clean isolation."""
    with flask_app.app_context():
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()
