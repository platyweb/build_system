// Copyright (c) 2026 DMAdash Engineering Ltd. All Rights Reserved.
// This file is proprietary and confidential.
// Unauthorised use is strictly prohibited. See LICENSE.txt for details.


(function() {
    'use strict';

    // Initialize accordion functionality
    function initTenantAccordion() {
        // Get all floor cards
        const floorCards = document.querySelectorAll('.floor-card');

        floorCards.forEach(card => {
            // Prevent default link behavior
            card.addEventListener('click', function(e) {
                // Check if the click target is inside a floor-stats-group-link
                const isClickInsideLink = e.target.closest('.floor-stats-group-link');

                // If clicked inside a meter group link, allow navigation
                if (isClickInsideLink) {
                    return; // Let the link work normally
                }

                // Otherwise, prevent default and toggle accordion
                e.preventDefault();
                toggleAccordion(this);
            });

            // Add closed class by default (accordion starts closed)
            card.classList.add('accordion-closed');

            // Add expand/collapse icon to floor header if not exists
            const floorHeader = card.querySelector('.floor-header');
            if (floorHeader && !floorHeader.querySelector('.accordion-icon')) {
                const icon = document.createElement('i');
                icon.className = 'bx bx-chevron-down accordion-icon';
                floorHeader.appendChild(icon);
            }
        });
    }

    // Toggle accordion state
    function toggleAccordion(card) {
        const isClosed = card.classList.contains('accordion-closed');

        if (isClosed) {
            // Open the accordion
            card.classList.remove('accordion-closed');
            card.classList.add('accordion-open');
        } else {
            // Close the accordion
            card.classList.remove('accordion-open');
            card.classList.add('accordion-closed');
        }
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initTenantAccordion);
    } else {
        initTenantAccordion();
    }

})();
