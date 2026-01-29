// Cookie Banner functionality
(function() {
    'use strict';
    
    const COOKIE_CONSENT_KEY = 'diminumero_cookie_consent';
    const banner = document.getElementById('cookie-banner');
    
    if (!banner) return;
    
    // Check if user has already accepted
    const hasConsented = localStorage.getItem(COOKIE_CONSENT_KEY);
    
    if (!hasConsented) {
        // Show banner after a brief delay for better UX
        setTimeout(() => {
            banner.classList.add('show');
        }, 1000);
    }
    
    // Handle accept button click
    const acceptBtn = document.getElementById('cookie-accept');
    if (acceptBtn) {
        acceptBtn.addEventListener('click', function() {
            localStorage.setItem(COOKIE_CONSENT_KEY, 'true');
            banner.classList.remove('show');
            
            // Remove banner from DOM after animation
            setTimeout(() => {
                banner.remove();
            }, 300);
        });
    }
})();
