# 🔢 Spanish Numbers Quiz

![Tests](https://github.com/stefanwezel/spanish_numbers_quiz/workflows/Tests/badge.svg)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Code Coverage](https://img.shields.io/badge/coverage-85%25-brightgreen.svg)](https://github.com/stefanwezel/spanish_numbers_quiz)

An interactive web application to practice Spanish number translations. Built with Flask, featuring 1,000 numbers from basic digits to millions with weighted random selection that prioritizes smaller numbers for effective learning.

## ✨ Features

- **1,000 Spanish Numbers**: From 1 to millions with correct Spanish grammar
- **Smart Weighting**: Numbers ≤5,000 appear 4× more often than larger numbers
- **Multiple Choice Quiz**: 4 options per question with randomized order
- **25 Questions per Session**: Complete quiz with score tracking
- **Toast Notifications**: Instant feedback on correct/incorrect answers
- **Responsive Design**: Works seamlessly on desktop and mobile
- **Keyboard Shortcuts**: Use keys 1-4 for quick answer selection
- **Beautiful UI**: Warm color scheme with smooth animations

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd spanish_numbers_quiz

# Install dependencies
uv sync
```

### Run the Application

```bash
# Start the Flask development server
uv run flask --app app run --debug
```

Visit **http://127.0.0.1:5000** in your browser to start learning!

## 📁 Project Structure

```
spanish_numbers_quiz/
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

1. **Start Quiz**: Click to begin a 25-question session
2. **Answer Questions**: Select the correct Spanish translation from 4 options
3. **Get Instant Feedback**: Toast notifications confirm correctness
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
