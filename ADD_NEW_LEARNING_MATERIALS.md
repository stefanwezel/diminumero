# Adding New Learning Materials to diminumero

This guide explains how to contribute learning/tutorial pages for a language that is already registered in diminumero.

## Overview

Each language can optionally have a **Learn page** — a reference page that teaches users the number patterns for that language before (or alongside) quizzing. Currently only Spanish has learn pages:

- `templates/learn_es_en.html` — English UI version
- `templates/learn_es_de.html` — German UI version

Learn pages are accessible at `/<lang_code>/learn` and linked from the mode selection page.

## Prerequisites

The target language must already be registered in `languages/config.py` with `'ready': True`. If you want to add a new language entirely, see [ADDING_LANGUAGES.md](ADDING_LANGUAGES.md) first.

## Steps to Add Learning Materials

### 1. Create the HTML Templates

Create two template files — one per UI language:

```
templates/learn_<lang_code>_en.html   ← English UI
templates/learn_<lang_code>_de.html   ← German UI
```

Use the Spanish templates as your starting point:

```bash
cp templates/learn_es_en.html templates/learn_<lang_code>_en.html
cp templates/learn_es_de.html templates/learn_<lang_code>_de.html
```

Then adapt the content for your language (see [Template Structure](#template-structure) below).

### 2. Enable the Learn Route in app.py

Open `app.py` and find the `learn()` route (around line 545). Update the language guard to include your language code:

**Before:**
```python
# Currently only Spanish has learn pages
if lang_code != "es":
    flash(get_text("flash_learn_not_available"), "info")
    return redirect(url_for("mode_selection", lang_code=lang_code))
```

**After:**
```python
if lang_code not in ["es", "<lang_code>"]:
    flash(get_text("flash_learn_not_available"), "info")
    return redirect(url_for("mode_selection", lang_code=lang_code))
```

### 3. Enable the Learn Button on Mode Selection

In `app.py`, find the `mode_selection()` route (around line 100) and update the `has_learn_materials` flag:

**Before:**
```python
# Currently only Spanish has learning materials
has_learn_materials = lang_code == "es"
```

**After:**
```python
has_learn_materials = lang_code in ["es", "<lang_code>"]
```

This causes the "Learn" button to appear on the mode selection page for your language.

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

For the German version (`_de.html`), translate all user-facing text: headings, section titles, explanations, button labels. Keep the number words in the target language unchanged.

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

## Example: Adding a French Learn Page

```bash
# 1. Copy the Spanish templates
cp templates/learn_es_en.html templates/learn_fr_en.html
cp templates/learn_es_de.html templates/learn_fr_de.html

# 2. Edit both files to replace Spanish content with French number patterns
#    (e.g. soixante-dix, quatre-vingts, quatre-vingt-dix irregularities)

# 3. In app.py learn() route, change:
#      if lang_code != "es":
#    to:
#      if lang_code not in ["es", "fr"]:

# 4. In app.py mode_selection() route, change:
#      has_learn_materials = lang_code == "es"
#    to:
#      has_learn_materials = lang_code in ["es", "fr"]

# 5. Run the dev server and navigate to /fr/learn to verify
uv run flask --app app run --debug
```

### French-specific content to include

- 1–16: irregular base words
- 17–19: dix-sept, dix-huit, dix-neuf (ten + seven etc.)
- 70–79: soixante-dix pattern (sixty + ten…)
- 80–89: quatre-vingts (four twenties)
- 90–99: quatre-vingt-dix pattern
- 100, 200, 1000: cent, deux cents, mille
- Liaison and elision rules (un, une)
- Belgian/Swiss variants (optional callout)

## Testing Checklist

Before submitting a pull request:

- [ ] Both `learn_<lang_code>_en.html` and `learn_<lang_code>_de.html` are created
- [ ] The templates extend `base.html` and use the `learn-content` / `learn-section` CSS classes
- [ ] The back link and "Start Quiz" button both use `url_for()` (not hardcoded URLs)
- [ ] All number examples are accurate (native speaker or authoritative source verified)
- [ ] All number ranges present in the quiz are covered in the learn page
- [ ] The `learn()` route guard in `app.py` includes the new lang code
- [ ] The `has_learn_materials` flag in `app.py` includes the new lang code
- [ ] The "Learn" button appears on the mode selection page for the language
- [ ] Navigating to `/<lang_code>/learn` renders without errors in both UI languages
- [ ] Other languages' learn pages are unaffected

## Questions?

Check the existing Spanish templates in `templates/learn_es_*.html` for a complete worked example, or open an issue on GitHub.
