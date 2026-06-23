/**
 * Verb-conjugation practice — same two flavors as the index-card practice:
 *
 *   advanced (default): live word-by-word validation via /api/conjugate/validate,
 *     auto-advance on a complete correct answer.
 *
 *   hardcore: no live feedback. On Enter, normalize the input client-side and
 *     compare to the correct answer (leaked into a data attribute only when
 *     difficulty=hardcore). The input flashes green or red before submitting.
 *
 * Mirrors cards_practice.js; the only difference is the validation endpoint.
 */

document.addEventListener('DOMContentLoaded', function () {
    const answerInput = document.getElementById('answerInput');
    const validationFeedback = document.getElementById('validationFeedback');
    const answerForm = document.getElementById('answerForm');
    if (!answerInput || !validationFeedback || !answerForm) return;

    const isHardcore = answerInput.getAttribute('data-difficulty') === 'hardcore';

    if (isHardcore) {
        setupHardcore(answerInput, answerForm);
    } else {
        setupAdvanced(answerInput, validationFeedback, answerForm);
    }
});

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function normalizeText(text) {
    text = text.toLowerCase().trim();
    text = text.replace(/ü/g, 'ue');
    text = text.replace(/ö/g, 'oe');
    text = text.replace(/ä/g, 'ae');
    text = text.replace(/ß/g, 'ss');
    text = text.replace(/\s+/g, ' ');
    text = text.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
    return text;
}

function setupAdvanced(answerInput, validationFeedback, answerForm) {
    let isSubmitting = false;
    let validationTimer = null;

    function displayValidation(validation) {
        if (!validation.words || validation.words.length === 0) {
            validationFeedback.innerHTML = '';
            validationFeedback.className = 'validation-feedback';
            return;
        }
        const wordsHtml = validation.words
            .map((w) => `<span class="word-${w.status}">${escapeHtml(w.text)}</span>`)
            .join(' ');
        validationFeedback.innerHTML = wordsHtml;
        if (validation.is_complete && validation.is_correct) {
            validationFeedback.className = 'validation-feedback feedback-complete';
        } else if (validation.words.some((w) => w.status === 'incorrect')) {
            validationFeedback.className = 'validation-feedback feedback-error';
        } else {
            validationFeedback.className = 'validation-feedback feedback-progress';
        }
    }

    async function validateInput() {
        const userInput = answerInput.value;
        if (!userInput.trim()) {
            validationFeedback.innerHTML = '';
            validationFeedback.className = 'validation-feedback';
            return;
        }
        try {
            const response = await fetch('/api/conjugate/validate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ input: userInput }),
            });
            if (!response.ok) return;
            const validation = await response.json();
            displayValidation(validation);
            if (validation.is_complete && validation.is_correct && !isSubmitting) {
                isSubmitting = true;
                setTimeout(() => answerForm.submit(), 500);
            }
        } catch (e) {
            // Network errors are non-fatal — the user can still submit manually.
        }
    }

    answerInput.addEventListener('input', function () {
        if (validationTimer) clearTimeout(validationTimer);
        validationTimer = setTimeout(validateInput, 200);
    });
    answerInput.focus();

    answerForm.addEventListener('submit', function (e) {
        if (e.submitter && e.submitter.name === 'reveal') return true;
        if (isSubmitting) {
            e.preventDefault();
            return false;
        }
    });
}

function setupHardcore(answerInput, answerForm) {
    const correctAnswer = answerInput.getAttribute('data-correct-answer') || '';
    const normalizedCorrect = normalizeText(correctAnswer);
    let isSubmitting = false;

    answerInput.focus();

    answerInput.addEventListener('input', function () {
        answerInput.classList.remove('input-correct', 'input-incorrect');
    });

    answerForm.addEventListener('submit', function (e) {
        if (e.submitter && e.submitter.name === 'reveal') return true;
        if (isSubmitting) return true;

        e.preventDefault();
        const userAnswer = (answerInput.value || '').trim();
        if (!userAnswer) return;

        const isCorrect = normalizeText(userAnswer) === normalizedCorrect;
        answerInput.classList.remove('input-correct', 'input-incorrect');
        answerInput.classList.add(isCorrect ? 'input-correct' : 'input-incorrect');
        isSubmitting = true;
        setTimeout(() => answerForm.submit(), 700);
    });
}
