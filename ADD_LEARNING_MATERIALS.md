# Adding New Learning Materials to diminumero

This guide explains how to contribute learning/tutorial pages for a language that is already registered in diminumero.

## Overview

Each language can optionally have a **Learn page** — a reference page that teaches users the number patterns for that language before (or alongside) quizzing.

Languages that currently have learn pages: `es`, `fr`, `ja`, `de`, `ko`, `it`, `zh`, `pt`, `tr`, `sv`, `da`, `no`.

For each language the app looks for a UI-language-specific template first, then falls back to the English version:

```
templates/learn_<lang_code>_en.html   ← required (fallback for all UI languages)
templates/learn_<lang_code>_de.html   ← optional
templates/learn_<lang_code>_es.html   ← optional
templates/learn_<lang_code>_it.html   ← optional
templates/learn_<lang_code>_fr.html   ← optional
templates/learn_<lang_code>_pt.html   ← optional
templates/learn_<lang_code>_ar.html   ← optional
templates/learn_<lang_code>_uk.html   ← optional
```

Learn pages are accessible at `/<lang_code>/learn` and linked from the mode selection page.

## Prerequisites

The target language must already be registered in `languages/config.py` with `'ready': True`. If you want to add a new language entirely, see [ADD_LANGUAGE.md](ADD_LANGUAGE.md) first.

## Steps to Add Learning Materials

### 1. Create the HTML Templates

The `_en` template is mandatory — it acts as the fallback for any UI language that doesn't have its own template. Create as many UI-language variants as you like:

```bash
cp templates/learn_es_en.html templates/learn_<lang_code>_en.html
# optional per-UI-language variants:
cp templates/learn_es_de.html templates/learn_<lang_code>_de.html
# ... repeat for es, it, fr, pt, ar, uk as needed
```

