// Language picker for the home page's "Open Conjugation" CTA.
(function () {
    'use strict';

    const btn = document.getElementById('conjugateLangBtn');
    const modal = document.getElementById('conjugate-lang-modal');
    if (!btn || !modal) return;

    const closeBtn = document.getElementById('conjugate-lang-close-btn');

    function openModal() {
        modal.classList.add('show');
        const first = modal.querySelector('.conj-lang-option');
        if (first) first.focus();
    }

    function closeModal() {
        modal.classList.remove('show');
        btn.focus();
    }

    btn.addEventListener('click', openModal);
    if (closeBtn) closeBtn.addEventListener('click', closeModal);
    modal.addEventListener('click', (event) => {
        if (event.target === modal) closeModal();
    });
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && modal.classList.contains('show')) closeModal();
    });
})();
