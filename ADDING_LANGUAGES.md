# Adding New Languages to diminumero

This guide explains how to add support for a new learning language to diminumero.

## Overview

diminumero is designed to support multiple languages for number learning. Currently supported:
- **Spanish (es)**: Fully implemented
- **Nepalese (ne)**: Placeholder (coming soon)

## Architecture

The multi-language system consists of:

1. **languages/** directory - Contains language-specific data
   - `config.py` - Language registry and metadata
   - `<lang_code>/` - Individual language directories
     - `numbers.py` - Number translations
     - `generate_numbers.py` - Script to generate numbers
     - `__init__.py` - Package initialization

2. **Route structure** - URL pattern: `/<lang_code>/...`
   - `/` - Language selection page
   - `/<lang_code>` - Mode selection page
   - `/<lang_code>/quiz/<mode>` - Quiz pages
   - `/<lang_code>/results` - Results page
   - `/<lang_code>/learn` - Learn page

3. **Session management**
   - `language` - UI language (German/English)
   - `learn_language` - Learning language (Spanish/Nepalese/etc)

## Steps to Add a New Language

### 1. Create Language Directory

```bash
mkdir -p languages/<lang_code>
touch languages/<lang_code>/__init__.py
```

### 2. Register Language in Config

Edit `languages/config.py` and add your language to `AVAILABLE_LANGUAGES`:

```python
AVAILABLE_LANGUAGES = {
    'es': {...},  # Existing languages
    'xx': {  # Your new language code
        'name': 'LanguageName',
        'native_name': 'Native Name',
        'flag': '🏳️',  # Emoji flag
        'ready': False,  # Set to True when ready
        'description': 'Learn LanguageName numbers!',
    },
}
```

Update the import logic in `get_language_numbers()`:

```python
def get_language_numbers(lang_code):
    # ... existing code ...
    try:
        if lang_code == 'es':
            from .es import NUMBERS
        elif lang_code == 'xx':  # Add this
            from .xx import NUMBERS
        # ... rest of existing code ...
```

### 3. Create Number Data

Create `languages/<lang_code>/numbers.py`:

```python
"""<Language> numbers data for diminumero."""

NUMBERS = {
    1: "one",
    2: "two",
    3: "three",
    # Add more numbers...
}
```

### 4. Create Number Generator (Optional but Recommended)

Copy and adapt `languages/es/generate_numbers.py`:

```python
"""Generate <Language> numbers programmatically for diminumero."""

def number_to_<language>(n):
    """Convert a number to <Language>."""
    # Implement language-specific logic
    pass

# Generate numbers and write to numbers.py
# ...
```

### 5. Create Package Init

Create `languages/<lang_code>/__init__.py`:

```python
"""<Language> language module for diminumero."""

from .numbers import NUMBERS

__all__ = ['NUMBERS']
```

### 6. Create Learn Pages (Optional)

If you want learning materials, create:
- `templates/learn_<lang_code>_de.html` - German UI version
- `templates/learn_<lang_code>_en.html` - English UI version

Copy from existing `templates/learn_es_*.html` and adapt content.

Update `app.py` learn route to support your language:

```python
@app.route('/<lang_code>/learn')
def learn(lang_code):
    # Add condition for your language
    if lang_code not in ['es', 'xx']:
        flash(get_text('flash_learn_not_available'), 'info')
        return redirect(url_for('mode_selection', lang_code=lang_code))
    # ... rest of code
```

### 7. Enable the Language

Once everything is ready:

1. Set `'ready': True` in `languages/config.py`
2. Test thoroughly
3. Deploy!

## Example: Adding French

```bash
# 1. Create directory
mkdir -p languages/fr
touch languages/fr/__init__.py

# 2. Edit config to add:
'fr': {
    'name': 'French',
    'native_name': 'Français',
    'flag': '🇫🇷',
    'ready': False,
    'description': 'Learn French numbers from 1 to millions!',
}

# 3. Create numbers.py with French translations

# 4. Test with ready: False (shows "Coming Soon")

# 5. When ready, set ready: True
```

## Number Generation Best Practices

1. **Coverage**: Include variety across magnitudes
   - 1-100: All numbers
   - 100-1000: Good coverage
   - 1000+: Sample representative numbers

2. **Irregular forms**: Don't forget special cases
   - Spanish: cien/ciento, veintiún vs veinte y uno
   - Each language has its quirks!

3. **Test thoroughly**: Verify accuracy of generated numbers
   - Have a native speaker review
   - Test edge cases (100, 1000, millions, etc.)

## UI Translations

Currently, the UI language (German/English) is separate from the learning language. To add UI translations for language-specific content:

1. Add keys to `TRANSLATIONS` dict in `app.py`
2. Use `get_text('key')` in templates
3. Keep learning content (numbers) separate from UI text

## Testing Checklist

Before marking a language as `ready: True`:

- [ ] Numbers dictionary is complete and accurate
- [ ] Language appears on selection page (but disabled)
- [ ] Mode selection works when accessed directly
- [ ] Quiz modes function correctly
- [ ] Results page displays properly
- [ ] (Optional) Learn pages are created and work
- [ ] Edge cases tested (very small/large numbers)
- [ ] Native speaker review completed

## Questions?

Check existing implementations in `languages/es/` for reference, or contact the maintainer.
