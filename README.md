# diminumero

<p align="center">
  <img src="static/logo-512.png" alt="diminumero logo" width="150" />
</p>

![Tests](https://github.com/stefanwezel/diminumero/workflows/Tests/badge.svg)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

An interactive web application to practice number translations in multiple languages. "diminumero" is Spanish for "say my number". Built with Flask, featuring 1,000 numbers per language from basic digits to millions with weighted random selection that prioritizes smaller numbers for effective learning.

**Currently supported languages:** Spanish, French, Japanese, German, Korean, Italian, Chinese, Portuguese, Turkish, Nepalese, Swedish, Danish, Norwegian

## ✨ Features

- **Multi-Language Support**: Practice numbers in Spanish, German, and more (see [Adding Languages](ADD_LANGUAGE.md))
- **1,000 Numbers Per Language**: From 1 to millions with correct grammar for each language
- **Smart Weighting**: Configurable order-of-magnitude dial (5 levels) controls how often large numbers appear — from mostly small numbers to uniform across all sizes
- **Three Quiz Modes**: Easy (multiple choice), Advanced (text input with live validation), and Hardcore
- **Multilingual UI**: Interface available in English, German, Spanish, Italian, French, Portuguese, Arabic, and Ukrainian
- **Responsive Design**: Works seamlessly on desktop and mobile
- **Keyboard Shortcuts**: Use keys 1-4 for quick answer selection

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Installation
Clone and setup the repository:
```bash
git clone git@github.com:stefanwezel/diminumero.git && cd diminumero && uv sync
```

### Run the Application
Start the Flask development server with:
```bash
uv run flask --app app run --debug
```
Access the application at http://127.0.0.1:5000.

### Testing Code
You can trigger local tests with:
```bash
uv run pytest
```

### Run Production Setup with Docker
Before you start with a docker setup, make sure to setup a `.env` file. Have a look at the `.env.example` for reference. To start the production container, run
```bash
docker-compose -f docker-compose.prod.yml up --build
```
Access the application at http://127.0.0.1:5005.

## 📁 Project Structure

```
diminumero/
├── app.py                 # Flask application & routes
├── quiz_logic.py          # Quiz generation & weighting logic
├── languages/             # Multi-language support
│   ├── config.py          # Language registry & metadata
│   ├── es/                # Spanish (numbers.py, generate_numbers.py)
│   └── ...                # Additional languages
├── templates/             # HTML templates
│   ├── base.html
│   ├── index.html
│   ├── quiz_easy.html
│   ├── quiz_advanced.html
│   ├── quiz_hardcore.html
│   └── results.html
└── static/
    ├── css/
    │   └── style.css      # Styling & animations
    └── js/
        ├── quiz.js        # Easy mode interactions
        ├── quiz_advanced.js   # Live validation logic
        └── quiz_hardcore.js   # Hardcore mode logic
```

## 🎯 How It Works

### Easy Mode (Multiple Choice)
1. **Start Quiz**: Select a language and click to begin
2. **Answer Questions**: Select the correct translation from 4 options
3. **Get Instant Feedback**: Toast notifications confirm correctness
4. **Track Progress**: See your score and progress bar throughout
5. **Review Results**: View final score with performance feedback

### Advanced Mode (Text Input)
1. **Start Quiz**: Select a language and click to begin
2. **Type Your Answer**: Enter the translation manually
3. **Live Validation**: Get real-time word-by-word feedback as you type
4. **Track Progress**: See your score and progress bar throughout
5. **Review Results**: View final score with performance feedback

### Hardcore Mode
Same as Advanced mode but with stricter validation requirements for an extra challenge.

## 🛠️ Technologies

- **Backend**: Flask 3.1+
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **Styling**: Custom CSS with responsive design
- **Number Generation**: Algorithmic grammar rules per language

## 📝 Regenerating Numbers

Each language has its own number generator. To regenerate numbers for a specific language:

```bash
python languages/<lang_code>/generate_numbers.py  # e.g., es, de, fr
```

This creates a fresh `numbers.py` in the respective language directory with proper translations.

## 🔥 Stress Testing

The `tools/` directory contains two scripts for load testing a running instance.

### Run a stress test

```bash
uv run tools/stress_test.py --url https://diminumero.com --users 5 --duration 30 --output /tmp/result.json
```

Key options:

| Flag | Default | Description |
|------|---------|-------------|
| `--url` | `https://diminumero.com` | Base URL of the target instance |
| `--users` | `5` | Number of concurrent virtual users |
| `--duration` | `30` | Test duration in seconds |
| `--mode` | `easy` | Quiz mode to exercise (`easy`, `advanced`, `hardcore`, or `mixed` to rotate randomly) |
| `--language` | `es` | Language to practice (`es`, `de`, `fr`, `ne`, or `random` to rotate each quiz) |
| `--output` | auto-timestamped | Path for the JSON result file |

### Analyse results

Print a terminal report for one or more result files:

```bash
uv run tools/analyze_results.py /tmp/result.json
```

Generate an HTML report with charts:

```bash
uv run tools/analyze_results.py /tmp/result.json --html /tmp/report.html
```

Pass multiple files to get a side-by-side comparison table:

```bash
uv run tools/analyze_results.py result_a.json result_b.json --html /tmp/compare.html
```

The HTML report includes a response-time timeline, a success/failure doughnut chart, and a per-endpoint detail table.

## 🎨 Customization

- **Quiz Length**: Modify `QUESTIONS_PER_QUIZ` in `config.py` (default 10 questions)
- **Number Weighting**: Users control the number range via a 5-level magnitude dial on the mode selection page. Decay factors are defined in `MAGNITUDE_DECAY_FACTORS` in `quiz_logic.py`
- **Colors**: Update color variables in `static/css/style.css`

## 🌍 Adding New Languages

Want to add support for a new language? See [ADD_LANGUAGE.md](ADD_LANGUAGE.md) for a complete guide on how to extend the application with new languages.

## 📄 License

This project is open source and available for educational purposes.


## 🤝 Contribution

Contributions are welcome! Please follow these steps:

### 1. Create a Branch from an Issue

Before implementing a feature, create a branch from the corresponding GitHub issue.

Pull latest changes:
```bash
git pull origin main
```

Create a feature branch (use issue number and short description)
```bash
git switch -c 6-your-issue-name
```

### 2. Implement and Test Your Changes

Make your changes and ensure everything works:

```bash
uv run pytest
```

Run the development server to manually test
```bash
uv run flask --app app run --debug
```
Access at http://127.0.0.1:5000.

Before committing, format your code with the project formatter:

```bash
uv run ruff format .
```

**Important**: Add or update tests if you're introducing new functionality. Ensure all tests pass before proceeding.

### 3. Commit and Create a Pull Request

Write descriptive commit messages and reference issue numbers for automatic closing:

```bash
git commit -m "Fix: description of what you changed (Closes #6)"
git push origin 6-your-issue-name
```

Go to GitHub and create a pull request. Update the README and CLAUDE.md if adding new features.

### 4. Test with Production Setup

Before merge, verify your changes work in production:

```bash
# Build and start the production container
docker-compose -f docker-compose.prod.yml up --build

# Access at http://127.0.0.1:5005
```

Ensure everything works correctly in the production environment before requesting final review.
