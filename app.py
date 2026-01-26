"""Flask application for Spanish Numbers Quiz."""

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from dotenv import load_dotenv
import quiz_logic
import os

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# Configuration
QUESTIONS_PER_QUIZ = 25

# Translations
TRANSLATIONS = {
    'en': {
        # General
        'app_title': 'Spanish Numbers Quiz',
        'language_en': 'English',
        'language_de': 'German',
        
        # Home page
        'home_title': 'Spanish Numbers Quiz - Home',
        'home_hero_title': 'Spanish Numbers Quiz',
        'home_hero_subtitle': 'Test your Spanish number knowledge!',
        'home_hero_description': 'Practice translating numbers from digits to Spanish words. Choose your difficulty mode and start learning!',
        
        # Mode selection
        'mode_easy': 'Easy',
        'mode_easy_desc': 'Multiple choice with 4 options. Perfect for beginners!',
        'mode_easy_btn': 'Start Easy Mode',
        'mode_advanced': 'Advanced',
        'mode_advanced_desc': 'Type the answer with live word-by-word feedback.',
        'mode_advanced_btn': 'Start Advanced Mode',
        'mode_hardcore': 'Hardcore',
        'mode_hardcore_desc': 'Ultimate challenge mode.',
        'mode_hardcore_btn': 'Coming Soon',
        
        # Info section
        'info_questions': 'Questions',
        'info_numbers': 'Numbers',
        
        # Footer
        'footer_feedback': 'Send Feedback',
        'footer_imprint': 'Imprint',
        
        # Quiz interface
        'quiz_question': 'Question',
        'quiz_score': 'Score',
        'quiz_exit': 'Exit Quiz',
        'quiz_easy_prompt': 'What is this number in Spanish?',
        'quiz_advanced_prompt': 'Type this number in Spanish:',
        'quiz_advanced_placeholder': 'Type your answer here...',
        'quiz_give_up': 'Give Up',
        
        # Results page
        'results_title': 'Quiz Results',
        'results_complete': 'Quiz Complete! 🎊',
        'results_correct': 'Correct Answers',
        'results_perfect': '🌟 Perfect score! You\'re a Spanish numbers master!',
        'results_great': '🎉 Great job! You really know your Spanish numbers!',
        'results_good': '👍 Good work! Keep practicing to improve!',
        'results_keep_practicing': '📚 Keep practicing! You\'ll get better with time!',
        'results_try_again': 'Try Again',
        'results_back_home': 'Back to Home',
        
        # Flash messages
        'flash_invalid_mode': 'Invalid mode selected.',
        'flash_hardcore_soon': 'Hardcore mode is coming soon! Try Easy or Advanced mode.',
        'flash_correct': '¡Correcto! 🎉',
        'flash_incorrect': 'Incorrect. The answer was: {}',
        'flash_gave_up': 'The answer was: {}',
        
        # Imprint page
        'imprint_title': 'Imprint - Spanish Numbers Quiz',
        'imprint_heading': 'Imprint',
        'imprint_legal_info': 'Information according to § 5 TMG',
        'imprint_contact': 'Contact',
        'imprint_email': 'Email',
        'imprint_disclaimer': 'Disclaimer',
        'imprint_content_heading': 'Liability for Content',
        'imprint_content_text': 'As a service provider, we are responsible for our own content on these pages in accordance with general legislation pursuant to Section 7(1) of the German Telemedia Act (TMG). However, according to Sections 8 to 10 TMG, we are not obligated as a service provider to monitor transmitted or stored third-party information or to investigate circumstances that indicate illegal activity. Obligations to remove or block the use of information under general legislation remain unaffected. However, liability in this regard is only possible from the time of knowledge of a specific legal violation. Upon becoming aware of corresponding legal violations, we will remove this content immediately.',
        'imprint_links_heading': 'Liability for Links',
        'imprint_links_text': 'Our website contains links to external third-party websites over whose content we have no influence. Therefore, we cannot assume any liability for this external content. The respective provider or operator of the pages is always responsible for the content of the linked pages. The linked pages were checked for possible legal violations at the time of linking. Illegal content was not recognizable at the time of linking. However, permanent monitoring of the content of the linked pages is unreasonable without concrete evidence of a legal violation. Upon becoming aware of legal violations, we will remove such links immediately.',
        'imprint_copyright_heading': 'Copyright',
        'imprint_copyright_text': 'The content and works created by the site operators on these pages are subject to German copyright law. Reproduction, editing, distribution, and any kind of use outside the limits of copyright law require the written consent of the respective author or creator. Downloads and copies of this site are only permitted for private, non-commercial use. Insofar as the content on this site was not created by the operator, the copyrights of third parties are respected. In particular, third-party content is marked as such. Should you nevertheless become aware of a copyright infringement, please inform us accordingly. Upon becoming aware of legal violations, we will remove such content immediately.',
        'imprint_back_home': 'Back to Home',
        
        # Email subject
        'feedback_subject': 'Spanish Numbers Quiz Feedback',
    },
    'de': {
        # General
        'app_title': 'Spanische Zahlen Quiz',
        'language_en': 'Englisch',
        'language_de': 'Deutsch',
        
        # Home page
        'home_title': 'Spanische Zahlen Quiz - Startseite',
        'home_hero_title': 'Spanische Zahlen Quiz',
        'home_hero_subtitle': 'Teste dein Wissen über spanische Zahlen!',
        'home_hero_description': 'Übe die Übersetzung von Zahlen in spanische Wörter. Wähle deinen Schwierigkeitsgrad und fang an zu lernen!',
        
        # Mode selection
        'mode_easy': 'Einfach',
        'mode_easy_desc': 'Multiple Choice mit 4 Optionen. Perfekt für Anfänger!',
        'mode_easy_btn': 'Einfachen Modus starten',
        'mode_advanced': 'Fortgeschritten',
        'mode_advanced_desc': 'Tippe die Antwort mit Live-Feedback Wort für Wort.',
        'mode_advanced_btn': 'Fortgeschrittenen Modus starten',
        'mode_hardcore': 'Hardcore',
        'mode_hardcore_desc': 'Ultimativer Herausforderungsmodus.',
        'mode_hardcore_btn': 'Kommt bald',
        
        # Info section
        'info_questions': 'Fragen',
        'info_numbers': 'Zahlen',
        
        # Footer
        'footer_feedback': 'Feedback senden',
        'footer_imprint': 'Impressum',
        
        # Quiz interface
        'quiz_question': 'Frage',
        'quiz_score': 'Punktzahl',
        'quiz_exit': 'Quiz beenden',
        'quiz_easy_prompt': 'Wie lautet diese Zahl auf Spanisch?',
        'quiz_advanced_prompt': 'Schreibe diese Zahl auf Spanisch:',
        'quiz_advanced_placeholder': 'Gib deine Antwort hier ein...',
        'quiz_give_up': 'Aufgeben',
        
        # Results page
        'results_title': 'Quiz Ergebnisse',
        'results_complete': 'Quiz abgeschlossen! 🎊',
        'results_correct': 'Richtige Antworten',
        'results_perfect': '🌟 Perfekte Punktzahl! Du bist ein Meister der spanischen Zahlen!',
        'results_great': '🎉 Großartig! Du kennst deine spanischen Zahlen wirklich gut!',
        'results_good': '👍 Gute Arbeit! Übe weiter, um dich zu verbessern!',
        'results_keep_practicing': '📚 Weiter üben! Mit der Zeit wirst du besser!',
        'results_try_again': 'Nochmal versuchen',
        'results_back_home': 'Zurück zur Startseite',
        
        # Flash messages
        'flash_invalid_mode': 'Ungültiger Modus ausgewählt.',
        'flash_hardcore_soon': 'Hardcore-Modus kommt bald! Probiere den einfachen oder fortgeschrittenen Modus.',
        'flash_correct': '¡Correcto! 🎉',
        'flash_incorrect': 'Falsch. Die Antwort war: {}',
        'flash_gave_up': 'Die Antwort war: {}',
        
        # Imprint page
        'imprint_title': 'Impressum - Spanische Zahlen Quiz',
        'imprint_heading': 'Impressum',
        'imprint_legal_info': 'Angaben gemäß § 5 TMG',
        'imprint_contact': 'Kontakt',
        'imprint_email': 'E-Mail',
        'imprint_disclaimer': 'Haftungsausschluss',
        'imprint_content_heading': 'Haftung für Inhalte',
        'imprint_content_text': 'Als Diensteanbieter sind wir gemäß § 7 Abs.1 TMG für eigene Inhalte auf diesen Seiten nach den allgemeinen Gesetzen verantwortlich. Nach §§ 8 bis 10 TMG sind wir als Diensteanbieter jedoch nicht verpflichtet, übermittelte oder gespeicherte fremde Informationen zu überwachen oder nach Umständen zu forschen, die auf eine rechtswidrige Tätigkeit hinweisen. Verpflichtungen zur Entfernung oder Sperrung der Nutzung von Informationen nach den allgemeinen Gesetzen bleiben hiervon unberührt. Eine diesbezügliche Haftung ist jedoch erst ab dem Zeitpunkt der Kenntnis einer konkreten Rechtsverletzung möglich. Bei Bekanntwerden von entsprechenden Rechtsverletzungen werden wir diese Inhalte umgehend entfernen.',
        'imprint_links_heading': 'Haftung für Links',
        'imprint_links_text': 'Unser Angebot enthält Links zu externen Websites Dritter, auf deren Inhalte wir keinen Einfluss haben. Deshalb können wir für diese fremden Inhalte auch keine Gewähr übernehmen. Für die Inhalte der verlinkten Seiten ist stets der jeweilige Anbieter oder Betreiber der Seiten verantwortlich. Die verlinkten Seiten wurden zum Zeitpunkt der Verlinkung auf mögliche Rechtsverstöße überprüft. Rechtswidrige Inhalte waren zum Zeitpunkt der Verlinkung nicht erkennbar. Eine permanente inhaltliche Kontrolle der verlinkten Seiten ist jedoch ohne konkrete Anhaltspunkte einer Rechtsverletzung nicht zumutbar. Bei Bekanntwerden von Rechtsverletzungen werden wir derartige Links umgehend entfernen.',
        'imprint_copyright_heading': 'Urheberrecht',
        'imprint_copyright_text': 'Die durch die Seitenbetreiber erstellten Inhalte und Werke auf diesen Seiten unterliegen dem deutschen Urheberrecht. Die Vervielfältigung, Bearbeitung, Verbreitung und jede Art der Verwertung außerhalb der Grenzen des Urheberrechtes bedürfen der schriftlichen Zustimmung des jeweiligen Autors bzw. Erstellers. Downloads und Kopien dieser Seite sind nur für den privaten, nicht kommerziellen Gebrauch gestattet. Soweit die Inhalte auf dieser Seite nicht vom Betreiber erstellt wurden, werden die Urheberrechte Dritter beachtet. Insbesondere werden Inhalte Dritter als solche gekennzeichnet. Sollten Sie trotzdem auf eine Urheberrechtsverletzung aufmerksam werden, bitten wir um einen entsprechenden Hinweis. Bei Bekanntwerden von Rechtsverletzungen werden wir derartige Inhalte umgehend entfernen.',
        'imprint_back_home': 'Zurück zur Startseite',
        
        # Email subject
        'feedback_subject': 'Spanische Zahlen Quiz Feedback',
    }
}

