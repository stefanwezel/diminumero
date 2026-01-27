# 🔢 diminumero

![Tests](https://github.com/stefanwezel/diminumero/workflows/Tests/badge.svg)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Code Coverage](https://img.shields.io/badge/coverage-85%25-brightgreen.svg)](https://github.com/stefanwezel/diminumero)

An interactive web application to practice Spanish number translations. "diminumero" is Spanish for "say my number". Built with Flask, featuring 1,000 numbers from basic digits to millions with weighted random selection that prioritizes smaller numbers for effective learning.

## ✨ Features

- **1,000 Spanish Numbers**: From 1 to millions with correct Spanish grammar
- **Smart Weighting**: Numbers ≤100 appear 100× more often than larger numbers
- **Different Modes**: Begginer and advanced
- **Responsive Design**: Works seamlessly on desktop and mobile
- **Keyboard Shortcuts**: Use keys 1-4 for quick answer selection

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Installation

```bash
git clone git@github.com:stefanwezel/diminumero.git && cd diminumero
```
```bash
uv sync
```

### Run the Application
Start the Flask development server with:
```bash
uv run flask --app app run --debug
```

Visit **http://127.0.0.1:5000** in your browser to start learning!

### Run with Docker

```bash
docker-compose -f docker-compose.dev.yml up --build
```
```bash
docker-compose -f docker-compose.prod.yml up -d
```

Access the application at:
- **Development**: http://localhost:5001
- **Production**: http://localhost:5005

For detailed Docker configuration and commands, see [DOCKER.md](DOCKER.md).

## 📁 Project Structure

```
diminumero/
├── app.py                  # Flask application & routes
├── quiz_logic.py          # Quiz generation & weighting logic
├── numbers_data.py        # 1,000 Spanish number translations
├── generate_numbers.py    # Script to regenerate numbers
├── templates/             # HTML templates
│   ├── base.html
│   ├── index.html
│   ├── quiz.html
│   └── results.html
└── static/
    ├── css/
    │   └── style.css      # Styling & animations
    └── js/
        └── quiz.js        # Interactive features
```

## 🎯 How It Works

### Easy Mode (Multiple Choice)
1. **Start Quiz**: Click to begin a session
2. **Answer Questions**: Select the correct Spanish translation from 4 options
3. **Get Instant Feedback**: Toast notifications confirm correctness
4. **Track Progress**: See your score and progress bar throughout
5. **Review Results**: View final score with performance feedback

### Advanced Mode (Text Input)
1. **Start Quiz**: Click to begin a session
2. **Type Your Answer**: Enter the Spanish translation manually
3. **Live Validation**: Get real-time word-by-word feedback as you type
4. **Track Progress**: See your score and progress bar throughout
5. **Review Results**: View final score with performance feedback

## 🛠️ Technologies

- **Backend**: Flask 3.1+
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **Styling**: Custom CSS with responsive design
- **Number Generation**: Algorithmic Spanish grammar rules

## 📝 Regenerating Numbers

To generate a new set of 1,000 numbers:

```bash
python generate_numbers.py
```

This creates a fresh `numbers_data.py` with different random numbers while maintaining proper Spanish translations.

## 🎨 Customization

- **Quiz Length**: Modify `QUESTIONS_PER_QUIZ` in `app.py`
- **Number Weighting**: Adjust threshold and weights in `quiz_logic.py`
- **Colors**: Update color variables in `static/css/style.css`

## 📄 License

This project is open source and available for educational purposes.
