// Spanish Numbers Quiz - JavaScript

// Auto-hide toast notifications after animation
document.addEventListener('DOMContentLoaded', function() {
    const toasts = document.querySelectorAll('.toast');
    
    toasts.forEach(toast => {
        // Remove toast after animation completes (3 seconds total)
        setTimeout(() => {
            toast.remove();
        }, 3000);
    });
});

// Optional: Add keyboard shortcuts for quiz options
document.addEventListener('DOMContentLoaded', function() {
    const optionButtons = document.querySelectorAll('.option-btn');
    
    if (optionButtons.length > 0) {
        document.addEventListener('keydown', function(e) {
            // Map keys 1-4 to options
            const keyMap = {
                '1': 0,
                '2': 1,
                '3': 2,
                '4': 3
            };
            
            if (keyMap.hasOwnProperty(e.key) && optionButtons[keyMap[e.key]]) {
                optionButtons[keyMap[e.key]].click();
            }
        });
    }
});

// Add visual feedback on option selection
document.addEventListener('DOMContentLoaded', function() {
    const optionButtons = document.querySelectorAll('.option-btn');
    
    optionButtons.forEach(button => {
        button.addEventListener('click', function() {
            this.style.transform = 'scale(0.95)';
        });
    });
});
