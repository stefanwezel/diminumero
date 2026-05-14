// Feedback poll modal — shown on every visit until the user submits.
(function () {
    'use strict';

    const POLL_DONE_KEY = 'diminumero_poll_done';
    const modal = document.getElementById('poll-modal');
    if (!modal) return;

    if (localStorage.getItem(POLL_DONE_KEY)) {
        modal.remove();
        return;
    }

    const form = document.getElementById('poll-form');
    const errorEl = document.getElementById('poll-error');
    const submitBtn = form ? form.querySelector('button[type="submit"]') : null;

    setTimeout(() => modal.classList.add('show'), 1500);

    if (!form) return;

    form.addEventListener('submit', async function (e) {
        e.preventDefault();
        if (!form.reportValidity()) return;

        if (errorEl) errorEl.hidden = true;
        if (submitBtn) submitBtn.disabled = true;

        const fd = new FormData(form);
        const payload = {
            color_scheme_pref: fd.get('color_scheme_pref'),
            cards_aware: fd.get('cards_aware'),
            device: fd.get('device'),
            freeform: fd.get('freeform') || '',
        };

        try {
            const res = await fetch('/api/poll', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok || !data.ok) throw new Error('submit failed');

            localStorage.setItem(POLL_DONE_KEY, '1');
            modal.classList.remove('show');
            setTimeout(() => modal.remove(), 300);
        } catch (err) {
            if (errorEl) errorEl.hidden = false;
            if (submitBtn) submitBtn.disabled = false;
        }
    });
})();
