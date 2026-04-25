/**
 * Index-card practice — live word-by-word validation, auto-advance on correct.
 * Mirrors static/js/quiz_advanced.js but hits /api/cards/validate.
 */

document.addEventListener('DOMContentLoaded', function () {
    const answerInput = document.getElementById('answerInput');
    const validationFeedback = document.getElementById('validationFeedback');
    const answerForm = document.getElementById('answerForm');
    let isSubmitting = false;
    let validationTimer = null;

    if (!answerInput || !validationFeedback || !answerForm) return;

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

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
            const response = await fetch('/api/cards/validate', {
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
});
