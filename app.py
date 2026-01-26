"""Flask application for Spanish Numbers Quiz."""

from flask import Flask, render_template, request, redirect, url_for, session, flash
import quiz_logic
import os

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# Configuration
QUESTIONS_PER_QUIZ = 25


@app.route('/')
def index():
    """Landing page with Start Quiz button."""
    from numbers_data import NUMBERS
    return render_template('index.html', 
                         total_numbers=len(NUMBERS),
                         questions_per_quiz=QUESTIONS_PER_QUIZ)


@app.route('/start', methods=['POST'])
def start_quiz():
    """Initialize a new quiz session."""
    session.clear()
    session['score'] = 0
    session['total_questions'] = 0
    session['asked_numbers'] = []
    return redirect(url_for('quiz'))


@app.route('/quiz', methods=['GET', 'POST'])
def quiz():
    """Main quiz page - display question or process answer."""
    
    if request.method == 'POST':
        # Process the submitted answer
        user_answer = request.form.get('answer')
        correct_answer = session.get('correct_answer')
        current_number = session.get('current_number')
        
        if user_answer and correct_answer:
            is_correct = quiz_logic.check_answer(user_answer, correct_answer)
            
            if is_correct:
                session['score'] = session.get('score', 0) + 1
                flash('¡Correcto! 🎉', 'success')
            else:
                flash(f'Incorrect. The answer was: {correct_answer}', 'error')
            
            session['total_questions'] = session.get('total_questions', 0) + 1
        
        # Check if quiz is complete
        if session.get('total_questions', 0) >= QUESTIONS_PER_QUIZ:
            return redirect(url_for('results'))
        
        # Continue to next question
        return redirect(url_for('quiz'))
    
    # GET request - display new question
    # Check if quiz should end
    if session.get('total_questions', 0) >= QUESTIONS_PER_QUIZ:
        return redirect(url_for('results'))
    
    # Generate new question
    asked_numbers = session.get('asked_numbers', [])
    number, correct_answer = quiz_logic.get_random_question(asked_numbers)
    
    # Store in session
    session['current_number'] = number
    session['correct_answer'] = correct_answer
    
    # Update asked numbers
    if 'asked_numbers' not in session:
        session['asked_numbers'] = []
    session['asked_numbers'].append(number)
    
    # Generate multiple choice options
    options = quiz_logic.generate_multiple_choice(number, correct_answer)
    
    # Get current progress
    score = session.get('score', 0)
    total = session.get('total_questions', 0)
    
    return render_template('quiz.html', 
                         number=number, 
                         options=options,
                         score=score,
                         total=total,
                         max_questions=QUESTIONS_PER_QUIZ)


@app.route('/results')
def results():
    """Display final quiz results."""
    score = session.get('score', 0)
    total = session.get('total_questions', 0)
    
    # Calculate percentage
    percentage = (score / total * 100) if total > 0 else 0
    
    return render_template('results.html', 
                         score=score, 
                         total=total,
                         percentage=percentage)


@app.route('/restart', methods=['POST'])
def restart():
    """Restart the quiz."""
    session.clear()
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)

# Enable debug mode by default
app.config['DEBUG'] = True
