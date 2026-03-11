# Adding New Languages to diminumero

This guide explains how to add support for a new learning language to diminumero.

## Overview

diminumero supports multiple languages for number learning. Currently supported (all `ready: True`):
- **Spanish (es)**, **French (fr)**, **Japanese (ja)**, **German (de)**, **Korean (ko)**
- **Italian (it)**, **Chinese (zh)**, **Portuguese (pt)**, **Turkish (tr)**, **Nepalese (ne)**
- **Swedish (sv)**, **Danish (da)**, **Norwegian (no)**


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
        'validation_strategy': 'word_based',  # or 'component_based'
        # Display name in each supported UI language
        'ui_names': {
            'en': 'LanguageName', 'de': 'Sprachname', 'es': 'NombreLengua',
            'it': 'NomeLingua', 'fr': 'NomLangue', 'pt': 'NomeLíngua',
            'ar': 'اسم اللغة', 'uk': 'НазваМови',
        },
        # Description shown on the language selection page, in each UI language
        'ui_descriptions': {
            'en': 'Learn LanguageName numbers from 1 to 10 million',
            'de': 'Lerne Sprachname Zahlen von 1 bis 10 Millionen',
            'es': 'Aprende los números en NombreLengua del 1 al 10 millones',
            'it': 'Impara i numeri in NomeLingua da 1 a 10 milioni',
            'fr': 'Apprenez les nombres en NomLangue de 1 à 10 millions',
            'pt': 'Aprenda os números em NomeLíngua de 1 a 10 milhões',
            'ar': 'تعلم الأرقام باللغة من 1 إلى 10 ملايين',
            'uk': 'Вивчайте числа від 1 до 10 мільйонів',
        },
        # Word shown to the user when they answer correctly (in the target language)
        'feedback_expression': 'Correct!',
    },
}
```

> **Note on translations**: `ui_names` and `ui_descriptions` are how your language appears across all 8 UI languages. The app resolves `lang_xx_name` and `lang_xx_description` keys dynamically from these dicts — you do **not** need to add anything to `translations.py` for the language cards.

Update the import logic in `get_language_numbers()` in the same file — add an `elif` branch:

```python
elif lang_code == 'xx':
    from .xx import NUMBERS
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

If you want a learn/tutorial page for this language, create one template per UI language:

```
templates/learn_<lang_code>_en.html   ← required (fallback for all UI languages)
templates/learn_<lang_code>_de.html
templates/learn_<lang_code>_es.html
templates/learn_<lang_code>_it.html
templates/learn_<lang_code>_fr.html
templates/learn_<lang_code>_pt.html
templates/learn_<lang_code>_ar.html
templates/learn_<lang_code>_uk.html
```

The `_en` template is the only required one — the app falls back to it when a UI-language-specific template doesn't exist.

Then update `app.py` in **four** places (search for the `has_learn_materials` sets and the learn route guard):

**`mode_selection()` and `results()`** — add your code to `has_learn_materials`:
```python
has_learn_materials = lang_code in {
    "es", "fr", "ja", "de", "ko", "it", "zh", "pt", "tr", "sv", "da", "no", "xx",
}
```

**`learn()`** — add your code to the route guard:
```python
if lang_code not in {
    "es", "fr", "ja", "de", "ko", "it", "zh", "pt", "tr", "sv", "da", "no", "xx",
}:
```

**`sitemap_xml()`** — add your code to the learn-URLs list:
```python
for lc in ["es", "fr", "ja", "de", "ko", "it", "zh", "pt", "tr", "sv", "da", "no", "xx"]:
    urls.append((f"{base}/{lc}/learn", "0.7"))
```

See [ADD_LEARNING_MATERIALS.md](ADD_LEARNING_MATERIALS.md) for the full learn-page guide.

### 7. Update SEO Assets

**`translations.py`** — Add the language name to the index page SEO strings in **all 8 UI languages**:
- `meta_desc_index` — the `<meta name="description">` for the landing page
- `seo_title_index` — the `<title>` for the landing page

These are the only keys in `translations.py` that need updating for a new learning language.

**`templates/language_selection.html`** — Add your language code to the JSON-LD `inLanguage` array:
```json
"inLanguage": ["es", "fr", "ja", "de", "ko", "it", "zh", "pt", "tr", "ne", "sv", "da", "no", "xx"]
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
    'ui_names': {
        'en': 'Quechua', 'de': 'Quechua', 'es': 'Quechua',
        'it': 'Quechua', 'fr': 'Quechua', 'pt': 'Quechua',
        'ar': 'كيتشوا', 'uk': 'Кечуа',
    },
    'ui_descriptions': {
        'en': 'Learn Quechua numbers from 1 to 10 million',
        'de': 'Lerne Quechua Zahlen von 1 bis 10 Millionen',
        'es': 'Aprende los números en quechua del 1 al 10 millones',
        'it': 'Impara i numeri in quechua da 1 a 10 milioni',
        'fr': 'Apprenez les nombres en quechua de 1 à 10 millions',
        'pt': 'Aprenda os números em quechua de 1 a 10 milhões',
        'ar': 'تعلم الأرقام بالكيتشوا من 1 إلى 10 ملايين',
        'uk': 'Вивчайте числа кечуа від 1 до 10 мільйонів',
    },
    'feedback_expression': 'Allinmi!',
}

# 3. Edit languages/config.py - add import in get_language_numbers():
elif lang_code == 'qu':
    from .qu import NUMBERS

# 4. Create numbers.py with Quechua translations

# 5. Test with ready: False (shows "Coming Soon")

# 6. When ready, set ready: True in languages/config.py
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
- [ ] Language registered in `languages/config.py` with `ui_names` and `ui_descriptions` for all 8 UI languages, plus `feedback_expression`
- [ ] `elif` branch added to `get_language_numbers()` in `languages/config.py`
- [ ] Language appears on selection page with correct name in each UI language
- [ ] Mode selection works when accessed directly
- [ ] Quiz modes function correctly
- [ ] Results page displays properly
- [ ] (Optional) Learn pages created and all 4 `app.py` locations updated
- [ ] `meta_desc_index` and `seo_title_index` updated in `translations.py` for all 8 UI languages
- [ ] Language code added to JSON-LD `inLanguage` in `templates/language_selection.html`
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
   - `language` - UI language (one of the 8 supported UI languages)
   - `learn_language` - Learning language (es, fr, ja, de, …)


## Questions?

Check existing implementations in `languages/es/` for reference, or contact the maintainer.
