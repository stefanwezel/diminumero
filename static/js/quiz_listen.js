// Listening quiz: keep the page as a single living document and advance
// questions via fetch instead of full-page navigation. Because every
// transition is triggered by a user gesture (Start / a digit / Next), the
// document keeps its "user activation", so audio.play() is always allowed —
// this is what makes the mp3 autoplay reliably, like a YouTube video.
(function () {
    'use strict';

    var container = document.querySelector('.container');
    if (!container) return;

    var MAX_DIGITS = 9;

    // ---- audio ----
    function playAudio() {
        var audio = document.getElementById('audio-el');
        if (!audio) return;
        var doPlay = function () {
            // tiny lag so the audio doesn't start the very instant the
            // question appears
            setTimeout(function () {
                try { audio.currentTime = 0; } catch (e) {}
                var p = audio.play();
                if (p && typeof p.catch === 'function') p.catch(function () {});
            }, 100);
        };
        if (audio.readyState >= 2) {
            doPlay();
        } else {
            audio.addEventListener('canplay', doPlay, { once: true });
        }
    }

    // ---- numpad input (looked up live so it survives content swaps) ----
    function input() { return document.getElementById('answerInput'); }
    function renderDisplay() {
        var el = input();
        var display = document.getElementById('numpadDisplay');
        if (el && display) display.textContent = el.value.length ? el.value : ' ';
    }
    function setValue(v) {
        var el = input();
        if (el) { el.value = v; renderDisplay(); }
    }
    function appendDigit(d) {
        var el = input();
        if (!el || el.value.length >= MAX_DIGITS) return;
        setValue(el.value + d);
    }

    // ---- toasts (mirror static/js/quiz.js auto-hide for swapped-in toasts) ----
    function refreshToasts(doc) {
        document.querySelectorAll('body > .toast').forEach(function (t) { t.remove(); });
        if (doc) {
            doc.querySelectorAll('.toast').forEach(function (t) { document.body.appendChild(t); });
        }
        document.querySelectorAll('.toast').forEach(function (toast) {
            setTimeout(function () { toast.remove(); }, 3000);
        });
    }

    // ---- pjax ----
    function swapFrom(html, url) {
        var doc = new DOMParser().parseFromString(html, 'text/html');
        // Anything that isn't a listening-quiz page (e.g. the results page) is a
        // real navigation — let the browser go there normally.
        if (!doc.querySelector('.quiz-page')) {
            window.location.href = url;
            return;
        }
        var newContainer = doc.querySelector('.container');
        container.innerHTML = newContainer ? newContainer.innerHTML : '';
        if (url) {
            try {
                var samePath = new URL(url, window.location.href).pathname === window.location.pathname;
                history[samePath ? 'replaceState' : 'pushState']({ listen: true }, '', url);
            } catch (e) {}
        }
        refreshToasts(doc);
        renderDisplay();
        var next = document.querySelector('.reveal-modal-next');
        if (next) next.focus();
        playAudio();
    }

    function pjaxSubmit(form) {
        var method = (form.method || 'GET').toUpperCase();
        var opts = { method: method, headers: { 'X-Requested-With': 'fetch' } };
        if (method === 'POST') opts.body = new FormData(form);
        fetch(form.action, opts)
            .then(function (resp) {
                return resp.text().then(function (text) { return { url: resp.url, text: text }; });
            })
            .then(function (r) { swapFrom(r.text, r.url); })
            .catch(function () { form.submit(); });
    }

    // ---- delegated listeners (bound once; survive content swaps) ----
    container.addEventListener('click', function (e) {
        var digit = e.target.closest('[data-digit]');
        if (digit) { appendDigit(digit.getAttribute('data-digit')); return; }
        if (e.target.closest('#numpadBack')) {
            var el = input();
            if (el) setValue(el.value.slice(0, -1));
            return;
        }
        if (e.target.closest('#audio-play-btn') || e.target.closest('#audio-replay-btn')) {
            playAudio();
        }
    });

    container.addEventListener('submit', function (e) {
        var form = e.target;
        if (!form.matches || !form.matches('[data-listen-pjax]')) return;
        if (form.id === 'answerForm') {
            var el = input();
            if (!el || !el.value) { e.preventDefault(); return; }
        }
        e.preventDefault();
        pjaxSubmit(form);
    });

    document.addEventListener('keydown', function (e) {
        var form = document.getElementById('answerForm');
        if (!form) return;
        if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) return;
        if (e.key >= '0' && e.key <= '9') {
            appendDigit(e.key);
            e.preventDefault();
        } else if (e.key === 'Backspace') {
            var el = input();
            if (el) setValue(el.value.slice(0, -1));
            e.preventDefault();
        } else if (e.key === 'Enter') {
            var el2 = input();
            if (el2 && el2.value) {
                if (form.requestSubmit) form.requestSubmit();
                else pjaxSubmit(form);
            }
            e.preventDefault();
        }
    });

    // A back/forward navigation can't be reconstructed from session state
    // client-side, so fall back to a real load.
    window.addEventListener('popstate', function () { window.location.reload(); });

    // initial page
    renderDisplay();
    playAudio();
})();
