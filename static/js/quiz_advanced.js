/**
 * Advanced Quiz Mode - Live validation with word-by-word feedback
 */

document.addEventListener('DOMContentLoaded', function() {
    const answerInput = document.getElementById('answerInput');
    const validationFeedback = document.getElementById('validationFeedback');
    const answerForm = document.getElementById('answerForm');
    let isSubmitting = false;

    if (!answerInput || !validationFeedback) {
        console.error('Required elements not found');
        return;
    }

    // Debounce timer for validation
    let validationTimer = null;

    /**
     * Perform live validation via API
     */
    async function validateInput() {
        const userInput = answerInput.value;

        // Don't validate empty input
        if (!userInput.trim()) {
            validationFeedback.innerHTML = '';
            validationFeedback.className = 'validation-feedback';
            return;
        }

        try {
            const response = await fetch('/api/validate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ input: userInput })
            });

            if (!response.ok) {
                console.error('Validation request failed');
                return;
            }

            const validation = await response.json();
            displayValidation(validation);

            // Auto-submit if answer is complete and correct
            if (validation.is_complete && validation.is_correct && !isSubmitting) {
                isSubmitting = true;
                setTimeout(() => {
                    answerForm.submit();
                }, 500); // Small delay to show success feedback
            }

        } catch (error) {
            console.error('Validation error:', error);
        }
    }

    /**
     * Display word-by-word validation feedback
     */
    function displayValidation(validation) {
        if (!validation.words || validation.words.length === 0) {
            validationFeedback.innerHTML = '';
            validationFeedback.className = 'validation-feedback';
            return;
        }

        // Build HTML for word-by-word feedback
        const wordsHtml = validation.words.map(word => {
            const statusClass = `word-${word.status}`;
            return `<span class="${statusClass}">${escapeHtml(word.text)}</span>`;
        }).join(' ');

        validationFeedback.innerHTML = wordsHtml;
        
        // Add overall status class
        if (validation.is_complete && validation.is_correct) {
            validationFeedback.className = 'validation-feedback feedback-complete';
        } else if (validation.words.some(w => w.status === 'incorrect')) {
            validationFeedback.className = 'validation-feedback feedback-error';
        } else {
            validationFeedback.className = 'validation-feedback feedback-progress';
        }
    }

    /**
     * Escape HTML to prevent XSS
     */
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Handle input events with debouncing
     */
    answerInput.addEventListener('input', function() {
        // Clear existing timer
        if (validationTimer) {
            clearTimeout(validationTimer);
        }

        // Set new timer for validation (200ms debounce)
        validationTimer = setTimeout(() => {
            validateInput();
        }, 200);
    });

    /**
     * Focus input on load
     */
    answerInput.focus();

    /**
     * Prevent form submission if already submitting
     */
    answerForm.addEventListener('submit', function(e) {
        // Allow Give Up button to work
        if (e.submitter && e.submitter.name === 'give_up') {
            return true;
        }

        // Prevent double submission
        if (isSubmitting) {
            e.preventDefault();
            return false;
        }
    });
});
