/**
 * "Add this verb to conjugation practice" button on the cards practice page.
 * Shown only when the current card is a Spanish verb the user hasn't added yet.
 * POSTs the infinitive to /api/verbs; on success the button becomes a static
 * "added" confirmation. Progressive enhancement — no fallback needed since this
 * is a pure extra action.
 */

(function () {
    'use strict';

    const btn = document.getElementById('cards-practice-verb-add');
    if (!btn) return;

    const toastIcon = btn.getAttribute('data-toast-icon') || '';
    const toastMsg = btn.getAttribute('data-toast-msg') || '';
    const addedLabel = btn.getAttribute('data-i18n-added') || '✓ Added';

    function showToast(message) {
        if (!message) return;
        const toast = document.createElement('div');
        toast.className = 'toast toast-success';
        if (toastIcon) {
            const icon = document.createElement('img');
            icon.src = toastIcon;
            icon.alt = '';
            icon.className = 'toast-icon';
            toast.appendChild(icon);
        }
        const span = document.createElement('span');
        span.textContent = message;
        toast.appendChild(span);
        document.body.appendChild(toast);
        setTimeout(function () { toast.remove(); }, 3100);
    }

    btn.addEventListener('click', async function () {
        const infinitive = (btn.getAttribute('data-infinitive') || '').trim();
        const verbLang = btn.getAttribute('data-verb-lang') || 'es';
        if (!infinitive) return;
        btn.disabled = true;
        try {
            const res = await fetch('/api/verbs', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ infinitive: infinitive, lang: verbLang })
            });
            const data = await res.json();
            if (!res.ok || !data.ok) {
                btn.disabled = false;
                return;
            }
            btn.textContent = addedLabel;
            btn.classList.add('cards-practice-verb-add-done');
            showToast(toastMsg);
        } catch (err) {
            btn.disabled = false;
        }
    });
}());
