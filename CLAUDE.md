# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Development Commands

```bash
# Install dependencies
uv sync

# Run development server (http://127.0.0.1:5000)
uv run flask --app app run --debug

# Run tests
uv run pytest

# Run a single test file
uv run pytest tests/test_quiz_logic.py

# Run a specific test
uv run pytest tests/test_quiz_logic.py::test_get_random_question_returns_valid_number

# Lint code
uv run ruff check .

# Format code
uv run ruff format .

# Create a new Alembic migration after model changes
uv run flask --app app db migrate -m "describe change"

# Apply pending migrations locally (prod runs this on container start)
uv run flask --app app db upgrade

# Production deployment (uses .env.prod, not .env)
docker-compose -f docker-compose.prod.yml up --build
```

## Architecture

**diminumero** is a Flask-based web app for practicing number translations in multiple languages.

### Core Components

- **app.py**: Main Flask application with routes and session management. Wires up SQLAlchemy + Flask-Migrate, the Auth0 OIDC client (Authlib), and `ProxyFix` so `url_for(_external=True)` honors `X-Forwarded-Proto` from Coolify/Traefik (required for the Auth0 callback to match in prod). Imports `QUESTIONS_PER_QUIZ` and `DEFAULT_UI_LANGUAGE` from `config.py`, and `TEXTS` from `translations.py`.

- **config.py** (project root): Defines `QUESTIONS_PER_QUIZ = 10` and `DEFAULT_UI_LANGUAGE = "en"`.

- **translations.py** (project root): Contains the `TEXTS` dict used by `get_text()` in `app.py` for the multilingual UI.

- **models.py**: SQLAlchemy models. `Card(user_sub, front, back, created_at, updated_at)` is the only entity — owned by the Auth0 OIDC `sub`, free-form text on both sides (no per-card language).

