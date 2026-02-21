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

- **app.py**: Main Flask application with routes, session management, and bilingual UI (English/German). Contains `get_text()` for internationalization and defines `QUESTIONS_PER_QUIZ = 10`.

- **quiz_logic.py**: Quiz engine with weighted random selection (smaller numbers prioritized), multiple choice generation using `secrets` module, and language-aware answer validation. Key functions: `get_random_question()`, `generate_multiple_choice()`, `check_answer_advanced()`, `validate_partial_answer()`.

- **languages/**: Multi-language subsystem
  - `config.py`: Language registry (`AVAILABLE_LANGUAGES`) with metadata and validation strategies
  - Each language directory (es/, de/, fr/, ne/) contains `numbers.py` (number→translation dict) and `generate_numbers.py`

### Quiz Modes

1. **Easy**: Multiple choice with 4 options
2. **Advanced**: Text input with live word-by-word validation via `/validate_answer` API
3. **Hardcore**: Advanced mode with stricter validation

### Data Flow

User selects language → mode selection → `start_quiz()` initializes session → quiz route serves questions from `get_random_question()` → answers validated → after 10 questions → results page

### URL Route Structure

- `/` — Language selection page
- `/<lang_code>` — Mode selection page
- `/<lang_code>/start` — POST to initialize quiz session
- `/<lang_code>/quiz/<mode>` — Quiz pages (easy/advanced/hardcore)
- `/<lang_code>/results` — Results page
- `/<lang_code>/learn` — Learn page (Spanish only)
- `/api/validate` — POST, JSON: live word-by-word validation for advanced/hardcore modes
- `/set_language/<lang>` — Switch UI language (en/de)

### Session State

Two separate language keys coexist in the session:
- `language` — UI display language (`"en"` or `"de"`)
- `learn_language` — Language being practiced (`"es"`, `"de"`, `"fr"`, `"ne"`)

Quiz state keys: `score`, `total_questions`, `asked_numbers`, `mode`, `current_number`, `correct_answer`, `current_options` (easy mode only).

### Key Design Decisions

- **Weighted randomization**: Numbers <100 get baseline weight; larger numbers progressively less likely (0.1 for 100-999, 0.01 for 1000-9999, etc.)
- **Validation strategies**: Each language in `AVAILABLE_LANGUAGES` must declare `validation_strategy`: `"word_based"` (space-separated, e.g. Spanish/French) or `"component_based"` (compound words, e.g. German). Component-based languages also need a `decompose_<language>_number()` function in their `__init__.py`.
- **German normalization**: Umlauts converted (ü→ue, ö→oe, ä→ae, ß→ss) in `normalize_text()`
- **Session-based state**: Quiz progress, scores, and preferences stored in Flask session
- **Learn pages**: Only Spanish currently has learn templates (`templates/learn_es_en.html`, `templates/learn_es_de.html`); adding learn support for a language requires updating the hardcoded condition in the `learn()` route in `app.py`.

## Adding Languages

See ADDING_LANGUAGES.md for the complete guide. Key steps:
1. Create `languages/{code}/` directory with `numbers.py` and `generate_numbers.py`
2. Register in `languages/config.py` with `ready: False` initially
3. Add UI translations in app.py `TEXTS` dict
4. Create learning template if applicable
5. Set `ready: True` after testing
