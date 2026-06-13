/**
 * "Type to continue" reveal mode for index-card practice.
 *
 * After the answer is revealed, the user must retype it before the round
 * advances. We give live green/red feedback and auto-submit once the typed
 * answer matches; the Next button is otherwise blocked client-side (the server
 * enforces the same rule). Mirrors the normalization used by the backend's
 * normalize_text() so ASCII input for accented/umlaut answers is accepted.
 */

document.addEventListener('DOMContentLoaded', function () {
    const input = document.getElementById('revealInput');
    const form = document.getElementById('revealForm');
    if (!input || !form) return;

    const correct = normalizeReveal(input.getAttribute('data-correct-answer') || '');
    let submitting = false;

    input.focus();

    function isMatch() {
        return normalizeReveal(input.value || '') === correct;
    }

    function check() {
        if (submitting) return;
        if (isMatch()) {
            input.classList.remove('input-incorrect');
            input.classList.add('input-correct');
            submitting = true;
            setTimeout(function () { form.submit(); }, 400);
        }
    }

    input.addEventListener('input', function () {
        input.classList.remove('input-correct', 'input-incorrect');
        check();
    });

    form.addEventListener('submit', function (e) {
        // Block manual Next submits until the answer is typed correctly, so the
        // typing requirement can't be skipped (the server rejects it anyway).
        if (submitting) return true;
        if (!isMatch()) {
            e.preventDefault();
            input.classList.add('input-incorrect');
            input.focus();
            return false;
        }
    });
});

function normalizeReveal(text) {
    text = text.toLowerCase().trim();
    text = text.replace(/ü/g, 'ue');
    text = text.replace(/ö/g, 'oe');
    text = text.replace(/ä/g, 'ae');
    text = text.replace(/ß/g, 'ss');
    text = text.replace(/\s+/g, ' ');
    text = text.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
    return text;
}
