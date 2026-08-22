/**
 * Per-number notes: the lightbulb disclosure.
 *
 * Tap and click are the primary interaction and keyboard is a first-class one —
 * the control is a real <button> with aria-expanded, so it works with a screen
 * reader and without a pointer. Hover is deliberately not wired up: phones do
 * not have it, and a note that only appears on hover is a note half the readers
 * never see.
 *
 * The panel's content is already in the DOM; this only toggles `hidden`, so
 * with JS unavailable the note is still readable by anything that ignores it.
 */
(function () {
    'use strict';

    var toggles = document.querySelectorAll('.number-notes-toggle');
    if (!toggles.length) return;

    function panelFor(button) {
        return document.getElementById(button.getAttribute('aria-controls'));
    }

    function close(button) {
        var panel = panelFor(button);
        if (panel) panel.hidden = true;
        button.setAttribute('aria-expanded', 'false');
    }

    function closeAll() {
        for (var i = 0; i < toggles.length; i++) close(toggles[i]);
    }

    for (var i = 0; i < toggles.length; i++) {
        (function (button) {
            button.addEventListener('click', function (event) {
                event.stopPropagation();
                var panel = panelFor(button);
                if (!panel) return;
                var open = button.getAttribute('aria-expanded') === 'true';
                closeAll();
                if (!open) {
                    panel.hidden = false;
                    button.setAttribute('aria-expanded', 'true');
                }
            });
        }(toggles[i]));
    }

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') closeAll();
    });

    document.addEventListener('click', function (event) {
        if (!event.target.closest || !event.target.closest('.number-notes')) closeAll();
    });
}());
