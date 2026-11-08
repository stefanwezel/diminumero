/**
 * "Type to continue" reveal mode for index-card practice.
 *
 * After the answer is revealed, the user must retype it before the round
 * advances. We give live green/red feedback and auto-submit once the typed
 * answer matches; the Next button is otherwise blocked client-side (the server
 * enforces the same rule). Compares with normalizeText() (normalize_text.js,
 * loaded first) so ASCII input for accented/umlaut answers is accepted.
 */

document.addEventListener('DOMContentLoaded', function () {
    const input = document.getElementById('revealInput');
    const form = document.getElementById('revealForm');
    if (!input || !form) return;

    // Verb practice lists every form the server accepts; a card has just the one.
    const listed = input.getAttribute('data-accepted-answers');
    const accepted = (
        listed ? JSON.parse(listed) : [input.getAttribute('data-correct-answer') || '']
    ).map(normalizeText);
    let submitting = false;

    input.focus();

    function isMatch() {
        return accepted.includes(normalizeText(input.value || ''));
    }

    function check() {
        if (submitting) return;
        if (isMatch()) {
            input.classList.remove('input-incorrect');
            input.classList.add('input-correct');
            submitting = true;
            setTimeout(advance, 400);
        }
    }

    // Advance via the Next button so the POST carries its name/value
    // (next=1). A bare form.submit() omits the submit button, so the server
    // would mistake the retyped answer for a fresh answer submission and
    // double-count the question. requestSubmit() includes the submitter;
    // fall back to a hidden field for older engines.
    function advance() {
        var nextBtn = form.querySelector('button[name="next"]');
        if (nextBtn && form.requestSubmit) {
            form.requestSubmit(nextBtn);
            return;
        }
        if (!form.querySelector('input[name="next"]')) {
            var hidden = document.createElement('input');
            hidden.type = 'hidden';
            hidden.name = 'next';
            hidden.value = '1';
            form.appendChild(hidden);
        }
        form.submit();
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
