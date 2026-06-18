# Adding New Languages to diminumero

This guide explains how to add support for a new learning language to diminumero.

## Overview

diminumero supports multiple languages for number learning. Currently supported (all `ready: True`):
- **Spanish (es)**, **French (fr)**, **Japanese (ja)**, **German (de)**, **Korean (ko)**
- **Italian (it)**, **Chinese (zh)**, **Portuguese (pt)**, **Turkish (tr)**, **Nepalese (ne)**
- **Swedish (sv)**, **Danish (da)**, **Norwegian (no)**, **Welsh (cy)**, **Irish (ga)**


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
        'has_learn_materials': False,  # True once you add learn templates (step 6)
        'has_audio_mode': False,       # True once you generate Listening MP3s (step 9)
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

Then set **one flag** in `languages/config.py` — no `app.py` edits are needed:

```python
'xx': {
    ...
    'has_learn_materials': True,
    ...
}
```

`mode_selection()`, `results()`, `learn()`, and `sitemap_xml()` all consult `get_languages_with_learn_materials()`, which derives the list from that flag (plus `ready: True`). There are no hardcoded language sets in `app.py`.

See [ADD_LEARNING_MATERIALS.md](ADD_LEARNING_MATERIALS.md) for the full learn-page guide.

### 7. Update SEO Assets

**`translations.py`** — Add the language name to the index page SEO strings in **all 8 UI languages**:
- `meta_desc_index` — the `<meta name="description">` for the landing page
- `seo_title_index` — the `<title>` for the landing page

These are the only keys in `translations.py` that need updating for a new learning language.

**`templates/language_selection.html`** — Add your language code to the JSON-LD `inLanguage` array:
```json
"inLanguage": ["es", "fr", "ja", "de", "ko", "it", "zh", "pt", "tr", "ne", "sv", "da", "no", "cy", "ga", "xx"]
```

### 8. Enable the Language

Once everything is ready:

1. Set `'ready': True` in `languages/config.py`
2. Test thoroughly
3. Deploy!

### 9. Add Listening Audio (Optional)

The Listening quiz plays a pre-generated MP3 of a number and asks the user to type
the digits. It is gated by the `has_audio_mode` flag and the MP3s that actually
exist under `static/audio/<lang_code>/`. To enable it:

1. **Add a voice pool.** In `tools/generate_audio.py`, add a `VOICE_POOLS` entry for
   your code — a list of ElevenLabs voice IDs. Numbers are voiced by a speaker drawn
   at random from this list, so a deck mixes voices. Repeating an ID biases the draw
   toward that voice.
   ```python
   VOICE_POOLS = {
       ...
       "xx": ["voiceId1", "voiceId2", "voiceId2", "voiceId3"],
   }
   ```

2. **Generate the MP3s** via the ElevenLabs cloud API. Put `API_KEY_11_LABS` in `.env`
   (loaded with python-dotenv), then run the PEP-723 script:
   ```bash
   uv run tools/generate_audio.py --lang xx
   ```
   Each number in `languages/xx/numbers.py` is synthesized with the `eleven_turbo_v2_5`
   model at `mp3_44100_64` (~64 kbps mono) and written to `static/audio/xx/<n>.mp3`.
   Synthesis happens in the cloud — no local model is downloaded, so the API key is
   required and each call uses ElevenLabs credits. The run skips files that already
   exist; use `--force` to re-render, `--only <n>` for a single number, or
   `--limit <n>` for a quick test batch. Commit the generated MP3s.

3. **Flip the flag.** Set `'has_audio_mode': True` on the language's entry in
   `languages/config.py`. Both the index language cards and `mode_selection()` consult
   `get_languages_with_audio_mode()`, and the route intersects the deck with the MP3s
   actually present, so a half-generated deck still works.

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
- [ ] (Optional) Learn pages created and `has_learn_materials: True` set in `languages/config.py`
- [ ] (Optional) Listening audio: `VOICE_POOLS` entry added, MP3s generated and committed, `has_audio_mode: True` set
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
