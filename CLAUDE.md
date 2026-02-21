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

# Production deployment
docker-compose -f docker-compose.prod.yml up --build
```

## Architecture

**diminumero** is a Flask-based web app for practicing number translations in multiple languages.

### Core Components

- **app.py**: Main Flask application with routes and session management. Imports `QUESTIONS_PER_QUIZ` and `DEFAULT_UI_LANGUAGE` from `config.py`, and `TEXTS` from `translations.py`.

- **config.py** (project root): Defines `QUESTIONS_PER_QUIZ = 10` and `DEFAULT_UI_LANGUAGE = "en"`.

- **translations.py** (project root): Contains the `TEXTS` dict used by `get_text()` in `app.py` for the bilingual (English/German) UI.

- **quiz_logic.py**: Quiz engine with weighted random selection, multiple choice generation using `secrets` module, and language-aware answer validation. Key functions:
  - `get_random_question()` — weighted selection, smaller numbers prioritized
  - `generate_multiple_choice()` — 4 options using `secrets` for randomization
  - `check_answer()` — exact string comparison (easy mode multiple choice)
  - `check_answer_advanced()` — normalized comparison via `normalize_text()` (advanced/hardcore text input)
  - `validate_partial_answer()` — word-by-word live feedback, returns `{'is_complete', 'is_correct', 'words': [{'text', 'status'}]}`

- **languages/**: Multi-language subsystem
  - `config.py`: Language registry (`AVAILABLE_LANGUAGES`) with metadata, validation strategies, and helper functions (`get_language_numbers()`, `get_validation_strategy()`, `get_component_decomposer()`, etc.)
  - Each language directory (es/, de/, fr/, ne/) contains `numbers.py` (number→translation dict) and `generate_numbers.py`

### Quiz Modes

1. **Easy**: Multiple choice with 4 options; answer checked with `check_answer()` (exact match)
2. **Advanced**: Text input with live word-by-word validation via `/api/validate`; final check uses `check_answer_advanced()` (normalized)
3. **Hardcore**: Same as Advanced with stricter scoring

### Data Flow

User selects language → mode selection → `start_quiz()` initializes session → quiz route serves questions from `get_random_question()` → answers validated → after 10 questions → results page

### URL Route Structure

- `/` — Language selection page
- `/<lang_code>` — Mode selection page
- `/<lang_code>/start` — POST to initialize quiz session
- `/<lang_code>/quiz/easy` — Easy mode quiz (GET/POST)
- `/<lang_code>/quiz/advanced` — Advanced mode quiz (GET/POST)
- `/<lang_code>/quiz/hardcore` — Hardcore mode quiz (GET/POST)
- `/<lang_code>/results` — Results page
- `/<lang_code>/learn` — Learn page (Spanish only currently)
- `/api/validate` — POST, JSON: live word-by-word validation for advanced/hardcore modes
- `/set_language/<lang>` — Switch UI language (en/de)
- `/restart` — POST, restart quiz
- `/privacy`, `/about`, `/imprint` — Static info pages

### Session State

Two separate language keys coexist in the session:
- `language` — UI display language (`"en"` or `"de"`)
- `learn_language` — Language being practiced (`"es"`, `"de"`, `"fr"`, `"ne"`)

Quiz state keys: `score`, `total_questions`, `asked_numbers`, `mode`, `current_number`, `correct_answer`, `current_options` (easy mode only).

### Key Design Decisions

- **Weighted randomization**: Numbers <100 get baseline weight; larger numbers progressively less likely (0.1 for 100-999, 0.01 for 1000-9999, etc.)
- **Validation strategies**: Each language in `AVAILABLE_LANGUAGES` must declare `validation_strategy`: `"word_based"` (space-separated, e.g. Spanish/French) or `"component_based"` (compound words, e.g. German). Component-based languages also need a `decompose_<language>_number()` function in their `__init__.py`.
- **German normalization**: Umlauts converted (ü→ue, ö→oe, ä→ae, ß→ss) in `normalize_text()`, allowing ASCII input for German compound numbers.
- **Session-based state**: Quiz progress, scores, and preferences stored in Flask session
- **Learn pages**: Only Spanish currently has learn templates (`templates/learn_es_en.html`, `templates/learn_es_de.html`). Adding learn support for a language requires updating **two** places in `app.py`: the `has_learn_materials` flag in `mode_selection()` and the language guard in `learn()`.

### Tests

Tests live in `tests/` with no shared `conftest.py` — each file defines its own `app` and `client` fixtures. `test_app.py` covers routes and session behaviour; `test_quiz_logic.py` covers the quiz engine in isolation.

## Adding Languages

See ADDING_LANGUAGES.md for the complete guide. Key steps:
1. Create `languages/{code}/` directory with `numbers.py` and `generate_numbers.py`
2. Register in `languages/config.py` with `ready: False` initially; add import to `get_language_numbers()`
3. Set `ready: True` after testing

## Adding Learning Materials

See ADD_NEW_LEARNING_MATERIALS.md for the complete guide. Key steps:
1. Create `templates/learn_{code}_en.html` and `templates/learn_{code}_de.html`
2. Update `has_learn_materials` flag in `mode_selection()` in `app.py`
3. Update language guard in `learn()` in `app.py`
