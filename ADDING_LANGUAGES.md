# Adding New Languages to diminumero

This guide explains how to add support for a new learning language to diminumero.

## Overview

diminumero is designed to support multiple languages for number learning. Currently supported:
- **Spanish (es)**: Fully implemented
- **German (de)**: Fully implemented
- **French (fr)**: Fully implemented
- **Nepalese (ne)**: Placeholder (coming soon)


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

### 6. Update app.py Translations

Add your language to the following dictionaries in `app.py`:

**LANGUAGE_NAME_PLACEHOLDERS** (used for dynamic text replacement):
```python
LANGUAGE_NAME_PLACEHOLDERS = {
    # ... existing languages ...
    "xx": {"en": "LanguageName", "de": "Sprachname"},
}
```

**FEEDBACK_EXPRESSIONS** (shown when answer is correct):
```python
FEEDBACK_EXPRESSIONS = {
    # ... existing languages ...
    "xx": "Correct!",  # In target language
}
```

**TRANSLATIONS** (both English and German sections):
```python
# In TRANSLATIONS["en"]:
"lang_xx_name": "LanguageName",
"lang_xx_description": "Learn LanguageName numbers from 1 to 10 million",

# In TRANSLATIONS["de"]:
"lang_xx_name": "Sprachname",
"lang_xx_description": "Lerne Sprachname Zahlen von 1 bis 10 Millionen",
```

### 7. Create Learn Pages (Optional)

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

### 8. Enable the Language

Once everything is ready:

1. Set `'ready': True` in `languages/config.py`
2. Test thoroughly
3. Deploy!

## Example: Adding Quechua

```bash
# 1. Create directory
mkdir -p languages/qu
touch languages/qu/__init__.py

# 2. Edit languages/config.py - add to AVAILABLE_LANGUAGES:
'qu': {
    'name': 'Quechua',
    'native_name': 'Runasimi',
    'flag': '🇵🇪',
    'ready': False,
    'description': 'Learn Quechua numbers from 1 to millions!',
    'validation_strategy': 'word_based',
}

# 3. Edit languages/config.py - add import in get_language_numbers():
elif lang_code == 'qu':
    from .qu import NUMBERS

# 4. Create numbers.py with Quechua translations

# 5. Edit app.py - add to LANGUAGE_NAME_PLACEHOLDERS:
"qu": {"en": "Quechua", "de": "Quechua"},

# 6. Edit app.py - add to FEEDBACK_EXPRESSIONS:
"qu": "Allinmi!",

# 7. Edit app.py - add to TRANSLATIONS["en"]:
"lang_qu_name": "Quechua",
"lang_qu_description": "Learn Quechua numbers from 1 to 10 million",

# 8. Edit app.py - add to TRANSLATIONS["de"]:
"lang_qu_name": "Quechua",
"lang_qu_description": "Lerne Quechua Zahlen von 1 bis 10 Millionen",

# 9. Test with ready: False (shows "Coming Soon")

# 10. When ready, set ready: True in languages/config.py
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

## Testing Checklist

Before marking a language as `ready: True`:

- [ ] Numbers dictionary is complete and accurate
- [ ] Language registered in `languages/config.py`
- [ ] Import added to `get_language_numbers()` in `languages/config.py`
- [ ] `LANGUAGE_NAME_PLACEHOLDERS` updated in `app.py`
- [ ] `FEEDBACK_EXPRESSIONS` updated in `app.py`
- [ ] `TRANSLATIONS` updated (both `en` and `de` sections) in `app.py`
- [ ] Language appears on selection page with correct name
- [ ] Mode selection works when accessed directly
- [ ] Quiz modes function correctly
- [ ] Results page displays properly
- [ ] (Optional) Learn pages are created and work
- [ ] Edge cases tested (very small/large numbers)
- [ ] Native speaker review completed


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


## Questions?

Check existing implementations in `languages/es/` for reference, or contact the maintainer.