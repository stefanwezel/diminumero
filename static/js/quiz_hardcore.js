/**
 * Hardcore Quiz Mode - No intermediate feedback, only complete answer validation
 */

document.addEventListener('DOMContentLoaded', function() {
    const answerInput = document.getElementById('answerInput');
    const answerForm = document.getElementById('answerForm');
    const correctAnswer = answerInput.getAttribute('data-correct-answer');
    let isSubmitting = false;

    if (!answerInput || !correctAnswer) {
        console.error('Required elements not found');
        return;
    }

    /**
     * Normalize text for comparison (same logic as Python backend)
     * - Convert to lowercase
     * - Replace German umlauts (ü→ue, ö→oe, ä→ae, ß→ss)
     * - Remove extra spaces
     * - Remove accents
     */
    function normalizeText(text) {
        // Convert to lowercase and trim
        text = text.toLowerCase().trim();
        
        // Replace German umlauts and ß with ASCII equivalents
        // This allows users to type "fuenf" for "fünf", "zwoelf" for "zwölf", etc.
        // Using global regex replace for better browser compatibility
        text = text.replace(/ü/g, 'ue');
        text = text.replace(/ö/g, 'oe');
        text = text.replace(/ä/g, 'ae');
        text = text.replace(/ß/g, 'ss');
        
        // Remove extra spaces between words
        text = text.replace(/\s+/g, ' ');
        
        // Normalize accents (NFD normalization)
        text = text.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
        
        return text;
    }

    /**
     * Check if the answer is complete and correct
     */
    function checkAnswer() {
        const userInput = answerInput.value;
        
        // Don't validate empty input
        if (!userInput.trim()) {
            answerInput.classList.remove('input-correct');
            return;
        }

        const normalizedInput = normalizeText(userInput);
        const normalizedCorrect = normalizeText(correctAnswer);

        // Check if complete answer is correct
        if (normalizedInput === normalizedCorrect) {
            // Turn input green
            answerInput.classList.add('input-correct');
            
            // Auto-submit after delay
            if (!isSubmitting) {
                isSubmitting = true;
                setTimeout(() => {
                    answerForm.submit();
                }, 500); // Small delay to show success feedback
            }
        } else {
            // Remove green styling if answer no longer matches
            answerInput.classList.remove('input-correct');
        }
    }

    /**
     * Handle input events
     */
    answerInput.addEventListener('input', function() {
        checkAnswer();
    });

    /**
     * Focus input on load
     */
    answerInput.focus();

    /**
     * Prevent form submission if already submitting
     */
    answerForm.addEventListener('submit', function(e) {
        if (isSubmitting) {
            return true; // Allow submission
        }
        // Only allow manual submission via Enter key
        if (e.submitter === null || e.submitter.name === 'answer') {
            e.preventDefault();
            checkAnswer();
            if (answerInput.classList.contains('input-correct') && !isSubmitting) {
                isSubmitting = true;
                answerForm.submit();
            }
        }
    });
});