def get_text(key):
    """Get translated text for the current language."""
    lang = session.get('language', 'de')  # Default to German
    return TRANSLATIONS.get(lang, {}).get(key, key)


@app.route('/')
def index():
    """Landing page with Start Quiz button."""
    # Initialize language if not set
    if 'language' not in session:
        session['language'] = 'de'  # Default to German
    
    from numbers_data import NUMBERS
    return render_template('index.html', 
                         total_numbers=len(NUMBERS),
                         questions_per_quiz=QUESTIONS_PER_QUIZ,
                         get_text=get_text)


@app.route('/set_language/<lang>')
def set_language(lang):
    """Set the language preference."""
    if lang in ['en', 'de']:
        session['language'] = lang
    # Redirect back to the referring page or index
    return redirect(request.referrer or url_for('index'))


@app.route('/start', methods=['POST'])
def start_quiz():
    """Initialize a new quiz session."""
    # Get mode from form (default to easy if not specified)
    mode = request.form.get('mode', 'easy')
    
    # Validate mode
    if mode not in ['easy', 'advanced', 'hardcore']:
        flash(get_text('flash_invalid_mode'), 'error')
        return redirect(url_for('index'))
    
    # Hardcore mode not yet implemented
    if mode == 'hardcore':
        flash(get_text('flash_hardcore_soon'), 'info')
        return redirect(url_for('index'))
    
    # Initialize session
    session.clear()
    session['score'] = 0
    session['total_questions'] = 0
    session['asked_numbers'] = []
    session['mode'] = mode
    
    # Redirect to appropriate quiz
    if mode == 'easy':
        return redirect(url_for('quiz_easy'))
    elif mode == 'advanced':
        return redirect(url_for('quiz_advanced'))



