/**
 * Share-deck dialog. Posts to /api/cards/share, then shows the returned
 * URL in a modal with a "Copy" button. Falls back gracefully if the
 * Clipboard API is unavailable (user can still select-and-copy).
 */
(function () {
    'use strict';

    const btn = document.getElementById('cards-share-btn');
    if (!btn) return;

    const labels = {
        copy: btn.getAttribute('data-i18n-copy') || 'Copy link',
        copied: btn.getAttribute('data-i18n-copied') || 'Copied!',
        error: btn.getAttribute('data-i18n-error') || 'Could not create share link.',
        title: btn.getAttribute('data-i18n-modal-title') || 'Share your deck',
        desc: btn.getAttribute('data-i18n-modal-desc') || 'Anyone with this link can import a copy of your cards.',
        close: btn.getAttribute('data-i18n-close') || 'Close'
    };

    let modalEl = null;
    let urlInput = null;
    let copyBtn = null;

    function buildModal() {
        const overlay = document.createElement('div');
        overlay.className = 'cards-share-modal-overlay';
        overlay.setAttribute('role', 'dialog');
        overlay.setAttribute('aria-modal', 'true');
        overlay.setAttribute('aria-labelledby', 'cards-share-modal-title');

        const dialog = document.createElement('div');
        dialog.className = 'cards-share-modal';

        const title = document.createElement('h3');
        title.id = 'cards-share-modal-title';
        title.className = 'cards-share-modal-title';
        title.textContent = labels.title;

        const desc = document.createElement('p');
        desc.className = 'cards-share-modal-desc';
        desc.textContent = labels.desc;

        const row = document.createElement('div');
        row.className = 'cards-share-modal-row';

        urlInput = document.createElement('input');
        urlInput.type = 'text';
        urlInput.readOnly = true;
        urlInput.className = 'cards-share-modal-url';
        urlInput.addEventListener('focus', function () { urlInput.select(); });

        copyBtn = document.createElement('button');
        copyBtn.type = 'button';
        copyBtn.className = 'btn btn-primary cards-share-modal-copy';
        copyBtn.textContent = labels.copy;
        copyBtn.addEventListener('click', onCopy);

        row.appendChild(urlInput);
        row.appendChild(copyBtn);

        const close = document.createElement('button');
        close.type = 'button';
        close.className = 'btn btn-secondary cards-share-modal-close';
        close.textContent = labels.close;
        close.addEventListener('click', closeModal);

        dialog.appendChild(title);
        dialog.appendChild(desc);
        dialog.appendChild(row);
        dialog.appendChild(close);
        overlay.appendChild(dialog);

        overlay.addEventListener('click', function (e) {
            if (e.target === overlay) closeModal();
        });
        document.addEventListener('keydown', onKey);

        document.body.appendChild(overlay);
        return overlay;
    }

    function onKey(e) {
        if (e.key === 'Escape') closeModal();
    }

    function closeModal() {
        if (modalEl && modalEl.parentNode) {
            modalEl.parentNode.removeChild(modalEl);
        }
        modalEl = null;
        document.removeEventListener('keydown', onKey);
    }

    function onCopy() {
        if (!urlInput) return;
        const value = urlInput.value;
        const done = function () {
            const original = copyBtn.textContent;
            copyBtn.textContent = labels.copied;
            setTimeout(function () {
                if (copyBtn) copyBtn.textContent = original;
            }, 1600);
        };
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(value).then(done, function () {
                urlInput.select();
            });
        } else {
            urlInput.select();
            try { document.execCommand('copy'); done(); } catch (e) { /* noop */ }
        }
    }

    btn.addEventListener('click', function () {
        btn.disabled = true;
        fetch('/api/cards/share', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin'
        })
            .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
            .then(function (res) {
                if (!res.ok || !res.data || res.data.ok === false) {
                    const msg = (res.data && res.data.error) || labels.error;
                    window.alert(msg);
                    return;
                }
                modalEl = buildModal();
                urlInput.value = res.data.url;
                // Defer one frame so the modal is on screen before the input
                // gets focus, otherwise mobile keyboards can flash up briefly.
                requestAnimationFrame(function () {
                    urlInput.focus();
                    urlInput.select();
                });
            })
            .catch(function () { window.alert(labels.error); })
            .finally(function () { btn.disabled = false; });
    });
}());