Then adapt the content for your language (see [Template Structure](#template-structure) below).

### 2. Update app.py in Four Places

Search `app.py` for the `has_learn_materials` set (it appears in `mode_selection()` and `results()`) and the language guard in `learn()`, then add your language code to all four locations.

**`mode_selection()` — `has_learn_materials`:**
```python
has_learn_materials = lang_code in {
    "es", "fr", "ja", "de", "ko", "it", "zh", "pt", "tr", "sv", "da", "no", "<lang_code>",
}
```

**`results()` — `has_learn_materials`** (same set, different function):
```python
has_learn_materials = lang_code in {
    "es", "fr", "ja", "de", "ko", "it", "zh", "pt", "tr", "sv", "da", "no", "<lang_code>",
}
```

**`learn()` — route guard:**
```python
if lang_code not in {
    "es", "fr", "ja", "de", "ko", "it", "zh", "pt", "tr", "sv", "da", "no", "<lang_code>",
}:
    flash(get_text("flash_learn_not_available"), "info")
    return redirect(url_for("mode_selection", lang_code=lang_code))
```

**`sitemap_xml()` — learn URL list:**
```python
for lc in ["es", "fr", "ja", "de", "ko", "it", "zh", "pt", "tr", "sv", "da", "no", "<lang_code>"]:
    urls.append((f"{base}/{lc}/learn", "0.7"))
```

## Template Structure

Each learn template extends `base.html` and follows this structure:

```html
{% extends "base.html" %}

{% block title %}Learn <Language> Numbers - diminumero{% endblock %}

{% block content %}
<main class="container learn">
  <div class="learn-content">

    <!-- Back link -->
    <a href="{{ url_for('mode_selection', lang_code=lang_code) }}" class="btn-back">← Back</a>

    <!-- Hero header -->
    <header class="learn-hero">
      <h1>Learn <Language> Numbers</h1>
      <p>Brief description of what the page covers and any notable quirks.</p>
    </header>

    <!-- Table of contents -->
    <nav class="learn-toc">
      <strong>Contents</strong>
      <ul>
        <li><a href="#basics">Section 1</a></li>
        <li><a href="#tens">Section 2</a></li>
        <!-- ... -->
      </ul>
    </nav>

    <!-- Content sections -->
    <section id="basics" class="learn-section">
      <h2>Section title</h2>
      <p>Explanation text.</p>
      <ul>
        <li><strong>number</strong> = word</li>
        <!-- ... -->
      </ul>

      <!-- Optional interactive check -->
      <details class="learn-check">
        <summary><strong>Quick check</strong>: Which numbers are these?</summary>
        <p>Answers revealed on click.</p>
      </details>
    </section>

    <!-- Footer with quiz link -->
    <div class="learn-footer">
      <a href="{{ url_for('mode_selection', lang_code=lang_code) }}" class="btn btn-primary">
        Start Quiz
      </a>
    </div>

  </div>
</main>
{% endblock %}
```

For UI-language-specific templates (e.g. `_de.html`), translate all user-facing text: headings, section titles, explanations, button labels. Keep the number words in the target language unchanged.

## Content Guidelines

A good learn page covers the full range of numbers in the quiz and highlights the patterns learners need to internalise:

### Recommended Sections

| Section | What to cover |
|---|---|
| **Building blocks** | The base words (1–20 or 1–10) that must be memorised |
| **Tens** | How 20, 30, 40 … are formed and how ones are combined |
| **Hundreds** | Hundred words, any irregular forms |
| **Thousands** | Thousand words, any compounding rules |
| **Large numbers** | Millions and above, if the quiz covers them |
| **Spelling / script** | Accents, compound vs. separate words, non-Latin scripts |
| **Common mistakes** | The 3–5 errors learners make most often |

Not every section is required — only include what's relevant for the language.

### Quality Standards

- **Accuracy first**: have a native speaker or authoritative reference verify every example.
- **Completeness**: cover all number ranges that appear in the quiz.
- **Conciseness**: learners read to prepare for the quiz, not to study linguistics. Favour bullet lists and tables over long paragraphs.
- **Quick checks**: use `<details class="learn-check">` blocks to add lightweight self-quizzes after key sections.
- **Edge cases**: explicitly call out irregular forms (e.g. Spanish *cien* vs. *ciento*, German *ein* vs. *eins*).

## Example: Adding a Turkish Learn Page

```bash
# 1. Copy the Spanish template as starting point
cp templates/learn_es_en.html templates/learn_tr_en.html

# 2. Edit the file to replace Spanish content with Turkish number patterns

# 3. In app.py, add "tr" to the has_learn_materials set in mode_selection() and results(),
#    to the guard set in learn(), and to the list in sitemap_xml()

# 4. Run the dev server and navigate to /tr/learn to verify
uv run flask --app app run --debug
```

### Turkish-specific content to include

- 1–10: bir, iki, üç, dört, beş, altı, yedi, sekiz, dokuz, on
- Tens: on, yirmi, otuz, kırk, elli, altmış, yetmiş, seksen, doksan
- Hundreds: yüz, iki yüz, … (yüz used standalone for 100)
- Thousands: bin (1000), iki bin, …
- Agglutinative suffixation (numbers join without spaces)

## Testing Checklist

Before submitting a pull request:

- [ ] `learn_<lang_code>_en.html` is created (required fallback)
- [ ] Any additional UI-language templates created extend `base.html` correctly
- [ ] The templates use the `learn-content` / `learn-section` CSS classes
- [ ] The back link and "Start Quiz" button both use `url_for()` (not hardcoded URLs)
- [ ] All number examples are accurate (native speaker or authoritative source verified)
- [ ] All number ranges present in the quiz are covered in the learn page
- [ ] All four `app.py` locations updated: `mode_selection()`, `results()`, `learn()`, `sitemap_xml()`
- [ ] The "Learn" button appears on the mode selection page for the language
- [ ] Navigating to `/<lang_code>/learn` renders without errors in each UI language (or gracefully falls back to `_en`)
- [ ] Other languages' learn pages are unaffected

## Questions?

Check the existing Spanish templates in `templates/learn_es_*.html` for a complete worked example, or open an issue on GitHub.