- **migrations/**: Alembic migrations managed by Flask-Migrate. `flask db upgrade` is run on container start (see `Dockerfile`); add new revisions with `uv run flask --app app db migrate -m "..."`.

- **quiz_logic.py**: Quiz engine with weighted random selection, multiple choice generation using `secrets` module, and language-aware answer validation. Key functions:
  - `get_random_question(numbers_dict, exclude_numbers, magnitude_level)` — weighted selection with configurable magnitude level (1-5). `MAGNITUDE_DECAY_FACTORS` maps each level to a decay factor; weight per number = `(1/decay)^band` where band 0=<100 through band 4=100K+
  - `generate_multiple_choice()` — 4 options using `secrets` for randomization
  - `check_answer()` — exact string comparison (easy mode multiple choice)
  - `check_answer_advanced()` — normalized comparison via `normalize_text()` (advanced/hardcore text input; also reused by the cards practice endpoint)
  - `validate_partial_answer()` — word-by-word live feedback, returns `{'is_complete', 'is_correct', 'words': [{'text', 'status'}]}`

- **languages/**: Multi-language subsystem
  - `config.py`: Language registry (`AVAILABLE_LANGUAGES`) with metadata, validation strategies, and helper functions (`get_language_numbers()`, `get_validation_strategy()`, `get_component_decomposer()`, etc.)
  - Each language directory (es/, de/, fr/, ne/, da/, it/, ja/, ko/, zh/, pt/, tr/, sv/, no/) contains `numbers.py` (number→translation dict) and `generate_numbers.py`

### Quiz Modes

1. **Easy**: Multiple choice with 4 options; answer checked with `check_answer()` (exact match)
2. **Advanced**: Text input with live word-by-word validation via `/api/validate`; final check uses `check_answer_advanced()` (normalized)
3. **Hardcore**: Same as Advanced with stricter scoring

### Data Flow

User selects language → mode selection (+ magnitude dial) → `start_quiz()` initializes session (including `magnitude_level`) → quiz route serves questions from `get_random_question(magnitude_level=...)` → answers validated → after 10 questions → results page

### URL Route Structure

Quiz:
- `/` — Language selection page
- `/<lang_code>` — Mode selection page
- `/<lang_code>/start` — POST to initialize quiz session
- `/<lang_code>/quiz/easy` — Easy mode quiz (GET/POST)
- `/<lang_code>/quiz/advanced` — Advanced mode quiz (GET/POST)
- `/<lang_code>/quiz/hardcore` — Hardcore mode quiz (GET/POST)
- `/<lang_code>/results` — Results page
- `/<lang_code>/learn` — Learn page (Spanish only currently)
- `/api/validate` — POST, JSON: live word-by-word validation for advanced/hardcore modes

Auth (Auth0 OIDC):
- `/login` — Redirect to Auth0 Universal Login
- `/callback` — OIDC callback; stores `userinfo` on the session under `user`
- `/logout` — Clear local session, then bounce through `https://<AUTH0_DOMAIN>/v2/logout`

Cards (login required; ownership enforced by `Card.user_sub == session["user"]["sub"]`):
- `/cards` — List + create form (GET); `?edit=<id>` opens an edit row
- `/cards` (POST), `/cards/<id>/edit`, `/cards/<id>/delete` — Form-based CRUD (used as fallbacks)
- `/api/cards` (POST), `/api/cards/<id>` (PATCH/DELETE) — JSON CRUD used by `static/js/cards.js` for in-place updates
- `/cards/practice/start` — POST: starts a session with `direction` (`front_to_back`/`back_to_front`/`random`) and `count`
- `/cards/practice` — GET shows the next prompt; POST submits an answer or `reveal`
- `/cards/practice/results` — Final score; clears practice state
- `/api/cards/validate` — POST, JSON: word-by-word validation for the active practice card (forces word-based strategy regardless of card language)

Misc:
- `/set_language/<lang>` — Switch UI language
- `/restart` — POST, restart quiz
- `/privacy`, `/about`, `/imprint` — Static info pages
- `/robots.txt`, `/sitemap.xml` — SEO; `/cards*`, `/login`, `/callback`, `/logout` are disallowed and `no-store` cached

### Session State

Two separate language keys coexist in the session:
- `language` — UI display language (e.g. `"en"`, `"de"`)
- `learn_language` — Language being practiced (e.g. `"es"`, `"de"`, `"fr"`, `"ne"`, `"da"`, `"it"`, …)

Quiz state keys: `score`, `total_questions`, `asked_numbers`, `mode`, `magnitude_level`, `current_number`, `correct_answer`, `current_options` (easy mode only).

Auth/cards state keys:
- `user` — Auth0 `userinfo` dict (presence == logged in; preserved across `start_quiz()` and `/restart` so quizzing doesn't log the user out)
- `card_practice` — Practice session: `{direction, count, asked_ids, score, total, current_card_id, current_prompt_side, current_revealed}`

### Key Design Decisions

- **Weighted randomization**: Controlled by a user-facing magnitude dial (levels 1-5) on the mode selection page. Level 1 (default, decay=10) strongly favors small numbers; level 5 (decay=1) is uniform. The setting persists in the session so it carries across quizzes. Formula: `weight = (1/decay)^band` where bands are 0 (<100) through 4 (100K+).
- **Validation strategies**: Each language in `AVAILABLE_LANGUAGES` must declare `validation_strategy`: `"word_based"` (space-separated, e.g. Spanish/French) or `"component_based"` (compound words, e.g. German). Component-based languages also need a `decompose_<language>_number()` function in their `__init__.py`.
- **German normalization**: Umlauts converted (ü→ue, ö→oe, ä→ae, ß→ss) in `normalize_text()`, allowing ASCII input for German compound numbers.
- **Session-based state**: Quiz progress, scores, and preferences stored in Flask session.
- **Auth ownership**: All card routes use the `@login_required` decorator and `_user_card_or_404()` helper — never query `Card` without filtering by `user_sub == session["user"]["sub"]`. Auth0 client registration is skipped when `AUTH0_DOMAIN` is unset, so the dev server still boots without credentials but `/login` will fail.
- **Database**: SQLite at `instance/diminumero.db` by default (gitignored); set `DATABASE_URL` (e.g. `postgresql+psycopg://...`) to switch. The prod compose file bind-mounts `./data:/app/instance` for SQLite persistence and adds `host.docker.internal:host-gateway` so the container can reach a host-exposed Postgres (Coolify pattern).
- **Learn pages**: Only Spanish currently has learn templates (`templates/learn_es_en.html`, `templates/learn_es_de.html`). Adding learn support for a language requires updating **two** places in `app.py`: the `has_learn_materials` flag in `mode_selection()` and the language guard in `learn()`.

### Tests

Tests live in `tests/` with a shared `tests/conftest.py` that:
- forces `DATABASE_URL` to a temp SQLite file *before* `app.py` is imported (so dev `instance/` is never touched);
- sets dummy `AUTH0_*` env vars so `oauth.register("auth0", ...)` runs in CI (otherwise auth tests would hit `No such client: auth0`);
- creates/drops all tables around every test via an autouse fixture.

Test files: `test_app.py` (quiz routes/session), `test_quiz_logic.py` (engine in isolation), `test_auth.py` (Auth0 login/callback/logout, mocked), `test_cards.py` (card CRUD + practice flow). Each test file still defines its own `app`/`client` fixtures.

## Adding Languages

This is the most common recurring task in this repository. See ADD_LANGUAGE.md for the complete guide. Key steps:
1. Create `languages/{code}/` directory with `numbers.py` and `generate_numbers.py`
2. Register in `languages/config.py` with `ready: False` initially; add import to `get_language_numbers()`
3. Update SEO strings in `translations.py` and JSON-LD in `templates/language_selection.html`
4. Set `ready: True` after testing

## Adding Learning Materials

See ADD_LEARNING_MATERIALS.md for the complete guide. Key steps:
1. Create `templates/learn_{code}_en.html` and `templates/learn_{code}_de.html`
2. Update `has_learn_materials` flag in `mode_selection()` in `app.py`
3. Update language guard in `learn()` in `app.py`