@app.route('/quiz/easy', methods=['GET', 'POST'])
def quiz_easy():
    """Easy mode quiz page - multiple choice with 4 options."""
    
    # Ensure user is in easy mode
    if session.get('mode') != 'easy':
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        # Process the submitted answer
        user_answer = request.form.get('answer')
        correct_answer = session.get('correct_answer')
        current_number = session.get('current_number')
        
        if user_answer and correct_answer:
            is_correct = quiz_logic.check_answer(user_answer, correct_answer)
            
            if is_correct:
                session['score'] = session.get('score', 0) + 1
                flash(get_text('flash_correct'), 'success')
            else:
                flash(get_text('flash_incorrect').format(correct_answer), 'error')
            
            session['total_questions'] = session.get('total_questions', 0) + 1
        
        # Check if quiz is complete
        if session.get('total_questions', 0) >= QUESTIONS_PER_QUIZ:
            return redirect(url_for('results'))
        
        # Continue to next question
        return redirect(url_for('quiz_easy'))
    
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
    
    return render_template('quiz_easy.html', 
                         number=number, 
                         options=options,
                         score=score,
                         total=total,
                         max_questions=QUESTIONS_PER_QUIZ,
                         get_text=get_text)


@app.route('/quiz/advanced', methods=['GET', 'POST'])
def quiz_advanced():
    """Advanced mode quiz page - text input with live validation."""
    
    # Ensure user is in advanced mode
    if session.get('mode') != 'advanced':
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        # Check if user gave up
        if 'give_up' in request.form:
            correct_answer = session.get('correct_answer')
            flash(get_text('flash_gave_up').format(correct_answer), 'info')
            session['total_questions'] = session.get('total_questions', 0) + 1
            
            # Check if quiz is complete
            if session.get('total_questions', 0) >= QUESTIONS_PER_QUIZ:
                return redirect(url_for('results'))
            
            return redirect(url_for('quiz_advanced'))
        
        # Process the submitted answer
        user_answer = request.form.get('answer', '').strip()
        correct_answer = session.get('correct_answer')
        
        if user_answer and correct_answer:
            # Use word-by-word validation for final check
            is_correct = quiz_logic.check_answer_advanced(user_answer, correct_answer)
            
            if is_correct:
                session['score'] = session.get('score', 0) + 1
                flash(get_text('flash_correct'), 'success')
            else:
                flash(get_text('flash_incorrect').format(correct_answer), 'error')
            
            session['total_questions'] = session.get('total_questions', 0) + 1
        
        # Check if quiz is complete
        if session.get('total_questions', 0) >= QUESTIONS_PER_QUIZ:
            return redirect(url_for('results'))
        
        # Continue to next question
        return redirect(url_for('quiz_advanced'))
    
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
    
    # Get current progress
    score = session.get('score', 0)
    total = session.get('total_questions', 0)
    
    return render_template('quiz_advanced.html', 
                         number=number, 
                         correct_answer=correct_answer,
                         score=score,
                         total=total,
                         max_questions=QUESTIONS_PER_QUIZ,
                         get_text=get_text)


@app.route('/api/validate', methods=['POST'])
def validate_answer():
    """API endpoint for live validation of user input."""
    user_input = request.json.get('input', '')
    correct_answer = session.get('correct_answer', '')
    
    if not correct_answer:
        return jsonify({'error': 'No active question'}), 400
    
    validation = quiz_logic.validate_partial_answer(user_input, correct_answer)
    
    return jsonify(validation)


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
                         percentage=percentage,
                         get_text=get_text)


@app.route('/restart', methods=['POST'])
def restart():
    """Restart the quiz."""
    session.clear()
    return redirect(url_for('index'))


@app.route('/imprint')
def imprint():
    """Display imprint/impressum page."""
    return render_template('imprint.html', get_text=get_text)


if __name__ == '__main__':
    app.run(debug=True)

# Enable debug mode by default
app.config['DEBUG'] = True
